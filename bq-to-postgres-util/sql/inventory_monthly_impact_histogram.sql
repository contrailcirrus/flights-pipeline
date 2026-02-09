CREATE TABLE inventory_monthly_impact_histogram (
    airline_iata          TEXT NOT NULL,
    month                 DATE NOT NULL,
    bin_idx               INTEGER NOT NULL, -- The numerical bin ID to easily group multiple months
    lower_ef_mj           DOUBLE PRECISION, -- The lower inclusive range of the bin
    upper_ef_mj           DOUBLE PRECISION, -- The upper exclusive range of the bin
    flight_count          INTEGER,          -- The number of flights in this bin
    total_sum_ef_mj       DOUBLE PRECISION, -- Sum of energy forcing (MJ) of the flights in this bin

    PRIMARY KEY (airline_iata, month, bin_idx)
);

CREATE INDEX idx_histo_lookup ON inventory_monthly_impact_histogram (airline_iata, month);

ALTER TABLE inventory_monthly_impact_histogram owner TO postgres;
GRANT DELETE, INSERT, SELECT, UPDATE ON inventory_monthly_impact_histogram TO internal_user_rw;
GRANT SELECT ON inventory_monthly_impact_histogram TO internal_user_ro;