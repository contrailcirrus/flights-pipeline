-- Determine the most common reasons for flights being skipped, grouped by month.

-- Adjust logs table name to point to specific run logs
WITH 
    logs_tb AS (SELECT *
               FROM `contrails-301217.flights_pipeline_prod.twjf_2024_logs_feb2026` AS t
               WHERE t.jsonPayload.flight_id IS NOT NULL),

    skipped_tb AS (SELECT *
                    FROM logs_tb
                    WHERE logs_tb.jsonPayload.message = "skipping"
                      AND logs_tb.jsonPayload.detail = "violations found"),
     start_tb AS (SELECT *,
                  FROM logs_tb
                  WHERE logs_tb.jsonPayload.message = "start work"
                    AND logs_tb.jsonPayload.flight_id IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY logs_tb.jsonPayload.flight_id) = 1), reason_tb AS (
SELECT
    ranked_reasons.flight_id, SPLIT(ranked_reasons.reason, ':')[SAFE_OFFSET(0)] AS reason,
FROM (
    SELECT
    skipped_tb.jsonPayload.flight_id AS flight_id, reason, ROW_NUMBER() OVER (PARTITION BY skipped_tb.jsonPayload.flight_id ORDER BY COUNT (*) DESC) AS rn
    FROM
    skipped_tb, UNNEST(skipped_tb.jsonPayload.reason) AS reason
    WHERE
    skipped_tb.jsonPayload.flight_id IS NOT NULL
    GROUP BY
    skipped_tb.jsonPayload.flight_id, reason
    ) AS ranked_reasons
WHERE
    ranked_reasons.rn = 1)
    , summary_tb AS (
SELECT
    TIMESTAMP_TRUNC(start_tb.jsonPayload.start_time, MONTH) AS flight_month_bin, reason_tb.reason AS reason
FROM reason_tb
    LEFT JOIN start_tb
ON start_tb.jsonPayload.flight_id = reason_tb.flight_id
    )

SELECT reason, COUNT(reason) AS reason_count, flight_month_bin AS month
FROM summary_tb
GROUP BY reason, month
ORDER BY month, reason_count DESC;
