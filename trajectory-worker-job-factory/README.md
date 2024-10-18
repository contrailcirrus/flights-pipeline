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