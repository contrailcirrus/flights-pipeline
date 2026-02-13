DECLARE export_start_time TIMESTAMP DEFAULT TIMESTAMP("<export_start_time goes here>");
DECLARE export_end_time TIMESTAMP DEFAULT TIMESTAMP("<export_end_time goes here>");

EXPORT DATA OPTIONS (
uri ="<URL pattern goes here>",
format ='PARQUET',
overwrite = false) AS

-- Use a Common Table Expression to compute metrics from single segments
WITH segment_metrics AS (
  SELECT
    flight_id,
    SUM(CASE WHEN sum_ef_mj != 0 THEN chunk_len_km ELSE 0 END) AS contrail_generating_kms
  FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
  WHERE time_start BETWEEN export_start_time AND export_end_time
    AND seg_cnt = 1
  GROUP BY
    flight_id
)

SELECT main.chunk_len_km,
       main.lat_start,
       main.lon_start,
       main.lat_end,
       main.lon_end,
       main.time_start,
       main.time_end,
       main.sum_ef_mj,
       main.aircraft_type_icao,
       main.engine_uid,
       main.mean_aircraft_mass_kg,
       main.mean_overall_efficiency,
       main.icao_address,
       main.flight_id,
       main.callsign,
       main.tail_number,
       main.flight_number,
       main.airline_iata,
       main.departure_airport_icao,
       main.arrival_airport_icao,
       main._processed_at,
       main.total_fuel_burn_kg,
       main.pycontrails_ver,
       main.perf_model_id,
       main.nvpm_data_source,
       main.git_sha,
       main.zarr_uri,
       main.total_pos_ef_persistent_contrail_length_km,
       main.total_persistent_contrail_length_km,
       sm.contrail_generating_kms
FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod` AS main
LEFT JOIN segment_metrics AS sm
  ON main.flight_id = sm.flight_id
WHERE main.time_start BETWEEN export_start_time AND export_end_time
  AND main.seg_cnt > 1
  AND main.airline_iata IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY _processed_at DESC) = 1;