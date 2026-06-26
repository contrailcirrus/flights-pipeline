# Inventory 2021 (run: June 2026)

## Job ID compilation
```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2020-12-31T00:00:00" AND "2021-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2021-01-01T00:00:00"),
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

## Run

Note: spire cache confirmed to be warm for 2021 ADS-B in previous 2020 prod run.

```text
TWJD submit
06/06/19 15:13UTC
notes: completed at 15:53UTC; see below; DONE @ 16:40UTC
```

The job-id based TWJDs in the `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_jobs` table 
were submitted starting at ``.  See the [job-id list](2021_job_id_list.txt).  The flights referenced by those 
ids total `22,428,707`.

Executed on VM: `./cli.py jobworker submit -j /home/nickmasson/flights-pipeline/pipeline-playbook/notes_archive/inventory_2021_run_jun2026/2021_job_id_list.txt -l inventory_2021_run_jun2026_jobs -w gcs -s era5 -t > 2020_run.log 2>&1`.

NOTE: accidentally ran the `2021_job_id_list.txt` when the CSV header was still in the text file. As a result, the string literal `"job_id"` was submitted as a `job_id` value in one of the TWJDs. 
The TWJF gracefully steps over and ack's this bad message.  Noting it here, regardless, as we should expect one ERROR level log in the TWJF logs with message `"permanently failed to process twjd - acking msg"` and `twjd.job_id: "job_id"`. 

```bash
{"timestamp":"2026-06-19 15:51:32,789", "severity": "INFO", "textPayload": "🛠️published job_id 22501 of 22790", "labels":{"pid":"2558"}}
{"timestamp":"2026-06-19 15:51:42,965", "severity": "INFO", "textPayload": "🛠️published job_id 22601 of 22790", "labels":{"pid":"2558"}}
{"timestamp":"2026-06-19 15:51:53,143", "severity": "INFO", "textPayload": "🛠️published job_id 22701 of 22790", "labels":{"pid":"2558"}}
{"timestamp":"2026-06-19 15:52:01,288", "severity": "INFO", "textPayload": "🛠️published job_id 22790 of 22790", "labels":{"pid":"2558"}}
{"timestamp":"2026-06-19 15:52:01,288", "severity": "INFO", "textPayload": "⏲️ waiting for publish to finish...", "labels":{"pid":"2558"}}
{"timestamp":"2026-06-19 15:52:02,395", "severity": "INFO", "textPayload": "🙌 DONE!", "labels":{"pid":"2558"}}
```

```text
TWJF scale up
06/06/19 15:15UTC
notes: scale TWJF to 1000 replicas
```

```text
Scale node pool & TW
06/06/19 15:22UTC
notes: scale c3d-highcpu-90 qty 40; scale TW to 7030.
```

```text
Scale hyperdisk
06/06/19 17:15->17:35UTC
notes: scale hyperdisk to 152,400 mbps
```


```text
Scale node pool & TW
06/06/19 17:45UTC
notes: scale c3d-highcpu-90 qty 60; scale TW to 10,540.
```

```text
Scale node pool & TW
06/06/19 17:45UTC
notes: hyperdisk increase didn't extend IO availability. scale c3d-highcpu-90 qty 50; scale TW to 8785.
```

```text
Update TW & reconfig node pool
06/06/19 22:05UTC
notes: redeploy TW with 1vcpu/worker; scale down c3d-highcpu-90; scale up c4d-highcpu-192 qty 22; scale TW to ~4100. job rate ~500/sec.
```

```text
scale node pool & TW
06/06/19 22:35UTC
notes: scale down c4d-highcpu-192 to qty 12; scale up c3d-highcpu-90 qty 50; scale TW to 5,270 (recall vcpu now at 1/worker). 
```

```text
scale node pool & TW
06/06/19 22:50UTC
notes: scale down c4d-highcpu-192 to zero; scale TW to 4380.
```

```text
DONE. Scale down node pool; TW; hyperdisk
06/06/20 05:50UTC
notes: scale down TW; scale node pool to zero; remove hyperdisk/PVC.
```

## Closeout

Summary and per-seg tables were copied from the pipeline output.  Note that no time range subsetting was performed, 
as the BQ table was purged prior to the run.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_summary`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1)
```

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_segments` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1)
```

#### Dedupe BQ tables
The following two queries were executed to dedupe the segments table and the summary table.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_summary` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_summary`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_segments` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_segments`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```

### Notes

### Logs 

