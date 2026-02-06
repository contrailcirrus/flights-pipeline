CREATE TYPE flight_length_bucket_enum AS ENUM (
    'short_flight',
    'long_flight'
);

CREATE TYPE co2e_bucket_enum AS ENUM (
    'no_impact',
    'low_impact',
    'medium_impact',
    'high_impact'
);

CREATE TABLE "trajectory-cocip"
(
    chunk_len_km            smallint,
    lat_start               real,
    lon_start               real,
    lat_end                 real,
    lon_end                 real,
    time_start              timestamp without time zone not null,
    time_end                timestamp without time zone,
    sum_ef_mj               bigint,
    ef_mj_per_km            double precision,
    aircraft_type_icao      text,
    engine_uid              text,
    mean_aircraft_mass_kg   integer,
    mean_overall_efficiency real,
    icao_address            text,
    flight_id               text not null,
    callsign                text,
    tail_number             text,
    flight_number           text,
    airline_iata            text,
    departure_airport_icao  text,
    arrival_airport_icao    text,

    flight_length_bucket    flight_length_bucket_enum,
    co2e_kg_bucket          co2e_bucket_enum,
    co2e_kg_per_km_bucket   co2e_bucket_enum,

    -- Must include time_start for partitioning
    CONSTRAINT "trajectory-cocip_pk" PRIMARY KEY (flight_id, time_start)
) PARTITION BY RANGE (time_start);

-- Given that filters are optional any combination of them can be provided making standard B-Tree indices useless.
-- Using a GIN index which efficiently computes intersections of any filter combinations.
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE INDEX idx_trajectory_filters_gin
    ON "trajectory-cocip"
    USING GIN (
        time_start,
        airline_iata,
        aircraft_type_icao,
        engine_uid,
        flight_length_bucket,
        co2e_kg_bucket,
        co2e_kg_per_km_bucket,
        departure_airport_icao,
        arrival_airport_icao
    );

-- Add indices for sort options (and add time_start for deterministic sorting on equal values).
CREATE INDEX idx_sort_total_impact
    ON "trajectory-cocip" (sum_ef_mj DESC, time_start DESC);
CREATE INDEX idx_sort_per_km_impact
    ON "trajectory-cocip" (ef_mj_per_km DESC, time_start DESC);
CREATE INDEX idx_sort_time
    ON "trajectory-cocip" (time_start DESC, time_end DESC);

-- Create indices that include aggregation data for faster lookups.
CREATE INDEX idx_arr_sort_time ON "trajectory-cocip" (arrival_airport_icao, time_start DESC);
CREATE INDEX idx_dep_sort_time ON "trajectory-cocip" (departure_airport_icao, time_start DESC);

CREATE INDEX idx_dep_sort_impact ON "trajectory-cocip" (departure_airport_icao, sum_ef_mj DESC, time_start DESC);
CREATE INDEX idx_arr_sort_impact ON "trajectory-cocip" (arrival_airport_icao, sum_ef_mj DESC, time_start DESC);

CREATE INDEX idx_dep_sort_intensity ON "trajectory-cocip" (departure_airport_icao, ef_mj_per_km DESC, time_start DESC);
CREATE INDEX idx_arr_sort_intensity ON "trajectory-cocip" (arrival_airport_icao, ef_mj_per_km DESC, time_start DESC);

CREATE INDEX idx_airline_flight_length_sort_impact
    ON "trajectory-cocip" (airline_iata, flight_length_bucket, sum_ef_mj DESC, time_start DESC);
CREATE INDEX idx_flight_length_sort_impact
    ON "trajectory-cocip" (flight_length_bucket, sum_ef_mj DESC, time_start DESC);

alter table "trajectory-cocip" owner to postgres;
grant delete, insert, select, update on "trajectory-cocip" to internal_user_rw;
grant select on "trajectory-cocip" to internal_user_ro;

