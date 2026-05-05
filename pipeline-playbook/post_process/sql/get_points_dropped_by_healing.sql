WITH 
    logs_tb AS (SELECT *
               FROM `contrails-301217.flights_pipeline_prod.logs_inventory_2024_2025_run_march2026` AS t
               WHERE t.jsonPayload.flight_id IS NOT NULL),

    skipped_tb AS (SELECT *
                    FROM logs_tb
                    WHERE logs_tb.jsonPayload.message LIKE "%skipping%"
                      AND logs_tb.jsonPayload.detail = "violations found"
                      AND logs_tb.resource.labels.container_name = "trajectory-worker-job-factory"),
     start_tb AS (SELECT *,
                  FROM logs_tb
                  WHERE logs_tb.jsonPayload.message = "start work"
                    AND logs_tb.jsonPayload.flight_id IS NOT NULL
                    AND logs_tb.resource.labels.container_name = "trajectory-worker-job-factory"
    QUALIFY ROW_NUMBER() OVER (PARTITION BY logs_tb.jsonPayload.flight_id) = 1), 

    healing_tb AS (SELECT *,
                    FROM logs_tb
                    WHERE logs_tb.jsonPayload.message = "healing"
                      AND logs_tb.jsonPayload.flight_id IS NOT NULL
                      AND logs_tb.resource.labels.container_name = "trajectory-worker-job-factory"
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY logs_tb.jsonPayload.flight_id) = 1), 

    reason_tb AS (
        SELECT
            ranked_reasons.flight_id, SPLIT(ranked_reasons.reason, ':')[SAFE_OFFSET(0)] AS reason,
        FROM (
            SELECT
            skipped_tb.jsonPayload.flight_id AS flight_id, reason, ROW_NUMBER() OVER (PARTITION BY skipped_tb.jsonPayload.flight_id ORDER BY COUNT (*) DESC) AS rn
                FROM skipped_tb, UNNEST(skipped_tb.jsonPayload.reason) AS reason
                WHERE skipped_tb.jsonPayload.flight_id IS NOT NULL
            GROUP BY skipped_tb.jsonPayload.flight_id, reason
            ) AS ranked_reasons
        WHERE
            ranked_reasons.rn = 1), 

    speed_heal_tb AS (
        SELECT healing_tb.jsonPayload.flight_id AS flight_id, healing_tb.jsonPayload.detail as detail, REGEXP_EXTRACT_ALL(healing_tb.jsonPayload.detail, r'\d+') as nums
        FROM healing_tb
        WHERE healing_tb.jsonPayload.detail LIKE "speed filter%"
    ),

    selection_tb AS (
        SELECT TIMESTAMP_TRUNC(start_tb.jsonPayload.start_time, MONTH) AS flight_month, reason_tb.reason AS reason, start_tb.jsonPayload.start_time AS start_time,reason_tb.flight_id AS flight_id, speed_heal_tb.detail AS detail, CAST(speed_heal_tb.nums[ORDINAL(1)] AS INT64) AS ejected_waypoints, CAST(speed_heal_tb.nums[ORDINAL(2)] AS INT64) AS initial_waypoints,
        FROM reason_tb
            LEFT JOIN start_tb
            ON start_tb.jsonPayload.flight_id = reason_tb.flight_id
            LEFT JOIN speed_heal_tb
            ON speed_heal_tb.flight_id = reason_tb.flight_id

        WHERE reason = "FlightTooShortError"
    )

SELECT selection_tb.flight_month, selection_tb.start_time, selection_tb.flight_id, selection_tb.detail, selection_tb.ejected_waypoints, selection_tb.initial_waypoints
    FROM selection_tb
    where selection_tb.flight_month = '2024-05-01'
    AND selection_tb.ejected_waypoints/selection_tb.initial_waypoints > 0.7