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

ALTER TABLE inventory_monthly_stats OWNER TO postgres;
GRANT DELETE, INSERT, SELECT, UPDATE ON inventory_monthly_stats TO internal_user_rw;
GRANT SELECT ON inventory_monthly_stats TO internal_user_ro;