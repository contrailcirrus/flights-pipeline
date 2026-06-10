WITH fid_match_tb AS
         (SELECT timestamp, icao_address
          FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
          WHERE flight_id IN UNNEST(@flight_id)
            AND TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day, @target_day_after)),
     candidate_tb AS (SELECT *
                      FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
                      WHERE icao_address IN (SELECT DISTINCT icao_address FROM fid_match_tb)
                        AND TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day, @target_day_after))
SELECT *
FROM candidate_tb
WHERE timestamp <= (SELECT MAX(timestamp) FROM fid_match_tb)
  AND timestamp >= (SELECT MIN(timestamp) FROM fid_match_tb)
ORDER BY timestamp ASC
