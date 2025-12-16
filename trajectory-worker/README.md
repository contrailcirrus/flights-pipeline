# Trajectory Worker

## Overview
A Kubernetes deployment that ingests a single flight instance ("flight trajectory chunk")
and runs CoCip on that trajectory.

# Behavior
There are two trajectory worker deployments.

The primary deployment (`helm/trajectory-worker-gaia-deployment.yaml`) does the majority of the job processing.
This deployment is provisioned with less memory, and configured with a horizontal autoscaler with greater max concurrency.

The secondary deployment (`helm/trajectory-worker-gaia-backup-deployment.yaml`) handles the overflow from the primary deployment.
A job will overflow from the primary deployment if a worker in the primary deployment fails to process a job 
(under normal conditions, this is due to resource constraints).  The secondary deployment is provisioned with more
memory to handle the small volume of resource intensive jobs.

Coordination between the primary and secondary deployment is achieved via a PubSub topic/queue.
The primary worker will, before conducting work on a job, check to see if the job had failed in a previous processing
attempt by the primary worker. If so, it will forward the job to the secondary deployment's queue.


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

| name                                   |                                            description                                             |
|:---------------------------------------|:--------------------------------------------------------------------------------------------------:|
| TRAJECTORY_CHUNK_SUBSCRIPTION_ID       |   fully-qualified uri for the subscription from which the worker dequeues flight trajectory jobs   |
| HRES_SOURCE_PATH                       |               fully-qualified path in gcs for the hres zarr store used to run cocip                |
| ERA5_SOURCE_PATH                       |               fully-qualified path in gcs for the era5 zarr store used to run cocip                |
| LOG_LEVEL                              |                             log level for service in cloud environment                             |
| GIT_SHA                                |    git hash for the trajectory worker; injected into the big query outputs for lineage tracking    |
| TRAJECTORY_COCIP_BQ_TOPIC_ID           |                fully-qualified uri for publishing cocip outputs, flows to BigQuery                 |
| GCP_SVC_ACCT_KEY                       |               JSON service account key for the flights-pipeline GCP service account                |

## Audit: Skipped flight logs (log sink)

This service emits WARNING/INFO logs containing the word "skipping" when a flight cannot be processed.
These are exported to GCS via a Cloud Logging sink for audit.

- Bucket (prod): [contrails-301217-fp-prod-trajectory-worker](https://console.cloud.google.com/storage/browser/contrails-301217-fp-prod-trajectory-worker)
- Bucket (dev): [contrails-301217-fp-dev-trajectory-worker](https://console.cloud.google.com/storage/browser/contrails-301217-fp-dev-trajectory-worker)

Filter (prod):
```text
resource.type="k8s_container"
resource.labels.cluster_name="contrails-gke-general"
resource.labels.namespace_name="flights-pipeline-prod"
labels.k8s-pod/app="trajectory-worker-gaia"
jsonPayload.textPayload =~ "skipping"
```
Notes:
- Sinks write hourly batches; allow time for objects to appear
- Logs should appear under the respective bucket after up to ~1 hour. Example: `contrails-301217-fp-prod-trajectory-worker/stderr/2025/09/04`.

## Protobufs
The trajectory worker (if optionally indicated to do so in a Job) will write protobuf blobs to google cloud storage.
Those blobs contain per-segment trajectory values (including segment time evolution data), on a per-flight basis.

Updating the data model of the protobuf requires first updating the `*.proto` definition _then_ 
regenerate the Python code stubs, _then_ updating the source code to adapt to the updates reflected
in the regenerated code stub.

Furthermore, any external clients wishing to consume (deserialize) the proto files from GCS will
need a code stub for the proto-file's data model (generated for the client's code language).

The generation of code stubs from the `*.proto` file requires the CLI tool [protoc](https://protobuf.dev/downloads/).

Running the following from the root of the `trajectory-worker` subdirectory will generate the protobuf module with message metaclasses,
and place them in the `/lib` module.

```bash
protoc -I/usr/local/include --python_out=. --proto_path=protos protos/lib/trajectory.proto protos/lib/segment.proto
```

Note that you must have proto files for common types on your local machine, at the `/usr/local/include` location,
as per the `protoc` installation instructions.