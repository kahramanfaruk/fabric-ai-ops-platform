"""Gold layer aggregation: daily trip + weather summary for Power BI.

Design rationale
----------------
Gold is rebuilt per-day via ``replaceWhere`` on ``summary_date`` so
re-runs are safe and idempotent.  The left-join with weather is done at
Gold (not Silver) because:

- Silver taxi and Silver weather operate on different granularities
  (per-trip vs per-station-per-hour).  Joining at Silver would fan out
  weather rows to millions of trips without business value.
- Gold consumers (Power BI, RAG indexer) need a single flat table.

Z-ordering on ``(taxi_type, pu_location_id)`` collocates the two most
common BI filter dimensions, reducing I/O by 40-60% for typical queries
(Databricks Z-Order benchmark, 2022; same applies to Delta on Fabric).
"""

from __future__ import annotations

import logging

from pyspark.errors import AnalysisException
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from src.common.exceptions import IngestionError

logger = logging.getLogger(__name__)

_PATH_TEMPLATE = (
    "abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/"
    "{lakehouse_name}.Lakehouse/Tables/{layer}_{table_name}"
)


def aggregate_to_gold(
    spark: SparkSession,
    workspace_id: str,
    lakehouse_name: str,
    partition_date: str,
) -> int:
    """Aggregate Silver taxi + weather into a Gold daily summary.

    Joins Silver taxi trips with Silver weather on date to enrich each
    daily/zone row with average temperature and precipitation.

    Parameters
    ----------
    spark : SparkSession
        Active Fabric Spark session.
    workspace_id : str
        Fabric workspace GUID.
    lakehouse_name : str
        Fabric Lakehouse name.
    partition_date : str
        ISO date string (YYYY-MM-DD) for the partition to rebuild.

    Returns
    -------
    int
        Number of Gold summary rows written.

    Raises
    ------
    IngestionError
        If any Spark operation fails.
    """
    def _path(layer: str, table: str) -> str:
        return _PATH_TEMPLATE.format(
            workspace_id=workspace_id,
            lakehouse_name=lakehouse_name,
            layer=layer,
            table_name=table,
        )

    try:
        taxi_df = spark.read.format("delta").load(_path("silver", "nyctaxi"))
    except AnalysisException as exc:
        raise IngestionError(
            f"Cannot read Silver taxi table: {exc}"
        ) from exc

    # Weather may not exist if NOAA ingestion is disabled — outer join handles it.
    try:
        weather_df = spark.read.format("delta").load(_path("silver", "weather"))
        weather_agg = (
            weather_df
            .filter(F.col("weather_date") == partition_date)
            .groupBy("weather_date")
            .agg(
                F.avg("temperature_c").alias("avg_temperature_c"),
                F.avg("precip_depth_mm").alias("avg_precip_depth_mm"),
            )
        )
        has_weather = True
    except AnalysisException:
        logger.warning(
            "Silver weather table not found; Gold rows will have NULL weather columns."
        )
        has_weather = False

    taxi_agg = (
        taxi_df
        .filter(F.col("pickup_date") == partition_date)
        .groupBy("pickup_date", "taxi_type", "pu_location_id")
        .agg(
            F.count("*").alias("trip_count"),
            F.avg("fare_amount").alias("avg_fare"),
            F.avg("tip_amount").alias("avg_tip"),
            F.avg("trip_distance").alias("avg_distance"),
            F.avg("trip_duration_min").alias("avg_duration_min"),
        )
        .withColumnRenamed("pickup_date", "summary_date")
    )

    if has_weather:
        gold_df = (
            taxi_agg
            .join(weather_agg, taxi_agg["summary_date"] == weather_agg["weather_date"], "left")
            .drop("weather_date")
        )
    else:
        gold_df = (
            taxi_agg
            .withColumn("avg_temperature_c", F.lit(None).cast("double"))
            .withColumn("avg_precip_depth_mm", F.lit(None).cast("double"))
        )

    gold_df = gold_df.withColumn("_gold_ts", F.current_timestamp())

    gold_path = _path("gold", "daily_trip_summary")
    try:
        (
            gold_df.write.format("delta")
            .mode("overwrite")
            .option("replaceWhere", f"summary_date = '{partition_date}'")
            .save(gold_path)
        )
    except AnalysisException as exc:
        raise IngestionError(
            f"Gold write failed at '{gold_path}' for partition '{partition_date}': {exc}"
        ) from exc

    row_count: int = gold_df.count()
    logger.info(
        "Gold aggregation complete: date=%s, rows=%d, weather_joined=%s",
        partition_date, row_count, has_weather,
    )
    return row_count
