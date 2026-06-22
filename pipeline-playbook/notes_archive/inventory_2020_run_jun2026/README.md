# Inventory 2020 (run: June 2026)

## Job ID compilation
```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2019-12-31T00:00:00" AND "2020-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2020-01-01T00:00:00"),
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

## Hyperdisk-ML Met Data

Data were removed from the staging bucket `gs://contrails-301217-ecmwf-era5-zarr-v2/` using Lifecylce rules, then data copied in with 
```shell
./copy_era5_gcs_to_staging.sh 2019-12-31 2021-01-02 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```
Being sure to include the day before the year start, and two days after to allow both flights to bleed into the following day, but also contrail propagation from those flights to persist and evolve into Jan. 2nd of the following year.

Creating the hyperdisk involved setting up the PVC referencing the GCPDataSource which kicks off the custom GCP process to copy in all the data from the staging bucket:

```shell
kubectl apply -f hyperdiskml-useast4c-storage-class.yaml
```

The process takes about 5 hours for a year of ERA5 zarr stores.


## Run

Ran spire-cache-heater over 2020/01/01 -> 2021/01/02, with skip_existing=True. Confirmed that spire ADSB cache is already warm.

Also ran over 2021/01/01 -> 2024/01/02. Confirmed warm as well (thus will skip this step for the 2021, 2022 and 2023 runs).

```text
TWJD submit
06/18/2026 13:25UTC
notes: completed at 16:12UTC; see below
```

The job-id based TWJDs in the `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_jobs` table 
were submitted starting at ``.  See the [job-id list](2020_job_id_list.txt).  The flights referenced by those 
ids total `17,634,394`.

Executed on VM: `./cli.py jobworker submit -j /home/nickmasson/flights-pipeline/pipeline-playbook/notes_archive/inventory_2020_run_jun2026/2020_job_id_list.txt -l inventory_2020_run_jun2026_jobs -w gcs -s era5 -t > 2020_run.log 2>&1`.

```bash
{"timestamp":"2026-06-18 13:55:48,474", "severity": "INFO", "textPayload": "🛠️published job_id 17801 of 18002", "labels":{"pid":"1516"}}
{"timestamp":"2026-06-18 13:55:58,661", "severity": "INFO", "textPayload": "🛠️published job_id 17901 of 18002", "labels":{"pid":"1516"}}
{"timestamp":"2026-06-18 13:56:08,843", "severity": "INFO", "textPayload": "🛠️published job_id 18001 of 18002", "labels":{"pid":"1516"}}
{"timestamp":"2026-06-18 13:56:08,844", "severity": "INFO", "textPayload": "🛠️published job_id 18002 of 18002", "labels":{"pid":"1516"}}
{"timestamp":"2026-06-18 13:56:08,845", "severity": "INFO", "textPayload": "⏲️ waiting for publish to finish...", "labels":{"pid":"1516"}}
{"timestamp":"2026-06-18 13:56:09,935", "severity": "INFO", "textPayload": "🙌 DONE!", "labels":{"pid":"1516"}}
```

```text
Scale TWJF
06/18/2026 13:25UTC
notes: scale TWJF to 100 replicas
```

```text
Scale node pool and TW
06/18/2026 15:10UTC
notes: scale qty 1 c3d-highcpu-90; deploy TW at replica 10; TW-BU at replica 3
```

```text
Scale TWJF
06/18/2026 15:15UTC
notes: scale TWJF to 1000 replicas
```

```text
Scale node pool and TW
06/18/2026 15:18UTC
notes: scale qty 15 c3d-highcpu-90; deploy TW at replica 2630. job rate ~135-140 jobs/sec -> 3.1 jobs/worker/min
```

```text
Scale node pool and TW
06/18/2026 15:45UTC
notes: scale qty 30 c3d-highcpu-90; deploy TW at replica 5260. job rate ~260 jobs/sec -> 3 jobs/worker/min
```

