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
    time_start              timestamp without time zone,
    time_end                timestamp without time zone,
    sum_ef_mj               bigint,
    ef_mj_per_km            double precision,
    aircraft_type_icao      text,
    engine_uid              text,
    mean_aircraft_mass_kg   integer,
    mean_overall_efficiency real,
    icao_address            text,
    flight_id               text not null
        constraint "trajectory-cocip_pk"
            primary key,
    callsign                text,
    tail_number             text,
    flight_number           text,
    airline_iata            text,
    departure_airport_icao  text,
    arrival_airport_icao    text,

    flight_length_bucket    flight_length_bucket_enum,
    co2e_kg_bucket          co2e_bucket_enum,
    co2e_kg_per_km_bucket   co2e_bucket_enum
);

-- Given that filters are optional any combination of them can be provided making standard B-Tree indices useless.
-- Using a GIN index which efficiently computes intersections of any filter combinations.
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE INDEX idx_trajectory_filters_gin
    ON "trajectory-cocip"
    USING GIN (
        airline_iata,
        aircraft_type_icao,
        engine_uid,
        flight_len_bucket,
        co2e_impact_bucket,
        co2e_intensity_bucket,
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
CREATE INDEX idx_arrival_time_covering
    ON "trajectory-cocip" (arrival_airport_icao, time_start)
    INCLUDE (sum_ef_mj, chunk_len_km);
CREATE INDEX idx_departure_time_covering
    ON "trajectory-cocip" (departure_airport_icao, time_start)
    INCLUDE (sum_ef_mj, chunk_len_km);

alter table "trajectory-cocip" owner to postgres;
grant delete, insert, select, update on "trajectory-cocip" to internal_user_rw;
grant select on "trajectory-cocip" to internal_user_ro;

