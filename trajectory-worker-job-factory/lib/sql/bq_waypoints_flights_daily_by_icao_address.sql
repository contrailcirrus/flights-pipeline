WITH candidate_waypoints_tb AS (SELECT *
                                FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
                                WHERE icao_address IN UNNEST(@icao_address)
                                  AND TIMESTAMP_TRUNC(timestamp, DAY) IN
                                      (@target_day_before, @target_day, @target_day_after)),
     candidate_fid_tb AS
         (SELECT MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts, flight_id
          FROM candidate_waypoints_tb
          GROUP BY flight_id),
     target_dt_range_tb AS (SELECT min_ts, max_ts
                            FROM candidate_fid_tb
                            WHERE TIMESTAMP_TRUNC(min_ts, DAY) = @target_day)
SELECT *
FROM candidate_waypoints_tb
WHERE timestamp BETWEEN (SELECT MIN(min_ts) FROM target_dt_range_tb) AND (SELECT MAX(max_ts) FROM target_dt_range_tb)
