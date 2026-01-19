CREATE MATERIALIZED VIEW inventory_monthly_airlines_stats AS
SELECT
    date_trunc('month', time_start) as month_bucket,
    -- Distinct airlines from 2024: 478
    airline_iata,
    -- Disting aircraft types from 2024: 58
    aircraft_type_icao,
    COUNT(*) as flight_cnt,
    SUM(sum_ef_mj) as total_ef_mj,
    SUM(chunk_len_km) as total_len_km
FROM "trajectory-cocip"
GROUP BY month_bucket, airline_iata, aircraft_type_icao;

-- Create an index for instant access from the FER endpoints (filters before ranges).
CREATE INDEX idx_mv_monthly_airline_stats
ON inventory_monthly_airlines_stats (airline_iata, aircraft_type_icao, month_bucket);

ALTER TABLE inventory_monthly_airlines_stats OWNER TO postgres;
GRANT DELETE, INSERT, SELECT, UPDATE ON inventory_monthly_airlines_stats TO internal_user_rw;
GRANT SELECT ON inventory_monthly_airlines_stats TO internal_user_ro;