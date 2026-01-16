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
);

alter table "trajectory-cocip" owner to postgres;

CREATE index index_time_start_time_end
    ON "trajectory-cocip" (time_start, time_end);
CREATE INDEX idx_ef_time_start
    ON "trajectory-cocip" (sum_ef_mj DESC, time_start);
CREATE INDEX idx_ef_per_km_time_start
    ON "trajectory-cocip" (ef_mj_per_km DESC, time_start);

grant delete, insert, select, update on "trajectory-cocip" to internal_user_rw;

grant select on "trajectory-cocip" to internal_user_ro;

