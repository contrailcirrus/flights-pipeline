# (TWJF) logs to BQ

This describes our process for loading log files from the Trajectory Worker Job Factory
GCS file sync into BigQuery, and how we use BQ tooling to do some/all of our (pre-)aggregation analysis.

## Data
The logs are set up to copy to a GCS bucket via the Google Cloud Log Sink mechanism which copies logs every hour for the previous hour. These logs end up [here](gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr). After the Mar. 2026 run through of the 2024-2025 Spire data, we saved the logs [here](gs://contrails-301217-flights-pipeline-prod/logs/inventory_2024-2025_run_mar2026). 

## Limitations
This Mar. 2026 run had some inconsistencies in the format of the `jsonPayload.reason` field where it was sometimes provided as an array, and sometimes as a nullable string. Notes on how this was handled are detailed in the notes for that run and should be fixed moving forward. Similarly, we added the `jsonPayload.job_hash` field to the schema for the logs table, but it has not been included in this dataset, though it will be in the future.

## Playbook
Here is an example flow.

### Step 1: load all logs into BQ
Load all the newline JSON log files for a given run into a BQ table by modifying and then running [bq_load_twjf_logs.sh](bq_load_twjf_logs.sh), [bq_load_tw_logs.sh](bq_load_tw_logs.sh), [bq_load_tw_backup_logs.sh](bq_load_tw_backup_logs.sh).

We use the `logs_bq_table_schema.json`, which is harmonized to handle TWJF and TW logs, but which may need to be updated if any of the log messages to be captured change.

### Step 2: Querying the logs

The [total_time_and_skipped.sql](../sql/total_time_and_skipped.sql) SQL query pulls the total flight time in minutes binned by month, and provides skipped time both from the TWJF and TW by linking results with those from the final results table which has outputs from the TW. Here's what those results look like:

[](total_minutes_skipped.png)

This example query:
- creates a CTE with a record of the initial state of all flights entering the TWJF (`start work`), calculating the initial flight duration from the raw ADS-B
- create a CTE with a record of the flights post-resample, with a calculation of the final duration of the flight
- create a CTE segregating the flights that were ejected/skipped
- create a CTE segregation flights from the results BQ table (TW output) with appropriate time bounds and binned by month
- create a CTE with those flights that passed the TWJF (i.e. were present entering the TWJF, and _not_ found in the skipped records)
- create a CTE calculating and binning the total ejected flight time per month, based on the skipped flights CTE & the initial duration of those flights
- create a CTE calculating and binning the total passed flight time per month, based on the passed flights CTE & the post-resample duration of those flights
- create a final summary output, joining the skipped, passed, and final results data along with fractions dropped/skipped at each step.

The output of this query looks like this:

![](example_analysis_query.png)

Another SQL query helps disambiguate the reasons for TWJF skipping: [skipped_reasons_by_month.sql](../sql/skipped_reasons_by_month.sql). This query uses the logs and separates out skipped flights, then bins them by skip type and month.

The first month of skip reasons for the Feb. 2026 run of the 2024 Spire data looks like this:

[](skip_reasons.png)