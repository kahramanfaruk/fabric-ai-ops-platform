"""Medallion schema contracts: Bronze → Silver → Gold.

Schemas are defined centrally to prevent silent drift between layers.
PySpark StructType objects are used so ingestion code can enforce them
at read and write time.

NYC Taxi Yellow column names match the Azure Open Datasets Parquet schema
exactly (camelCase as published by Microsoft TLC):
  https://learn.microsoft.com/en-us/azure/open-datasets/dataset-taxi-yellow
"""

from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ─────────────────────────────────────────────────────────────────────────────
# BRONZE  — raw, append-only, schema matches Azure Open Datasets Parquet output
# ─────────────────────────────────────────────────────────────────────────────

BRONZE_NYCTAXI_YELLOW: StructType = StructType(
    [
        # Native TLC / Azure Open Datasets columns (camelCase)
        StructField("vendorID",             StringType(),    nullable=True),
        StructField("tpepPickupDatetime",   TimestampType(), nullable=False),
        StructField("tpepDropoffDatetime",  TimestampType(), nullable=True),
        StructField("passengerCount",       IntegerType(),   nullable=True),
        StructField("tripDistance",         DoubleType(),    nullable=True),
        StructField("puLocationId",         StringType(),    nullable=True),
        StructField("doLocationId",         StringType(),    nullable=True),
        StructField("rateCodeId",           IntegerType(),   nullable=True),
        StructField("storeAndFwdFlag",      StringType(),    nullable=True),
        StructField("paymentType",          StringType(),    nullable=True),
        StructField("fareAmount",           DoubleType(),    nullable=True),
        StructField("extra",                DoubleType(),    nullable=True),
        StructField("mtaTax",               DoubleType(),    nullable=True),
        StructField("improvementSurcharge", DoubleType(),    nullable=True),
        StructField("tipAmount",            DoubleType(),    nullable=True),
        StructField("tollsAmount",          DoubleType(),    nullable=True),
        StructField("totalAmount",          DoubleType(),    nullable=True),
        StructField("puYear",               IntegerType(),   nullable=True),
        StructField("puMonth",              IntegerType(),   nullable=True),
        # Audit columns added at ingestion time
        StructField("_ingested_ts",  TimestampType(), nullable=False),
        StructField("_source_file",  StringType(),    nullable=False),
        StructField("_source_name",  StringType(),    nullable=False),
    ]
)

BRONZE_NYCTAXI_GREEN: StructType = StructType(
    [
        StructField("vendorID",            StringType(),    nullable=True),
        StructField("lpepPickupDatetime",  TimestampType(), nullable=False),
        StructField("lpepDropoffDatetime", TimestampType(), nullable=True),
        StructField("passengerCount",      IntegerType(),   nullable=True),
        StructField("tripDistance",        DoubleType(),    nullable=True),
        StructField("puLocationId",        StringType(),    nullable=True),
        StructField("doLocationId",        StringType(),    nullable=True),
        StructField("rateCodeId",          IntegerType(),   nullable=True),
        StructField("storeAndFwdFlag",     StringType(),    nullable=True),
        StructField("paymentType",         StringType(),    nullable=True),
        StructField("fareAmount",          DoubleType(),    nullable=True),
        StructField("extra",               DoubleType(),    nullable=True),
        StructField("mtaTax",              DoubleType(),    nullable=True),
        StructField("tipAmount",           DoubleType(),    nullable=True),
        StructField("tollsAmount",         DoubleType(),    nullable=True),
        StructField("totalAmount",         DoubleType(),    nullable=True),
        StructField("tripType",            StringType(),    nullable=True),
        StructField("puYear",              IntegerType(),   nullable=True),
        StructField("puMonth",             IntegerType(),   nullable=True),
        StructField("_ingested_ts",        TimestampType(), nullable=False),
        StructField("_source_file",        StringType(),    nullable=False),
        StructField("_source_name",        StringType(),    nullable=False),
    ]
)

