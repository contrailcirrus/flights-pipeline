-- Get the number of minutes coming into the pipeline, the number skipped by TWJD,
-- the fraction skipped, and the fraction dropped in total (from the TW compared with into the TWJD).

-- Set date range
DECLARE date_range_start TIMESTAMP DEFAULT '2024-01-01T00:00:00';
DECLARE date_range_end TIMESTAMP DEFAULT '2024-12-31T11:59:59';

-- Set the logs table for the specific run
WITH 
logs_tb AS (SELECT *
           FROM `contrails-301217.flights_pipeline_prod.twjf_2024_logs_feb2026`
           WHERE jsonPayload.flight_id IS NOT NULL),

results_tb AS (SELECT * FROM `contrails-301217.flights_pipeline_prod.inventory_2024_run_feb2026_summary`),

start_tb AS (SELECT *,
            TIMESTAMP_DIFF(jsonPayload.end_time, jsonPayload.start_time, MINUTE) AS initial_duration_mins
    FROM logs_tb
    WHERE jsonPayload.message LIKE "%start work%"
    QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1), 
    
finish_tb AS (
    SELECT *, TIMESTAMP_DIFF(jsonPayload.end_time, jsonPayload.start_time, MINUTE) AS final_duration_mins
    FROM logs_tb
    WHERE jsonPayload.message LIKE "%resample%"
        QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1), 
    
skipped_tb AS (
    SELECT *
    FROM logs_tb
    WHERE jsonPayload.message LIKE "%skipping%"
        QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1), 
    
final_time_tb AS (
    SELECT SUM (TIMESTAMP_DIFF(time_end, time_start, MINUTE)) AS total_final_flight_time_mins, 
    TIMESTAMP_TRUNC(time_start, MONTH) AS flight_month_bin
    FROM results_tb
    WHERE time_start >= date_range_start
    AND time_start <= date_range_end
    GROUP BY flight_month_bin),
    
skipped_w_time_tb AS (
    SELECT skipped_tb.*, start_tb.jsonPayload.start_time AS start_time, start_tb.initial_duration_mins
    FROM skipped_tb
        LEFT JOIN start_tb
    ON skipped_tb.jsonPayload.flight_id = start_tb.jsonPayload.flight_id),

success_tb AS (
    SELECT start_tb.*
    FROM start_tb
        LEFT JOIN skipped_tb
    ON start_tb.jsonPayload.flight_id = skipped_tb.jsonPayload.flight_id
    WHERE skipped_tb.jsonPayload.flight_id IS NULL), 

success_w_time_tb AS (
    SELECT success_tb.*, finish_tb.final_duration_mins
    FROM success_tb
        LEFT JOIN finish_tb
    ON success_tb.jsonPayload.flight_id = finish_tb.jsonPayload.flight_id),

bin_success_tb AS (
    SELECT TIMESTAMP_TRUNC(jsonPayload.start_time, MONTH) AS flight_month_bin, SUM (final_duration_mins) AS total_flight_time_mins
    FROM success_w_time_tb
    GROUP BY flight_month_bin),
    
bin_skipped_tb AS (
    SELECT TIMESTAMP_TRUNC(start_time, MONTH) AS flight_month_bin, SUM (initial_duration_mins) AS total_flight_time_mins
    FROM skipped_w_time_tb
    GROUP BY flight_month_bin),
    
summary_tb
    AS (
        SELECT COALESCE (bin_success_tb.flight_month_bin, bin_skipped_tb.flight_month_bin) AS flight_month_bin, 
        COALESCE (bin_success_tb.total_flight_time_mins, 0) AS twjf_passed_flight_time_minutes, 
        COALESCE (bin_skipped_tb.total_flight_time_mins, 0) AS twjf_skipped_flight_time_minutes, 
        COALESCE (final_time_tb.total_final_flight_time_mins, 0) AS total_final_flight_time_minutes
    FROM bin_success_tb
        FULL JOIN bin_skipped_tb
    ON bin_success_tb.flight_month_bin = bin_skipped_tb.flight_month_bin
        FULL JOIN final_time_tb ON bin_success_tb.flight_month_bin = final_time_tb.flight_month_bin)


SELECT *,
       twjf_skipped_flight_time_minutes / (twjf_skipped_flight_time_minutes + twjf_passed_flight_time_minutes) *
       100                                                                    AS skipped_perc,
       (twjf_passed_flight_time_minutes - total_final_flight_time_minutes) * 100 /
       (twjf_skipped_flight_time_minutes + twjf_passed_flight_time_minutes) AS tw_dropped_perc,
       (twjf_skipped_flight_time_minutes + twjf_passed_flight_time_minutes - total_final_flight_time_minutes) * 100 /
       (twjf_skipped_flight_time_minutes + twjf_passed_flight_time_minutes) AS total_dropped_perc
FROM summary_tb
WHERE flight_month_bin IS NOT NULL
ORDER BY flight_month_bin DESC