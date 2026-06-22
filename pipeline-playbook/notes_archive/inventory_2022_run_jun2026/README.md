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

This created a new table with 24743 Job IDs.