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