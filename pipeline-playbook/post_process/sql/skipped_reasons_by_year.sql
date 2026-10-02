-- Determine the most common reasons for flights being skipped, grouped by year.

-- Adjust logs table name to point to specific run logs
WITH 
    logs_tb AS (
        SELECT *
            FROM `contrails-301217.flights_pipeline_prod.logs_inventory_2026Q1_run_sept2026` AS t
            WHERE t.jsonPayload.flight_id IS NOT NULL),

    skipped_tb AS (
        SELECT *
            FROM logs_tb
            WHERE logs_tb.jsonPayload.message LIKE "%skipping%"
                AND logs_tb.jsonPayload.detail = "violations found"
                AND logs_tb.resource.labels.container_name = "trajectory-worker-job-factory"),

    start_tb AS (
        SELECT *,
            FROM logs_tb
            WHERE logs_tb.jsonPayload.message = "start work"
            AND logs_tb.jsonPayload.flight_id IS NOT NULL
            AND logs_tb.resource.labels.container_name = "trajectory-worker-job-factory"
        QUALIFY ROW_NUMBER() OVER (PARTITION BY logs_tb.jsonPayload.flight_id) = 1), 

    -- Whole days spanned by start_time within each year bin
    span_tb AS (
        SELECT
            EXTRACT(YEAR FROM start_tb.jsonPayload.start_time) AS flight_year_bin,
            TIMESTAMP_DIFF(
                MAX(start_tb.jsonPayload.start_time),
                MIN(start_tb.jsonPayload.start_time),
                DAY) AS span_days
            FROM start_tb
            GROUP BY flight_year_bin),
    reason_tb AS (
        SELECT
            ranked_reasons.flight_id, SPLIT(ranked_reasons.reason, ':')[SAFE_OFFSET(0)] AS reason,
            FROM (
                SELECT
                skipped_tb.jsonPayload.flight_id AS flight_id, reason, ROW_NUMBER() OVER (
                        PARTITION BY skipped_tb.jsonPayload.flight_id ORDER BY COUNT (*) DESC
                    ) AS rn
                    FROM
                    skipped_tb, UNNEST(skipped_tb.jsonPayload.reason) AS reason
                    WHERE
                    skipped_tb.jsonPayload.flight_id IS NOT NULL
                    GROUP BY 
                    skipped_tb.jsonPayload.flight_id, reason
            ) AS ranked_reasons
        WHERE
        ranked_reasons.rn = 1), 

    summary_tb AS (
        SELECT
            EXTRACT(YEAR FROM start_tb.jsonPayload.start_time) AS flight_year_bin, reason_tb.reason AS reason
            FROM reason_tb
                LEFT JOIN start_tb
            ON start_tb.jsonPayload.flight_id = reason_tb.flight_id)

SELECT
    summary_tb.reason,
    COUNT(summary_tb.reason) AS reason_count,
    ROUND(SAFE_DIVIDE(COUNT(summary_tb.reason), ANY_VALUE(span_tb.span_days)),1) AS reason_count_per_day,
    summary_tb.flight_year_bin AS year,
    FROM summary_tb
        LEFT JOIN span_tb
        ON summary_tb.flight_year_bin = span_tb.flight_year_bin
GROUP BY summary_tb.reason, year
ORDER BY reason_count DESC;
