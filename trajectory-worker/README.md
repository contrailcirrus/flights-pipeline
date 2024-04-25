# Trajectory Worker

## Overview
A Kubernetes deployment that ingests a set of contiguous waypoints ("flight trajectory chunk")
for a given flight-instance, and runs CoCip on that trajectory segment.
The set of waypoints in each job contains one additional leading waypoint 
(and by extension, one additional leading segment), which serves as a sacrificial segment for 
running CoCip. 

# Behavior


## Environment Variables
The following environment variables are expected for production and development environments.

| name                             |                                         description                                          |
|:---------------------------------|:--------------------------------------------------------------------------------------------:|
| TRAJECTORY_CHUNK_SUBSCRIPTION_ID |          fully-qualified uri for the flights trajectory chunks pubsub subscription           |
| HRES_SOURCE_PATH                 |            fully-qualified path in gcs for the hres zarr store used to run cocip             |
| LOG_LEVEL                        |                          log level for service in cloud environment                          |
| GIT_SHA                          | git hash for the trajectory worker; injected into the big query outputs for lineage tracking |
| TRAJECTORY_COCIP_BQ_TOPIC_ID     |          fully-qualified uri for trajectory chunk cocip outputs, flows to BigQuery           |
| CHUNKS_PER_JOB                   |                  (not implemented) max number of chunks ot process per job                   |

