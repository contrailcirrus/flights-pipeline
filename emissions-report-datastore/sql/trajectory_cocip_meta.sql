create table "trajectory-cocip-meta"
(
    _processed_at    bigint,
    total_fuel_burn_kg      smallint,
    pycontrails_ver  text,
    perf_model_id    text,
    nvpm_data_source text,
    git_sha          text,
    zarr_uri         text,
    flight_id        text not null
        constraint flight_id_fk
            references "trajectory-cocip",
    total_pos_ef_persistent_contrail_length_km smallint,
    total_persistent_contrail_length_km smallint
);

alter table "trajectory-cocip-meta" owner to postgres;
grant select on "trajectory-cocip-meta" to internal_user_ro;
grant delete, insert, select, update on "trajectory-cocip-meta" to internal_user_rw;

