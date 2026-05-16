-- Semantic model base queries for Power BI Direct Lake mode.
-- These queries define the measure tables; calculated measures are
-- defined in the .bim / tabular model, not here.

-- Fact table: daily operations events
SELECT
    CAST(summary_date AS DATE)   AS [Date],
    source_system                AS [Source System],
    category                     AS [Category],
    event_count                  AS [Event Count],
    critical_count               AS [Critical Count],
    avg_numeric_value            AS [Avg Numeric Value]
FROM
    gold.daily_operations_summary;

-- Dimension: date (spine for time intelligence)
-- Generated externally via a date-spine notebook; referenced here for documentation.
-- Table: dim_date (date_key DATE, year INT, quarter INT, month INT, week INT, is_weekday BIT)
