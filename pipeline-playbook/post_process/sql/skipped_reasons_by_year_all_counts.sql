DECLARE date_range_start TIMESTAMP DEFAULT '2026-01-01T00:00:00';
DECLARE date_range_end   TIMESTAMP DEFAULT '2026-04-01T00:00:00'; -- exclusive
DECLARE dataset_name STRING DEFAULT 'Q1';

WITH 
logs_tb AS (
    SELECT *
    FROM `contrails-301217.flights_pipeline_prod.logs_inventory_2026Q1_run_sept2026`
    WHERE jsonPayload.flight_id IS NOT NULL
      AND resource.labels.container_name = "trajectory-worker-job-factory"),

skipped_tb AS (
    SELECT *
    FROM logs_tb
    WHERE jsonPayload.message LIKE "%skipping%"
      AND jsonPayload.detail = "violations found"),

start_tb AS (
    SELECT *
    FROM logs_tb
    WHERE jsonPayload.message = "start work"
      AND jsonPayload.start_time >= date_range_start
      AND jsonPayload.start_time <  date_range_end
    QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1), 

-- Calendar days spanned by start_time within each year bin (inclusive)
span_tb AS (
    SELECT
        EXTRACT(YEAR FROM jsonPayload.start_time) AS flight_year_bin,
        DATE_DIFF(DATE(MAX(jsonPayload.start_time)),
                  DATE(MIN(jsonPayload.start_time)), DAY) + 1 AS span_days
    FROM start_tb
    GROUP BY flight_year_bin),

-- Every distinct (flight, reason category) pair
reason_tb AS (
    SELECT DISTINCT
        jsonPayload.flight_id AS flight_id,
        SPLIT(reason, ':')[SAFE_OFFSET(0)] AS reason
    FROM skipped_tb, UNNEST(jsonPayload.reason) AS reason),

-- Inner join: only skipped flights that started in the date window
summary_tb AS (
    SELECT
        EXTRACT(YEAR FROM start_tb.jsonPayload.start_time) AS flight_year_bin,
        reason_tb.flight_id,
        reason_tb.reason
    FROM reason_tb
    JOIN start_tb
      ON start_tb.jsonPayload.flight_id = reason_tb.flight_id),

year_totals_tb AS (
    SELECT flight_year_bin, COUNT(DISTINCT flight_id) AS n_skipped_flights
    FROM summary_tb
    GROUP BY flight_year_bin)

SELECT
    reason,
    COUNT(*) AS flights_with_reason,
    ROUND(SAFE_DIVIDE(COUNT(*), ANY_VALUE(span_days)), 1) AS flights_with_reason_per_day,
    ROUND(100 * SAFE_DIVIDE(COUNT(*), ANY_VALUE(n_skipped_flights)), 2) AS pct_of_skipped_flights,
    flight_year_bin AS year,
    dataset_name AS dataset
FROM summary_tb
LEFT JOIN span_tb USING (flight_year_bin)
LEFT JOIN year_totals_tb USING (flight_year_bin)
GROUP BY reason, flight_year_bin
ORDER BY year, flights_with_reason DESC;