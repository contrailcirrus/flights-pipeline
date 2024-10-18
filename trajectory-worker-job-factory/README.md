# Trajectory Worker Job Factory

The Trajectory Worker Job Factory is a k8s service responsible for building and submitting
jobs to the trajectory worker job queue (PubSub topic: `projects/contrails-301217/topics/prod-fp-gaia-trajectory-chunk`).

Recall that a trajectory worker "job" is a `WaypointsRecord` object, as defined in [lib/schemas.py](lib/schemas.py).
The `WaypointsRecord` object packages a flight trajectory for a single flight instance.

This Trajectory Worker Job Factory service has the responsibility of fetching raw ADS-B data from BigQuery for a given flight instance,
applying validation rules to that trajectory (and ejecting/stepping over the flight if the trajectory is invalid),
and, lastly, resampling the trajectory to a 1min segment interval.

The Trajectory Worker Job Factory operates by consuming "trajectory worker job descriptors" (TWJDs) from an input queue.
A TJWD is defined in the `TrajWorkerJobDescriptor` in [lib/schemas.py](lib/schemas.py).

Any service wishing to generate CoCiP trajectories can publish a TWJD to the worker queue.
At present, this is done by:
a) the gaia cli (gaia_cli.py) in the `flight-emissions-report` service, when invoked manually by a user
b) the daily cron (main_cron.py) in the `flight-emissions-report` service, 
which dispatches a daily request to process a previous day's trajectories for a select list of airlines

### `TrajectoryWorkerJobDescriptor` Anatomy

A Trajectory Worker Job Descriptor (TWJD) provides instructions 
to this service on how to build a trajectory worker job (`WaypointsRecord`).

Two "flavors" of TWJD are accepted by this service.

** (1) build a trajectory worker job for a single flight **
```python
tjwd = TrajectoryWorkerJobDescriptor(
    day="2024-10-12",
    flight_id="5028a7bc-b834-4b71-b655-46988d8fc56f",
    met_source=MetSource.HRES,
)
```
This TJWD tells this service to compose and submit a single trajectory worker job, for a single `flight_id`.
Here, `day` should indicate the day (UTC) on which the flight originates.

** (2) build trajectory worker jobs for all flights belonging to an icao address, on a given day **
```python
tjwd = TrajectoryWorkerJobDescriptor(
    day="2024-10-12",
    icao_address="013D4E",
    met_source=MetSource.HRES,
)
```
This TJWD tells this service to compose and submit multiple trajectory worker jobs
(if multiple flights exist for a given aircraft originating on the same day)
where each job is a flight instance belonging to an aircraft (`icao_address`) and where the
flight instances all originate (UTC) on a given `day`.

** (3) build trajectory worker jobs for all flights belonging to an airline, on a given day **
```python
tjwd = TrajectoryWorkerJobDescriptor(
    day="2024-10-12",
    airline_iata="AA",
    met_source=MetSource.HRES,
)
```
This TJWD tells this service to compose and submit multiple trajectory worker jobs, 
each job being a flight instance
for a target airline that originates (UTC) on a given `day`.

**Discussion**
```
Why use one flavor of TJWD over the other?
--
A TJWD that targets all flights for an airline-day will minimize BigQuery costs,
since we have a ratio of one query to many flights.  Recall that our ADS-B data is partitioned by timestamp (daily),
thus each query will be billed as a scan of 1 day's data.
The tradeoff, however, is that using this flavor of TJWD has a larger failure "blast radius",
given that the size of the unit of work is large (all flights for a given airline-day).
If this service fails and retries on a TJWD of this flavor, it is is forced to reprocess
an entire airline-day's data, and, if the previous failed job partially succeeded, we expect to 
have a larger number of duplicate jobs submitted to the trajectory worker.

A TJWD that targets a single flight instance (`flight_id`), in contrast, has a much smaller blast radius
(if the service fails on this flavor of TJWD, it is only retrying submission for a single flight instance).
In contrast to the above, however, we have one query to BQ per flight instance, each query being billed
as a day's scan of the BQ table, thus we incurr higher BQ costs.

A TJWD that targets multiple flight instances occuring on the same day for a given aircraft (`icao_address`)
falls between the two above cases (closer to the `flight_id` case...) w.r.t. BQ billing and failure blast radius.
```

## Environment Variables
The following environment variables are expected for production and development environments.

| name                       |                                               description                                                |
|:---------------------------|:--------------------------------------------------------------------------------------------------------:|
| TWJD_CHUNK_SUBSCRIPTION_ID | fully-qualified uri for the pubsub subscription from which to dequeue trajectory worker job descriptions |
| TRAJECTORY_CHUNK_TOPIC_ID  |       fully-qualified path for the pubsub topic to which the svc publishes trajectory worker jobs        |
| LOG_LEVEL                  |                                log level for service in cloud environment                                |
