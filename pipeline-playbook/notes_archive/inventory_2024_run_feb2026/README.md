# Inventory 2024 -- run date: Feb 2026

## Summary
A flights pipeline run, encompassing all 2024 flights.

This was run in the `prod` environment.
`flights-pipeline` version/git-hash: `adbbf54f3de3aa6830aac08cff47a2cdf7b5c259`

## Captain's Notes

## TWJD jobs submitted - RUN #1 (all non-null airline iata)
### Overview
TWJDs were submitted to the TWJF (prod envn't),
using the CLI (./cli.py) in the `flights-pipeline/flight-emissions-report` subdir.
Note that the location of that CLI will change (this if you need to reference the CLI that was used
at the time of this pipeline run; please check-out the GIT SHA listed in [#Summary](#summary)).

TWJDs were submitted in 3 batches.  Each TWJD is an `airline_iata`-`calendar_day`.

These three batches encompass all _airline_iata_ values observed in the raw spire data, over 2024,
with one or more waypoints above 20k ft. Note that the `null` airline iata is a special case,
and processed separately (see Run 2), in order to keep our log files isolated for that run.

Batch A, B and C are with airlines ranked in descending order based on the volume of waypoints
observed above 20k ft.

**TWJD batch A**

This list is in [cli_runlist_run_A.txt](twjd_inputs/cli_runlist_run_A.txt).
The following command was used to iterate thru the airline iatas, 
and submit a full year's worth of jobs for that airline.

```bash
cat cli_runlist_run_A.txt | xargs -I % ./cli.py jobworker submit -a % -d 2024-01-01_2024-12-31 -w gcs -s era5 -t
```

List A was submitted manually on a personal machine. Logs (stderr/stdout) were _not_ captured
from the CLI for List A. Rather, successful completion of the above command was confirmed visually.

**TWJD batch B & C**

These lists are similarly [cli_runlist_run_B.txt](twjd_inputs/cli_runlist_run_B.txt) and [cli_runlist_run_C.txt](twjd_inputs/cli_runlist_run_C.txt).

Batch B and C were similar submitted, but run from a VM.
The following command was executed on a VM:
```bash
cat cli_runlist_run_<B/C>.txt | xargs -I % ./cli.py jobworker submit -a % -d 2024-01-01_2024-12-31 -w gcs -s era5 -t > my_airline_iatas.log 2>&1 &
```
This was run as a background task, and took several hours to complete.

The stdout/stderr output logs from each of these command line invocations 
is in [run_list_B.log](twjd_inputs/logs/run_list_B.log) and [run_list_C.log](twjd_inputs/logs/run_list_C.log).

Successful completion of the jobs submitted in batch B and C were confirmed by inspecting these logs.

### Timeline
#### Run 1.1
List A
```text
start: Feb 17 23:30 UTC
airline_iata: run list A
range: 2024-01-01_2024-12-31
```

### Run 1.2
List B
```text
start: Feb 18 00:20 UTC
airline_iata: run list B
range: 2024-01-01_2024-12-31
```

### Run 1.3
List C
```text
start: Feb 18 02:35 UTC
airline_iata: run list C
range: 2024-01-01_2024-12-31
```

### Run 1.4
Patch dead-lettered TWJDs
```text
start: Feb 19 00:30 UTC
airline_iata: AA
range: 2024-05-09
```

### Run 1 - finish
```text
❗NOTE: both the TWJF, TW and TW-backup were observed to be done by `Feb 20 3:30 UTC`
```


## TWJD jobs submitted - RUN #2 (null airline iata)
### Overview
Same context as [#Run 1](#twjd-jobs-submitted---run-1-all-non-null-airline-iata) above, accept the null airline iata jobs were submitted with a single
invocation of the CLI.
```bash
./cli.py jobworker submit -a null -d 2024-01-01_2024-12-31 -w gcs -s era5 -t
```

```text
❗NOTE: the TWJF kubernetes deployment was manually updated (by modifying the YAML in Cloud Console),
to increase the pod memory to 10Gi per pod.  The null airline iata case pulls a lot more 
data into memory, as we have to comb thru GA flights. The HPA was also dropped to 50 replicas.
```

### Run 2.1
null `airline_iata`, full year
```text
start: Feb 20 04:15 UTC
airline_iata: null
range: 2024-01-01_2024-12-31
```

### Run 2.2
Patch dead-lettered TWJDs
```text
start: Feb 20 15:45 UTC
airline_iata: null
range: 2024-12-03
```

### Run 2 - finish
```text
❗NOTE: both the TWJF, TW and TW-backup were observed to be done by `Feb 20 16:50 UTC`
```

### Remediation
Three flights were found in the TW-backup dead letter queue.
#### Failed jobs
- no TWJDs were observed in the TWJF's queue
- some TW-backup jobs failed and were in the TW queue, for the following flights:
```json
[
    {"airline_iata": "UA", "flight_id": "997076a7-6b07-4809-9d3a-07f9c448565e", "departure_scheduled_time": "2024-06-24T10:15:00Z"},
    {"airline_iata": "YX", "flight_id": "3d43e776-a30a-4500-bf69-05cb7ab672fe", "departure_scheduled_time": "2024-06-26T17:03:00Z"},
    {"airline_iata": "AK", "flight_id": "d07b52bd-42ed-484c-b986-b744f1a4cafb", "departure_scheduled_time": "2024-05-28T09:30:00Z"}
]
```
(Note: I've included the flight time in the above, should we have to go back and surgically find these data in our BQ tables, which are partitioned by time)

These three jobs were reinjected (Feb 20 17:40 UTC) into the TW-backup ingress queue, using the CLI's `reinject` functionality.
All three jobs failed with permanent errors (`nacking - cocip failed`).

As such, we expect these failures to be documented/captured in the `Run 1` logs of the TW-backup service.
The TW-backup dead letter queue was purged/cleared manually after this remediation attempt, 
leaving the TW-backup deadletter subscription empty and ready for any future pipeline runs.

## Stats, Usage Metrics and Other Observations
### system stats
- gcs spire-api pq cache; 2024 pq files total ~300GB on disk
- gcs spire egress - bandwidth observed around 20GiB/sec from spire-api pq cache (~500 TWJF workers). TWJF runtime ~20hrs :. ~1.5PB spire pq total transmitted
- TW cost estimate (CPU & mem): $4.00/1k-worker-hr
- TWJF cost estimate (CPU & mem): $3.38/100-worker-hr
- TW throughput estimate: ~2.3-2.5 jobs/min
- gcs era5-v2 zarr egress - bandwidth observed around 40GiB/sec (~7k workers). runtime ~40-60hours :. 5.8-PB era5-v2 total transmitted
- GCS class B requests (`zarr-v2` bucket), `02-18T00:00 -> 02-20T00:00`, `15,424,869,040` requests :. avg. 588 requests/flight
- `zarr-v2` met data broken into one zarr store per day; separate store for pl and sl. `9.85gb` per store (pl), `73mb` per store (sl)

### raw output stats
- total flights written to BQ from TW (includes dupes; count(*) with seg_cnt>1): 26,223,755
- number of dupes among non-null airline iata flights: 19,460
- number of null airline iata flights let thru TW: 377,424
- number of false-null flights let thru TW: 7,542

## Post Processing & Archive outputs
As per instructions in the [playbook/README.md](../../playbook/README.md).

The `contrails-301217.flights_pipeline_prod.inventory_2024_run_feb2026_summary` table was created
to hold the per-flight summary values.

The [raw output stats](#raw-output-stats) section above was generated from the initial export to this table.

Next, the dataset was deduped with Step 1 and Step 2 of [post_process/sql/dedupe.sql](../../post_process/sql/dedupe.sql).
As noted in the [playbook/README.md](../../playbook/README.md), Step 1 will have no effect
with future updates to the TWJF, and Step 2 will only remove normal dupes (not airline_iata conflicts).

## Log Archiving
As per instructions in the [playbook/README.md](../../playbook/README.md).

TWJF, TW and TW-backup logs were selectively copied to `contrails-301217-sandbox-internal/flights-pipeline/inventory_2024_run_feb2026`. Using the [bq_load_example.sh](../../post_process/logs_to_bq/bq_load_example.sh) script, we created a logs table in BQ (`contrails-301217.flights_pipeline_prod.twjf_2024_logs_feb2026`) containing both run 1 and run 2 data (with `airline_iata` not null, and null respectively). That 

# Initial analysis queries

To get the total minutes of flight time processed and skipped by TWJF and TW, run [total_time_and_skipped.sql](../../post_process/sql/total_time_and_skipped.sql) as described in the [logs_to_bq README](../../post_process/logs_to_bq/README.md).

To check on TWJF skip reasons, binned by reason and month, run 
[skipped_reasons_by_month.sql](../../post_process/sql/skipped_reasons_by_month.sql) as described in the [logs_to_bq README](../../post_process/logs_to_bq/README.md).

To compare the flights-pipleine results with Roger's GAIA analysis, run [compare_with_gaia.sql](../../post_process/sql/compare_with_gaia.sql).