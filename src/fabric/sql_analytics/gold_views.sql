-- Gold layer analytical views for the NYC Taxi + NOAA dataset.
-- Exposed via Fabric SQL Endpoint; consumed by Power BI Direct Lake mode.
-- Rolling 90-day window to bound query cost and keep Power BI responsive.

CREATE OR ALTER VIEW gold.daily_trip_summary AS
SELECT
    summary_date,
    taxi_type,
    pu_location_id,
    trip_count,
    avg_fare,
    avg_tip,
    CASE
        WHEN avg_fare > 0 THEN avg_tip / avg_fare
        ELSE NULL
    END                         AS tip_rate,          -- derived: tip / fare
    avg_distance,
    avg_duration_min,
    avg_temperature_c,
    avg_precip_depth_mm,
    _gold_ts                    AS refreshed_at
FROM
    gold_daily_trip_summary
WHERE
    summary_date >= CAST(DATEADD(DAY, -90, GETDATE()) AS DATE);

GO

-- KPI view: last-7-day zone performance for the Power BI KPI cards.
CREATE OR ALTER VIEW gold.kpi_last_7_days AS
SELECT
    taxi_type,
    pu_location_id,
    SUM(trip_count)                                      AS total_trips,
    AVG(avg_fare)                                        AS avg_fare_7d,
    AVG(avg_tip / NULLIF(avg_fare, 0))                   AS avg_tip_rate_7d,
    AVG(avg_distance)                                    AS avg_distance_7d,
    AVG(avg_duration_min)                                AS avg_duration_7d,
    AVG(avg_temperature_c)                               AS avg_temp_c_7d,
    MAX(_gold_ts)                                        AS last_refresh
FROM
    gold_daily_trip_summary
WHERE
    summary_date >= CAST(DATEADD(DAY, -7, GETDATE()) AS DATE)
GROUP BY
    taxi_type,
    pu_location_id;

GO

-- Drift monitoring view: compare avg fare by year for anomaly review.
-- Used by the RAG assistant and the Power BI drift dashboard.
CREATE OR ALTER VIEW gold.yearly_fare_distribution AS
SELECT
    LEFT(summary_date, 4)       AS pickup_year,
    taxi_type,
    COUNT(*)                    AS day_count,
    AVG(avg_fare)               AS mean_fare,
    MIN(avg_fare)               AS min_fare,
    MAX(avg_fare)               AS max_fare
FROM
    gold_daily_trip_summary
GROUP BY
    LEFT(summary_date, 4),
    taxi_type;

GO
