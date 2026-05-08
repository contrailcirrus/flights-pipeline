# Inventory 2024/2025 -- run date: March 20+ 2026

### Timeline

#### Run 1.1

List A

```text
start: March 20 03:05 UTC
airline_iata: run list A
range: 2024-01-01_2025-12-31
```

#### Run 1.1a

```text
start: March 20 21:40 UTC
airline_iata: AA
range: 2025-07-10, 2025-07-09
note: remediation; TWJD dead-letters
```

#### Run 1.1b

```text
start: March 20 23:05 UTC
airline_iata: AA
range: 2025-07-09
note: remediation; TWJD dead-letters; OOM symptoms; TWJF memory increased manually in console
```

#### Run 1.2

```text
start: March 21 01:20 UTC
airline_iata: runlist_B.txt
range: 2024-01-01_2025-12-31
notes: run on VM
```

#### Run 1.3

```text
start: March 25 02:27 UTC
airline_iata: runlist_C.txt
range: 2024-01-01_2025-12-31
notes: run on VM
```

#### Run 1.4

```text
start: March 26 18:05 UTC
airline_iata: null
range: 2024-01-01_2025-12-31
notes: run locally
```

#### Run 1.4b

```text
start: March 26 19:50 UTC
airline_iata: null
range: 2024-01-01_2025-12-31
notes: remediation; most null airline iata dead lettered
```

### VM run cmd ref

```bash
cat runlist_<B/C>.txt | xargs -I % ./cli.py jobworker submit -a % -d 2024-01-01_2025-12-31 -w gcs -s era5 -t > my_airline_iatas.log 2>&1 &

```

## Notes

For the first 200 or so top airlines, the nominal TW config worked well (0.4vcpu, 1.2gb ram),
and optimal bandwidth from the hyperdisk was somewhere around 40 mb/sec per vcpu (3000-4000 workers saturated 50GB/sec).

For the null airlines and the tail of the airline list, vcpu and bandwidth were highly underutilized.
It was noticed that for the null airlines specifically, many flights were skipped due to not being above the altitude threshold
or being in the PS/BADA list of accepted aircraft types. If we are concerned with improving perf, we may want to filter these at
the TWJF stage.

## Postprocessing

The following table was created from the BQ outputs (per-flight summary data only, i.e. seg_cnt > 1).

```text
`contrails-301217.flights_pipeline_prod.inventory_2024_2025_run_march2026_summary`
```

The initial table of raw per-flight records had `58,733,269` rows.

The false null airline iata pruning and dedupeing [with these queries](../../post_process/sql/dedupe.sql) was then applied.

Step 1 dropped `2,885` false null airline iata rows.

Step 2 dropped `348,500` dupes.

### BigQuery to Impact Explorer Postgres DEV

The Mar2026 run outputs are stored in the `contrails-301217.flights_pipeline_prod.inventory_2024_2025_run_march2026_summary` BigQuery table.

Following along the [instructions README](../../../bq-to-postgres-util/README.md) in the BQ to Postgres tool. The first pass is to export the data to a new GCS bucket path. Since we have two years here, we'll make two paths:

- `contrails-301217-sandbox-internal/flights-pipeline/emissions-export/2024/20260327`
- `contrails-301217-sandbox-internal/flights-pipeline/emissions-export/2025/20260327`

Exports are fast!

**Dev Database**
Starting with procesing the Dev database.

Purging Postgres tables:

```sql
DROP TABLE "trajectory-cocip" CASCADE;
drop table "trajectory-cocip-meta" cascade;
drop table inventory_monthly_impact_histogram cascade;
```

Then in DataGrip, ran `1_trajectory_cocip.sql`, `2_trajectory_cocip_meta.sql`, `3_inventory_monthly_impact_histogram.sql`, `4_inventory_monthly_airlines_stats.sql`, and `5_inventory_monthly_od_pair_airline_stats.sql`.

Running the util now to copy data from parquet files to Postgres. Going to run 2024 and 2025 separately.

