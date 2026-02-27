create table "trajectory-cocip-meta"
(
    _processed_at       bigint,
    total_fuel_burn_kg  integer,
    pycontrails_ver     text,
    perf_model_id       text,
    nvpm_data_source    text,
    git_sha             text,
    zarr_uri            text,
    flight_id           text not null,
    time_start          timestamp without time zone not null,
    total_pos_ef_persistent_contrail_length_km smallint,
    total_persistent_contrail_length_km smallint,

    CONSTRAINT "trajectory-cocip-meta_pk" PRIMARY KEY (flight_id, time_start),

    CONSTRAINT flight_id_time_fk
        FOREIGN KEY (flight_id, time_start)
        REFERENCES "trajectory-cocip" (flight_id, time_start)
        ON DELETE CASCADE
) PARTITION BY RANGE (time_start);

alter table "trajectory-cocip-meta" owner to postgres;
grant select on "trajectory-cocip-meta" to internal_user_ro;
grant delete, insert, select, update on "trajectory-cocip-meta" to internal_user_rw;

