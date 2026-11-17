# Inventory 2026 Q1, Q2 (run: Sept 2026)

## Setup

### Job ID compilation
Created a new Job ID table for Q1, Q2 using the following BQ query:

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2025-12-31T00:00:00" AND "2026-03-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2026-01-01T00:00:00"),
     job_grp_tb AS (SELECT *,
                           SUBSTR(TO_HEX(SHA256(CONCAT(
                                   CAST(CAST(0.001 * ROW_NUMBER() OVER (PARTITION BY day_bin ORDER BY min_ts) AS INT64) AS STRING),
                                   CAST(day_bin AS STRING)))), 1, 32) AS job_id
                    FROM target_tb),
     agg_tb AS (SELECT job_id,
                       ARRAY_AGG(day_bin)   AS day_bin_arr,
                       ARRAY_AGG(flight_id) AS flight_id_list
                FROM job_grp_tb
                WHERE flight_id IS NOT NULL
                GROUP BY job_id)
SELECT job_id, FORMAT_DATE('%Y-%m-%d', ARRAY_FIRST(day_bin_arr)) AS day, flight_id_list
FROM agg_tb
```

With the table name changed for Q2 and Q3 with the following changes:
* Q2: timestamp range `BETWEEN "2026-03-31T00:00:00" AND "2026-06-30T23:59:59"` and `min_ts >= "2026-04-01T00:00:00"`

Q1 jobs table has 9577 entries with no null or zero length `flight_id_list`s.
Q2 jobs table has 10065 entries with no null or zero length `flight_id_list`s.

I created the job lists with e.g. `SELECT job_id FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_jobs`;`, exporting the result as CSV, removing the column name top row, and changing the file name to `2026Q1_job_id_list.txt`.

### Hyperdisk Setup

The 2026 Q1 ERA5 met data was put into the standard GCP bucket `gs://contrails-301217-ecmwf-era5-zarr-v2-staging` using the `copy_era5_gcs_to_staging.sh` script.  This dataset includes zarr stores from 2025-12-31 through 2026-04-02:

```shell
./copy_era5_gcs_to_staging.sh 2025-12-31 2026-04-02 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```

The 2026-04-02 data was not copied by the script for some reason. I manually copied it afterward.

To create the hyperdisk, we used the existing [GCSDataSource](../../pre_process/hyperdisk-setup/gcs-era5-zarr-data-source.yaml) and a new [PVC](../../pre_process/era5-zarr-gcs-pvc-useast4c_1quarter.yaml) for a 1-quarter dataset, opting to start the disk with 600MB/s bandwidth referencing the `hyperdiskml-useast4c-storage-class.yaml` storage class and and planning to scale bandwidth up.

After the Q1 run, I removed all data in the `gs://contrails-301217-ecmwf-era5-zarr-v2-staging/` bucket by running a rm command on a VM:

```shell
gsutil -m rm -R "gs://contrails-301217-ecmwf-era5-zarr-v2-staging/*"
```

Then copied data in with:

```shell
./copy_era5_gcs_to_staging.sh 2026-03-31 2026-07-02 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```

This time, the final day was copied, and I see data from 2026-03-31 through and including 2026-07-02 in the staging bucket.

Created the hyperdisk with:

```shell
kubectl apply -f era5-zarr-gcs-pvc-useast4c_1quarter.yaml -n flights-pipeline-prod
```

### Truncate results table

Truncating the results table before the runs:

```sql
TRUNCATE TABLE `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`;
```

## Q1 Run
```text
Started run at 15:45 UTC on 2026-09-24.

On my laptop, I changed the `pipeline-cli/services.py` file to point to the production TWJF PubSub queue `projects/contrails-301217/topics/prod-fp-twjd-ingress`, then ran:
```

```shell
./cli.py jobworker submit -j /Users/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_2026Q1Q2_run_sept2026/2026Q1_job_id_list.txt -l inventory_2026Q1_run_sept2026_jobs -w gcs -s era5 -t > 2026Q1_cli_run.log 2>&1
```

```text
Noted appropriate TWJF logs. Seeing TWJF and TW messages start to accumulate. Scaling TWJF to 10 workers at 16:01 UTC.
```

```text
Scaled  TWJF to 500 workers, since I see over 6k messages in the TWJF queue.
```

```text
12:15 UTC cli finished - all jobs published to TWJF queue.

Spinning up one c3dhighcpu90 node to start in on TW and get hyperdisk scaling request in.
```


```text
12:23 UTC - scaling TW to 87 replicas.
```

```text
CLI finished at 16:15 UTC.
```

```text
Requesting Hyperdisk bandwidth increase to 120000MB/s at 16:31 UTC.
```

```text
Hyperdisk bandwidth updated at 16:54 UTC:

Successfully updated disk "pvc-1fcf371c-ae2f-4b03-956e-10a3187ebb85".
```

