# Inventory 2022 (run: June 2026)

## Hyperdisk Setup

The 2022 ERA5 met data was put into a new GCP bucket `gs://contrails-301217-ecmwf-era5-zarr-v2-staging-2022` so that data for 2020-2023 could be set up in parallel, letting us set up hyperdisks with the met data in parallel without having to purge the staging bucket before getting started on another year. This dataset includes zarr stores from 2021-12-31, 2023-01-01, and 2023-01-02 in addition to all of 2022. It was copied into the staging bucket wit `gsutil -m cp` commands on a VM rather than setting up a transfer job with the `copy_era5_gcs_to_staging.sh` script, mostly because I forgot that script existed. There were no errors though, and data seem to be present.

To create the hyperdisk, we created a new [GCSDataSource](../../pre_process/hyperdisk-setup/gcs-era5-zarr-data-source-2022.yaml) and a new [PVC](../../pre_process/hyperdisk-setup/era5-zarr-gcs-pvc-useast4c-2022.yaml) for the 2022 dataset, opting to start the disk with 600MB/s bandwidth and hoping we can scale it up.

## Job ID compilation
Created a new Job ID table using the following BQ query:

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2021-12-31T00:00:00" AND "2022-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2022-01-01T00:00:00"),
     job_grp_tb AS (SELECT *,
                           SUBSTR(TO_HEX(SHA256(CONCAT(
                                   CAST(CAST(0.001 * ROW_NUMBER() OVER (PARTITION BY day_bin ORDER BY min_ts) AS INT64) AS STRING),
                                   CAST(day_bin AS STRING)))), 1, 32) AS job_id
                    FROM target_tb),
     agg_tb AS (SELECT job_id,
                       ARRAY_AGG(day_bin)   AS day_bin_arr,
                       ARRAY_AGG(flight_id) AS flight_id_list
                FROM job_grp_tb
                GROUP BY job_id)
SELECT job_id, FORMAT_DATE('%Y-%m-%d', ARRAY_FIRST(day_bin_arr)) AS day, flight_id_list
FROM agg_tb
```

This created a new table with 24743 Job IDs. I created the job list with `SELECT job_id FROM `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_jobs`;`, exporting the result as CSV, removing the column name top row, and changing the file name to `2022_job_id_list.txt`.

## Run
Started run at 16:25 UTC on 2026-06-22.

On a VM, I changed the `pipeline-cli/services.py` file to point to the production TWJF PubSube queue, then ran:

```shell
./cli.py jobworker submit -j /home/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_2022_run_jun2026/2022_job_id_list.txt -l inventory_2022_run_jun2026_jobs -w gcs -s era5 -t > 2022_cli_run.log 2>&1
```

After observing normal TWJF logs, and seeing a few thousand jobs published to the TWJF queue, I scaled the number of TWJF workers to 1000 at 16:37 UTC.

----
```text
Deployed TW and TWBU:
Updated the TW and TWBU helm configs to change the PVC reference to match the hyperdisk PVC created for the 2022 ERA5 data. This kicked off the CI/CD process to update the TW and TWBU deployments. These took a while to roll over because the horizontal scaling was still set to 2395 replicas.

