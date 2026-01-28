CREATE MATERIALIZED VIEW inventory_monthly_airlines_stats AS
SELECT
    date_trunc('month', time_start) as month_bucket,
    -- Distinct airlines from 2024: 478
    airline_iata,
    -- Distinct aircraft types from 2024: 58
    aircraft_type_icao,
    -- Distinct engines from 2024: 54
    engine_uid,
    -- Distinct flight lengths: 2
    flight_length_bucket,
    -- Distinct flight lengths: 4
    co2e_kg_bucket,
    -- Distinct flight lengths: 4
    co2e_kg_per_km_bucket,
    COUNT(*) as flight_cnt,
    SUM(sum_ef_mj) as total_ef_mj,
    SUM(chunk_len_km) as total_len_km
FROM "trajectory-cocip"
GROUP BY
    month_bucket,
    airline_iata,
    aircraft_type_icao,
    engine_uid,
    flight_length_bucket,
    co2e_kg_range,
    co2e_kg_per_km_range;


-- Given that filters are optional any combination of them can be provided making standard B-Tree indices useless.
-- Using a GIN index which efficiently computes intersections of any filter combinations.
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE INDEX idx_mv_filters_gin
    ON inventory_monthly_airlines_stats
    USING GIN (
        airline_iata,
        aircraft_type_icao,
        engine_uid,
        flight_len_bucket,
        co2e_impact_bucket,
        co2e_intensity_bucket
    );

-- Use a standard B-Tree for the range filter.
CREATE INDEX idx_mv_month_bucket
    ON inventory_monthly_airlines_stats (month_bucket);

ALTER TABLE inventory_monthly_airlines_stats OWNER TO postgres;
GRANT DELETE, INSERT, SELECT, UPDATE ON inventory_monthly_airlines_stats TO internal_user_rw;
GRANT SELECT ON inventory_monthly_airlines_stats TO internal_user_ro;