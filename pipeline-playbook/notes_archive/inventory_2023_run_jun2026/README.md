# Inventory 2023 (run: June 2026)

## Setup

### Hyperdisk Setup

The 2023 ERA5 met data was put into a new GCP bucket `gs://contrails-301217-ecmwf-era5-zarr-v2-staging-2023` so that data for 2020-2023 could be set up in parallel, letting us set up hyperdisks with the met data in parallel without having to purge the staging bucket before getting started on another year. This dataset includes zarr stores from 2022-12-31, 2024-01-01, and 2024-01-02 in addition to all of 2023. It was copied into the staging bucket wit `gsutil -m cp` commands on a VM rather than setting up a transfer job with the `copy_era5_gcs_to_staging.sh` script, mostly because I forgot that script existed. There were no errors though, and data seem to be present.

To create the hyperdisk, we created a new [GCSDataSource](../../pre_process/hyperdisk-setup/gcs-era5-zarr-data-source-2023.yaml) and a new [PVC](../../pre_process/hyperdisk-setup/era5-zarr-gcs-pvc-useast4c-2023.yaml) for the 2023 dataset, opting to start the disk with 600MB/s bandwidth and and planning to scale it up.

### Job ID compilation
Created a new Job ID table using the following BQ query:

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2022-12-31T00:00:00" AND "2023-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2023-01-01T00:00:00"),
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

This failed because ARRAY_AGG doesn't allow null values, and there were some rows with flight_id = null.  To figure out where those were and what to do with them, I found the days on which there were null flight_ids:

```sql
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2022-12-31T00:00:00" AND "2023-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2023-01-01T00:00:00"),
     job_grp_tb AS (SELECT *,
                           SUBSTR(TO_HEX(SHA256(CONCAT(
                                   CAST(CAST(0.001 * ROW_NUMBER() OVER (PARTITION BY day_bin ORDER BY min_ts) AS INT64) AS STRING),
                                   CAST(day_bin AS STRING)))), 1, 32) AS job_id
                    FROM target_tb),
     agg_tb AS (SELECT job_id,
                       ARRAY_AGG(day_bin)   AS day_bin_arr,
                       flight_id
                FROM job_grp_tb
                where flight_id is NULL
                GROUP BY job_id, flight_id)
SELECT job_id, FORMAT_DATE('%Y-%m-%d', ARRAY_FIRST(day_bin_arr)) AS day, flight_id
FROM agg_tb
```
which resulted in:
|job_id |	day |	flight_id |
| ---   |   --- |  ---- |
| 153e3ea002b1e1762556091ff93d3f6a	| 2023-09-05 | *null* |	

Then I found the specific rows at fault:

```sql
SELECT * FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
    WHERE timestamp BETWEEN "2023-09-05T00:00:00" AND "2023-09-05T23:59:59"
    AND flight_id is null
```

Which gave me:

| _instance_hash | src_id | ingestion_time | timestamp | latitude | longitude | collection_type | altitude_baro | icao_address | flight_id | callsign | tail_number | flight_number | aircraft_type_icao | airline_iata | departure_airport_icao | departure_scheduled_time | arrival_airport_icao | arrival_scheduled_time | altitude_gnss | nic | nacp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4088990533 | spire | 2024-08-31 03:05:29.559000 UTC | 2023-09-05 14:21:32.000000 UTC | 68.98242188 | -60.9840611 | satellite | 37000 | 3C6573 | | | | | | | | | | | | | |
| 3410076656 | spire | 2024-08-31 03:05:29.341000 UTC | 2023-09-05 14:25:06.000000 UTC | 56.46295166 | -60.47590776 | satellite | 40000 | 4C0222 | | ASL500 | | | | | | | | | | | |
| 3355603553 | spire | 2024-08-31 03:05:29.559000 UTC | 2023-09-05 14:22:22.000000 UTC | 68.97615051 | -61.26983643 | satellite | 37000 | 3C6573 | | | | | | | | | | | | | |
| 2591078409 | spire | 2024-08-31 03:05:29.559000 UTC | 2023-09-05 14:24:26.000000 UTC | 56.92444882 | -61.05767035 | satellite | 38000 | 478F43 | | | | | | | | | | | | | |
| 1378847886 | spire | 2024-08-31 03:05:29.341000 UTC | 2023-09-05 14:24:45.000000 UTC | 56.92444882 | -61.05767035 | satellite | 38000 | 478F43 | | | | | | | | | | | | | |
| 2172704541 | spire | 2024-08-31 03:05:29.559000 UTC | 2023-09-05 14:24:44.000000 UTC | 56.49897766 | -60.43878729 | satellite | 40000 | 4C0222 | | ASL500 | | | | | | | | | | | |
| 1218259284 | spire | 2024-08-31 03:05:29.559000 UTC | 2023-09-05 14:21:20.000000 UTC | 68.98399224 | -60.90779114 | satellite | 37000 | 3C6573 | | | | | | | | | | | | | |
| 635733908 | spire | 2024-08-31 03:05:29.559000 UTC | 2023-09-05 14:24:16.000000 UTC | 56.55226135 | -60.38385565 | satellite | 40000 | 4C0222 | | ASL500 | | | | | | | | | | | |
| 1360495822 | spire | 2024-08-31 03:05:29.559000 UTC | 2023-09-05 14:22:00.000000 UTC | 68.97891804 | -61.1459198 | satellite | 37000 | 3C6573 | | | | | | | | | | | | | |

