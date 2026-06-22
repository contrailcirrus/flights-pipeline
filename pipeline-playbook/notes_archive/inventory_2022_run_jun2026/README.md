# Inventory 2022 (run: June 2026)

## Hyperdisk Setup

The 2022 ERA5 met data was put into a new GCP bucket `gs://contrails-301217-ecmwf-era5-zarr-v2-staging-2022` so that data for 2020-2023 could be set up in parallel, letting us set up hyperdisks with the met data in parallel without having to purge the staging bucket before getting started on another year. This dataset includes zarr stores from 2021-12-31, 2023-01-01, and 2023-01-02 in addition to all of 2022. It was copied into the staging bucket wit `gsutil -m cp` commands on a VM rather than setting up a transfer job with the `copy_era5_gcs_to_staging.sh` script, mostly because I forgot that script existed. There were no errors though, and data seem to be present.

To create the hyperdisk, we created a new [GCSDataSource](../../pre_process/hyperdisk-setup/gcs-era5-zarr-data-source-2022.yaml) and a new [PVC](../../pre_process/hyperdisk-setup/era5-zarr-gcs-pvc-useast4c-2022.yaml) for the 2022 dataset, opting to start the disk with 600MB/s bandwidth and hoping we can scale it up.

## Job ID compilation
Created a new Job ID table using the following BQ query:

```sql
CREATE TABLE contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_jobs AS
WITH main_tb AS (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_baro
                 FROM contrails-301217.flights_pipeline_prod.spire_flights_raw_prod
                 WHERE timestamp BETWEEN "2021-12-31T00:00:00" AND "2022-12-31T23:59:59"
                 GROUP BY flight_id),
     target_tb AS (SELECT flight_id, min_ts, TIMESTAMP_TRUNC(min_ts, DAY) AS day_bin
                   FROM main_tb
                   WHERE max_alt_baro > 18000 AND min_ts >= "2022-01-01T00:00:00"),
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

This created a new table with 24743 Job IDs. I created the job list with `SELECT job_id FROM `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_jobs`;`, exporting the result as CSV, removing the column name top row, and changing the file name to `2022_job_id_list.txt`.

## Run
Started run at 16:25 UTC on 2026-06-22.

On a VM, I changed the `pipeline-cli/services.py` file to point to the production TWJF PubSube queue, then ran:

```shell
./cli.py jobworker submit -j /home/joffreypeters/repos/flights-pipeline/pipeline-playbook/notes_archive/inventory_2022_run_jun2026/2022_job_id_list.txt -l inventory_2022_run_jun2026_jobs -w gcs -s era5 -t > 2022_cli_run.log 2>&1
```

After observing normal TWJF logs, and seeing a few thousand jobs published to the TWJF queue, I scaled the number of TWJF workers to 1000 at 16:37 UTC.

----
```text
Deployed TW and TWBU:
Updated the TW and TWBU helm configs to change the PVC reference to match the hyperdisk PVC created for the 2022 ERA5 data. This kicked off the CI/CD process to update the TW and TWBU deployments. These took a while to roll over because the horizontal scaling was still set to 2395 replicas.
```


```text
Scaled hyperdisk bandwidth using the webconsole from 600MB/s to 60000MB/s at 17:26 UTC. 
Took about 20 minutes, but scaling was successful.
```

```text
13 unschedulable pods due to insufficient CPU, though there were 50x90 = 2500 cpus available and only 2395 pods scheduled. Backed off to 2380 and seems fine.
```

```text
TWJF done 18:32 UTC.
TWJF queue empty. Scaled back to 1 worker. 
No deadlettered TWJDs.
```

```text
Not seeing more than about 150 acks/s with this configuration. That's 2 acks/min/worker. We think this should be higher. Going to start scaling back workers to see if ack rate/worker goes up.
18:49 UTC: scaling back to 4105 (removing 3 nodes worth of workers).
Scaled nodes back to 47
```

```text
Throughput still seems around 150 acks/s, which is now about 2.2 acks/min/worker.
Scaling back to 3835 workers and 44 nodes at 19:26 UTC.
After about 15 minutes, that seems ot have settled at about 148 acks/s or 2.3 acks/min/worker. Hyperdisk bandwidth is about 63 GB/s - maybe down very slightly.
```

```text
Scaling back to 3465 workers and 40 nodes at 19:44 UTC.
The absolute throughput still looks about the same: about 148 acks/s, and 62 GB/s hyperdisk bandwidth for 2.5 acks/min/worker.
This seems like it may be hyperdisk bandwidth saturation.
```

```text
Scaling back to 3000 workers and 35 nodes at 20:13 UTC.
The absolute throughput seems to remain at 148 acks/s, and hyperdisk bandwidth is still maximized. Now we're at nearly 3 acks/min/worker. I have seen the IO queue depth come down as we scale down workers, the bandwidth and ack rate are consistent, so we're clearly hitting a hyperdisk bandwidth limit.
```

``text 
Scaling back to 2000 workers at 23 nodes at 20:27 UTC.
```

```text
Ack rate dropped to about 130 acks/s and bandwidth usage down to 54 GB/s or 3.9 acks/min/worker. That indicates we could go to just under 2300 workers to maximize bandwidth usage if scaling is linear.

Scaling up to 2270 workers at 26 nodes at 21:11 UTC.
```