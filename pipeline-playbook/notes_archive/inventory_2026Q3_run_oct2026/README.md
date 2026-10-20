# Inventory 2026 Q3 (run: Oct 2026)

## Setup

### Job ID compilation
Created a new Job ID table for Q3 using the following BQ query:

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2026-06-30T00:00:00" AND "2026-09-30T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2026-07-01T00:00:00"),
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

The job table has 10,769 entries with no null or zero-length `flight_id_list`s.

Created the job lists with `SELECT job_id FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_jobs`;`, exporting the result as CSV, removing the column name top row, and changing the file name to `2026Q3_job_id_list.txt`.

### Hyperdisk Setup

The 2026 Q3 ERA5 met data was put into the standard GCP bucket `gs://contrails-301217-ecmwf-era5-zarr-v2-staging` using the `copy_era5_gcs_to_staging.sh` script.  This dataset includes zarr stores from 2026-06-30 through 2026-10-02:

```shell
./copy_era5_gcs_to_staging.sh 2026-06-30 2026-10-02 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```


To create the hyperdisk, we used the existing [GCSDataSource](../../pre_process/hyperdisk-setup/gcs-era5-zarr-data-source.yaml) and a new [PVC](../../pre_process/era5-zarr-gcs-pvc-useast4c_1quarter.yaml) for a 1-quarter dataset, opting to start the disk with 600MB/s bandwidth referencing the `hyperdiskml-useast4c-storage-class.yaml` storage class and and planning to scale bandwidth up.

Created the hyperdisk with:

```shell
kubectl apply -f era5-zarr-gcs-pvc-useast4c_1quarter.yaml -n flights-pipeline-prod
```

### Warm the GCS Spire Cache

On a VM, check out the `flights-pipeline` repo, and navigate to the `spire-cache-heater` subdirectory.

Set the `CACHE_START` and `CACHE_END` variables in the `main.py` file, and skip existing cached entries:

```python
# USER DEFINED
# SET START AND END TIME (INCLUSIVE) FOR CACHE WARMING
CACHE_START = "2026-06-30T00"  # hour resolution
CACHE_END = "2026-10-02T00"  # hour resolution
SKIP_EXISTING = True  # skip any hours where a pq file is found in GCS already
```

Make and activate an environment for the cache heater:



```shell
python3 -m venv .venv
source .venv/bin/activate
pip install pipenv
pipenv sync
source .env
python main.py 2>&1 | tee 2026Q3_cache_warming.log &
./main.py
```

Only the removed 2026-09-27 hours needed to be warmed, since I removed the cache after patching in the data Spire sent after service breakdown for several hours on 2026-09-27.

### Truncate results table

The results table contained only 2026 Q2 results.

Truncating the results table before the runs:

```sql
TRUNCATE TABLE `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`;
```

## Q3 Run
```text
Started run at 13:46 UTC on 2026-10-14.

On my laptop, I changed the `pipeline-cli/services.py` file to point to the production TWJF PubSub queue `projects/contrails-301217/topics/prod-fp-twjd-ingress`, then ran:
```

```shell
./cli.py jobworker submit -j /Users/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_2026Q3_run_oct2026/2026Q3_job_id_list.txt -l inventory_2026Q3_run_oct2026_jobs -w gcs -s era5 -t > 2026Q3_cli_run.log 2>&1
```

```text
Noted appropriate TWJF logs. Seeing TWJF and TW message queues building.Scaling TWJF to 500 workers at 13:55 UTC.
```

```text
Requested hyperdisk bandwidth:  120000MB/s 13:56 UTC.
```

```text
Spinning up one c3dhighcpu90 node to start in on TW and get hyperdisk scaling request in. 13:57 UTC.
```


```text
14:12 UTC... not sure what's going on; TWJF pods can't get disk access with error:

  Warning  FailedAttachVolume  2m                     attachdetach-controller  (combined from similar events): AttachVolume.Attach failed for volume "pvc-0cc393ec-93dc-478e-a01b-ac3ee359cf31" : rpc error: code = InvalidArgument desc = Failed to update access mode: failed waiting for op for zonal disk update for Key{"pvc-0cc393ec-93dc-478e-a01b-ac3ee359cf31", zone: "us-east4-c"}: rpc error: code = InvalidArgument desc = operation operation-1791986815903-65dcd719aa8db-a7437b2e-0b623f1c failed (INVALID_USAGE): Disk cannot be updated while there is an ongoing mutation.

It looks like maybe the hyperdisk bandwith increase request is getting in the way of mounting the disk. So I guess we'll see once the bandwidth increase has gone through.
```

```text
14:07 UTC cli finished - all jobs published to TWJF queue.
```


```text
14:26 UTC:

OK. The TW worker started up finally and seems to be processing jobs.

2M jobs in the TW queue. Time to spin up the number of nodes.
```

