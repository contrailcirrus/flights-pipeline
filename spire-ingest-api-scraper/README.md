# Spire Ingest API Scraper

A Kubernetes `CronJob` that ingests flight position data from the [Spire API](https://aviation-docs.spire.com/api/tracking-stream/usage/#batch-mode) and publishes position updates to a PubSub topic. 
This is the primary trigger for async event-driven consumers downstream in the flights-pipeline.

This service maintains a checkpoint in FireStore to indicate what time period of data has already been fetched from Spire's AirSafe API. 
On each invocation, it determines what data can be synced after the last checkpoint, fetches time-batches of flight position updates, and publishes results to PubSub ordered in time. 
The flight's `icao_address` is used as the ordering key to guarantee consumers process position updates per-flight ascending in time.

## Environment Variables
The following environment variables are expected for production and development environments.

| name                                  |                                 description                                  |
|:--------------------------------------|:----------------------------------------------------------------------------:|
| FIRESTORE_STATE_DB                    |    name of the Firestore database, used for data pertaining to app state     |
| FIRESTORE_STATE_COLLECTION            |    name of the Firstore collection, used for data pertaining to app state    |
| FIRESTORE_STATE_DOC_ID                |    name of the Firestore document id, used for the last-sync-time pointer    |
| PUBSUB_EGRESS_TOPIC_ID                | fully-qualified uri for the pubsub topic receiving sanitized spire waypoints |
| SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID |   fully-qualified uri for the pubsub topic receiving tardy spire waypoints   |
| SPIRE_API_TOKEN                       |          REST API token for the Spire API, injected via k8s secret           |
| LOG_LEVEL                             |                  log level for service in cloud environment                  |
| SUSPEND_CRONJOB                        | (cloud deploy only) boolean value indicating state of running k8s cron   |

## Egress interface

Messages are serialized as JSON and published to a PubSub topic configured by the `PUBSUB_EGRESS_TOPIC_ID` environment variable. 
Each message contains a JSON-formatted payload following the conventions in [`src/schemas.py`](src/schemas.py)

Additionally, any tardy records are sent to a PubSub topic configured by the `SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID` env var.
This topic is configured to write those records to BigQuery.
A tardy record is any record where `(ingestion_time - event_time) < wall_time`.
Here, `event_time` is the record `timestamp`, `ingestion_time` is the record `ingestion_time`,
and `wall_time` is the `LAG_TIME` in `lib.spire`.

## Development environment

Set the `spire-ignest-api-scraper` path as your working directory and install development dependencies:

```bash
make install
```

This will create a virtual environment in the `.venv` directory. 
You may need to configure your IDE to reference the interpreter within this virtual environment.

Run static analysis checks for linting and type checking with:

```bash
make lint
make type-check
```

Run tests with

```bash
make pytest
# or to run tests and static analyses
make test
```

## Spire access
This service expects the Spire API token to be stored as a k8s secret in the `flights-pipeline-<dev/prod>` namespace.

See `helm/Makefile` for an example of how to instantiate the k8s secret via Helm.