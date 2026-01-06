create table "trajectory-cocip-meta"
(
    _processed_at    bigint,
    seg_cnt          bigint,
    pycontrails_ver  text,
    perf_model_id    text,
    nvpm_data_source text,
    git_sha          text,
    zarr_uri         text,
    flight_id        text not null
        constraint flight_id_fk
            references "trajectory-cocip",
    total_pos_ef_persistent_contrail_length_km double precision,
    total_persistent_contrail_length_km double precision
);

alter table "trajectory-cocip-meta"
    owner to postgres;

grant select on "trajectory-cocip-meta" to internal_user_ro;

grant delete, insert, select, update on "trajectory-cocip-meta" to internal_user_rw;

