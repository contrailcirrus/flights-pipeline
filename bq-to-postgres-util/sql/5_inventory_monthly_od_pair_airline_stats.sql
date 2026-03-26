CREATE MATERIALIZED VIEW inventory_monthly_od_pair_airline_stats AS
SELECT
    date_trunc('month', time_start) as month_bucket,
    -- Distinct airlines from 2024: 478
    airline_iata,
    arrival_airport_icao,
    arrival_country_iso,
    arrival_continent_iso,
    departure_airport_icao,
    departure_country_iso,
    departure_continent_iso,
    is_eu_mrv,
    aircraft_type_icao,
    COUNT(*) as flight_cnt,
    SUM(sum_ef_mj) as total_ef_mj,
    SUM(chunk_len_km) as total_len_km,
    SUM(contrail_generating_kms) as total_contrail_generating_km
    SUM(warming_contrail_generating_kms) as total_warming_contrail_generating_km
FROM "trajectory-cocip"
GROUP BY (
    month_bucket,
    airline_iata,
    is_eu_mrv,
    arrival_airport_icao,
    arrival_country_iso,
    arrival_continent_iso,
    departure_airport_icao,
    departure_country_iso,
    departure_continent_iso,
    aircraft_type_icao
);

-- Create an index for instant access from the FER endpoints.
CREATE INDEX idx_mv_od_path_base_time ON inventory_monthly_od_pair_airline_stats (
    is_eu_mrv,
    month_bucket
) INCLUDE (
    airline_iata,
    aircraft_type_icao,
    departure_airport_icao,
    arrival_airport_icao,
    departure_country_iso,
    departure_continent_iso,
    arrival_country_iso,
    arrival_continent_iso,
    flight_cnt,
    total_ef_mj,
    total_len_km
)
WHERE arrival_airport_icao IS NOT NULL
  AND arrival_airport_icao != 'None'
  AND departure_airport_icao IS NOT NULL
  AND departure_airport_icao != 'None';

CREATE INDEX idx_mv_od_path_operator ON inventory_monthly_od_pair_airline_stats (
    airline_iata,
    is_eu_mrv,
    month_bucket
) INCLUDE (
    departure_airport_icao,
    arrival_airport_icao,
    departure_country_iso,
    departure_continent_iso,
    arrival_country_iso,
    arrival_continent_iso,
    flight_cnt,
    total_ef_mj,
    total_len_km
)
WHERE arrival_airport_icao IS NOT NULL
  AND arrival_airport_icao != 'None'
  AND departure_airport_icao IS NOT NULL
  AND departure_airport_icao != 'None';

ALTER TABLE inventory_monthly_od_pair_airline_stats OWNER TO postgres;
GRANT DELETE, INSERT, SELECT, UPDATE ON inventory_monthly_od_pair_airline_stats TO internal_user_rw;
GRANT SELECT ON inventory_monthly_od_pair_airline_stats TO internal_user_ro;