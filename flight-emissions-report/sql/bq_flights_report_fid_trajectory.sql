-- fetch full trajectory (per-seg values) for a given flight_id
-- flight w. flight_id must exist in range day_start -> day_end

WITH
candidate_flights_tb AS
  (SELECT * FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
  WHERE source_id="flightsreport_full"
  AND flight_id IN (@flight_ids)
  AND timestamp_trunc(time_start, DAY) >= @day_start
  AND timestamp_trunc(time_start, DAY) <= @day_end
  AND seg_cnt=1
  ),
conus_intersect_tb AS
  (SELECT _chunk_hash,
   ST_INTERSECTSBOX(ST_GEOGPOINT(lon_start, lat_start), @lng1, @lat1, @lng2, @lat2) AS in_conus
   FROM candidate_flights_tb),
ranked_candidate_flights_tb AS
  (SELECT ROW_NUMBER() OVER (PARTITION BY _chunk_hash ORDER BY _processed_at DESC) as row_number, * FROM candidate_flights_tb)

SELECT *
FROM ranked_candidate_flights_tb rcf_tb LEFT JOIN conus_intersect_tb ci_tb
ON rcf_tb._chunk_hash=ci_tb._chunk_hash
WHERE row_number=1
ORDER BY time_start ASC;