# Flight Emissions Report Cache

## Description
This subdirectory holds resources and services used to maintain 
a cache of flight emissions report data.

Specifically, data from BigQuery (`flights_pipeline_prod.trajectory_cocip_prod`) is selectively 
mirrored to a postgres database (`flight-emissions-report-<dev/prod>.flights-pipeline.trajectory-cocip`).
The postgres database serves as a cache backing APIs and other internal services that
require high volume/low latency access to the flights pipeline data residing in Big Query.

### Infrastructure
## Postgres
### PSDB access
If accessing the `flight-emissions-report` database instances from outside the GCP VPC,
then you'll need to add your client IP address to the instance's security settings.

In the UI, navigate to `Overview` and click the `Edit` button in the main view.
Under "Connections > Authorized Networks" click `Add Network`, and enter your IP address.

### Initial Setup
The GCP SQL instances, postgres databases and database users are codified in [.cloud/psdb_prod.tf](../.cloud/psdb_prod.tf).
These definitions provide initial instantiation of the resources.

See this reference for [database instance settings](https://cloud.google.com/sql/docs/postgres/instance-settings).

The following additional steps are carried out manually to:
1) instantiate table(s)
2) configure user access and permissions

**Revoke `cloudsqlsuperuser` from non-su roles**

Roles created in GCP SQL will have `cloudsqlsuperuser` roles by default.
Following the principle of least-priviledge, we do _not_ want our service-to-service (internal)
access credentials to have permissive PSDB access.

Running the following revokes the default superuser role from our users:
```sql
REVOKE cloudsqlsuperuser FROM internal_user_ro;
REVOKE cloudsqlsuperuser FROM internal_user_rw;
```

**Add `trajectory-cocip` table**
The SQL scripting [HERE](.docs/sql/create_cocip_trajectory_table.sql) is run to create 
a `trajectory-cocip` table in the `flight-emissions-report-<dev/prod>.flights-pipeline` database.
This scripting also configures access control for our read-only and read-write user credentials.

### PSDB user credentials
The postgres database instance has three users.
- `postgres` -- this is the super-user; credentials for this user should never be used by services accessing the database
- `internal_user_ro` -- this user's credentials should be used by any applications needing read-only access to database tables
- `internal_user_rw` -- this user's credentials should be used ... needing read and write access ...

When the users are initially created, they are given default (vulnerable) passwords.

These passwords were manually updated. This can be done either by logging into the database and using the psql command line.
Or, these can be updated via the web interface.
If using the web interface, navigate to `Users`, click the triple-dots next to a user and click `Change password`.

The current passwords for each user are stored in 1Password, in the Contrails-SRE collection.
The passwords are also stored in GCP Secret Manager,
under secret name `postgres-flight-emissions-report-<dev/prod>-internal-user-<ro/rw>`.

## Environment Variables
The following environment variables are expected for production and development environments.

| name      |                              description                              |
|:----------|:---------------------------------------------------------------------:|
| PSDB_USER |         PSDB username for the read/write access internal user         |
| PSDB_PASS |                          PSDB password " " "                          |
| PSDB_HOST | public IPv4 address (_without_ protocol prefix) for the PSDB instance |
| LOG_LEVEL |              log level for service in cloud environment               |