```shell
python main.py --db_user "postgres" --db_password=$PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES --db_host=**.**.***.** --gcs_paths="flights-pipeline/emissions-export/2024/20260327" 2>&1 | tee 2024.log
Connecting via TCP to **.**.***.**:5432
Found 510 parquet shards in flights-pipeline/emissions-export/2024/20260327.
100%|██████████| 510/510 [3:55:21<00:00, 27.69s/it]
```

```shell
 python main.py --db_user "postgres" --db_password=$PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES --db_host=**.**.***.** --gcs_paths="flights-pipeline/emissions-export/2025/20260327" 2>&1 | tee 2025.log
Connecting via TCP to **.**.***.**:5432
Found 510 parquet shards in flights-pipeline/emissions-export/2025/20260327.
100%|██████████| 510/510 [4:26:28<00:00, 31.35s/it]
```

Ran the 2025 dataset in the morning of 20260328, but kept the 20260327 pathing for consistency.
Found no errors in the 2024 logs, but the util print statements have no consistent format, so it's not so straightforward to grep through. There's also just very little in them at all. This should probably be updated to be a lot more verbose and with easily searchable keys so we see when each file is done, and also get logging for things like `on_conflict_do_update` calls and when/where they happen and what is done.

Checking the number of entries in the Postgres database against the number in BQ, I found the same number!

BQ count from contrails-301217.flights_pipeline_prod.inventory_2024_2025_run_march2026_summary: 58381984
PG count from trajectory-cocip-meta: 58381984

Refresh materialized views:

```sql
REFRESH MATERIALIZED VIEW inventory_monthly_airlines_stats;
REFRESH MATERIALIZED VIEW inventory_monthly_od_pair_airline_stats;
```

**Prod Database**

Re-running the above procedure for the prod Postgres.

Since the BQ table has already been dumped to Parquet files, I'm going to use those same Buckets to reload the prod Postgres.

A note on the Postgres connections: I have had to use the `postgres` user to run this python util application for these processes. That's probably because I've dropped all the tables. Perhaps when all tables exist, it's possible to run these procedures using the typical RO user instead.

Ran the sql scritps 1-5.

Since the dev run went so smoothly, combining the 2024 and 2025 runs:

```shell
python main.py --db_user "postgres" --db_password=$PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES_PROD --db_host=**.***.***.*** --gcs_paths="flights-pipeline/emissions-export/2024/20260327,flights-pipeline/emissions-export/2025/20260327" 2>&1 | tee 2024_2025_prod.log
```

Finished without errors, though it seemed very slow.

Here's the final count of rows inserted:

```sql
select count(*) from "trajectory-cocip";
    58381984
```

Refreshed the two materialized views. All set now!

### Flights Pipeline Logs to BQ

Copied logs over to `contrails-301217-flights-pipeline-prod/logs/inventory_2024-2025_run_mar2026/` for the `tw`, `twjf`, and `tw-backup`.

I had a lot of roundabout processing and loading of these logs into BigQuery. In the end, we have a harmonized schema for the logs messags which allows TWJF, TW, TW-Backup workers all to import their logs into a single source-of-truth log table which allows full traceability of each trajectory through the flights pipeline. The schema is [here](../../post_process/logs_to_bq/logs_bq_table_schema.json). The ultimate SoT logs table ended up in `contrails-301217.flights_pipeline_prod.logs_inventory_2024_2025_run_march2026`.

The main issue with harmonization between TWJF and TW logs (and even caused some issues with TWJF logs) is that some of the logs with `"reason"` keyword store that variable as an array of strings and some as a nullable string. Moving forward, it will be expected to provide an array of strings, but in this processing, we've had to work around it a little bit as documented below.

