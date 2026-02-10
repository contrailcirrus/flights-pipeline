CREATE MATERIALIZED VIEW inventory_monthly_od_pair_airline_stats AS
SELECT
    date_trunc('month', time_start) as month_bucket,
    -- Distinct airlines from 2024: 478
    airline_iata,
    arrival_airport_icao,
    departure_airport_icao,
    is_eu_mrv,
    aircraft_type_icao,
    COUNT(*) as flight_cnt,
    SUM(sum_ef_mj) as total_ef_mj,
    SUM(chunk_len_km) as total_len_km
FROM "trajectory-cocip"
GROUP BY month_bucket, airline_iata, is_eu_mrv, arrival_airport_icao, departure_airport_icao, aircraft_type_icao;

-- Create an index for instant access from the FER endpoints.
CREATE UNIQUE INDEX idx_mv_monthly_od_pair_airline_stats ON inventory_monthly_od_pair_airline_stats (
    airline_iata,
    month_bucket,
    arrival_airport_icao,
    departure_airport_icao,
    is_eu_mrv,
    aircraft_type_icao
) INCLUDE (
    flight_cnt,
    total_ef_mj,
    total_len_km
);

ALTER TABLE inventory_monthly_od_pair_airline_stats OWNER TO postgres;
GRANT DELETE, INSERT, SELECT, UPDATE ON inventory_monthly_od_pair_airline_stats TO internal_user_rw;
GRANT SELECT ON inventory_monthly_od_pair_airline_stats TO internal_user_ro;