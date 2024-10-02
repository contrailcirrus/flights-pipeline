-- fetch most recently processed trajectory for a given flight_id, for a given airline, on a given day
WITH base_tb AS (SELECT *
                 FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
                 WHERE source_id = "flightsreport_full"
                   AND airline_iata = @airline
                   AND timestamp_trunc(time_start, DAY) >= @day_start
                   AND timestamp_trunc(time_start, DAY) <= @day_end),
     candidate_flights_tb AS
         (SELECT *
          FROM base_tb
          WHERE seg_cnt > 1),
     candidate_segments_tb AS
         (SELECT *,
                 ((time_start_sunrise_offset_mins <= 0) AND (time_start_sunset_offset_mins <= 3 * 60)) OR
                 ((0 < time_start_sunrise_offset_mins) AND (time_start_sunset_offset_mins < 0)) OR
                 ((-3 * 60 <= time_start_sunrise_offset_mins) AND (0 <= time_start_sunset_offset_mins)) AS is_nighttime
          FROM base_tb
          WHERE seg_cnt = 1),
     ranked_candidate_flights_tb AS
         (SELECT ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY _processed_at DESC) as row_number, *
          FROM candidate_flights_tb),
     summary_flights_tb AS
         (SELECT * FROM ranked_candidate_flights_tb WHERE row_number = 1 ORDER BY time_start ASC),
     nighttime_agg_tb AS (SELECT flight_id,
                                 is_nighttime,
                                 SUM(chunk_len_km)                               AS dist_km,
                                 SUM(sum_ef_mj)                                  AS sum_ef_mj,
                                 SUM(total_persistent_contrail_length_km)        AS contrail_dist_km,
                                 SUM(total_pos_ef_persistent_contrail_length_km) AS warming_contrail_dist_km
                          FROM candidate_segments_tb
                          WHERE is_nighttime IS NOT NULL
                          GROUP BY flight_id, is_nighttime
                          ORDER BY flight_id),
     flat_nighttime_agg_tb AS (SELECT COALESCE(nt_tb.flight_id, dt_tb.flight_id) AS flight_id,
                                      nighttime_dist_km,
                                      nighttime_sum_ef_mj,
                                      nighttime_contrail_dist_km,
                                      nighttime_warming_contrail_dist_km,
                                      daytime_dist_km,
                                      daytime_sum_ef_mj,
                                      daytime_contrail_dist_km,
                                      daytime_warming_contrail_dist_km,
                               FROM (SELECT flight_id,
                                            dist_km                  AS nighttime_dist_km,
                                            sum_ef_mj                AS nighttime_sum_ef_mj,
                                            contrail_dist_km         AS nighttime_contrail_dist_km,
                                            warming_contrail_dist_km AS nighttime_warming_contrail_dist_km,
                                     FROM nighttime_agg_tb
                                     WHERE is_nighttime IS TRUE) nt_tb
                                        FULL OUTER JOIN
                                    (SELECT flight_id,
                                            dist_km                  AS daytime_dist_km,
                                            sum_ef_mj                AS daytime_sum_ef_mj,
                                            contrail_dist_km         AS daytime_contrail_dist_km,
                                            warming_contrail_dist_km AS daytime_warming_contrail_dist_km,
                                     FROM nighttime_agg_tb
                                     WHERE is_nighttime IS FALSE) dt_tb ON nt_tb.flight_id = dt_tb.flight_id)
SELECT *
FROM summary_flights_tb sf_tb
         LEFT JOIN flat_nighttime_agg_tb fna_tb ON sf_tb.flight_id = fna_tb.flight_id