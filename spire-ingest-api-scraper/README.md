# Spire Ingest API Scraper
A Kubernetes deployment that performs ETL from the [Spire API](https://aviation-docs.spire.com/api/tracking-stream/usage/#batch-mode) into this system.

This service consumes ordered jobs from the [Spire Ingest Job Publisher](../spire-ingest-job-publisher).
Ordered jobs means the Spire Ingest API Scraper will scrape the API contiguously in time.
e.g.
```text
job1: 2024-02-01T10:05:00 -> 2024-02-01T10:10:00
job2: 2024-02-01T10:10:00 -> 2024-02-01T10:15:00
...
```

The Spire Ingest API Scraper will pull a batch of data from the Spire API,
resample flight trajectories on a per-flight-instance basis,
and publish to PubSub an ordered list of flight waypoints (on a per-flight-instance-basis).
Specifically, flight waypoints are published to PubSub in order (temporally),
and the PubSub ordering key is the flight-instance identifier.

The Spire Waypoint Resampler service consumes messages from this service.