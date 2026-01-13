# Emissions Report Datastore
This subdirectory holds tooling, references, guides/instructions and documentation 
relevant for the maintenance of the emissions report data tables (housed in a GCP Cloud SQL Postgres instance).

## Data Models
The emissions report data (per-flight CoCiP outputs) live in the `contrails-default-<dev/prod>` 
postgres instances in Cloud SQL, in the `flights-pipeline-fer-cache` database.

The table definitions are stored in the `sql` directory.

Several materialized views are also built from these base tables.

### Table Overviews

#### `trajectory-cocip`
This is the table of primary significance, holding the per-flight emissions data, and those 
flight attributes necessary for filtering/searching for a flight.

#### `trajectory-cocip-meta`
This table is 1:1 with `trajectory-cocip`, and holds additional attributes for a given flight.

## Data Sync'ing
The source-of-truth for flight emissions data lives in BigQuery.
Those data sync'ed to the postgres instance originate in the BigQuery `flights_pipeline_prod.trajectory_cocip_prod`.

1. Export the BigQuery data into Parquet shards under the following URL pattern:
   `gs://contrails-301217-sandbox-internal/flights-pipeline/emissions-export/<target_daterange>/<process_time>/*.pq`
   - Where target_daterange is of format %Y(Q%N) where %Y is the full calendar year, and %N is the quarter. Q%N is
     optional. Valid entries include e.g. 2025 or 2025Q2.
   - Where process_time is the time at which the export was run. This is %Y%m%d, the date (utc) on which the export
     command was run against BQ

2. Ensure that the Postgres tables and views are defined. Otherwise run these in the following order:
   1. `sql/trajectory_cocip.sql` and `sql/trajectory_cocip_meta.sql`
   2. `sql/inventory_monthly_airlines_stats.sql`
   3. `sql/inventory_monthly_stats.sql`
3. Run `main.py --gcs_paths=<path1,path2,...>` to export the Parquet shards to Postgres. If a different GCS bucket is used 
   in (1) change the default values here as well.
   - You can either run the util through a Cloud SQL Proxy or you can connect directly to a specific IP address:
     ```
     docker run --rm -it \
      -e PSDB_CONTRAILS_DEFAULT_PWD="<password of read/write user>" \
      -e DB_HOST="<Postgres DB IP address>" \
      -e DB_PORT="5432" \
      gcs-to-pgdb \
      --gcs_paths flights-pipeline/emissions-export/2024/20260112,flights-pipeline/emissions-export/2025Q1/20260112 \
      --num_workers 10
     ```
4. Update the materialized views by running the following sequence of SQL commands:
   1. `REFRESH MATERIALIZED VIEW inventory_monthly_airlines_stats;`
   2. `REFRESH MATERIALIZED VIEW inventory_monthly_stats;`

<TODO: TOOLING/INSTRUCTIONS FOR SYNC'ING>

