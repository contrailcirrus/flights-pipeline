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
The data sync'ed to the Postgres instance originate in a BigQuery table.

During a BigQuery to Postgres data sync run, you will need to first determine the source BQ table
intended for the sync.
This will generally be an archived/static BQ dataset, resulting from a given run of the flights-pipeline.
See reference documentation [here](https://github.com/contrailcirrus/flights-pipeline/tree/develop/pipeline-playbook/playbook) for how those BQ datasets are archived, with an example in this table (`contrails-301217.flights_pipeline_prod.inventory_2024_run_feb2026_summary`)
as documented in the Feb2026 run of the 2024 flights inventory ([ref](../pipeline-playbook/notes_archive/inventory_2024_run_feb2026_summary))

### Steps

1. Export the BigQuery data into Parquet shards under the following URL pattern:
   `gs://contrails-301217-sandbox-internal/flights-pipeline/emissions-export/<target_date_range>/<process_time>/*.pq`
   - Where `target_date_range` is of format %Y(Q%N) where %Y is the full calendar year, and %N is the quarter. Q%N is
     optional. Valid entries include e.g. 2025 or 2025Q2.
   - Where `process_time` is the time at which the export was run. This is %Y%m%d, the date (utc) on which the export
     command was run against BQ
   - Here is the export SQL command to run from the BigQuery prod instance: [`sql/0_bigquery_export.sql`](sql/0_bigquery_export.sql).

2. Ensure that the Postgres tables and views are defined. Otherwise run these in the following order:
   1. [`sql/1_trajectory_cocip.sql`](sql/1_trajectory_cocip.sql)
   2. [`sql/2_trajectory_cocip_meta.sql`](sql/2_trajectory_cocip_meta.sql)
   3. [`sql/3_inventory_monthly_impact_histogram.sql`](sql/3_inventory_monthly_impact_histogram.sql)
   4. [`sql/4_inventory_monthly_airlines_stats.sql`](sql/4_inventory_monthly_airlines_stats.sql)
   5. [`sql/5_inventory_monthly_od_pair_airline_stats.sql`](sql/5_inventory_monthly_od_pair_airline_stats.sql)
3. Run `main.py --gcs_paths=<path1,path2,...>` to export the Parquet shards to Postgres. If a different GCS bucket is used
   in (1) change the default values here as well.
   - First login to gcloud to access cloud storage:
     - `gcloud auth login`
   - Load the pipenv:
     - `pip install -U pip && pip install pipenv && pipenv sync && pipenv shell`
   - Run the utility (example for 2024 and 2025Q1 data):
     ```bash
     ./main.py \
       --db_user "internal_user_rw" \
       --db_password "<password of Postgres user internal_user_rw>" \
       --db_host "<target_DB_ipv4>" \
       --gcs_paths "flights-pipeline/emissions-export/<target_date_range_A>/<process_time_A>,flights-pipeline/emissions-export/<target_date_range_B>/<process_time_B>"
     ```
   - The DB utility ensures that the required monthly partition tables are correctly created.
     If a partition table needs to be created you have to use the following flags instead `--db_user "postgres" and --db_password "<pw of postgres user>"`
4. Update the materialized views by running the following sequence of SQL commands:
   1. `REFRESH MATERIALIZED VIEW inventory_monthly_airlines_stats;`
   2. `REFRESH MATERIALIZED VIEW inventory_monthly_od_pair_airline_stats;`