```text
Scale node pool and TW
06/18/2026 16:12UTC
notes: scale qty 45 c3d-highcpu-90; deploy TW at replica 7890. job rate ~320 jobs/sec -> 2.5 jobs/worker/min
```

```text
Scale node pool & TW
06/18/2026 17:30UTC
notes: scale down c3d-highcpu-90 to 40; scale up c4d-highcpu-96 to 5; scale TW to 7960.
```

```text
Scale node pool & TW
06/18/2026 17:30UTC
notes: scale up c4d-highcpu-96 to 0; scale TW to 7020.
```

```text
Scale node pool & TW
06/19/2026 01:20UTC
notes: scale up c3d-highcpu-90 to 50; scale TW to 8780.
```

```text
DONE: TW/TW-BU completed. Scale node pool & TW
06/19/2026 04:30UTC
notes: scale down node pool & TW.
```

## Closeout

Summary and per-seg tables were copied from the pipeline output.  Note that no time range subsetting was performed, 
as the BQ table was purged prior to the run.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_summary`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1)
```

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_segments` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1)
```

### Notes

## Dead-lettered jobs
No deadlettered TW or TWBU jobs observed. No TWJF deadlettered jobs.

## Logs

Logs all copied from log sink buckets to flights-pipeline-prod bucket:

```shell
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-backup/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2020_run_jun2026/tw-backup-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2020_run_jun2026/tw-logs/
gsutil -m cp -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/06/* gs://contrails-301217-flights-pipeline-prod/logs/inventory_2020_run_jun2026/twjf-logs/
```

And log sink buckets cleared for the next run:

```shell
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-backup/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker/*
gsutil -m rm -r gs://contrails-301217-fp-prod-trajectory-worker-job-factory/*
```

### Loading logs into BQ

Logs were loaded into BQ by adjusting the log bucket prefix to `gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026` and changing the BQ table name in the bq load scripts to `logs_inventory_2020_run_june2026`. Kept the `--max_bad_records=140` flag in the TWJF log loader. Running the scripts:

```shell

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json] Error while reading data, error message: JSON parsing error in row starting at position 1690899339: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S10.json'

Waiting on bqjob_r16f7841e7a54d1b8_0000019ee5094518_1 ... (10s) Current status: DONE   
Waiting on bqjob_r48e444a9a0e01088_0000019ee50977d8_1 ... (8s) Current status: DONE   
Waiting on bqjob_r4f34508a528f38db_0000019ee509a493_1 ... (15s) Current status: DONE   
Waiting on bqjob_r711727f51337a14f_0000019ee509ebb3_1 ... (15s) Current status: DONE   
Waiting on bqjob_r648d25f1e62ff6f_0000019ee50a3254_1 ... (15s) Current status: DONE   
Waiting on bqjob_r10f6e8f9441fa1f8_0000019ee50a78fa_1 ... (10s) Current status: DONE   
Waiting on bqjob_r3439ab74d6d89977_0000019ee50aac7f_1 ... (15s) Current status: DONE   
Warnings encountered during job execution:

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3273068748: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3297060304: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3230540387: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json] Error while reading data, error message: JSON parsing error in row starting at position 3253504163: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S8.json'

Waiting on bqjob_r616c05e63ba5848f_0000019ee50af36d_1 ... (15s) Current status: DONE   
Warning encountered during job execution:

b'[gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S9.json] Error while reading data, error message: JSON parsing error in row starting at position 1921641989: Only optional fields can be set to NULL. Field: airline_iata; Value: NULL File: gs://contrails-301217-flights-pipeline-prod/logs/inventory_2021_run_jun2026/twjf-logs/19/16:00:00_16:59:59_S9.json'
```

Shows several null airline_iata fields where it should have been an array-like value. This is a bit odd; I thought we had removed all such code paths from the TWJF.

There wer no errors loading logs for the TW  or TWBU.