Set to run at 1vCPU/worker with 0.58 GiB memory up to 1.2 GiB.
```


```text
Scaled hyperdisk bandwidth using the webconsole from 600MB/s to 60000MB/s at 17:26 UTC. 
Took about 20 minutes, but scaling was successful.
```

```text
13 unschedulable pods due to insufficient CPU, though there were 50x90 = 2500 cpus available and only 2395 pods scheduled. Backed off to 2380 and seems fine.
```

```text
TWJF done 18:32 UTC.
TWJF queue empty. Scaled back to 1 worker. 
No deadlettered TWJDs.
```

```text
Not seeing more than about 150 acks/s with this configuration. That's 2 acks/min/worker. We think this should be higher. Going to start scaling back workers to see if ack rate/worker goes up.
18:49 UTC: scaling back to 4105 (removing 3 nodes worth of workers).
Scaled nodes back to 47
```

```text
Throughput still seems around 150 acks/s, which is now about 2.2 acks/min/worker.
Scaling back to 3835 workers and 44 nodes at 19:26 UTC.
After about 15 minutes, that seems ot have settled at about 148 acks/s or 2.3 acks/min/worker. Hyperdisk bandwidth is about 63 GB/s - maybe down very slightly.
```

```text
Scaling back to 3465 workers and 40 nodes at 19:44 UTC.
The absolute throughput still looks about the same: about 148 acks/s, and 62 GB/s hyperdisk bandwidth for 2.5 acks/min/worker.
This seems like it may be hyperdisk bandwidth saturation.
```

```text
Scaling back to 3000 workers and 35 nodes at 20:13 UTC.
The absolute throughput seems to remain at 148 acks/s, and hyperdisk bandwidth is still maximized. Now we're at nearly 3 acks/min/worker. I have seen the IO queue depth come down as we scale down workers, the bandwidth and ack rate are consistent, so we're clearly hitting a hyperdisk bandwidth limit.
```

``text 
Scaling back to 2000 workers at 23 nodes at 20:27 UTC.
```

```text
Ack rate dropped to about 130 acks/s and bandwidth usage down to 54 GB/s or 3.9 acks/min/worker. That indicates we could go to just under 2300 workers to maximize bandwidth usage if scaling is linear.

Scaling up to 2270 workers at 26 nodes at 21:11 UTC.
```

```text
Scaling TW up to 2275 workers. Noticed one node was a little low on CPU requested and we have not quite maxed out hyperdisk bandwidth (sitting at about 59GB/s).
```

```text
Increasing hyperdisk bandwidth to 100000MB/s at 00:38 UTC 2026-06-23.
```

```text
Bandwidth increase went through at 01:00 UTC.
Scaling to 44 nodes, 3800 workers.
```

```text
Seems to have worked. Ack rate at about 230-240 ack/s, so 3.6-3.9 acks/min/worker.
The hyperdisk bandwidth was maxed out at about 99 GB/s.
```

```text
Updating hyperdisk bandwith to 160000 MB/s at 09:38 UTC.

It failed:

Failed to update disk pvc-5b91bc9e-2d58-4937-910c-f19125698e96: Operation type [update] failed with message "The zone 'projects/contrails-301217/zones/us-east4-c' does not have enough resources available to fulfill the request. '(resource type:hyperdisk-ml)'."
```

```text
Trying to update the hyperdisk bandwidth to 140000 MB/s at 10:06 UTC.
Succeeded.
```

```text
Updating to 5300 workers on 61 nodes at 11:11 UTC.

Using most of the 140 GB/s hyperdis bandwidth (high 130s), and have about 320 acs/s for about 3.6 acks/min/worker.

Still have a number of nodes with ~86 CPUs out of 90 scheduled, so bumped up to 5330 workers.
```

```text
Updating to 5340 workers, because we still have a little excess CPU on a few nodes at 14:45 UTC.
```

```text
It seems the average pod uses <50% of its CPU allocation. Considering dropping to 0.7 CPU/worker to get a little more efficient.

If I leave the number of workers the same at 5340, that would involve scaling back the number of nodes to 43. I will try to make the CPU and number of workers update in CI/CD, then update number of nodes through terraform.
```

```text
After rolling the pods and dropping the number of nodes, I see only about 100GB/s hyperdisk usage, and ack rate down to 230acks/s.

Will scale up workers by ~40% to try to maximize bandwidth usage.

Going for 7400 workers on 60 nodes.
```

```text
This yielded about 345 acks/s using 135GB/s hyperdisk bandwidth. Seemed to be a little extra CPU overhead on the nodes, so added 80 workers to 7480 total.
Still a little more. Bumping up to 7500 workers.
```

