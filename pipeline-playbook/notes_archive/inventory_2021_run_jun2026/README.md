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
06/ UTC
notes: completed at ; see below
```

The job-id based TWJDs in the `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_jobs` table 
were submitted starting at ``.  See the [job-id list](2021_job_id_list.txt).  The flights referenced by those 
ids total `22,428,707`.

Executed on VM: `./cli.py jobworker submit -j /home/nickmasson/flights-pipeline/pipeline-playbook/notes_archive/inventory_2021_run_jun2026/2021_job_id_list.txt -l inventory_2021_run_jun2026_jobs -w gcs -s era5 -t > 2020_run.log 2>&1`.

```bash

```