"""Silver layer transformation: cleanse and upsert NYC Taxi / NOAA Bronze data.

Design rationale
----------------
Idempotent MERGE on ``trip_id`` (SHA-2 surrogate key derived from
``vendorID + tpepPickupDatetime + puLocationId``) ensures exactly-once
semantics even when the pipeline re-runs after a partial failure.

``trip_duration_min`` is derived here (Silver), not in Bronze, because:
- Bronze must preserve the raw source verbatim.
- Duration requires two columns (pickup + dropoff); cross-column derivations
  belong in the cleansing layer, not the raw layer.

Negative fare_amount / trip_distance rows are filtered out: TLC data
documentation explicitly states these are recording errors, not valid
business events (NYC TLC Data Dictionary, 2023).
"""

from __future__ import annotations

import logging

from delta.tables import DeltaTable
from pyspark.errors import AnalysisException
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.common.exceptions import IngestionError
from src.fabric.lakehouse.schema_registry import SILVER_NYCTAXI, SILVER_WEATHER

logger = logging.getLogger(__name__)

_PATH_TEMPLATE = (
    "abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/"
    "{lakehouse_name}.Lakehouse/Tables/{layer}_{table_name}"
)


def _build_path(workspace_id: str, lakehouse_name: str, layer: str, table_name: str) -> str:
    return _PATH_TEMPLATE.format(
        workspace_id=workspace_id,
        lakehouse_name=lakehouse_name,
        layer=layer,
        table_name=table_name,
    )


def _upsert(
    spark: SparkSession,
    silver_df: DataFrame,
    silver_path: str,
    merge_key: str,
) -> None:
    """MERGE silver_df into the Silver Delta table.

    If the table does not yet exist, writes it directly (first run).

    Parameters
    ----------
    spark : SparkSession
        Active Spark session.
    silver_df : DataFrame
        Transformed rows ready for Silver.
    silver_path : str
        ABFSS path of the Silver Delta table.
    merge_key : str
        Column name used as the unique row identifier.

    Raises
    ------
    IngestionError
        If the write operation fails.
    """
    try:
        if DeltaTable.isDeltaTable(spark, silver_path):
            (
                DeltaTable.forPath(spark, silver_path)
                .alias("target")
                .merge(silver_df.alias("source"), f"target.{merge_key} = source.{merge_key}")
                .whenMatchedUpdateAll()
                .whenNotMatchedInsertAll()
                .execute()
            )
        else:
            silver_df.write.format("delta").mode("overwrite").save(silver_path)
    except AnalysisException as exc:
        raise IngestionError(
            f"Silver upsert failed at '{silver_path}': {exc}"
        ) from exc


