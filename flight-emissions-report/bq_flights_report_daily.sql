-- fetch most recently processed trajectory for a given flight_id, for a given airline, on a given day

WITH
candidate_flights_tb AS
  (SELECT * FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
  WHERE source_id="flightsreport"
  AND airline_iata=@airline
  AND timestamp_trunc(time_start, DAY) >= @day_start
  AND timestamp_trunc(time_start, DAY) <= @day_end
  ),
ranked_candidate_flights_tb AS
  (SELECT ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY _processed_at DESC) as row_number, * FROM candidate_flights_tb)

SELECT * FROM ranked_candidate_flights_tb WHERE row_number=1 ORDER BY time_start ASC;