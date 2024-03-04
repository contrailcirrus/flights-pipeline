# Spire Ingest Resample Worker
A Kubernetes deployment that ingests waypoint records from a pubsub subscription, 
and performs backwards interpolation for missing waypoints, on a per flight-instance basis.

A waypoint record is a list of one or more contiguous (1Min sampling) waypoints, 
for a given flight-instance.

In order to perform the backward interpolation, 
the Resample Worker checks a remote datastore for the last known waypoint for the flight instance.
The Resample Worker then interpolates between the waypoint record and the last known waypoint.

Lastly, the Resample Worker will generate flight segment tuples 
from the contiguous 1Min waypoint samples.

The Resample Worker, on egress, will:
1) publish an ordered list of flight segments to a pubsub topic (to be consumed by a worker that runs CoCip on each segment)
2) publishes interpolated (aka imputed) waypoints to a pubsub topic (to be injected into BigQuery)
