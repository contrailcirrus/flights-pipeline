WITH start_tb AS (SELECT *,
                         TIMESTAMP_DIFF(jsonPayload.end_time, jsonPayload.start_time, MINUTE) AS initial_duration_mins
                  FROM `contrails-301217.flights_pipeline_prod.twjf_2024_logs_feb2026_EXAMPLE`
                  WHERE jsonPayload.message LIKE "%start work%"
                  QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1),
     finish_tb AS (SELECT *, TIMESTAMP_DIFF(jsonPayload.end_time, jsonPayload.start_time, MINUTE) AS final_duration_mins
                   FROM `contrails-301217.flights_pipeline_prod.twjf_2024_logs_feb2026_EXAMPLE`
                   WHERE jsonPayload.message LIKE "%resample%"
                   QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1),
     skipped_tb AS (SELECT *
                    FROM `contrails-301217.flights_pipeline_prod.twjf_2024_logs_feb2026_EXAMPLE`
                    WHERE jsonPayload.message LIKE "%skipping%"
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1),
     skipped_w_time_tb AS (SELECT skipped_tb.*,
                                  start_tb.jsonPayload.start_time AS start_time,
                                  start_tb.initial_duration_mins
                           FROM skipped_tb
                                    LEFT JOIN start_tb
                                              ON skipped_tb.jsonPayload.flight_id = start_tb.jsonPayload.flight_id),
     success_tb AS (SELECT start_tb.*
                    FROM start_tb
                             LEFT JOIN skipped_tb ON start_tb.jsonPayload.flight_id = skipped_tb.jsonPayload.flight_id
                    WHERE skipped_tb.jsonPayload.flight_id IS NULL),
     success_w_time_tb AS (SELECT success_tb.*, finish_tb.final_duration_mins
                           FROM success_tb
                                    LEFT JOIN finish_tb
                                              ON success_tb.jsonPayload.flight_id = finish_tb.jsonPayload.flight_id),
     bin_success_tb AS (SELECT TIMESTAMP_TRUNC(jsonPayload.start_time, MONTH) AS flight_month_bin,
                               SUM(final_duration_mins)                       AS total_flight_time_mins
                        FROM success_w_time_tb
                        GROUP BY flight_month_bin),
     bin_skipped_tb AS (SELECT TIMESTAMP_TRUNC(start_time, MONTH) AS flight_month_bin,
                               SUM(initial_duration_mins)         AS total_flight_time_mins
                        FROM skipped_w_time_tb
                        GROUP BY flight_month_bin),
     summary_tb
         AS (SELECT COALESCE(bin_success_tb.flight_month_bin, bin_skipped_tb.flight_month_bin) AS flight_month_bin,
                    COALESCE(bin_success_tb.total_flight_time_mins, 0)                         AS total_passed_flight_time_minutes,
                    COALESCE(bin_skipped_tb.total_flight_time_mins, 0)                         AS total_skipped_flight_time_minutes
             FROM bin_success_tb
                      FULL JOIN bin_skipped_tb ON bin_success_tb.flight_month_bin = bin_skipped_tb.flight_month_bin)
SELECT *,
       total_skipped_flight_time_minutes / (total_skipped_flight_time_minutes + total_passed_flight_time_minutes) *
       100 AS skipped_perc
FROM summary_tb
WHERE flight_month_bin IS NOT NULL
ORDER BY flight_month_bin DESC
