-- A comparison of the flights-pipeline output with Roger's GAIA analysis

-- Set date range
DECLARE date_range_start TIMESTAMP DEFAULT '2024-01-01T00:00:00';
DECLARE date_range_end TIMESTAMP DEFAULT '2024-12-31T11:59:59';

-- Set the project and dataset for the GAIA summary table

WITH gaia_table AS (SELECT * FROM `contrails-301217.flights_pipeline_prod.gaia_jeta_lowvpn_2024_summary`),
 inventory_table AS (SELECT * FROM `contrails-301217.flights_pipeline_prod.inventory_2024_run_feb2026_summary`),

inventory_tb AS (SELECT SUM(TIMESTAMP_DIFF(time_end, time_start, MINUTE)) AS total_flight_time_mins,
                        TIMESTAMP_TRUNC(time_start, MONTH)           AS flight_month_bin,
                        SUM(sum_ef_mj)                               AS ef_mj_month_bin,
                        COUNT(DISTINCT(flight_id))                   AS counts_month_bin
                 FROM inventory_table
                 WHERE time_start >= date_range_start
                   AND time_start <= date_range_end
                 GROUP BY flight_month_bin
                 ORDER BY flight_month_bin desc),

     gaia_inventory_tb AS (SELECT TIMESTAMP_TRUNC(takeoff_time_utc, MONTH) AS flight_month_bin,
                              SUM(duration_hours) * 60.0              AS total_flight_time_mins,
                              SUM(ef_sum)/1000000.0                   AS ef_mj_month_bin,
                              COUNT(DISTINCT(flight_id))              AS counts_month_bin
                       FROM gaia_table
                       WHERE takeoff_time_utc >= date_range_start
                         AND takeoff_time_utc <= date_range_end
                       GROUP BY flight_month_bin
                       ORDER BY flight_month_bin DESC),

     summary_tb
         AS (SELECT COALESCE(inventory_tb.flight_month_bin, gaia_inventory_tb.flight_month_bin) AS flight_month_bin,
                    COALESCE(inventory_tb.total_flight_time_mins, 0)                       AS summary_flight_time_minutes,
                    COALESCE(gaia_inventory_tb.total_flight_time_mins, 0)                  AS gaia_total_flight_time,
                    COALESCE(inventory_tb.ef_mj_month_bin, 0)                              AS summary_ef_mj_month_bin,
                    COALESCE(gaia_inventory_tb.ef_mj_month_bin, 0)                         AS gaia_ef_mj_month_bin,
                    COALESCE(inventory_tb.counts_month_bin, 0)                             AS summary_counts_month_bin,
                    COALESCE(gaia_inventory_tb.counts_month_bin, 0)                        AS gaia_counts_month_bin
             FROM inventory_tb
                      FULL JOIN gaia_inventory_tb ON inventory_tb.flight_month_bin = gaia_inventory_tb.flight_month_bin)

SELECT *
        ,
       summary_flight_time_minutes / gaia_total_flight_time AS flight_time_ratio,
       summary_ef_mj_month_bin / gaia_ef_mj_month_bin AS ef_mj_ratio,
       summary_counts_month_bin / gaia_counts_month_bin AS counts_ratio

FROM summary_tb
WHERE flight_month_bin IS NOT NULL
ORDER BY flight_month_bin ASC