Also added some new fields to enhance traceability. Added two `resource.labels` fields: `container_name` and `pod_name`. The first gives the name of the application (e.g. `trajectory-worker-gaia` or `trajectory-worker-job-factory`, and the latter gives the machine-named name of the pod itself). The `container_name` allows disambiguation of `start_time` and `start work` messages particularly. The `pod_name` isn't super useful, but it's our best handle to getting traceability back to the `twjd`. Some pods live long enough to handle multiple `twjd`s though, so it's a bit complicated to really get the `twjd`, but using the short list of associated `twjd`s with the `pod_name` and the timestamps you can probably get there.

**Loading TWJF logs**
Updated the `twjd_logs_bq_schema.json` file with current schema. Tried uploading to a test database and went well for a log file.

But then the run for all files had lots of errors. It took a while to track them down. Looking at job records for failed jobs did ultimately help - the location of the error (location in bytes; searchable with vim with `:<byte position int>go`) is provided, though it's typically indicated at the last properly processed line rather than the one causing the error.

The errors all turned out to be due to the job restart progress message which included `airline_iata` as a single value rather than an array. I made a fix for that, though it won't help with current logs processing. That log message also has a `marker` integer value which I added to the schema for future processing.

Looking at the GCS logs viewer, I found a maximum of 137 of these resume log messages in any hour during the mar2026 processing run, so I re-ran the BQ logs load `bq load` with the flag `--max_bad_records=140`.

All the logs (except those progress restart messages) are now in the new BQ table: `contrails-301217.flights_pipeline_prod.logs_inventory_2024_2025_run_march2026`.

**Loading TW and TW-backup logs**
Befor loading TW or TW-Backup logs, I changed the `jsonPayload.reason` mode in `logs_bq_table_schema.json` from `REPEATED` to `NULLABLE`. I used this configuration for both TW and TW-Backlog log loading.
TW logs load: using `bq_load_tw_logs.sh` to load all the Trajectory Worker logs into another table, changing the `jsonPayload.reason` schema element to `NULLABLE` from `REPEATED`, because none of the TW logs encapsulate these in arrays. After loading into the other table, they will be copied into the main logs table while wrapping that field in an array. The Backup Trajectory Worker logs were similarly loaded using `bq_load_tw_backup_logs.sh`. Both of these were loaded into the table `contrails-301217.flights_pipeline_prod.tw_2024-2025_logs_mar2026`.

There were no errors in loading either, so these are ready to be copied into the new logs table including all logs from twjf, tw, tw-backup.

**Harmonizing and merging TWJF and TW logs**

With all logs loaded, it's time to copy the TW and TW-Backup logs into the main logs table:

```sql
INSERT INTO `contrails-301217.flights_pipeline_prod.logs_inventory_2024_2025_run_march2026`
SELECT
  * REPLACE (
    (SELECT AS STRUCT
      jsonPayload.* REPLACE (
        IF(jsonPayload.reason IS NULL, [], [jsonPayload.reason]) AS reason
      )
    ) AS jsonPayload
  )
FROM `contrails-301217.flights_pipeline_prod.tw_2024-2025_logs_mar2026`;
```

Now I can delete the `contrails-301217.flights_pipeline_prod.tw_2024-2025_logs_mar2026` table and all logs are nicely stored in one place.

#### Tracing the trajectory job back to the Job Description that intiated it

This is a bit tricky and the logging wasn't really set up to handle this. The TWJD is described when it's picked up by the TWJF, but the TWJD isn't echoed along with each trajectory picked up or job minted. I've added the `resource.labels.pod_name` field which allows getting all the TWJDs associated with the `pod_name` for the pod that handled a given `flight_id`, but the mapping may be one to many. Using timing info, you could almost certainly back out the correct TWJD for every job/trajectory, however it's a bit clunky. Moving forward, I plan to pass a TWJD hash along to be included when each trajectory is picked up and worked on and logged, that way there will be a more easily queryable method to get back to this information. For now, I'll add a new nullable string field to hold that variable and will create the column in the logs table, though it'll be unpopulated until future runs.

To add the column:

```shell
bq update flights_pipeline_prod.logs_inventory_2024_2025_run_march2026 logs_bq_table_schema.json
```
