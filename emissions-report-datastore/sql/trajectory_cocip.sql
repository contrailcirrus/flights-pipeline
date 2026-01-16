create table "trajectory-cocip"
(
    chunk_len_km            smallint,
    lat_start               real,
    lon_start               real,
    lat_end                 real,
    lon_end                 real,
    time_start              timestamp,
    time_end                timestamp,
    sum_ef_mj               bigint,
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

    ef_mj_per_km double precision GENERATED ALWAYS AS (
        CASE WHEN chunk_len_km = 0 THEN NULL ELSE sum_ef_mj::double precision / chunk_len_km END
    ) STORED,
    duration_mins smallint GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (time_end - time_start)) / 60) STORED,
);

CREATE INDEX idx_ef_desc
    ON "trajectory-cocip" (sum_ef_mj DESC, time_start);
CREATE INDEX idx_ef_per_km_desc
    ON "trajectory-cocip" (ef_mj_per_km DESC, time_start);
CREATE INDEX idx_duration_mins
    ON "trajectory-cocip" (duration_mins);
CREATE INDEX index_time_start_time_end
    ON "trajectory-cocip" (time_start, time_end);
CREATE INDEX idx_airline_time_start_ef
    ON "trajectory-cocip" (airline_iata, sum_ef_mj DESC, time_start);
CREATE INDEX idx_airline_time_start_ef_per_km
    ON "trajectory-cocip" (airline_iata, ef_mj_per_km DESC, time_start);

alter table "trajectory-cocip" owner to postgres;
grant delete, insert, select, update on "trajectory-cocip" to internal_user_rw;
grant select on "trajectory-cocip" to internal_user_ro;

