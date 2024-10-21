-- targeting flights with takeoff_datetime on '2024-04-24'
-- find all flights for an airline with a non-null flight_id originating on the target day
-- pull extra data (needing pruning downstream), but guaranteeing capture of null flight_id values needing imputing

WITH candidate_flights_tb AS
         (SELECT timestamp, flight_id, icao_address
          FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
          WHERE airline_iata = @airline
            AND TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day_before, @target_day)
            AND flight_id IS NOT NULL),
     ranked_candidate_flights_tb AS
         (SELECT ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY timestamp ASC) as row_number, *
          FROM candidate_flights_tb),
     target_flight_id_tb AS
         (SELECT flight_id, icao_address
          FROM ranked_candidate_flights_tb
          WHERE row_number = 1
            AND TIMESTAMP_TRUNC(timestamp, DAY) = @target_day)

SELECT *
FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
WHERE (flight_id IN (SELECT flight_id FROM target_flight_id_tb) AND
       TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day, @target_day_after))
   OR (icao_address IN (SELECT icao_address FROM target_flight_id_tb) AND flight_id IS NULL AND
       TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day, @target_day_after))
ORDER BY icao_address, flight_id, timestamp ASC;