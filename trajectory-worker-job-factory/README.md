# Trajectory Worker Job Factory

The Trajectory Worker Job Factory is a k8s service responsible for building and submitting
jobs to the trajectory worker job queue (PubSub topic: `projects/contrails-301217/topics/prod-fp-gaia-trajectory-chunk`).

Recall that a trajectory worker "job" is a `WaypointsRecord` object, as defined in [lib/schemas.py](lib/schemas.py).
The `WaypointsRecord` object packages a flight trajectory for a single flight instance.

This Trajectory Worker Job Factory service has the responsibility of fetching raw ADS-B data from BigQuery for a given flight instance,
applying validation rules to that trajectory (and ejecting/stepping over the flight if the trajectory is invalid),
and, lastly, resampling the trajectory to a 1min segment interval.

The Trajectory Worker Job Factory operates by consuming "trajectory worker job descriptors" (TWJDs) from an input queue.
A TWJD is defined in the `TrajWorkerJobDescriptor` in [lib/schemas.py](lib/schemas.py).

Any service wishing to generate CoCiP trajectories can publish a TWJD to the worker queue.
At present, this is done by:
a) the flight emissions report cli (cli.py) in the `flight-emissions-report` service, when invoked manually by a user
b) the daily cron (main_cron.py) in the `flight-emissions-report` service, 
which dispatches a daily request to process a previous day's trajectories for a select list of airlines

### `TrajectoryWorkerJobDescriptor` Anatomy

A Trajectory Worker Job Descriptor (TWJD) provides instructions 
to this service on how to build a trajectory worker job (`WaypointsRecord`).

Two "flavors" of TWJD are accepted by this service.

** (1) build a trajectory worker job for a single flight **
```python
twjd = TrajectoryWorkerJobDescriptor(
    day="2024-10-12",
    flight_id="5028a7bc-b834-4b71-b655-46988d8fc56f",
    met_source=MetSource.HRES,
)
```
This TWJD tells this service to compose and submit a single trajectory worker job, for a single `flight_id`.
Here, `day` should indicate the day (UTC) on which the flight originates.

** (2) build trajectory worker jobs for all flights belonging to an icao address, on a given day **
```python
twjd = TrajectoryWorkerJobDescriptor(
    day="2024-10-12",
    icao_address="013D4E",
    met_source=MetSource.HRES,
)
```
This TWJD tells this service to compose and submit multiple trajectory worker jobs
(if multiple flights exist for a given aircraft originating on the same day)
where each job is a flight instance belonging to an aircraft (`icao_address`) and where the
flight instances all originate (UTC) on a given `day`.

** (3) build trajectory worker jobs for all flights belonging to an airline, on a given day **
```python
twjd = TrajectoryWorkerJobDescriptor(
    day="2024-10-12",
    airline_iata="AA",
    met_source=MetSource.HRES,
)
```
This TWJD tells this service to compose and submit multiple trajectory worker jobs, 
each job being a flight instance
for a target airline that originates (UTC) on a given `day`.

**Discussion**
```
Why use one flavor of twjd over the other?
--
A twjd that targets all flights for an airline-day will minimize BigQuery costs,
since we have a ratio of one query to many flights.  Recall that our ADS-B data is partitioned by timestamp (daily),
thus each query will be billed as a scan of 1 day's data.
The tradeoff, however, is that using this flavor of twjd has a larger failure "blast radius",
given that the size of the unit of work is large (all flights for a given airline-day).
If this service fails and retries on a twjd of this flavor, it is is forced to reprocess
an entire airline-day's data, and, if the previous failed job partially succeeded, we expect to 
have a larger number of duplicate jobs submitted to the trajectory worker.

A twjd that targets a single flight instance (`flight_id`), in contrast, has a much smaller blast radius
(if the service fails on this flavor of TJWD, it is only retrying submission for a single flight instance).
In contrast to the above, however, we have one query to BQ per flight instance, each query being billed
as a day's scan of the BQ table, thus we incurr higher BQ costs.

A twjd that targets multiple flight instances occuring on the same day for a given aircraft (`icao_address`)
falls between the two above cases (closer to the `flight_id` case...) w.r.t. BQ billing and failure blast radius.
```

## Environment Variables
The following environment variables are expected for production and development environments.

| name                       |                                               description                                                |
|:---------------------------|:--------------------------------------------------------------------------------------------------------:|
| TWJD_CHUNK_SUBSCRIPTION_ID | fully-qualified uri for the pubsub subscription from which to dequeue trajectory worker job descriptions |
| TRAJECTORY_CHUNK_TOPIC_ID  |       fully-qualified path for the pubsub topic to which the svc publishes trajectory worker jobs        |
| LOG_LEVEL                  |                                log level for service in cloud environment                                |

## Audit: Skipped flight logs (log sink)

When a flight fails QA/QC, this service logs messages containing "skipping". These are exported to GCS via a Cloud Logging sink for audit.

- Bucket (prod): [contrails-301217-fp-prod-trajectory-worker-job-factory](https://console.cloud.google.com/storage/browser/contrails-301217-fp-prod-trajectory-worker-job-factory)
- Bucket (dev): [contrails-301217-fp-dev-trajectory-worker-job-factory](https://console.cloud.google.com/storage/browser/contrails-301217-fp-dev-trajectory-worker-job-factory)

Filter (prod):
```text
resource.type="k8s_container"
resource.labels.cluster_name="contrails-gke-general"
resource.labels.namespace_name="flights-pipeline-prod"
labels.k8s-pod/app="trajectory-worker-job-factory"
jsonPayload.textPayload =~ "skipping"
```
Notes:
- Sinks write hourly batches; allow time for objects to appear
- Logs should appear under the respective bucket after up to ~1 hour. Example: `contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2025/09/04`.


## Resumable Work (stateful behavior)
The trajectory worker job factory makes use of an external Redis cache to maintain a progress marker when executing a TWJD.
The current implementation only uses resumable work logic for TWJDs that request flight trajectories be minted on a *per airline-day* basis.
i.e. TWJDs that request flight trajectories for a single flight_id, or an icao_address-day, are not candidates for resumable work.

**This cache is not used when executing any of the CLI commands**

Because some TWJDs result in a sizeable unit of work (generating trajectory blobs for 3000+ flights) running over a decent period of time (30min),
the blast radius is large for failures while these jobs is in-progress.

### Redis access
If you plan to connect to the remote redis instance from localhost, you will need to:

create a GCP Compute Engine VM
use the VM to establish a tunnel between localhost > VM (in VPC) > redis
Follow these steps (don't forget to clean up your VM after use!).

```bash
gcloud compute instances create SOME_VM_NAME --machine-type=f1-micro --zone=us-east1-b
REDIS_HOST=REMOTE_HOST_IPV4 && REDIS_PORT=6379 && gcloud compute ssh SOME_VM_NAME --zone=us-east1-b -- -N -L $REDIS_PORT:$REDIS_HOST:$REDIS_PORT
```

