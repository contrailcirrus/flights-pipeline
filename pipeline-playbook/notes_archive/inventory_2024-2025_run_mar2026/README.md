# Notes

## BigQuery to Impact Explorer Postgres DEV

The Mar2026 run outputs are stored in the `contrails-301217.flights_pipeline_prod.inventory_2024_2025_run_march2026_summary` BigQuery table.

Following along the [instructions README](../../../bq-to-postgres-util/README.md) in the BQ to Postgres tool. The first pass is to export the data to a new GCS bucket path. Since we have two years here, we'll make two paths:

- `contrails-301217-sandbox-internal/flights-pipeline/emissions-export/2024/20260327`
- `contrails-301217-sandbox-internal/flights-pipeline/emissions-export/2025/20260327`

Exports are fast!

Purging Postgres tables:

```sql
DROP TABLE "trajectory-cocip" CASCADE;
drop table "trajectory-cocip-meta" cascade;
drop table inventory_monthly_impact_histogram cascade;
```

Then in DataGrip, ran `1_trajectory_cocip.sql`, `2_trajectory_cocip_meta.sql`, `3_inventory_monthly_impact_histogram.sql`, `4_inventory_monthly_airlines_stats.sql`, and `5_inventory_monthly_od_pair_airline_stats.sql`.

Running the util now to copy data from parquet files to Postgres. Going to run 2024 and 2025 separately.

```shell
python main.py --db_user "postgres" --db_password=$PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES --db_host=34.23.237.52 --gcs_paths="flights-pipeline/emissions-export/2024/20260327" 2>&1 | tee 2024.log
Connecting via TCP to 34.23.237.52:5432
Found 510 parquet shards in flights-pipeline/emissions-export/2024/20260327.
100%|██████████| 510/510 [3:55:21<00:00, 27.69s/it]
```

```shell
 python main.py --db_user "postgres" --db_password=$PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES --db_host=34.23.237.52 --gcs_paths="flights-pipeline/emissions-export/2025/20260327" 2>&1 | tee 2025.log
Connecting via TCP to 34.23.237.52:5432
Found 510 parquet shards in flights-pipeline/emissions-export/2025/20260327.
100%|██████████| 510/510 [4:26:28<00:00, 31.35s/it]
```

I ran the 2025 dataset in the morning of 20260328, but kept the 20260327 pathing for consistency.
I found no errors in the 2024 logs, but the util print statements have no consistent format, so it's not so straightforward to grep through. There's also just very little in them at all. This should probably be updated to be a lot more verbose and with easilyt searchable keys so we see when each file is done, and also get logging for things like `on_conflict_do_update` calls and when/where they happen and what is done.

Checking the number of entries in the Postgres database against the number in BQ, I found the same number!

BQ count from contrails-301217.flights_pipeline_prod.inventory_2024_2025_run_march2026_summary: 58381984
PG count from trajectory-cocip-meta: 58381984

---

I then forgot to refresh materialized views. Nick pointed that out, then I ran:


```sql
REFRESH MATERIALIZED VIEW inventory_monthly_airlines_stats;
REFRESH MATERIALIZED VIEW inventory_monthly_od_pair_airline_stats;
```

---

2026-03-30

Re-running this again for the prod Postgres.

Since the BQ table has already been dumped to Parquet files, I'm going to use those same Buckets to reload the prod Postgres.

A note on the Postgres connections: I have had to use the `postgres` user to run this python util application for these processes. That's probably because I've dropped all the tables. Perhaps when all tables exist, it's possible to run these procedures using the typical RO user instead.

Ran the sql scritps 1-5.

Since the dev run went so smoothly, combining the 2024 and 2025 runs:

```shell
python main.py --db_user "postgres" --db_password=$PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES_PROD --db_host=35.190.184.203 --gcs_paths="flights-pipeline/emissions-export/2024/20260327,flights-pipeline/emissions-export/2025/20260327" 2>&1 | tee 2024_2025_prod.log
```

Finished without errors, though it seemed very slow.

Here's the final count of rows inserted:

```sql
select count(*) from "trajectory-cocip";
    58381984
```

Refreshed the two materialized views. All should be set now!

---

Copied logs over to `gs://contrails-301217-sandbox-internal/flights-pipeline/inventory_2024-2025_run_mar2026` for the `tw`, `twjf`, and `tw-backup`.


Apparently, the new home for these things should be:

```shell
gs://contrails-301217-flights-pipeline-prod/logs/<inventory_XXX_run_YYY>/<service_name; e.g. trajectory_worker>/<files>.json
```

All files copied.

----
Updated the `twjd_logs_bq_schema.json` file with current scheme. Tried uploading to a test database and went well for a log file.

But then the run for all files had lots of errors. It took a while to track them down. Looking at job records for failed jobs did ultimately help - the location of the error (location in bytes; searchable with vim with `:<byte position int>go`) is provided, though it's typically indicated at the last properly processed line rather than the one causing the error.

The errors all turned out to be due to the job restart progress message which included `airline_iata` as a single value rather than an array. I made a fix for that, though it won't help with current logs processing. That log message also has a `marker` integer value which I added to the schema for future processing.

Looking at the GCS logs viewer, I found a maximum of 137 of these resume log messages in any hour during the mar2026 processing run, so I re-ran the BQ logs load `bq load` with the flag `--max_bad_records=140`.

All the logs (except those progress restart messages) are now in the new BQ table: `contrails-301217.flights_pipeline_prod.twjf_2024-2025_logs_mar2026`.


