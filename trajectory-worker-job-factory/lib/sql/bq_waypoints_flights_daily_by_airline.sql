-- targeting flights with takeoff_datetime on '{day}'
-- find all flights for an airline with a non-null flight_id originating on the target day
-- pull extra data (needing pruning downstream), but guaranteeing capture of null flight_id values needing imputing

WITH all_waypoints_tb AS (SELECT *
                          FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
                          WHERE
                              TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day_before, @target_day, @target_day_after)),
     flights_sub_tb AS (SELECT *
                        FROM all_waypoints_tb
                        WHERE IFNULL(airline_iata, 'null') = @airline),
     ranked_candidate_flights_tb AS
         (SELECT timestamp,
                 flight_id,
                 icao_address,
                 ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY timestamp ASC) as row_number
          FROM flights_sub_tb
          WHERE TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day_before, @target_day)
            AND flight_id IS NOT NULL),
     target_flight_id_tb AS
         (SELECT flight_id, icao_address
          FROM ranked_candidate_flights_tb
          WHERE row_number = 1
            AND TIMESTAMP_TRUNC(timestamp, DAY) = @target_day)

SELECT *
FROM all_waypoints_tb
WHERE (flight_id IN (SELECT flight_id FROM target_flight_id_tb) AND
       TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day, @target_day_after))
   OR (icao_address IN (SELECT icao_address FROM target_flight_id_tb) AND flight_id IS NULL AND
       TIMESTAMP_TRUNC(timestamp, DAY) IN (@target_day, @target_day_after))
ORDER BY icao_address, flight_id, timestamp ASC;