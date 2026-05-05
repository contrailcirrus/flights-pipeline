WITH 
    logs_tb AS (SELECT *
               FROM `contrails-301217.flights_pipeline_prod.logs_inventory_2024_2025_run_march2026` AS t
               WHERE t.jsonPayload.flight_id IS NOT NULL),

    skipped_tb AS (SELECT *
                    FROM logs_tb
                    WHERE logs_tb.jsonPayload.message LIKE "%skipping%"
                      AND logs_tb.jsonPayload.detail = "violations found"),
     start_tb AS (SELECT *,
                  FROM logs_tb
                  WHERE logs_tb.jsonPayload.message = "start work"
                    AND logs_tb.jsonPayload.flight_id IS NOT NULL
                  QUALIFY ROW_NUMBER() OVER (PARTITION BY logs_tb.jsonPayload.flight_id) = 1), 

    reason_tb AS (
        SELECT
            ranked_reasons.flight_id, SPLIT(ranked_reasons.reason, ':')[SAFE_OFFSET(0)] AS reason,
        FROM (
            SELECT skipped_tb.jsonPayload.flight_id AS flight_id, reason, ROW_NUMBER() OVER (PARTITION BY skipped_tb.jsonPayload.flight_id ORDER BY COUNT (*) DESC) AS rn
                FROM skipped_tb, 
                    UNNEST(skipped_tb.jsonPayload.reason) AS reason
                WHERE skipped_tb.jsonPayload.flight_id IS NOT NULL
                GROUP BY skipped_tb.jsonPayload.flight_id, reason
            ) AS ranked_reasons
        WHERE
            ranked_reasons.rn = 1), 

    airlines_tb AS (
        SELECT start_tb.jsonPayload.flight_id AS flight_id, 'AA' IN UNNEST(start_tb.jsonPayload.airline_iata) AS is_present
        FROM start_tb
    )



SELECT reason_tb.reason, count(reason_tb.reason)  AS incidence_count
    FROM reason_tb
        LEFT JOIN start_tb
        ON start_tb.jsonPayload.flight_id = reason_tb.flight_id
        LEFT JOIN airlines_tb 
        ON start_tb.jsonPayload.flight_id = airlines_tb.flight_id

    WHERE airlines_tb.is_present = TRUE

    GROUP BY reason_tb.reason
    ORDER BY incidence_count DESC