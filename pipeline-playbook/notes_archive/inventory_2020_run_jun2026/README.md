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
notes: scale qty 1 c3d-highmem-90; deploy TW at replica 10; TW-BU at replica 3
```

```text
Scale TWJF
06/18/2026 15:15UTC
notes: scale TWJF to 1000 replicas
```

```text
Scale node pool and TW
06/18/2026 15:18UTC
notes: scale qty 15 c3d-highmem-90; deploy TW at replica 2630. job rate ~135-140 jobs/sec -> 3.1 jobs/worker/min
```

```text
Scale node pool and TW
06/18/2026 15:45UTC
notes: scale qty 30 c3d-highmem-90; deploy TW at replica 5260. job rate ~260 jobs/sec ->  3 jobs/worker/min
```

```text
Scale node pool and TW
06/18/2026 16:05UTC
notes: scale qty 45 c3d-highmem-90; deploy TW at replica 7890. job rate ~ jobs/sec ->   jobs/worker/min
```


```text
DONE: TWJF
06/18/2026 16:12UTC
notes: scale qty 45 c3d-highmem-90; deploy TW at replica 7890. job rate ~ jobs/sec ->   jobs/worker/min
```
