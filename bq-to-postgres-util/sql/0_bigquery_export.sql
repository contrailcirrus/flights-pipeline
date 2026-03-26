DECLARE export_start_time TIMESTAMP DEFAULT TIMESTAMP("<export_start_time goes here>");
DECLARE export_end_time TIMESTAMP DEFAULT TIMESTAMP("<export_end_time goes here>");

EXPORT DATA OPTIONS (
    uri = :output_gcs_uri,
    format ='PARQUET',
    overwrite = false) AS
    SELECT seg_cnt,
           chunk_len_km,
           lat_start,
           lon_start,
           lat_end,
           lon_end,
           time_start,
           time_end,
           sum_ef_mj,
           aircraft_type_icao,
           engine_uid,
           mean_aircraft_mass_kg,
           mean_overall_efficiency,
           icao_address,
           flight_id,
           callsign,
           tail_number,
           flight_number,
           airline_iata,
           departure_airport_icao,
           arrival_airport_icao,
           _processed_at,
           total_fuel_burn_kg,
           pycontrails_ver,
           perf_model_id,
           nvpm_data_source,
           git_sha,
           zarr_uri,
           total_pos_ef_persistent_contrail_length_km,
           total_persistent_contrail_length_km,
           total_persistent_contrail_length_km AS contrail_generating_kms,
    FROM :target_table
    WHERE
        seg_cnt > 1
        AND time_start BETWEEN export_start_time AND export_end_time;