```
Adding another node and 125 workers to try to saturate HD bandwidth at 14:55 UTC.
This only bumped HD bandwidth usage up a little bit. Up to 3.8 acks/min/vcpu, up from 3.66 acks/min/vcpu with the 1 vcpu/worker setup from earlier.

Going to add another node to try to maximize HD bandwidth usage.

Up to 62 nodes and 7750 workers at 16:10 UTC.
```

```text
The change seems to have dropped down to 3.66 acks/min/vcpu with 340 acks/s. It seems that rolling back to 7480 workers on 60 nodes may be slightly better.

Rolling back to 7480 workers, 60 nodes at 16:22 UTC.

Essentially flat performance.
```

```text
All TW jobs and TWBU jobs appear to be done at 20:30 UTC, 2026-06-23.
Scaling down TW workers and nodes.
```

```text
Scaled TW workers down to 1, then scaled c3d-highcpu-90 nodes down to 0 on the standard cluster.
```

```text
Removed PVC:
kubectl delete pvc era5-zarr-gcs-pvc-useast4c -n flights-pipeline-prod

PV failed to be deleted because it's registered as being attached to nodes that no longer exist. Deleting PV:

kubectl get pv -n flights-pipeline-prod
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS     CLAIM                                              STORAGECLASS                        VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-5b91bc9e-2d58-4937-910c-f19125698e96   4000Gi     ROX            Delete           Released   flights-pipeline-prod/era5-zarr-gcs-pvc-useast4c   hyperdisk-ml-single-zone-useast4c   <unset>                          35h

kubectl delete pv pvc-5b91bc9e-2d58-4937-910c-f19125698e96 -n flights-pipeline-prod

But this failed... apparently the PV had just been removed. None remain:

kubectl get pv -n flights-pipeline-prod                                              
No resources found

Disk does not appear in the GCP web console any more either.
```

## Closeout
### BQ tables
Summary and per-segment BigQuery tables were copied from the pipeline output.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_summary_temp`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1
      AND _processed_at BETWEEN UNIX_MICROS("2026-06-22T00:00:00Z") AND UNIX_MICROS("2026-06-23T23:00:00Z"))
```
This generated a table with 20895694 entries.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_segments_temp` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1
      AND _processed_at BETWEEN UNIX_MICROS("2026-06-22T00:00:00Z") AND UNIX_MICROS("2026-06-23T23:00:00Z"))
```
This generated a table with 2931415488 entries.

The _processed_at between statement is likely unnecessary, but I didn't clear the `trajectory_cocip_prod` table myself befoer the run, so just trying to be certain we only get data from this run.


#### Dedupe BQ tables
The following two queries were executed to dedupe the segments table and the summary table.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_summary` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_summary_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 20886689 entries.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_segments` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_segments_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 2929354948 entries. 

Both deduplicated tables dropped less than 1% of entries.

### Logs 

Copied logs for the TWJF, TW, and TW-Backup:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2022_run_jun2026/tw-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2022_run_jun2026/tw-backup-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2022_run_jun2026/twjf-logs/
```

There are NO LOGS in the `gs://contrails-301217-fp-prod-trajectory-worker-job-factory` bucket!
When I removed the logs from the 2021 run, it appeared that I also accidentally removed the bucket (it disappeared from view in the GCS web console). So I re-created the bucket. That had the unintended effect of removing the Storage Object Creator role for the logging sink service account such that the log sink for that bucket stopped working.

To fix, copied logs out of the log explorer:

```shell
gcloud logging copy _Default storage.googleapis.com/contrails-301217-fp-prod-trajectory-worker-job-factory --location=global --log-filter='resource.type="k8s_container" AND resource.labels.project_id="contrails-301217" AND resource.labels.location="us-east1" AND resource.labels.cluster_name="contrails-gke-general" AND resource.labels.namespace_name="flights-pipeline-prod" AND labels.k8s-pod/app="trajectory-worker-job-factory" AND severity>="INFO" AND timestamp > "2026-06-22T00:00:00Z"'
```

Now I can copy those logs to their final home:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2022_run_jun2026/twjf-logs/
```

And clean up the log sink buckets in preparation for the 2023 run:

```shell
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/*
```