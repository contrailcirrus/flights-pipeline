create table "trajectory-cocip"
(
    chunk_len_km            double precision,
    lat_start               double precision,
    lon_start               double precision,
    lat_end                 double precision,
    lon_end                 double precision,
    time_start              timestamp,
    time_end                timestamp,
    sum_ef_mj               bigint,
    total_fuel_burn_kg      bigint,
    aircraft_type_icao      text,
    engine_uid              text,
    mean_aircraft_mass_kg   double precision,
    mean_overall_efficiency double precision,
    icao_address            text,
    flight_id               text not null
        constraint "trajectory-cocip_pk"
            primary key,
    callsign                text,
    tail_number             text,
    flight_number           text,
    airline_iata            text,
    departure_airport_icao  text,
    arrival_airport_icao    text
);

alter table "trajectory-cocip"
    owner to postgres;

create index index_time_start_time_end
    on "trajectory-cocip" (time_start, time_end);

grant delete, insert, select, update on "trajectory-cocip" to internal_user_rw;

grant select on "trajectory-cocip" to internal_user_ro;