```text
14:40 UTC:

Going up to 55 nodes. Scaling to 4700 TW workers.
```

```text
15:04 UTC

All nodes up and running and seems to be going smoothly. Using 124GB/s of 120GB/s allocated, so quite well right now apparently. 4.96 acks/min/CPU (not per worker).

```

```text
15:12 UTC.

OK, hyperdisk utilization was perhaps overstated as it summed all peak bandwidths over a minute time frame, so spikes led to over max utilization. Looking just at bytes read summed over all, we get to 113 GB/s which makes more sense.

A little overhead available, so adding 50 more TW workers to 4750 workers.
```

``text
Scaled TWJF back to 250 workers because I wanted to make sure I was present when it finished.
```

```text
17:40 UTC: TWJF done. Scaled workers back to 1.

No TWJF dead lettered messages.
```

```text
18:00 UTC: Pushed TW workers up to 4770 because there seemed to be a few more resources available.

Still doing around 400 acks/s, and about 5M more TW messages in the queue, so about 5 hours left.
```




```text
Around 00:30 UTC on 2026-09-25, got 160GB/s bandwidth with around 650k messages left in the TW queue. Bumped up to 70 90-core nodes and 6050 workers. Ack rate dropped to around 3.7 acks/min/CPU.

Only using about 144GB/s bandwidth, so maybe more CPUs will help? But maybe saturation is lower with these nodes.

Bumping up to 6150 bumped it up to 3.9 acks/min/cpu, so that's better, but probably approaching saturation. Seems like < 150GB/s for the hyperdisk with these c3dhighcpu90 nodes.
```

```text
TW finished around 21:43 UTC.
TW Backup queue empty.

Everything seemed smooth.

TW replicas auto scaled to 1; set max replicas to 1 as well. Scaling nodes to 0. Removed PVC/hyperdisk.
```


## Closeout
### BQ tables
Summary and per-segment BigQuery tables were copied from the pipeline output.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_summary_temp`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1)
```
This generated a table with 8,336,794 entries.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_segments_temp` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1)
```
This generated a table with 1,208,460,060 entries.

Did not use a `_processed_at` statement in the temp table generation, since I cleared the `trajectory_cocip_prod` table myself before the run.


#### Dedupe BQ tables
The following two queries were executed to dedupe the segments table and the summary table for the Q1 results.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_summary` 
PARTITION BY DATE(time_start) AS (
  SELECT *  
    FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_summary_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 8,332,526 entries, less than 0.1% drop.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_segments` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_segments_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 1,207,539,513 rows. Less than a 0.1% drop.

### Logs 

Copied logs for the TWJF, TW, and TW-Backup for Q3 run:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/10/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q3_run_oct2026/twjf-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/2026/10/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q3_run_oct2026/tw-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/2026/10/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q3_run_oct2026/tw-backup-logs/
```

And clean up the log sink buckets in preparation for the Q3 run:

```shell
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/*
```

#### Loading logs to BQ

Updated the `bq_load_*_logs.sh` scripts to set the log source prefix for the new data run (in `gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q3_run_oct2026`) as well as the destination table for the new run (`flights_pipeline_prod.logs_inventory_2026Q3_run_oct2026`). Removed the `--max_bad_records` flag from the `bq load` command.

Now I noticed that I had never merged in the fix for the `airline_iata: [null]` logs from restarting a job. That fix was merged into `develop`, but never into the `main` branch, so it wasn't deployed and running. Oops! Instead of a few hundred issues, this time we had thousands for some reason. That led me to have Claude write a quick script to fix the logs:

* fix_repeated_nulls.jq
* fix_twjf_logs_gcs.sh

I ran the fix on my VM with:

```shell
$ ./fix_twjf_logs_gcs.sh gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q3_run_oct2026/twjf-logs gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q3_run_oct2026/twjf-logs-fixed
```

Now, after changing the `bq_load_twjf_logs.sh` script to point to logs in `gs://contrails-301217-flights-pipeline-prod/logs/inventory_2026Q3_run_oct2026/twjf-logs-fixed`, the log load ran smoothly.

Ran scripts:
```shell
./bq_load_twjf_logs.sh 2>&1 | tee bq_load_twjf_logs_2026Q3_run_oct2026.log
./bq_load_tw_logs.sh 2>&1 | tee bq_load_tw_logs_2026Q3_run_oct2026.log 
./bq_load_tw_backup_logs.sh  2>&1 | tee bq_load_tw_backup_logs_2026Q3_run_oct2026.log
```

All logs loaded to the `flights_pipeline_prod.logs_inventory_2026Q3_run_oct2026` BQ table.


### Clean up ERA5 staging bucket

Remove data from the ERA5 staging bucket so it is empty and ready for the next run.

```shell
gsutil -m rm -r gs://contrails-301217-ecmwf-era5-zarr-v2-staging/*
```