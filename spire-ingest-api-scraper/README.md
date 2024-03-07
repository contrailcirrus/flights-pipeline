# Spire Ingest API Scraper

A Kubernetes `CronJob` that ingests flight position data from the [Spire API](https://aviation-docs.spire.com/api/tracking-stream/usage/#batch-mode) and publishes position updates to a PubSub topic. This is the primary trigger for async event-driven consumers downstream in the flights-pipeline.

This service maintains a checkpoint in FireStore to indicate what time period of data has already been fetched from Spire's AirSafe API. On each invocation, it determines what data can be synced after the last checkpoint, fetches time-batches of flight position updates, and publishes results to PubSub ordered in time. The flight's `icao_address` is used as the ordering key to guarantee consumers process position updates per-flight ascending in time.

## Egress interface

Messages are serialized as JSON and published to a PubSub topic configured by the `PUBSUB_EGRESS_TOPIC_ID` environment variable. Each message contains a JSON-formatted payload following the conventions in [`src/schemas.py`](src/schemas.py)

## Development environment

Set the `spire-ignest-api-scraper` path as your working directory and install development dependencies:

```bash
make install
```

This will create a virtual environment in the `.venv` directory. You may need to configure your IDE to reference the interpreter within this virtual environment.

Run static analysis checks for formatting, linting, and type checking with:

```bash
make check
```

Run tests with

```bash
make test
```