Copied logs for the TWJF, TW, and TW-Backup:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/tw-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/tw-backup-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/
```

Cleaned up the log sink buckets in preparation for the 2022 run:

```shell
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/*
```

#### Loading logs to BQ

Updated the `bq_load_*_logs.sh` scripts to set the log source prefix for the new data run as well as the destination table for the new run. The `max_bad_records` flag for `bq load` was removed to ensure we would see any non-conformant logs.

Ran scripts:

```shell
./bq_load_twjf_logs.sh 2>&1 | tee bq_load_twjf_logs_2021_run_june2026.log
```
Error in loading logs: Only optional fields can be set to NULL. Field: airline_iata;

Investigating, it looks like this is the problematic block:

```json
        "airline_iata": [
            null
        ],
```
Deleting the logs BQ table, putting back in `--max_bad_records=40`:

```shell
./bq_load_twjf_logs.sh 2>&1 | tee bq_load_twjf_logs_2021_run_june2026.log
Waiting on bqjob_r75105cd1384be542_0000019efac9f96b_1 ... (15s) Current status: DONE   
Waiting on bqjob_r1560e36878110443_0000019efaca44f7_1 ... (15s) Current status: DONE   
Waiting on bqjob_r4afab5d2326799df_0000019efaca8c0c_1 ... (15s) Current status: DONE   
Waiting on bqjob_r3b8f81f99db2825d_0000019efacad500_1 ... (15s) Current status: DONE   
Waiting on bqjob_r4e80c4d2788decb8_0000019efacb1c79_1 ... (15s) Current status: DONE   
Waiting on bqjob_r1bd4af82297a14a2_0000019efacb6464_1 ... (10s) Current status: DONE   
Waiting on bqjob_r3f6924534eaf71fd_0000019efacb973d_1 ... (15s) Current status: DONE   
Waiting on bqjob_r3c3023c9f7accb42_0000019efacbdf7f_1 ... (15s) Current status: DONE   
Waiting on bqjob_r789a0cecaaf663eb_0000019efacc25f4_1 ... (15s) Current status: DONE   
Waiting on bqjob_r57997a0853d5aa8b_0000019efacc6cb3_1 ... (15s) Current status: DONE   
Waiting on bqjob_r31f509efb9f9ddec_0000019efaccb32e_1 ... (15s) Current status: DONE   
Waiting on bqjob_r34ef323c9cccb031_0000019efaccf9ee_1 ... (15s) Current status: DONE   
Waiting on bqjob_r3efe9ff0a72b2bd_0000019efacd41d9_1 ... (15s) Current status: DONE   
Waiting on bqjob_r70010ab7b45599c4_0000019efacd8944_1 ... (15s) Current status: DONE   
Waiting on bqjob_r57e48108d2b29bed_0000019efacdd084_1 ... (15s) Current status: DONE   
Waiting on bqjob_rc038fab5737c44c_0000019eface174c_1 ... (15s) Current status: DONE   
Waiting on bqjob_r179f826cb13f1e7f_0000019eface5e9c_1 ... (15s) Current status: DONE   
Warnings encountered during job execution:

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json] Error while reading data, error message: JSON parsing error in row starting at position 1684206961: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json] Error while reading data, error message: JSON parsing error in row starting at position 1686732307: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json] Error while reading data, error message: JSON parsing error in row starting at position 1690899339: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json'

Waiting on bqjob_r198ddaa2bc76109d_0000019efacea529_1 ... (15s) Current status: DONE   
Waiting on bqjob_r4cbbb3a565e0ffc5_0000019efaceebfa_1 ... (15s) Current status: DONE   
Waiting on bqjob_r662db9651518eaf_0000019efacf3353_1 ... (15s) Current status: DONE   
Waiting on bqjob_r482e77841412552e_0000019efacf7a04_1 ... (15s) Current status: DONE   
Waiting on bqjob_r7e53983d8a8b904a_0000019efacfc21d_1 ... (15s) Current status: DONE   
Waiting on bqjob_r258a94a4b52dad35_0000019efad0096b_1 ... (15s) Current status: DONE   
Waiting on bqjob_r7ebd1b6493b8a299_0000019efad050fa_1 ... (15s) Current status: DONE   
Warnings encountered during job execution:

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3230540387: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3253504163: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3273068748: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3297060304: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

Waiting on bqjob_r494d4ead94ec3e73_0000019efad09877_1 ... (15s) Current status: DONE   
Warning encountered during job execution:

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S9.json] Error while reading data, error message: JSON parsing error in row starting at position 1921641989: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S9.json'
```

And the rest of the logs (without max_bad_records).

```shell
./bq_load_tw_logs.sh 2>&1 | tee bq_load_tw_logs_2021_run_june2026.log 
./bq_load_tw_backup_logs.sh  2>&1 | tee bq_load_tw_backup_logs_2021_run_june2026.log
```

The rest of the logs loaded without error to the `flights_pipeline_prod.logs_inventory_2021_run_june2026` BQ table.

## Dead-lettered jobs
No deadlettered TW or TWBU jobs observed. No TWJF deadlettered jobs.