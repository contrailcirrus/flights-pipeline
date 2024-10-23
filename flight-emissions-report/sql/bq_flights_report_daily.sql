-- fetch most recently processed trajectory for a given flight_id, for a given airline, on a given day
WITH base_tb AS (SELECT *
                 FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
                 WHERE source_id = "flightsreport"
                   AND airline_iata = @airline
                   AND zarr_uri LIKE ANY UNNEST(@met_src_str_match)
                   AND timestamp_trunc(time_start, DAY) >= @day_start
                   AND timestamp_trunc(time_start, DAY) <= @day_end),
     candidate_flights_tb AS
         (SELECT *
          FROM base_tb
          WHERE seg_cnt > 1),
     candidate_segments_tb AS
         (SELECT *,
                 FORMAT("%s_%s", flight_id, FORMAT_TIMESTAMP("%s", time_start))                         AS seg_id,
                 ((time_start_sunrise_offset_mins <= 0) AND (time_start_sunset_offset_mins <= 3 * 60)) OR
                 ((0 < time_start_sunrise_offset_mins) AND (time_start_sunset_offset_mins < 0)) OR
                 ((-3 * 60 <= time_start_sunrise_offset_mins) AND (0 <= time_start_sunset_offset_mins)) AS is_nighttime,
                 ST_INTERSECTS(ST_GEOGPOINT(lon_start, lat_start),
                               ST_GEOGFROMTEXT(@conus_wkt))                                             AS in_conus,
          FROM base_tb
          WHERE seg_cnt = 1),
     summary_segments_tb
         AS -- dedupe candidate segments; take first record by _processed_at on (flight_id, time_start) basis
         (SELECT *
          FROM candidate_segments_tb
          QUALIFY ROW_NUMBER() OVER (PARTITION BY seg_id ORDER BY _processed_at DESC) = 1),
     summary_flights_tb AS -- dedupe candidate flights; take first record by _processed_at on flight_id basis
         (SELECT *
          FROM candidate_flights_tb
          QUALIFY ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY _processed_at DESC) = 1
          ORDER BY time_start DESC),
     nighttime_agg_tb AS (SELECT flight_id,
                                 is_nighttime,
                                 SUM(chunk_len_km)                               AS dist_km,
                                 SUM(sum_ef_mj)                                  AS sum_ef_mj,
                                 SUM(total_persistent_contrail_length_km)        AS contrail_dist_km,
                                 SUM(total_pos_ef_persistent_contrail_length_km) AS warming_contrail_dist_km
                          FROM summary_segments_tb
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
                                     WHERE is_nighttime IS FALSE) dt_tb ON nt_tb.flight_id = dt_tb.flight_id),
     in_conus_agg_tb AS (SELECT flight_id,
                                in_conus,
                                SUM(chunk_len_km)                               AS dist_km,
                                SUM(sum_ef_mj)                                  AS sum_ef_mj,
                                SUM(total_persistent_contrail_length_km)        AS contrail_dist_km,
                                SUM(total_pos_ef_persistent_contrail_length_km) AS warming_contrail_dist_km
                         FROM summary_segments_tb
                         GROUP BY flight_id, in_conus
                         ORDER BY flight_id),
     flat_in_conus_agg_tb AS (SELECT COALESCE(in_tb.flight_id, out_tb.flight_id) AS flight_id,
                                     in_conus_dist_km,
                                     in_conus_sum_ef_mj,
                                     in_conus_contrail_dist_km,
                                     in_conus_warming_contrail_dist_km,
                                     out_conus_dist_km,
                                     out_conus_sum_ef_mj,
                                     out_conus_contrail_dist_km,
                                     out_conus_warming_contrail_dist_km,
                              FROM (SELECT flight_id,
                                           dist_km                  AS in_conus_dist_km,
                                           sum_ef_mj                AS in_conus_sum_ef_mj,
                                           contrail_dist_km         AS in_conus_contrail_dist_km,
                                           warming_contrail_dist_km AS in_conus_warming_contrail_dist_km
                                    FROM in_conus_agg_tb
                                    WHERE in_conus IS TRUE) in_tb
                                       FULL OUTER JOIN
                                   (SELECT flight_id,
                                           dist_km                  AS out_conus_dist_km,
                                           sum_ef_mj                AS out_conus_sum_ef_mj,
                                           contrail_dist_km         AS out_conus_contrail_dist_km,
                                           warming_contrail_dist_km AS out_conus_warming_contrail_dist_km
                                    FROM in_conus_agg_tb
                                    WHERE in_conus IS FALSE) out_tb ON in_tb.flight_id = out_tb.flight_id)
SELECT *
FROM summary_flights_tb sf_tb
         LEFT JOIN flat_nighttime_agg_tb fna_tb ON sf_tb.flight_id = fna_tb.flight_id
         LEFT JOIN flat_in_conus_agg_tb fica_tb ON sf_tb.flight_id = fica_tb.flight_id