def transform_nyctaxi_to_silver(
    spark: SparkSession,
    taxi_type: str,
    workspace_id: str,
    lakehouse_name: str,
    year: int,
    month: int | None = None,
) -> int:
    """Cleanse Bronze NYC Taxi data and upsert into Silver.

    Parameters
    ----------
    spark : SparkSession
        Active Fabric Spark session.
    taxi_type : str
        ``"yellow"`` or ``"green"`` — selects the correct Bronze source
        and pickup timestamp column.
    workspace_id : str
        Fabric workspace GUID.
    lakehouse_name : str
        Fabric Lakehouse name.
    year : int
        Year partition to process.
    month : int | None
        Month partition to process, or None for the full year.

    Returns
    -------
    int
        Approximate number of rows upserted.

    Raises
    ------
    ValueError
        If *taxi_type* is not ``"yellow"`` or ``"green"``.
    IngestionError
        If any Spark operation fails.
    """
    if taxi_type not in ("yellow", "green"):
        raise ValueError(
            f"taxi_type must be 'yellow' or 'green', got '{taxi_type}'."
        )

    pickup_col = "tpepPickupDatetime" if taxi_type == "yellow" else "lpepPickupDatetime"
    dropoff_col = "tpepDropoffDatetime" if taxi_type == "yellow" else "lpepDropoffDatetime"
    source_table = f"nyctaxi_{taxi_type}"

    bronze_path = _build_path(workspace_id, lakehouse_name, "bronze", source_table)
    silver_path = _build_path(workspace_id, lakehouse_name, "silver", "nyctaxi")

    try:
        bronze_df: DataFrame = spark.read.format("delta").load(bronze_path)
    except AnalysisException as exc:
        raise IngestionError(
            f"Cannot read Bronze table at '{bronze_path}': {exc}"
        ) from exc

    # Filter to the requested year/month partition.
    filtered = bronze_df.filter(F.year(F.col(pickup_col)) == year)
    if month is not None:
        filtered = filtered.filter(F.month(F.col(pickup_col)) == month)

    silver_df = (
        filtered
        # Remove TLC-documented recording errors (TLC Data Dictionary 2023).
        .filter(F.col("fareAmount") >= 0)
        .filter(F.col("tripDistance") >= 0)
        .filter(F.col(pickup_col).isNotNull())
        # Derive surrogate key: SHA-256 of (vendorID, pickupDatetime, puLocationId).
        .withColumn(
            "trip_id",
            F.sha2(
                F.concat_ws("|",
                    F.coalesce(F.col("vendorID"), F.lit("")),
                    F.col(pickup_col).cast("string"),
                    F.coalesce(F.col("puLocationId"), F.lit("")),
                ),
                256,
            ),
        )
        .dropDuplicates(["trip_id"])
        # Derive trip duration in fractional minutes.
        .withColumn(
            "trip_duration_min",
            (
                F.unix_timestamp(F.col(dropoff_col)) - F.unix_timestamp(F.col(pickup_col))
            ).cast("double") / 60.0,
        )
        .withColumn("taxi_type", F.lit(taxi_type))
        .withColumn("pickup_date", F.to_date(F.col(pickup_col)).cast("string"))
        .withColumn("_silver_ts", F.current_timestamp())
        .select(
            "trip_id",
            F.col(pickup_col).alias("pickup_ts"),
            F.col(dropoff_col).alias("dropoff_ts"),
            "trip_duration_min",
            "passengerCount",
            "tripDistance",
            F.col("puLocationId").alias("pu_location_id"),
            F.col("doLocationId").alias("do_location_id"),
            "paymentType",
            "fareAmount",
            "tipAmount",
            "totalAmount",
            "taxi_type",
            "pickup_date",
            "_silver_ts",
        )
        .toDF(*[f.name for f in SILVER_NYCTAXI.fields])
    )

    _upsert(spark, silver_df, silver_path, "trip_id")

    row_count: int = silver_df.count()
    logger.info(
        "Silver transform complete: source=nyctaxi_%s, year=%d, month=%s, rows=%d",
        taxi_type, year, str(month) if month else "all", row_count,
    )
    return row_count


def transform_weather_to_silver(
    spark: SparkSession,
    workspace_id: str,
    lakehouse_name: str,
    year: int,
    month: int | None = None,
) -> int:
    """Cleanse Bronze NOAA weather data and upsert into Silver.

    Parameters
    ----------
    spark : SparkSession
        Active Fabric Spark session.
    workspace_id : str
        Fabric workspace GUID.
    lakehouse_name : str
        Fabric Lakehouse name.
    year : int
        Year partition to process.
    month : int | None
        Month partition to process, or None for the full year.

    Returns
    -------
    int
        Approximate number of rows upserted.

    Raises
    ------
    IngestionError
        If any Spark operation fails.
    """
    bronze_path = _build_path(workspace_id, lakehouse_name, "bronze", "noaa_weather")
    silver_path = _build_path(workspace_id, lakehouse_name, "silver", "weather")

    try:
        bronze_df: DataFrame = spark.read.format("delta").load(bronze_path)
    except AnalysisException as exc:
        raise IngestionError(
            f"Cannot read Bronze weather table at '{bronze_path}': {exc}"
        ) from exc

    filtered = bronze_df.filter(F.col("year") == year)
    if month is not None:
        filtered = filtered.filter(F.col("month") == month)

    silver_df = (
        filtered
        .filter(F.col("datetime").isNotNull())
        .dropDuplicates(["stationName", "datetime"])
        .withColumn("weather_date", F.to_date(F.col("datetime")).cast("string"))
        .withColumn("_silver_ts", F.current_timestamp())
        .select(
            F.col("stationName").alias("station_name"),
            F.col("datetime").alias("weather_ts"),
            "latitude",
            "longitude",
            F.col("temperature").alias("temperature_c"),
            F.col("windSpeed").alias("wind_speed_ms"),
            F.col("precipDepth").alias("precip_depth_mm"),
            "weather_date",
            "_silver_ts",
        )
        .toDF(*[f.name for f in SILVER_WEATHER.fields])
    )

    _upsert(spark, silver_df, silver_path, "weather_ts")

    row_count: int = silver_df.count()
    logger.info(
        "Silver weather transform complete: year=%d, month=%s, rows=%d",
        year, str(month) if month else "all", row_count,
    )
    return row_count