BRONZE_NOAA_WEATHER: StructType = StructType(
    [
        StructField("stationName",      StringType(),    nullable=True),
        StructField("datetime",         TimestampType(), nullable=False),
        StructField("latitude",         DoubleType(),    nullable=True),
        StructField("longitude",        DoubleType(),    nullable=True),
        StructField("elevation",        DoubleType(),    nullable=True),
        StructField("windAngle",        DoubleType(),    nullable=True),
        StructField("windSpeed",        DoubleType(),    nullable=True),
        StructField("temperature",      DoubleType(),    nullable=True),
        StructField("dewPoint",         DoubleType(),    nullable=True),
        StructField("seaLvlPressure",   DoubleType(),    nullable=True),
        StructField("precipTime",       DoubleType(),    nullable=True),
        StructField("precipDepth",      DoubleType(),    nullable=True),
        StructField("snowDepth",        DoubleType(),    nullable=True),
        StructField("year",             IntegerType(),   nullable=True),
        StructField("month",            IntegerType(),   nullable=True),
        StructField("day",              IntegerType(),   nullable=True),
        StructField("_ingested_ts",     TimestampType(), nullable=False),
        StructField("_source_file",     StringType(),    nullable=False),
        StructField("_source_name",     StringType(),    nullable=False),
    ]
)

# ─────────────────────────────────────────────────────────────────────────────
# SILVER  — cleansed, deduplicated, typed, with derived columns
# ─────────────────────────────────────────────────────────────────────────────

SILVER_NYCTAXI: StructType = StructType(
    [
        StructField("trip_id",           StringType(),    nullable=False),  # SHA2 surrogate key
        StructField("pickup_ts",         TimestampType(), nullable=False),
        StructField("dropoff_ts",        TimestampType(), nullable=True),
        StructField("trip_duration_min", DoubleType(),    nullable=True),   # derived
        StructField("passenger_count",   IntegerType(),   nullable=True),
        StructField("trip_distance",     DoubleType(),    nullable=True),
        StructField("pu_location_id",    StringType(),    nullable=True),
        StructField("do_location_id",    StringType(),    nullable=True),
        StructField("payment_type",      StringType(),    nullable=True),
        StructField("fare_amount",       DoubleType(),    nullable=True),
        StructField("tip_amount",        DoubleType(),    nullable=True),
        StructField("total_amount",      DoubleType(),    nullable=True),
        StructField("taxi_type",         StringType(),    nullable=False),  # "yellow" | "green"
        StructField("pickup_date",       StringType(),    nullable=False),  # ISO date, partition col
        StructField("_silver_ts",        TimestampType(), nullable=False),
    ]
)

SILVER_WEATHER: StructType = StructType(
    [
        StructField("station_name",    StringType(),    nullable=True),
        StructField("weather_ts",      TimestampType(), nullable=False),
        StructField("latitude",        DoubleType(),    nullable=True),
        StructField("longitude",       DoubleType(),    nullable=True),
        StructField("temperature_c",   DoubleType(),    nullable=True),
        StructField("wind_speed_ms",   DoubleType(),    nullable=True),
        StructField("precip_depth_mm", DoubleType(),    nullable=True),
        StructField("weather_date",    StringType(),    nullable=False),  # ISO date, partition col
        StructField("_silver_ts",      TimestampType(), nullable=False),
    ]
)

# ─────────────────────────────────────────────────────────────────────────────
# GOLD  — aggregated, denormalised, query-optimised, joined with weather
# ─────────────────────────────────────────────────────────────────────────────

GOLD_DAILY_TRIP_SUMMARY: StructType = StructType(
    [
        StructField("summary_date",          StringType(),    nullable=False),
        StructField("taxi_type",             StringType(),    nullable=False),
        StructField("pu_location_id",        StringType(),    nullable=False),
        StructField("trip_count",            LongType(),      nullable=False),
        StructField("avg_fare",              DoubleType(),    nullable=True),
        StructField("avg_tip",               DoubleType(),    nullable=True),
        StructField("avg_distance",          DoubleType(),    nullable=True),
        StructField("avg_duration_min",      DoubleType(),    nullable=True),
        StructField("avg_temperature_c",     DoubleType(),    nullable=True),  # joined from NOAA
        StructField("avg_precip_depth_mm",   DoubleType(),    nullable=True),  # joined from NOAA
        StructField("_gold_ts",              TimestampType(), nullable=False),
    ]
)
