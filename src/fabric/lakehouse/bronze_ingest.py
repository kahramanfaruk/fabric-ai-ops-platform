"""Bronze layer ingestion: land raw NYC Taxi / NOAA data into OneLake.

Design rationale
----------------
Bronze is append-only and enforces the declared schema at column level.
No business logic runs here: every row that arrives is persisted verbatim
so re-processing Silver/Gold can always restart from the immutable raw state.
Delta format provides ACID transactions and time-travel auditing.

Data source strategy
--------------------
1. If the OneLake shortcut exists (preferred), read from the ABFSS path —
   data stays within Microsoft-managed storage, no egress cost, full
   Fabric governance and lineage.
2. If the shortcut is not yet provisioned, fall back to the direct
   Azure Open Datasets wasbs:// endpoint (also hosted by Microsoft,
   always free, but outside OneLake governance).

The shortcut is created once in the Fabric Portal:
  Lakehouse → New shortcut → Azure Data Lake Storage Gen2
  → Account: azureopendatastore.blob.core.windows.net
  → Container: nyctlc  (or isd for NOAA)
  → Subpath: /yellow  (or /green, or /)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pyspark.errors import AnalysisException
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.common.exceptions import IngestionError
from src.fabric.lakehouse.data_sources import DataSourceConfig

logger = logging.getLogger(__name__)

_BRONZE_PATH_TEMPLATE = (
    "abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/"
    "{lakehouse_name}.Lakehouse/Tables/bronze_{table_name}"
)


def _resolve_source_path(
    config: DataSourceConfig,
    workspace_id: str,
    lakehouse_name: str,
    spark: SparkSession,
) -> str:
    """Return the OneLake shortcut path if accessible, else the wasbs fallback.

    Attempts a lightweight ``limit(0)`` probe on the shortcut path.  If that
    raises ``AnalysisException`` (shortcut not yet created), falls back to the
    direct Azure Open Datasets endpoint.

    Parameters
    ----------
    config : DataSourceConfig
        Source configuration object from the registry.
    workspace_id : str
        Fabric workspace GUID.
    lakehouse_name : str
        Fabric Lakehouse name.
    spark : SparkSession
        Active Spark session.

    Returns
    -------
    str
        Resolved readable path.
    """
    shortcut_path = config.resolved_shortcut_path(workspace_id, lakehouse_name)
    try:
        spark.read.format(config.format).load(shortcut_path).limit(0).count()
        logger.info("Using OneLake shortcut path: %s", shortcut_path)
        return shortcut_path
    except AnalysisException:
        logger.warning(
            "OneLake shortcut not accessible at '%s'. "
            "Falling back to Azure Open Datasets wasbs endpoint: %s. "
            "Create the shortcut in the Fabric Portal to bring data under OneLake governance.",
            shortcut_path,
            config.fallback_wasbs_path,
        )
        return config.fallback_wasbs_path


def ingest_to_bronze(
    spark: SparkSession,
    config: DataSourceConfig,
    workspace_id: str,
    lakehouse_name: str,
    year: int,
    month: int | None = None,
) -> int:
    """Read NYC Taxi or NOAA data and append to the Bronze Delta table.

    Filters to a single *year* (and optionally *month*) at read time to
    avoid pulling the full multi-year dataset in one shot.  Azure Open
    Datasets Parquet files are partitioned by ``puYear`` / ``puMonth``
    (taxi) or ``year`` / ``month`` (NOAA), so Spark pushes the predicate
    down to the storage layer — only the matching files are transferred.

    Parameters
    ----------
    spark : SparkSession
        Active Fabric Spark session.
    config : DataSourceConfig
        Source configuration from ``data_sources.SOURCE_REGISTRY``.
    workspace_id : str
        Fabric workspace GUID.
    lakehouse_name : str
        Fabric Lakehouse name.
    year : int
        Calendar year to ingest (e.g. ``2023``).
    month : int | None
        Calendar month 1-12.  If None, all months for *year* are ingested.

    Returns
    -------
    int
        Number of rows written to the Bronze Delta table.

    Raises
    ------
    IngestionError
        If reading the source or writing the Delta table fails.
    """
    ingested_ts = datetime.now(tz=UTC)
    source_path = _resolve_source_path(config, workspace_id, lakehouse_name, spark)
    target_path = _BRONZE_PATH_TEMPLATE.format(
        workspace_id=workspace_id,
        lakehouse_name=lakehouse_name,
        table_name=config.name,
    )

    # ── Read with partition-predicate pushdown ────────────────────────────────
    try:
        raw_df: DataFrame = (
            spark.read.format(config.format)
            .option("recursiveFileLookup", "true")
            .load(source_path)
            .filter(F.col(config.year_partition_col) == year)
        )
        if month is not None:
            # Azure Open Datasets uses puMonth / lpepMonth / month.
            month_col = config.year_partition_col.replace("Year", "Month").replace("year", "month")
            raw_df = raw_df.filter(F.col(month_col) == month)
    except AnalysisException as exc:
        raise IngestionError(
            f"Cannot read source '{source_path}' as format '{config.format}' "
            f"for year={year}, month={month}: {exc}"
        ) from exc

    # ── Enrich with audit columns ─────────────────────────────────────────────
    enriched_df = (
        raw_df
        .withColumn("_ingested_ts", F.lit(ingested_ts).cast("timestamp"))
        .withColumn("_source_file", F.input_file_name())
        .withColumn("_source_name", F.lit(config.name))
    )

    # ── Write to Delta (append-only; schema evolution disabled in Bronze) ─────
    try:
        (
            enriched_df.write
            .format("delta")
            .mode("append")
            .option("mergeSchema", "false")
            .save(target_path)
        )
    except AnalysisException as exc:
        raise IngestionError(
            f"Delta write failed for table 'bronze_{config.name}' "
            f"at '{target_path}': {exc}"
        ) from exc

    row_count: int = enriched_df.count()
    logger.info(
        "Bronze ingest complete: source=%s, year=%d, month=%s, rows=%d",
        config.name,
        year,
        str(month) if month else "all",
        row_count,
    )
    return row_count