It looks like there are a few satellite pings that didn't get associated with any flight. Let's try to simply remove these rows when creating the job_id table.

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2022-12-31T00:00:00" AND "2023-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2023-01-01T00:00:00"),
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


This created a new table with 31,443 Job IDs. I created the job list with `SELECT job_id FROM `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_jobs`;`, exporting the result as CSV, removing the column name top row, and changing the file name to `2023_job_id_list.txt`.

### False start
Had a false start on the run where I forgot to truncate the results table before starting, so there will be an additional flush-out period to let log sinks propagate. The TWJF and TW PubSub queues were purged. The twjf log sink worked, which was a good test after the issues in the 2022 run. The twjf logs were purged.

### Truncate results table

Truncating the results table before the run:

```sql
TRUNCATE TABLE `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`;
```

## Run
```text
Started run at 14:26 UTC on 2026-06-24.

On a VM, I changed the `pipeline-cli/services.py` file to point to the production TWJF PubSube queue, then ran:
```

```shell
./cli.py jobworker submit -j /home/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_2023_run_jun2026/2023_job_id_list.txt -l inventory_2023_run_jun2026_jobs -w gcs -s era5 -t > 2023_cli_run.log 2>&1
```

```text
Noted appropriate TWJF logs, TWJF and TW queues filling. Scaling TWJF workers to 500 at 14:32 UTC.
```

```text
Requesting Hyperdisk bandwidth increase to 150000MB/s at 14:32 UTC.
```

```text
14:47 UTC
Adding one c3d-highcpu-90 node.
Kicking off CI/CD for TW and TW-BU. Setting TW replicas to 1 and lowering vcpu to 0.6 vcpu/worker.
```

```text
Hyperdisk bandwidth updated at 14:57 UTC:

Successfully updated disk "pvc-3b4040d8-cac1-4c22-becb-6ec584120b63".
```

```text
TW logs look good. Scaling up nodes to 60, and workers to 8700.
This took us to about 350 acks/s and a little over 120 GB/s hyperdisk bandwidth usage.
```

```text
CLI finished at 15:19 UTC.
```

```text
Trying to maximize bandwidth usage. Scaling workers up to (150GB/s)/(125GB/s)*8700 workers = 1044 workers.  At (90 vcpus)/(0.6 vcpus/worker) = 150 workers, that's 70 c3d-highcpu-90 nodes.
Scaling up to 70 nodes and 10440 workers at 15:24 UTC.
```

```text
This does not seem to have improved matters very much. Only up to 135 GB/s. Ack rate not clearly improved.

Going to try to go to 0.8 vcpus/worker. Leaving nodes at 70, moving to 0.8 vcpus/worker and 7840 workers.
```

```text
Seems like too high CPU usage. Backed off to 7650 workers.

This yielded about 380 acks/s and 142 GB/s HD BW usage. About 3.6 acks/min/vcpu. We might do better with 1 vcpu/worker.
```

```text
Moving to 1 vcpu/worker and 5220 workers at 16:43 UTC.

Scaling down to 60 nodes after all pods rolled at 16:56 UTC. 
```

```text
After letting the above settle for a bit, I see ~345 acks/s or 3.8 acks/min/vcpu, and 130GB/s HD BW usage. Seems like we could get a little more out of this, perhaps with more nodes.

Trying to scale up to 66 nodes, 5750 workers.
```

```text
Seems to have bumped slightly up to 370 acks/s or 3.7 acks/min/vcpu, and 140 GB/s HD BW usage.

Have a little cpu overhead, moving up to 5760 workers.
```

```text
TWJF finished around 19:05 UTC. No more messages in queue and no recent log messages. Scaled back to 1 worker.

No TWJDs in the deadletter queue.
```

```text
Everything seems to be running smoothly. Had some extra CPU resources, so added 20 more workers, bumping up to 5780 at 02:25 UTC, 2026-06-25.
```

```text
TW finished around 13:30 UTC, 2026-06-25.
TW Backup queue empty.

Everything seemed smooth.

TW replicas auto scaled to 1; set max replicas to 1 as well. Scaling nodes to 0. Removed PVC/hyperdisk.
```



## Closeout
### BQ tables
Summary and per-segment BigQuery tables were copied from the pipeline output.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_summary_temp`
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt > 1)
```
This generated a table with 26479838 entries.

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_segments_temp` 
PARTITION BY DATE(time_start) AS 
  (SELECT *
    FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
    WHERE seg_cnt = 1)
```
This generated a table with 3677810346 entries.

Did not use a `_processed_at` statement in the temp table generation, since I cleared the `trajectory_cocip_prod` table myself before the run.


#### Dedupe BQ tables
The following two queries were executed to dedupe the segments table and the summary table.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_summary` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_summary_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 26465836 entries.

```sql
CREATE OR REPLACE TABLE `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_segments` 
PARTITION BY DATE(time_start) AS (
  SELECT *
    FROM `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_segments_temp`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CONCAT(flight_id, time_start) ORDER BY _processed_at DESC) = 1);
```
This created a table with 3674764025 entries. 

Both deduplicated tables dropped substantially less than 1% of entries.

