# PSDB Flight Emissions Report Proxy

This is a k8s Deployment of the Google [Cloud SQL Proxy](https://github.com/GoogleCloudPlatform/cloud-sql-proxy) application.

A k8s Deployment hosts the Cloud SQL Proxy application.  
A k8s Service exposes the Deployment to other pods in k8s.

The Cloud SQL Proxy application accepts local (cluster internal) traffic from other k8s pods,
and proxies that connection to the `flight-emissions-report-<dev/prod>` GCP Cloud SQL instances.

This implementation adapts from the example sidecar implementations of the SQL Proxy, 
as detailed [here](https://cloud.google.com/sql/docs/postgres/sql-proxy), 
with supporting docs [here](https://cloud.google.com/sql/docs/postgres/connect-instance-kubernetes).

## Motivation
The sidecar implementation does not play well with ephemeral pods (for instance, pods that run as Jobs or CronJobs).
When the main application exits, the sidecar does not exit, and implementing inter-container signalling is messy.

As such, we favor having this external service, which is long-lived and handles proxying on an as-needed basis.

# How To Use

Any pod running in k8s can talk to this proxy, and access the `flight-emissions-report-<dev/prod>` Cloud SQL instance.

This can be done by connecting to the k8s Service resource at the Cluster IP assigned to the resource.
(see `kubectl get svc -n flights-pipeline-<dev/prod>`).

The k8s Service is also assigned an internal URI by the [k8s DNS](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#a-aaaa-records).
This service, then is accessed at `<service-name>.<namespace>.svc.cluster.local`

As such, pods can connect to PSDB using the address:
```text
 postgresql://USER:PASSWORD@psdb-flight-emissions-report-proxy.flights-pipeline-<dev/prod>.svc.cluster.local/DATABASE_NAME
```

## Implementation
See the `flight-emissions-report-cache` src code for an example implementation.