```text
16:56 UTC:
Scaling up nodes to 40, and workers to 3360.
```

```text
TWJF finished around 17:52 UTC. 

No TWJF dead letter messages. No error logs - warnings all for resuming from a previous job (142 times).
```

```text
18:52 UTC: hyperdisk bandwidth about 83GB/s. Retiring around 4.1 jobs/min/worker.
```

```text
19:29 UTC. Scaling up to 55 nodes, 4650 workers.
```

```text
19:48 UTC
Now up to 115GB/s hyperdisk usage - that's about as good as I can reasonably hope for, I think.

Retiring 4.06 jobs/min/CPU (using total node CPUs, not workers). So doing quite well.
```

```text
19:35UTC
Bumping TW workers up to 4720, because there seeemed to be substantial overhead in the cluster.
```

```text
20:53 UTC
Scaling up to 4770 workers, because there seemed to still be overhead.
```

```text
Around 00:30 UTC on 2026-09-25, got 160GB/s bandwidth with around 650k messages left in the TW queue. Bumped up to 70 90-core nodes and 6050 workers. Ack rate dropped to around 3.7 acks/min/CPU.

Only using about 144GB/s bandwidth, so maybe more CPUs will help? But maybe saturation is lower with these nodes.

Bumping up to 6150 bumped it up to 3.9 acks/min/cpu, so that's better, but probably approaching saturation. Seems like < 150GB/s for the hyperdisk with these c3dhighcpu90 nodes.
```

```text
TW finished around 00:57 UTC.
TW Backup queue empty.

Everything seemed smooth.

TW replicas auto scaled to 1; set max replicas to 1 as well. Scaling nodes to 0. Removed PVC/hyperdisk.
```

## Q2 Run
Log sink buckets all cleared out before beginning.

```text
Started run at 14:54 UTC on 2026-09-25.
```

```shell
./cli.py jobworker submit -j /Users/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_2026Q1Q2_run_sept2026/2026Q2_job_id_list.txt -l inventory_2026Q2_run_sept2026_jobs -w gcs -s era5 -t > 2026Q2_cli_run.log 2>&1
```

```text
Noted appropriate TWJF logs. Seeing TWJF and TW messages start to accumulate. Scaling TWJF to 10 workers at 16:01 UTC.
```

```text
Scaled  TWJF to 500 workers, since I see several k messages in the TWJF queue.
```

```text
Since the data copy to the hyperdisk topped out at 999GB for a nominal 1TiB disk, I was a little worried about size. Inspecting the mounted drive in the inspector pod, I see it's well below 1TiB:

935.2G  ./ecmwf-zarr-v2
```

```text
15:13 UTC: cli done.
```

```text
15:21 UTC: requesting Hyperdisk ML bandwidth increase to 150000 MB/s.
```

```text
15:22 UTC:
Spinning up one c3dhighcpu90 node to start in on TW and ensure configuration is correct (changed yaml back to add volume mounts).

All good - logs good, single pod in good state in both TW and TW-BU.
```

```text
15:31 UTC
Spinning up to 65 c3dhighcpu90 nodes and 5710 pods to get going.
```

```text
16:09 UTC
After some warm up time, only using a bit over 110 GB/s bandwidth and hitting low acks at about 3.6/min/cpu.

Bump up to 70 nodes and 6100 workers.
```

```text
17:32 UTC
Still low bandwidth utilization around 116GB/s. Bumping up workers substantially with 84 nodes and 7350 workers.
```

```text
17:30UTC
This didn't really help. Only took bandwidth up to about 130GB/s. Only about 390 acks/s, or 3.0 acks/min/cpu.

Scaling back down to 70 nodes, 6100 workers.
```

```text
TWJF finished around 17:25 UTC. 

No TWJF dead letter messages. Only error logs were from skipped flights (141).
```

```text
If this is some sort of scaling limitation we might expect there to be an uptick in acks/min/worker (not per cpu) if I drop the number of workers leaving the number of CPUs constant. Will try to drop down to 5200 workers to see.

This dropped bandwidth usage barely from 122GB/s to 120 GB/s and overall ack rates from 375/s to 365/s, but acks/min/worker went up from 3.7 to 4.2. I think we're seeing bandwidth per node capped, and that's the limiter here. So maybe I'll try to add in some smaller machines.

The c3d-highcpu-30 have higher Tier1 egress/core by 66% and the same default egress bandwidth per core. Will try some of those.

Stepping back c3d90s to 30 nodes and 2600 workers.
Adding 90 c3d30 nodes to get another 2600 workers.
This keeps me at 5200 workers for now, just shifts what nodes they are on.
```

```text
18:26 UTC
I don't think this really helped - bandwidth is the same, but acks are slightly lower. There are also >50 unschedulable containers - I think the overhead per node is relatively the same regardless of how many cores it provides, so maybe that's a problem here. Ultimately that reduction in workers essentially accounts for the lower acks/s of 350. Maybe I should try higher CPU/node nodes?

Swapping 90 c3d-highcpu-30s for 15 c4d-highcpu-192s.

That lowered both bandwidth usage (95GB/s) and ack rate (330 acks/s).
```

