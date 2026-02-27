# Inventory Cache

## Description
This subdirectory holds resources and services used to maintain 
a cache of the impact inventory data, mirroring the SOT records in BigQuery to a Postgres instance..

Specifically, data from BigQuery (`flights_pipeline_prod.trajectory_cocip_prod`) is selectively 
mirrored to a postgres database (`contrails-default-<dev/prod>.flights-pipeline-fer-cache`).
The postgres database serves as a cache backing APIs and other internal services that
require high volume/low latency access to the flights pipeline data residing in Big Query.

### Infrastructure
## Postgres
### PSDB access
If accessing the `contrails-default-<dev/prod>` database instances from outside the GCP VPC,
then you'll need to add your client IP address to the instance's security settings.

In the UI, navigate to `Overview` and click the `Edit` button in the main view.
Under "Connections > Authorized Networks" click `Add Network`, and enter your IP address.

#### PSDB k8s access
The postgres instance is accessed by talking with the Cloud SQL Proxy that is deployed in [psdb-flight-emissions-report-proxy](../psdb-contrails-default-proxy).

### Initial Setup
The postgres databases are codified in [.cloud/psdb_prod.tf](../.cloud/psdb_prod.tf).
These definitions provide initial instantiation of the resources owned by the `inventory-cache` service.

See this reference for [database instance settings](https://cloud.google.com/sql/docs/postgres/instance-settings).

The following additional steps are carried out manually to:
1) instantiate table(s)

**Add `trajectory-cocip` table**
The SQL scripting [HERE](.docs/sql/create_cocip_trajectory_table.sql) is run to create 
a `trajectory-cocip` table in the `contrails-default-<dev/prod>.flights-pipeline-fer-cache` database.
This scripting also configures access control for our read-only and read-write user credentials.

## Environment Variables
The following environment variables are expected for production and development environments.

| name      |                              description                              |
|:----------|:---------------------------------------------------------------------:|
| PSDB_USER |         PSDB username for the read/write access internal user         |
| PSDB_PASS |                          PSDB password " " "                          |
| PSDB_HOST | public IPv4 address (_without_ protocol prefix) for the PSDB instance |
| LOG_LEVEL |              log level for service in cloud environment               |