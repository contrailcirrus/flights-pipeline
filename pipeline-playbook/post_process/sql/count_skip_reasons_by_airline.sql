WITH 
    logs_tb AS (SELECT *
               FROM `contrails-301217.flights_pipeline_prod.twjf_2024-2025_logs_mar2026` AS t
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
        SELECT start_tb.jsonPayload.flight_id AS flight_id, start_tb.jsonPayload.airline_iata[SAFE_OFFSET(0)] as airline_iata
        FROM start_tb
    )


-- Alternate airlines_tb with some double-counting, but also not arbitrary airline choice
    -- airlines_tb AS (
    --     SELECT start_tb.jsonPayload.flight_id AS flight_id, airline_iata
    --     FROM start_tb,
    --       UNNEST(start_tb.jsonPayload.airline_iata) AS airline_iata
    -- )

SELECT distinct(airlines_tb.airline_iata) AS airline_iata, count(airlines_tb.airline_iata)  AS incidence_count
    FROM reason_tb
        LEFT JOIN start_tb
        ON start_tb.jsonPayload.flight_id = reason_tb.flight_id
        LEFT JOIN airlines_tb ON start_tb.jsonPayload.flight_id = airlines_tb.flight_id

    WHERE reason = "FlightTooShortError"

    GROUP BY airlines_tb.airline_iata
    ORDER BY incidence_count DESC