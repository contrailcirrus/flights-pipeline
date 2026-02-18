-- generate a list of all non-null airline iatas with waypoints above 20k feet
-- this list will be fed into the cli to generate TWJDs
-- note that null airline iata will be run separately from this large list of target iatas
WITH airline_iata_rank_tb AS (SELECT airline_iata, COUNT(*) AS wp_cnt
                              FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
                              WHERE timestamp BETWEEN "2024-01-01" AND "2024-12-31"
                                AND altitude_baro > 20000
                                AND airline_iata IS NOT NULL
                              GROUP BY airline_iata
                              ORDER BY wp_cnt DESC)
SELECT airline_iata
from airline_iata_rank_tb