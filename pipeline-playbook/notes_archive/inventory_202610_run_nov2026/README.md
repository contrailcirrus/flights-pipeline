# Inventory 2026 October (run: Nov 2026)

## Setup

### Job ID compilation
Created a new Job ID table for October using the following BQ query:

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_202610_run_nov2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2026-09-30T00:00:00" AND "2026-10-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2026-10-01T00:00:00"),
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

The job table has 3,493 entries with no null or zero-length `flight_id_list`s.

Created the job lists with `SELECT job_id FROM `contrails-301217.flights_pipeline_prod.inventory_202610_run_nov2026_jobs`;`, exporting the result as CSV, removing the column name top row, and changing the file name to `202610_job_id_list.txt`.

### Hyperdisk Setup

The 2026 October ERA5 met data was put into the standard GCP bucket `gs://contrails-301217-ecmwf-era5-zarr-v2-staging` using the `copy_era5_gcs_to_staging.sh` script.  This dataset includes zarr stores from 2026-09-30 through 2026-11-02:

```shell
./copy_era5_gcs_to_staging.sh 2026-09-30 2026-11-02 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```


To create the hyperdisk, we used the existing [GCSDataSource](../../pre_process/hyperdisk-setup/gcs-era5-zarr-data-source.yaml) and a new [PVC](../../pre_process/era5-zarr-gcs-pvc-useast4c_1month.yaml) for a 1-quarter dataset, opting to start the disk with 600MB/s bandwidth referencing the `hyperdiskml-useast4c-storage-class.yaml` storage class and and planning to scale bandwidth up.

Created the hyperdisk with:

```shell
kubectl apply -f era5-zarr-gcs-pvc-useast4c_1month.yaml -n flights-pipeline-prod
```

### Warm the GCS Spire Cache

On a VM, check out the `flights-pipeline` repo, and navigate to the `spire-cache-heater` subdirectory.

Set the `CACHE_START` and `CACHE_END` variables in the `main.py` file, and skip existing cached entries:

```python
# USER DEFINED
# SET START AND END TIME (INCLUSIVE) FOR CACHE WARMING
CACHE_START = "2026-09-30T00"  # hour resolution
CACHE_END = "2026-11-02T00"  # hour resolution
SKIP_EXISTING = True  # skip any hours where a pq file is found in GCS already
```

Activate the environment for the cache heater:

```shell
source .venv/bin/activate
source .env
python main.py 2>&1 | tee 202610_cache_warming.log &
```

All date/hours already warmed.

### Truncate results table

The results table contained only 2026 Q3 results.

Truncating the results table before the runs:

```sql
TRUNCATE TABLE `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`;
```

## Update `main` branch

There were some outstanding changes that had not made it to `main` for the 2026 Q1,Q2,Q3 runs that needed to be merged in documented in PR #711. That includes some logging fixes, updates to BQ to Postgres, fixes for output protobufs, and some small bug fixes. 

Unfortunately, the GitHub Actions deployments all just failed due to some issue in the gcloud auth. It's weird because it works for other pieces of the GHA pipeline - the image built and pushed without issue. But the helm deploy failed. I was able to run the helm deploy locally without issue though. Not sure what the issue is, but it seems tied to the github action, not the tooling or auth itself.

## October Run
```text
Started run at 19:24 UTC on 2026-11-12.

On my laptop, I changed the `pipeline-cli/services.py` file to point to the production TWJF PubSub queue `projects/contrails-301217/topics/prod-fp-twjd-ingress`, then ran:
```

```shell
./cli.py jobworker submit -j /Users/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_202610_run_nov2026/202610_job_id_list.txt -l inventory_202610_run_nov2026_jobs -w gcs -s era5 -t > 202610_cli_run.log 2>&1
```

```text
Noted appropriate TWJF logs. Seeing TWJF and TW message queues building.Scaling TWJF to 200 workers.
```

```text
19:30 UTC cli finished - all jobs published to TWJF queue.
```


```text
Requested hyperdisk bandwidth:  120000MB/s 19:56 UTC.

I'm seeing a new-to-me setting: "Access mode" which was set to "Single VM read-write", which is counter to how it's set in the PVC yaml file where it is set to "ReadOnlyMany". I couldn't change to read only many at the same time as updating bandwidth though.
```