```text
19:00 UTC:

Swapping back to 70 c3d-highcpu-90s with 6100 workers.

That took things pretty much back to where they were, but mabye a little bit lower throughput. It seems like performance is just generally more meager today. Maybe a difference in dataset, maybe in GCP infrastructure load in us-east4?
```

```text
22:46 UTC: jobs all done.

backup empty, nothing in backup deadletter.

Removing nodes and Hyperdisk.
```


```text
TW finished around 00:57 UTC.
TW Backup queue empty.

Everything seemed smooth.

TW replicas auto scaled to 1; set max replicas to 1 as well. Scaling nodes to 0. Removed PVC/hyperdisk.
```


## Closeout
### BQ tables
Summary and per-segment BigQuery tables were copied from the pipeline output.

#### 2026Q1
```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_summary_temp`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1)
```
This generated a table with 7,340,482 entries.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_segments_temp` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1)
```
This generated a table with 1,071,596,350 entries.

Did not use a `_processed_at` statement in the temp table generation, since I cleared the `trajectory_cocip_prod` table myself before the run.

#### 2026Q2
```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_summary_temp`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1)
```
This generated a table with 7,650,462 entries.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_segments_temp` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1)
```
This generated a table with 1,095,583,454 entries.

Did not use a `_processed_at` statement in the temp table generation, since I cleared the `trajectory_cocip_prod` table myself before the run.


#### Dedupe BQ tables
The following two queries were executed to dedupe the segments table and the summary table for the Q1 results.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_summary` 
PARTITION BY DATE(time_start) AS (
  SELECT *  
    FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_summary_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 7,336,778 entries, less than 1% drop.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_segments` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_segments_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 1,070,722,762 rows. Less than a 1% drop.


The following two queries were executed to dedupe the segments table and the summary table for the Q2 results.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_summary` 
PARTITION BY DATE(time_start) AS (
  SELECT *  
    FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_summary_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 7,643,105 entries. Less than a 1% drop. 

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_segments` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_segments_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 1,094,195,411 entries. Less than a 1% drop.


### Logs 

Copied logs for the TWJF, TW, and TW-Backup for Q1 run:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/09/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q1_run_sept2026/twjf-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/2026/09/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q1_run_sept2026/tw-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/2026/09/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q1_run_sept2026/tw-backup-logs/
```

And clean up the log sink buckets in preparation for the Q2 run:

```shell
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/*
```

After the Q2 run, copied logs and cleand up:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/09/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q2_run_sept2026/twjf-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/2026/09/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q2_run_sept2026/tw-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/2026/09/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q2_run_sept2026/tw-backup-logs/

```

And clean up the log sink buckets in preparation for the Q2 run:

```shell
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/*
```
#### Loading logs to BQ

Updated the `bq_load_*_logs.sh` scripts to set the log source prefix for the new data run (in `gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q1_run_sept2026`) as well as the destination table for the new run (`flights_pipeline_prod.logs_inventory_2026Q1_run_sept2026`). Removed the `--max_bad_records` flag from the `bq load` command. This led me to discover a bit of an edge case in the TWJF logging where the `airline_iata` field isn't set on resuming a job leading to a non-conformant log. Rather that fix those in the Q1 and Q2 logs, I decided to skip those messages, implement a fix for Q3 onward and re-instate the `max_bad_records` flag set to 80. The most issues was 51 in one log file.

Ran scripts:
```shell
./bq_load_twjf_logs.sh 2>&1 | tee bq_load_twjf_logs_2026Q1_run_sept2026.log
./bq_load_tw_logs.sh 2>&1 | tee bq_load_tw_logs_2026Q1_run_sept2026.log 
./bq_load_tw_backup_logs.sh  2>&1 | tee bq_load_tw_backup_logs_2026Q1_run_sept2026.log
```

All logs loaded to the `flights_pipeline_prod.logs_inventory_2026Q1_run_sept2026` BQ table.

Next, I updated the same log load scripts for the Q2 run and ran:

```shell
./bq_load_twjf_logs.sh 2>&1 | tee bq_load_twjf_logs_2026Q2_run_sept2026.log
./bq_load_tw_logs.sh 2>&1 | tee bq_load_tw_logs_2026Q2_run_sept2026.log 
./bq_load_tw_backup_logs.sh  2>&1 | tee bq_load_tw_backup_logs_2026Q2_run_sept2026.log
```

I had to adjust the `max_bad_records` in the TWJF log load script to 140, because there were quite a few bad records with some files having 108, 110, 122, 133 bad records. Not sure why there were so many restarts in this run.

All logs loaded to the `flights_pipeline_prod.logs_inventory_2026Q2_run_sept2026` BQ table.