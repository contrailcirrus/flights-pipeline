# Playbook
The following instructions are for the Captain of a flights-pipeline run.

## Setup
TODO

## Initiate
TODO

Take note of when work is initially submitted to the TWJF queue. Take note of what that work is 
(if running the pipeline in separate sub-batches).
This is important later on when fetching the correct & complete log files for the TWJF, TW and TW-backup.

ProTip:
If initiating separate sub-batches within an overall pipeline run,
wait until a quiescent period (work done in TWJF, TW and TW-backup) of at least 1 hour has elapsed 
before initiating a subsequent sub-batch.  This will help with easily separating the TWJF, TW and TW-backup 
log files, which are partitioned on hourly boundaries.

## Monitor
TODO 

Take note of when work finishes for the TWJF, TW and TW-backup services.
This is important later on when fetching the correct & complete log files for the TWJF, TW and TW-backup.

## Remediation
TODO

## Document
TODO

## Archive
### Archive Log Files
#### TWJF log files
TWJF log files are written to GCS with this path prefix: `contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/**`.
The remaining filepath/URI represents the time range of the logs (UTC).

The first step is to identify the complete and exclusive set of log files that represent the run.
The second step is to copy them to an archive location (`gs://contrails-301217-sandbox-internal`).

The path for the twjf files should have the form:
```text
gs://contrails-301217-sandbox-internal/flights-pipeline/inventory_{flight_date_range}_run_{pipeline_run_time}/twjf-logs/*.json
```
The `inventory_{flight_date_range}_run_{pipeline_run_time}` path designator is the same as described
in the naming convention for archiving pipelines notes, see [notes_archive/README.md](../notes_archive/README.md)

### TW and TW backup log files
The same process applies for the TW and TW backup log files.

The paths for archiving those files is, respectively:
```text
# tw logs
gs://contrails-301217-sandbox-internal/flights-pipeline/inventory_{flight_date_range}_run_{pipeline_run_time}/tw-logs/*.json
```
and
```text
tw-backup logs
gs://contrails-301217-sandbox-internal/flights-pipeline/inventory_{flight_date_range}_run_{pipeline_run_time}/tw-backup-logs/*.json
```

## Post Process
### Post Process & Archive BQ Table
First, move the final raw results to a dedicated table, where we will clean and ultimately freeze/archive the run's outputs.
This table should have a prefix matching the name of the `notes_archive` directory in which a given run's notes are archived.
See the [note_archive/README.md](../notes_archive/README.md) for that naming convention.

For example: `inventory_2024_run_feb2026`

The first table we create is a summary table, summary meaning the per-flight values (excluding the per-segment).
To create the table, run:
```sql
CREATE TABLE :inventory_summary_table AS (SELECT *
                                          FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
                                          WHERE seg_cnt > 1
                                            AND _processed_at BETWEEN UNIX_MICROS(:run_start_time_utc) AND UNIX_MICROS(:run_end_time_utc))
```

Where:
- `inventory_summary_table` is the target table
- `run_start_time_utc` is an ISO formatted UTC datetime string of when the run began
- `run_end_time_utc` is an ISO formatted UTC datetime string of when the run ended (no more TW or TW-backup work observed, and all remediation finished)

e.g.
```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.inventory_2024_run_feb2026_summary` AS (SELECT *
                                                                                           FROM `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`
                                                                                           WHERE seg_cnt > 1
                                                                                             AND _processed_at BETWEEN UNIX_MICROS("2026-02-17T23:30:00Z") AND UNIX_MICROS("2026-02-20T16:50:00Z"))                                                                                                                  AND _processed_at BETWEEN UNIX_SECONDS("2026-02-17T23:30:00Z") AND UNIX_SECONDS("2026-02-20T16:50:00Z"))
```

```text
❗NOTE: the above queries assume no other records were written to the `trajectory-cocip-prod` table during
the pipeline run. If they were, then one would need to disentangle those records as part of this new table creation.
```

### Generate Initial Stats
Generate some initial stats from the inventory summary table generated above,
by running the sequence of queries in [post_process/sql/initial_stats.sql](../post_process/sql/initial_stats.sql)

Document any relevant stats in the run notes

### Manipulation: Remove Dupes
Next, we remove three types of dupes by running Step 1 and Step 2 (_in that order_) of [post_process/sql/dedupe.sql](../post_process/sql/dedupe.sql).


#### Overview
The following root causes result in dupes in the output dataset.
```text
❗NOTE: future improvements to the TWJF should result in only one dupe case (normal dupes) in our data.
This requires updating the data fetching (BQ or GCS) handles in the TWJF, such that records outside the target
airline_iata match are pulled into a flight_id group.
This should result in deterministic behavior, whereby the priority-value rule of the healing handler
will write the highest prevalence airline_iata in all cases.
```

##### False Null `airline_iata` Case
The first is when we observe two airline iatas for a given `flight_id` -- the true airline iata (non-null) and the 
conflicting null airline iata. We attempt to gate these from passing through the TWJF, but some make it thru.
The root cause of these false null airline iata dupes comes from the TWJF run with `airline_iata: "null"`, 
which will build flight trajectories both for flights where "null" is the _only_ observed airline iata value for _all_
waypoints in a given `flight_id` waypoint group, and, will build phony trajectories from spurious records of a `flight_id` waypoint group
where just a few of the group's records have `null` airline iata.

In other words, a "null" airline iata has two meanings. A true null airline iata is a flight where there is no airline iata
listed for the flight. A false null airline iata is where a flight does have a true non-null airline iata, but some records are missing it in the airline iata k-v.

##### Conflicting `airline_iata` Case
Similar to the false `null` airline iata case, we sometimes see two flights minted for the same `flight_id`,
if the flight shows up with a sufficiently high prevalence of flip-flop in the `airline_iata` that both flights make it thru
the TWJF validation handler.

Unlike the false `null` case, we don't have a good rule regarding which of the two dupes to keep.
As such, we choose to randomly eject one of the two (with the expectation that future improvements will eliminate this issue).

##### Normal Dupes
Normal dupes may occur if pubsub spuriously redelivers a message.
In this case, we'd expect the entire row to be an exact replica across the dupe.

### Log Processing
The TWJF, TW and TW-backup logs are processed to generate a consolidated and structured record
of the events affecting a flight in each service.

For instance, the TWJF logs will provide a record of whether or not a given flight (`flight_id`)
passed the ValidationHandler and was passed to the trajectory worker, or, ejected from the pipeline (and if so, for what reasons).
For flights that do pass the TWJF, the logs will also provide some information on the manipulations
that took place to the flight (did we interpolate the flight to the origin airport location? etc...).

The TW and TW-backup logs will generally provide a record of whether or not a flight was ejected from the TW 
due to known reasons (for instance, the engine or aircraft type not being recognized and present in the performance lookup).

Lastly, the logs of all three will identify cases where we may have ejected a flight due to unknown/unexpected reasons (irrecoverable failures).

#### Post Processing Logs
##### Upload to BQ
TODO
##### Structure & Derive Stats
TODO

#### Archiving Post Processed Logs
TODO