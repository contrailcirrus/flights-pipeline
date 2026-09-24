# Inventory 2026 Q1, Q2, Q3 (run: Sept/Oct 2026)

## Setup

### Job ID compilation
Created a new Job ID table for Q1, Q2, Q3 using the following BQ query:

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
* Q3: timestamp range `BETWEEN "2026-06-30T00:00:00" AND "2026-09-30T23:59:59"` and `min_ts >= "2026-07-01T00:00:00"` -- have to wait until October to create 2026Q3 table.

Q1 jobs table has 9577 entries with no null or zero length `flight_id_list`s.
Q2 jobs table has 10065 entries with no null or zero length `flight_id_list`s.

I created the job lists with e.g. `SELECT job_id FROM `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_jobs`;`, exporting the result as CSV, removing the column name top row, and changing the file name to `2026Q1_job_id_list.txt`.

### Hyperdisk Setup

The 2026 Q1 ERA5 met data was put into the standard GCP bucket `gs://contrails-301217-ecmwf-era5-zarr-v2-staging` using the `copy_era5_gcs_to_staging.sh` script.  This dataset includes zarr stores from 2025-12-31 through 2026-04-02:

```shell
./copy_era5_gcs_to_staging.sh 2025-12-31 2026-04-02 gs://contrails-301217-ecmwf-era5-zarr-v2/ gs://contrails-301217-ecmwf-era5-zarr-v2-staging/
```

The 2026-04-02 data was not copied by the script. I manually copied it afterward and added a note to the script that the end-date is not inclusive. We'll have to change date ranges accordingly.

To create the hyperdisk, we used the existing [GCSDataSource](../../pre_process/hyperdisk-setup/gcs-era5-zarr-data-source.yaml) and a new [PVC](../../pre_process/era5-zarr-gcs-pvc-useast4c_1quarter.yaml) for a 1-quarter dataset, opting to start the disk with 600MB/s bandwidth referencing the `hyperdiskml-useast4c-storage-class.yaml` storage class and and planning to scale bandwidth up.

### Truncate results table

Truncating the results table before the run:

```sql
TRUNCATE TABLE `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`;
```

## Run
```text
Started run at 15:45 UTC on 2026-09-24.

On my laptop, I changed the `pipeline-cli/services.py` file to point to the production TWJF PubSub queue `projects/contrails-301217/topics/prod-fp-twjd-ingress`, then ran:
```

```shell
./cli.py jobworker submit -j /Users/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_2026Q1Q2Q3_run_sept2026/2026Q1_job_id_list.txt -l inventory_2026Q1_run_sept2026_jobs -w gcs -s era5 -t > 2026Q1_cli_run.log 2>&1
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

