-- Append-only staging table for inventory_monthly_impact_histogram.
--
-- main.py COPYs each parquet file's pre-aggregated histogram rows in here (fast, no
-- conflict resolution needed), then runs a single GROUP BY + upsert merge into
-- inventory_monthly_impact_histogram once at the end of the run, instead of doing an
-- upsert per file. See bq-to-postgres-util/README.md for the merge step.
CREATE TABLE inventory_monthly_impact_histogram_staging (
    airline_iata          TEXT NOT NULL,
    month                 DATE NOT NULL,
    is_eu_mrv             BOOLEAN,
    bin_idx               INTEGER NOT NULL,
    lower_ef_mj           DOUBLE PRECISION,
    upper_ef_mj           DOUBLE PRECISION,
    flight_count          INTEGER,
    total_sum_ef_mj       DOUBLE PRECISION
);

ALTER TABLE inventory_monthly_impact_histogram_staging OWNER TO postgres;
GRANT DELETE, INSERT, SELECT ON inventory_monthly_impact_histogram_staging TO internal_user_rw;
