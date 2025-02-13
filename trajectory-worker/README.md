# Trajectory Worker

## Overview
A Kubernetes deployment that ingests a set of contiguous waypoints ("flight trajectory chunk")
for a given flight-instance, and runs CoCip on that trajectory segment.
The set of waypoints in each job contains one additional leading waypoint 
(and by extension, one additional leading segment), which serves as a sacrificial segment for 
running CoCip. 

# Behavior
There are two trajectory worker deployments.
1) realtime - this deployment consumes small segments (~5min flight segments) published by the resample worker.
These are exported to the BQ table under `source_id` of `spire`
2) gaia - this deployment consumes full flight trajectories (one job is a full flight) published by 
the flight emissions report cronjob (or manually)
These are exported to the BQ table under `source_id` of `flightsreport`. Trajectory workers in the gaia deployment
will also export per-segment cocip outputs under `source_id` of `flightsreport` full.  At present,
the flight emissions cronjob does not compose jobs that compel per-seg outputs 
(i.e all per-seg outputs are currently dispatched manually w/ the gaia cli).


## Application Authentication
Applications running in k8s (and many GCP fully managed services) typically authenticate auto-magically
into GCP using the service account/IAM belonging to the managing service instance.

In k8s, this is managed via a sidecar image running a metadata server on all k8s deployed pods.  
GCP client libraries are built to automatically check, when instantiated,
for the presence of this metadata server.

In mid-2024, this service unexpectedly experiences a persistent issue in which calls to 
`xarray.open_zarr()` would fail after 1 hour of application runtime.
Debugging suggests that the underlying remote filesystem package in `open_zarr()` that calls GCS
was failing to update credentials -- specifically, the gcsfs pkg was calling the metadata server
at the 1hour mark, requesting an updated credential (cred rotation), and that call perpetually fails.

Interestingly, other GCP packages (e.g. PubSub Client) did not experience metadata server key rotation issues.

This metadata server auth issue was raised with Google Support, and remains an open ticket and ongoing issue.

As a workaround, this service now no longer uses the metadata server to auto-magically authenticate to GCP services.
Instead, a custom service account was created in IAM, its service account key was saved as a k8s secret, 
and that key is mounted to this instance on boot-up, and injected into the GCP Client libs manually
(client libs prioritize using a service account key, if provided, before falling back to a metadata server).

## Environment Variables
The following environment variables are expected for production and development environments.

| name                             |                                         description                                          |
|:---------------------------------|:--------------------------------------------------------------------------------------------:|
| TRAJECTORY_CHUNK_SUBSCRIPTION_ID |          fully-qualified uri for the flights trajectory chunks pubsub subscription           |
| HRES_SOURCE_PATH                 |            fully-qualified path in gcs for the hres zarr store used to run cocip             |
| ERA5_SOURCE_PATH                 |            fully-qualified path in gcs for the era5 zarr store used to run cocip             |
| LOG_LEVEL                        |                          log level for service in cloud environment                          |
| GIT_SHA                          | git hash for the trajectory worker; injected into the big query outputs for lineage tracking |
| TRAJECTORY_COCIP_BQ_TOPIC_ID     |          fully-qualified uri for trajectory chunk cocip outputs, flows to BigQuery           |
| CHUNKS_PER_JOB                   |                  (not implemented) max number of chunks ot process per job                   |