```
text
Bumped TWJF up to 500 workers @ 19:58 UTC.
```

```text
Spinning up one c3dhighcpu90 node to start in on TW and get hyperdisk scaling request in. 20:07 UTC.
```


```text
Couldn't create pods with issues attaching to the hyperdisk while the bandwidth was updating again. Once it was done, the disk was changed to read-only-many mode, and the pod created and started picking up and running TW jobs.
```


```text
20:28 UTC:

Going up to 55 nodes. Scaling to 4700 TW workers.
```

```text
20:45 UTC: TWJF done. Scaled workers back to 1.

No TWJF dead lettered messages.
```



```text
20:54 UTC

All nodes up and running and seems to be going smoothly. Using only ~60GB/s of 120GB/s allocated. ~5.8 acks/min/CPU (not per worker).

Going very fast in spite of low bandwidth use.
```

```text
21:02 UTC.
A little overhead available, so adding 60 more TW workers to 4760 workers.
```


```text
TW finished around 22:30 UTC.
TW Backup queue empty. TW backup deadletter empty.

Everything smooth and fast on only a month.

TW replicas auto scaled to 1; set max replicas to 1 as well. Scaling nodes to 0. Removed PVC/hyperdisk.

Hyperdisk bandwidth peaked around 74GB/s. So  maybe for these one-month runs, lower bandwidth is sufficient. This ran through at > 5acks/min/cpu.
```


## Closeout
### BQ tables
Summary and per-segment BigQuery tables were copied from the pipeline output.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_202610_run_nov2026_summary_temp`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1)
```
This generated a table with 2,748,674 entries.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_202610run_nov2026_segments_temp` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1)
```
This generated a table with 397,380,914 entries.

Did not use a `_processed_at` statement in the temp table generation, since I cleared the `trajectory_cocip_prod` table myself before the run.


#### Dedupe BQ tables
The following two queries were executed to dedupe the segments table and the summary table for the Q1 results.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_202610_run_nov2026_summary` 
PARTITION BY DATE(time_start) AS (
  SELECT *  
    FROM `contrails-301217.flights_pipeline_prod.inventory_202610_run_nov2026_summary_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 2,707,200 entries, over a 1.5% drop. Not sure why so much more than past runs. Perhaps it's all concentrated at the edges and this being so much smaller a dataset has a higher proportion near the edges? No - the 2026Q3 dataset only drops about 4k entries, rather than over 40k. Looking at the results, I see that there are lots of instances of multiple counts of the same result (same processed at time etc). No idea why that's happening.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_202610_run_nov2026_segments` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_202610_run_nov2026_segments_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 391,266,884 rows. Again, about a 1.5% drop.

### Logs 

Copied logs for the TWJF, TW, and TW-Backup for Q3 run:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/11/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_202610_run_nov2026/twjf-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/2026/11/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_202610_run_nov2026/tw-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/2026/11/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_202610_run_nov2026/tw-backup-logs/
```

And clean up the log sink buckets in preparation for the the Nov. run:

```shell
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/*
```

#### Loading logs to BQ

Updated the `bq_load_*_logs.sh` scripts to set the log source prefix for the new data run (in `gs://contrails-301217-flights-pipeline-prod/logs/inventory_202610_run_nov2026`) as well as the destination table for the new run (`flights_pipeline_prod.logs_inventory_202610_run_nov2026`). Removed the `--max_bad_records` flag from the `bq load` command.

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
./bq_load_twjf_logs.sh 2>&1 | tee logs/bq_load_twjf_logs_202610_run_nov2026.log
./bq_load_tw_logs.sh 2>&1 | tee logs/bq_load_tw_logs_202610_run_nov2026.log 
./bq_load_tw_backup_logs.sh  2>&1 | tee logs/bq_load_tw_backup_logs_202610_run_nov2026.log
```

All logs loaded to the `flights_pipeline_prod.logs_inventory_202610_run_nov2026` BQ table.


### Clean up ERA5 staging bucket

Remove data from the ERA5 staging bucket so it is empty and ready for the next run.

```shell
gsutil -m rm -r gs://contrails-301217-ecmwf-era5-zarr-v2-staging/*
```