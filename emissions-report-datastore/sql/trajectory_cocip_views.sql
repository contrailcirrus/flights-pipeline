CREATE MATERIALIZED VIEW inventory_monthly_airlines_stats AS
SELECT
    date_trunc('month', time_start) as month_bucket,
    -- Distinct airlines from 2024: 478
    airline_iata,
    COUNT(*) as flight_cnt,
    SUM(sum_ef_mj) as total_ef_mj,
    SUM(chunk_len_km) as total_len_km
FROM "trajectory-cocip"
GROUP BY month_bucket, airline_iata;

-- Create an index for instant access from the FER endpoints.
CREATE INDEX idx_mv_monthly_airline_stats ON inventory_monthly_airlines_stats (month_bucket, airline_iata);

CREATE MATERIALIZED VIEW inventory_monthly_stats AS
SELECT
    month_bucket,
    SUM(flight_cnt) as flight_cnt,
    SUM(total_ef_mj) as total_ef_mj,
    SUM(total_len_km) as total_len_km
FROM inventory_monthly_airlines_stats
GROUP BY month_bucket;

-- Create an index for instant access from the FER endpoints.
CREATE INDEX idx_mv_monthly_stats ON inventory_monthly_stats (month_bucket);
