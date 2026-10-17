-- Get the number of minutes coming into the pipeline, the number skipped by TWJD,
-- the fraction skipped, and the fraction dropped in total (from the TW compared with into the TWJD).

-- Set date range
DECLARE date_range_start TIMESTAMP DEFAULT '2026-07-01T00:00:00';
DECLARE date_range_end TIMESTAMP DEFAULT '2026-10-01T00:00:00'; -- exclusive

-- Set the logs table for the specific run
WITH 
logs_tb AS (
  SELECT *
  FROM `contrails-301217.flights_pipeline_prod.logs_inventory_2026Q3_run_oct2026`
  WHERE jsonPayload.flight_id IS NOT NULL
    AND resource.labels.container_name = "trajectory-worker-job-factory"),

results_tb AS (SELECT * FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_summary`),

twjf_start_tb AS (
  SELECT *,
        TIMESTAMP_DIFF(jsonPayload.end_time, jsonPayload.start_time, SECOND) / 60 AS initial_duration_mins
  FROM logs_tb
  WHERE jsonPayload.message LIKE "%start work%"
    AND jsonPayload.start_time >= date_range_start
    AND jsonPayload.start_time <  date_range_end
  QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1), 
 
twjf_finish_tb AS (
  SELECT jsonPayload.flight_id                                                      AS flight_id, 
        TIMESTAMP_DIFF(jsonPayload.end_time, jsonPayload.start_time, SECOND) / 60   AS twjf_output_mins
  FROM logs_tb
      WHERE jsonPayload.message LIKE "%end work%"
      QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1), 
    
skipped_tb AS (
    SELECT *
    FROM logs_tb
    WHERE jsonPayload.message LIKE "%skipping%"
        QUALIFY ROW_NUMBER() OVER (PARTITION BY jsonPayload.flight_id) = 1), 
    
final_time_tb AS (
    SELECT TIMESTAMP_TRUNC(time_start, MONTH)                AS flight_month_bin,
      SUM(TIMESTAMP_DIFF(time_end, time_start, SECOND)) / 60 AS tw_output_time_mins
        FROM results_tb
        WHERE time_start >= date_range_start
        AND time_start < date_range_end
    GROUP BY flight_month_bin),
    
-- INNER JOIN: only skipped flights that started in the date window
skipped_w_time_tb AS (
    SELECT twjf_start_tb.jsonPayload.start_time AS start_time, 
            twjf_start_tb.initial_duration_mins AS twjf_skipped_mins
    FROM skipped_tb
    JOIN twjf_start_tb
      ON skipped_tb.jsonPayload.flight_id = twjf_start_tb.jsonPayload.flight_id),

twjf_success_tb AS (
    SELECT twjf_start_tb.jsonPayload.flight_id AS flight_id,
          twjf_start_tb.jsonPayload.start_time AS start_time,
          twjf_start_tb.initial_duration_mins  AS twjf_input_mins_passed,
    FROM twjf_start_tb
      LEFT JOIN skipped_tb
      ON twjf_start_tb.jsonPayload.flight_id = skipped_tb.jsonPayload.flight_id
      WHERE skipped_tb.jsonPayload.flight_id IS NULL), 

twjf_success_w_time_tb AS (
    SELECT s.start_time                 AS start_time, 
      s.twjf_input_mins_passed          AS twjf_input_mins_passed, 
      f.twjf_output_mins                AS twjf_output_mins
    FROM twjf_success_tb s
      LEFT JOIN twjf_finish_tb f
      ON s.flight_id = f.flight_id),

bin_success_tb AS (
    SELECT TIMESTAMP_TRUNC(start_time, MONTH) AS flight_month_bin,
    SUM(twjf_input_mins_passed)               AS twjf_input_mins_passed,
    SUM (twjf_output_mins)                    AS twjf_output_mins,
    FROM twjf_success_w_time_tb
    GROUP BY flight_month_bin),
    
bin_skipped_tb AS (
    SELECT TIMESTAMP_TRUNC(start_time, MONTH) AS flight_month_bin, 
            SUM (twjf_skipped_mins)       AS twjf_skipped_mins
        FROM skipped_w_time_tb
    GROUP BY flight_month_bin),

summary_tb AS (
  SELECT  
    COALESCE (bin_success_tb.flight_month_bin, bin_skipped_tb.flight_month_bin) AS flight_month_bin, 
    COALESCE(bin_success_tb.twjf_input_mins_passed, 0)                          AS twjf_input_mins_passed,
    COALESCE (bin_success_tb.twjf_output_mins, 0)                               AS twjf_output_mins, 
    COALESCE (bin_skipped_tb.twjf_skipped_mins, 0)                              AS twjf_skipped_mins, 
    COALESCE (final_time_tb.tw_output_time_mins, 0)                             AS tw_output_time_mins
  FROM bin_success_tb
      FULL JOIN bin_skipped_tb USING (flight_month_bin)
      FULL JOIN final_time_tb USING(flight_month_bin)
)

SELECT 
    DATE(summary_tb.flight_month_bin)                   AS month,
    ROUND(twjf_skipped_mins + twjf_input_mins_passed)   AS twjf_input_mins,
    ROUND(twjf_skipped_mins + twjf_output_mins)         AS twjf_resampled_input_mins,
    ROUND(twjf_skipped_mins)                            AS twjf_skipped_minutes,
    ROUND(twjf_output_mins)                             AS twjf_passed_minutes,
    ROUND(twjf_input_mins_passed)                       AS twjf_input_minutes_passed,
    ROUND(tw_output_time_mins)                          AS tw_output_minutes,
    ROUND(100 * SAFE_DIVIDE(twjf_skipped_mins, 
                            (twjf_skipped_mins + twjf_input_mins_passed)), 2)
                                                        AS twjf_skipped_perc,
    ROUND(100 * SAFE_DIVIDE(twjf_output_mins - tw_output_time_mins,
                            (twjf_input_mins_passed)), 2)                       
                                                        AS tw_dropped_perc,
    ROUND(100* SAFE_DIVIDE(twjf_skipped_mins + twjf_input_mins_passed - tw_output_time_mins,
                            (twjf_skipped_mins + twjf_input_mins_passed)), 2) 
                                                        AS total_dropped_perc
    FROM summary_tb
    WHERE flight_month_bin IS NOT NULL
ORDER BY flight_month_bin DESC