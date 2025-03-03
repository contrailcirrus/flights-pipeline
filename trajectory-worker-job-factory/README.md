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

## Command Line interface
This service has a CLI wrapper [`cli.py`](cli.py) that can be used to locally invoke the trajectory worker job factory service.

The CLI's `flights submit` method will fetch ads-b data from BQ, resample/validate and package those data as a `WaypointsRecord`, and
optionally submit those records as a job to the trajectory worker queue.

CLI-specific commands include the `dryrun` and `export-waypoints` flags.

Running the CLI with `--dryrun` will execute all logic, _accept_ the publishing of the output job to the trajectory worker queue.

Running the CLI with `--export-waypoints` will save to local disk the validated/resampled waypoint trajectories 
(i.e. exactly what gets packaged into the `WaypointsRecord` trajectory worker job).
The resampled waypoints will be saved as a `.csv` file, one file per flight instance (`flight_id`).

### Manual Job Dispatch (`flights submit` )
A "job" in this context represents a single flight instance.
Submitting a job means enqueueing it for the trajectory worker.
The trajectory worker runs CoCip against the trajectory for the flight instance, and writes the outputs to BigQuery.

The output to bigquery can either be a single row (summary stats) for the flight instance (default), or,
one-row per flight segment (1min) of the flight instance (include the flag `-t` in the CLI invocation).

The CLI is designed to help with dispatching batches of jobs.

Required flag combinations:
- `-a <airline_iata> -d <day> -s <met_data_src>` this submits multiple jobs representing all flights originating 
for `<airline_iata>` originating on day (utc) of `<day>`, using met data source `<met_data_src>`.
Originating means the first waypoint in the trajectory falls on `<day>`, using met data source `<met_data_src>`.
- `-c <icao_addr> -s -d <day> <met_data_src>` this submits multiple jobs representing all flights for 
a single aircraft (`<icao_addr>`) originating on day (utc) of `<day>`, using met data source `<met_data_src>`.
Multiple icao addresses can be submitted as a comma-delimited string.
- `-i <flight_id> -d <day> -s <met_data_src>` this submits a single job representing a single 
flight instance (`<flight_id>`) which has origination on day (utc) of `<day>`, using met data source `<met_data_src>`.

Optional flags:
- `-e` this writes to file the resampled ADS-B data for each flight instance.
The data written locally represents exactly the ADS-B trajectory submitted to the trajectory worker.
This is a useful flag for fetching input data when investigating and reproducing behavior of the trajectory worker,
or, can be used as a convenient way to fetch clean, resampled data for groups of flights.
- `-t` this tells the trajectory worker to export to big query per-segment data in 
addition to the full flight trajectory summary.  
If the per-segment trajectory data is exported by setting this flag to `True`,
then both per-flight and per-segment summary data will be exported.
The rows in the BQ table between per-seg and per-flight can be disambiguated 
by selecting on `seg_cnt=1` (per-segment summary) vs. `seg_cnt>1` (per-flight summary).
- `-r` this runs the CLI in dry-run mode. This will go through all the steps of 
fetching, resampling, packaging etc... of jobs,
but will _not_ publish the jobs to the job queue.

**Examples**

```bash
# submit all flights for American Airlines that originate on Jan 12, 2024 (UTC)
# running the trajectory model using hres met data
./cli.py flights submit -a AA -d 2024-01-12 -s hres
```

```bash
# submit all flights for aircraft w/ icao 3C6565 that originate on Jun 06, 2024 (UTC)
# running the trajectory model using era5 met data,
# telling trajectory worker to write-off both per-flight summaries, as well as per-flight-segment values
./cli.py flights submit -c 3C6565 -d 2024-06-01 -s era5 -t
```

```bash
# fetch all flights for KLM that originate on Apr 02, 2024, 
# # running the trajectory model using era5 met data, w/printout verbose
# save CSVs for the resampled ADS-B flight trajectories to local disk
# does NOT submit the jobs
./cli.py flights submit -a KL -d 2024-04-02 -s era5 -e -v -r
```

```bash
# fetch single flight based on flight-id, saves waypoints to disk, does NOT submit to traj worker queue
./cli.py flights submit -s era5 -d 2024-11-28 -i "3fa2f048-d289-4d32-8c7a-23feeccdd684" -r -e
```