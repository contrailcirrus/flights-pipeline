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

<TODO: TOOLING/INSTRUCTIONS FOR SYNC'ING>

