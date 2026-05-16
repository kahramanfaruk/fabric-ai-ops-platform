"""Fabric pipeline orchestrator: NYC Taxi + NOAA Bronze → Silver → Gold → AI Search.

Entry point called from a Fabric notebook activity.  Each step is
isolated so partial failures are resumable without re-processing earlier
stages.

Typical invocation from a Fabric notebook::

    from src.fabric.pipelines.orchestrator import run_full_pipeline
    from src.common.config import get_settings

    settings = get_settings()
    result = run_full_pipeline(
        spark=spark,          # Fabric-provided SparkSession
        settings=settings,
        year=2023,
        month=3,
        partition_date="2023-03-15",
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
from pyspark.sql import SparkSession

from src.aiops.drift_detector import detect_drift
from src.aiops.monitor import record_drift_score
from src.common.config import Settings
from src.fabric.lakehouse.bronze_ingest import ingest_to_bronze
from src.fabric.lakehouse.data_sources import NOAA_WEATHER, NYC_TAXI_GREEN, NYC_TAXI_YELLOW
from src.fabric.lakehouse.gold_aggregate import aggregate_to_gold
from src.fabric.lakehouse.silver_transform import (
    transform_nyctaxi_to_silver,
    transform_weather_to_silver,
)

logger = logging.getLogger(__name__)

# Reference year used as the drift baseline (2022 taxi data).
_DRIFT_REFERENCE_YEAR = 2022


@dataclass
class PipelineResult:
    """Summary of a completed pipeline run.

    Parameters
    ----------
    bronze_yellow_rows : int
        Rows ingested into Bronze for yellow taxi.
    bronze_green_rows : int
        Rows ingested into Bronze for green taxi.
    bronze_weather_rows : int
        Rows ingested into Bronze for NOAA weather.
    silver_rows : int
        Rows upserted into Silver taxi.
    gold_rows : int
        Rows written to Gold summary.
    partition_date : str
        ISO date of the rebuilt Gold partition.
    """

    bronze_yellow_rows: int
    bronze_green_rows: int
    bronze_weather_rows: int
    silver_rows: int
    gold_rows: int
    partition_date: str


def _collect_numeric_col(
    spark: SparkSession,
    path: str,
    col_name: str,
    year_filter: int,
) -> np.ndarray:
    """Collect a single numeric column from a Silver Delta table into a numpy array.

    Used to feed the drift detector with real data from the Lakehouse.

    Parameters
    ----------
    spark : SparkSession
        Active Spark session.
    path : str
        ABFSS path of the Silver Delta table.
    col_name : str
        Column name to collect.
    year_filter : int
        Filter rows where ``pickup_year == year_filter``.

    Returns
    -------
    np.ndarray
        1-D float64 array of non-null values.
    """
    from pyspark.sql import functions as F
    df = (
        spark.read.format("delta").load(path)
        .filter(F.year(F.col("pickup_ts")) == year_filter)
        .select(col_name)
        .dropna()
    )
    return np.array(df.rdd.map(lambda r: float(r[0])).collect(), dtype=np.float64)


def run_full_pipeline(
    spark: SparkSession,
    settings: Settings,
    year: int,
    month: int | None = None,
    partition_date: str | None = None,
    run_drift_check: bool = True,
) -> PipelineResult:
    """Execute Bronze → Silver → Gold for NYC Taxi + NOAA for one time partition.

    Parameters
    ----------
    spark : SparkSession
        Active Fabric Spark session (injected by notebook runtime).
    settings : Settings
        Validated platform settings.
    year : int
        Year to ingest (e.g. 2023).  Azure Open Datasets holds 2009-present.
    month : int | None
        Month 1-12, or None to ingest all months for *year*.
    partition_date : str | None
        ISO date for the Gold ``replaceWhere`` partition.  Defaults to today.
    run_drift_check : bool
        If True, runs drift detection comparing *year* vs ``_DRIFT_REFERENCE_YEAR``
        after Silver is written and emits metrics to Azure Monitor.

    Returns
    -------
    PipelineResult
        Row counts per layer and the rebuilt partition date.

    Raises
    ------
    IngestionError
        Propagated from any layer on unrecoverable failure.
    """
    if partition_date is None:
        partition_date = date.today().isoformat()

    ws = settings.fabric_workspace_id
    lh = settings.lakehouse_name

    logger.info("Pipeline start: year=%d, month=%s, partition=%s", year, month, partition_date)

    # ── Bronze ────────────────────────────────────────────────────────────────
    yellow_rows = ingest_to_bronze(
        spark=spark, config=NYC_TAXI_YELLOW, workspace_id=ws,
        lakehouse_name=lh, year=year, month=month,
    )
    green_rows = ingest_to_bronze(
        spark=spark, config=NYC_TAXI_GREEN, workspace_id=ws,
        lakehouse_name=lh, year=year, month=month,
    )
    weather_rows = ingest_to_bronze(
        spark=spark, config=NOAA_WEATHER, workspace_id=ws,
        lakehouse_name=lh, year=year, month=month,
    )
    logger.info(
        "Bronze complete: yellow=%d, green=%d, weather=%d",
        yellow_rows, green_rows, weather_rows,
    )

    # ── Silver ────────────────────────────────────────────────────────────────
    silver_yellow = transform_nyctaxi_to_silver(
        spark=spark, taxi_type="yellow", workspace_id=ws,
        lakehouse_name=lh, year=year, month=month,
    )
    silver_green = transform_nyctaxi_to_silver(
        spark=spark, taxi_type="green", workspace_id=ws,
        lakehouse_name=lh, year=year, month=month,
    )
    transform_weather_to_silver(
        spark=spark, workspace_id=ws, lakehouse_name=lh, year=year, month=month,
    )
    silver_rows = silver_yellow + silver_green
    logger.info("Silver complete: total_rows=%d", silver_rows)

    # ── Drift detection ───────────────────────────────────────────────────────
    if run_drift_check:
        silver_path = (
            f"abfss://{ws}@onelake.dfs.fabric.microsoft.com/"
            f"{lh}.Lakehouse/Tables/silver_nyctaxi"
        )
        for feature in ("fare_amount", "trip_distance", "tip_amount"):
            try:
                ref = _collect_numeric_col(spark, silver_path, feature, _DRIFT_REFERENCE_YEAR)
                cur = _collect_numeric_col(spark, silver_path, feature, year)
                if len(ref) > 0 and len(cur) > 0:
                    report = detect_drift(
                        feature=feature,
                        reference=ref,
                        current=cur,
                        psi_threshold=settings.drift_psi_threshold,
                        ks_threshold=settings.drift_ks_threshold,
                    )
                    record_drift_score(
                        feature=feature,
                        psi=report.psi,
                        ks_statistic=report.ks_statistic,
                        wasserstein=report.wasserstein,
                    )
                else:
                    logger.warning(
                        "Skipping drift check for '%s': reference or current array is empty "
                        "(reference_year=%d may not be in Silver yet).",
                        feature,
                        _DRIFT_REFERENCE_YEAR,
                    )
            except Exception as exc:  # noqa: BLE001
                # Drift failure must not block pipeline completion.
                logger.error("Drift check failed for feature '%s' (non-fatal): %s", feature, exc)

    # ── Gold ──────────────────────────────────────────────────────────────────
    gold_rows = aggregate_to_gold(
        spark=spark,
        workspace_id=ws,
        lakehouse_name=lh,
        partition_date=partition_date,
    )
    logger.info("Gold complete: rows=%d", gold_rows)

    result = PipelineResult(
        bronze_yellow_rows=yellow_rows,
        bronze_green_rows=green_rows,
        bronze_weather_rows=weather_rows,
        silver_rows=silver_rows,
        gold_rows=gold_rows,
        partition_date=partition_date,
    )
    logger.info("Pipeline complete: %s", result)
    return result
