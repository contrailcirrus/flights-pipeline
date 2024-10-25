WITH base_tb AS (SELECT FORMAT("%s_%s", flight_id, FORMAT_TIMESTAMP("%s", time_start)) AS seg_id, *
                 FROM flights_pipeline_prod.trajectory_cocip_prod
                 WHERE airline_iata IN UNNEST(@airline_iata_lst)
                   AND TIMESTAMP_TRUNC(time_start, DAY) = @date_str
                   AND zarr_uri LIKE "HRES/%"
                   AND seg_cnt > 1),
     dedupe_tb AS (SELECT ROW_NUMBER() OVER (PARTITION BY seg_id ORDER BY _processed_at DESC) AS rn, *
                   FROM base_tb
                   QUALIFY rn = 1)
SELECT * EXCEPT (seg_id, rn)
FROM dedupe_tb
