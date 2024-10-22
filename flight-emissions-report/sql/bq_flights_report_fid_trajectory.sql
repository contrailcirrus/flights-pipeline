-- fetch full trajectory (per-seg values) for a given flight_id
-- flight w. flight_id must exist in range day_start -> day_end

WITH candidate_flights_tb AS
         (SELECT FORMAT("%s_%s", flight_id, FORMAT_TIMESTAMP("%s", time_start)) AS seg_id, *
          FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
          WHERE source_id = "flightsreport_full"
            AND flight_id IN (@flight_ids)
            AND timestamp_trunc(time_start, DAY) >= @day_start
            AND timestamp_trunc(time_start, DAY) <= @day_end
            AND zarr_uri LIKE ANY UNNEST(@met_src_str_match)
            AND seg_cnt = 1),
     ranked_candidate_flights_tb AS
         (SELECT ROW_NUMBER() OVER (PARTITION BY seg_id ORDER BY _processed_at DESC) as row_number, *
          FROM candidate_flights_tb
          QUALIFY row_number = 1),
     rcf_augmented_tb AS (SELECT * EXCEPT (row_number),
                                 ST_INTERSECTS(ST_GEOGPOINT(lon_start, lat_start),
                                               ST_GEOGFROMTEXT(@conus_wkt)) AS in_conus,
                                 ((time_start_sunrise_offset_mins <= 0) AND
                                  (time_start_sunset_offset_mins <= 3 * 60)) OR
                                 ((0 < time_start_sunrise_offset_mins) AND (time_start_sunset_offset_mins < 0)) OR
                                 ((-3 * 60 <= time_start_sunrise_offset_mins) AND
                                  (0 <= time_start_sunset_offset_mins))     AS is_nighttime
                          FROM ranked_candidate_flights_tb)
SELECT *,
       IF(is_nighttime, sum_ef_mj, 0)                                         AS nighttime_sum_ef_mj,
       IF(IFNULL(is_nighttime, TRUE), 0, sum_ef_mj)                           AS daytime_sum_ef_mj,
       IF(is_nighttime, chunk_len_km, 0)                                      AS nighttime_dist_km,
       IF(IFNULL(is_nighttime, TRUE), 0, chunk_len_km)                        AS daytime_dist_km,
       IF(is_nighttime, total_persistent_contrail_length_km, 0)               AS nighttime_contrail_dist_km,
       IF(IFNULL(is_nighttime, TRUE), 0, total_persistent_contrail_length_km) AS daytime_contrail_dist_km,
       IF(is_nighttime, total_pos_ef_persistent_contrail_length_km, 0)        AS nighttime_warming_contrail_dist_km,
       IF(IFNULL(is_nighttime, TRUE), 0,
          total_pos_ef_persistent_contrail_length_km)                         AS daytime_warming_contrail_dist_km,
       IF(in_conus, chunk_len_km, 0)                                          AS in_conus_dist_km,
       IF(in_conus, sum_ef_mj, 0)                                             AS in_conus_sum_ef_mj,
       IF(in_conus, total_persistent_contrail_length_km, 0)                   AS in_conus_contrail_dist_km,
       IF(in_conus, total_pos_ef_persistent_contrail_length_km, 0)            AS in_conus_warming_contrail_dist_km,
       IF(in_conus, 0, chunk_len_km)                                          AS out_conus_dist_km,
       IF(in_conus, 0, sum_ef_mj)                                             AS out_conus_sum_ef_mj,
       IF(in_conus, 0, total_persistent_contrail_length_km)                   AS out_conus_contrail_dist_km,
       IF(in_conus, 0, total_pos_ef_persistent_contrail_length_km)            AS out_conus_warming_contrail_dist_km,

FROM rcf_augmented_tb
ORDER BY time_start ASC;
