# BQ to Postgres Util
This subdirectory holds tooling, references, guides/instructions and documentation 
relevant for the maintenance of the emissions report data tables (housed in a GCP Cloud SQL Postgres instance).

Bigquery is the source-of-truth destination for CoCiP outputs from the flights pipeline.

Those outputs are selectively mirrored/synced to a Postgres database,
those data in Postgres backing the public-facing data access to the flights pipeline outputs ("contrail impact inventory").

## Data Models
The per-flight trajectory-worker outputs live in the `contrails-default-<dev/prod>` 
postgres instances in Cloud SQL, in the `flights-pipeline-fer-cache` database.

The table definitions are stored in the `sql` directory.

Several materialized views are also built from these base tables.

### Table Overviews

#### `trajectory-cocip`
This is the table of primary significance, holding the per-flight CoCiP data, and those 
flight attributes necessary for filtering/searching for a flight.

#### `trajectory-cocip-meta`
This table is 1:1 with `trajectory-cocip`, and holds additional attributes for a given flight.

## Data Sync'ing
The source-of-truth for flight CoCiP data lives in BigQuery.
Those data sync'ed to the postgres instance originate in the BigQuery `flights_pipeline_prod.trajectory_cocip_prod`.

1. Export the BigQuery data into Parquet shards under the following URL pattern:
   `gs://contrails-301217-sandbox-internal/flights-pipeline/emissions-export/<target_date_range>/<process_time>/*.pq`
   - Where `target_date_range` is of format %Y(Q%N) where %Y is the full calendar year, and %N is the quarter. Q%N is
     optional. Valid entries include e.g. 2025 or 2025Q2.
   - Where `process_time` is the time at which the export was run. This is %Y%m%d, the date (utc) on which the export
     command was run against BQ
   - For the export range set the placeholders `export_start_time` (e.g. `2025-01-01T00:00:00`) and `export_end_time`
     (e.g. `2025-12-31T23:59:59`) in line with the desired `target_date_range` (e.g. `2025`) above.
   - This is the export SQL command to run from the BigQuery prod instance:
   ```
    EXPORT DATA OPTIONS (
    uri ="<URL pattern goes here>",
    format ='PARQUET',
    overwrite = false) AS
    SELECT chunk_len_km,
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
           total_persistent_contrail_length_km
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE time_start BETWEEN "<export_start_time goes here>" AND "<export_end_time goes here>"
      AND seg_cnt > 1
      AND airline_iata IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY _processed_at DESC) = 1;
   ```

2. Ensure that the Postgres tables and views are defined. Otherwise run these in the following order:
   1. `sql/trajectory_cocip.sql`, `sql/trajectory_cocip_meta.sql` and `sql/inventory_monthly_impact_histogram.sql`
   2. `sql/inventory_monthly_airlines_stats.sql`, `sql/inventory_monthly_od_pair_airline_stats.sql`
3. Run `main.py --gcs_paths=<path1,path2,...>` to export the Parquet shards to Postgres. If a different GCS bucket is used 
   in (1) change the default values here as well.
   - First login to gcloud to access cloud storage:
     - `gcloud auth login`
   - Load the pipenv:
     - `pip install -U pip; pip install pipenv; pipenv sync; pipenv shell`
   - Run the utility (example for 2024 and 2025Q1 data):
     ```
     ./main.py \
       --db_user "internal_user_rw" \
       --db_password "<password of Postgres user internal_user_rw>" \
       --db_host "34.23.237.52" \
       --gcs_paths "flights-pipeline/emissions-export/2024/20260112,flights-pipeline/emissions-export/2025Q1/20260112"
     ```
   - The DB utility ensures that the required monthly partition tables are correctly created.
     If a partition table needs to be created you have to use the following flags instead `--db_user "postgres" and --db_password "<pw of postgres user>"`
4. Update the materialized views by running the following sequence of SQL commands:
   1. `REFRESH MATERIALIZED VIEW inventory_monthly_airlines_stats;`
   2. `REFRESH MATERIALIZED VIEW inventory_monthly_od_pair_airline_stats;`


