# (TWJF) logs to BQ

This describes our process for loading log files from the Trajectory Worker Job Factory
GCS file sync into BigQuery, and how we use BQ tooling to do some/all of our (pre-)aggregation analysis.

## Data
The logs are set up to copy to a GCS bucket via the Google Cloud Log Sink mechanism which copies logs every hour for the previous hour. These logs end up [here](gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr). After the Feb. 2026 run through of the 2024 Spire data, we saved the logs [here](gs://contrails-301217-sandbox-internal/flights-pipeline/flights-pipeline/inventory_2024_run_feb2026). There were two runs (run1, and run2), which had `airline_iata not null` and `airline_iata null` respectively.

## Limitations
There is one known hard-block limitation.
The logs we generated in the Feb16-Feb20 run of 2024 flight data packages several output fields as arrays.
For instance, `airline_iata`, `callsign`, etc...
```text
"jsonPayload":{"airline_iata":["AA"],"arrival_airport_icao":["KRDU"],"asyncio_taskname":null,"callsign":["AAL2683"],"departure_airport_icao":["KDFW"],"end_time":"2024-01-11T15:24:58Z","flight_id":"+/4Aw2SJedk+Gc52z6eYqA==","flight_number":["AA2683"],"message":"start work","pid":1,"start_time":"2024-01-11T13:28:55Z","thread":133308409215872,"timestamp":"2026-02-17T23:29:56.428684+00:00","waypoint_count":234}
```

This is not a problem for BQ. We can define the type of these values as arrays, and if the k-v is missing,
it would show up as empty (`null`) in BQ.

_BUT_, BQ does not allows `null` values _in_ an array.

So BQ load will fail for lines where we have, e.g.
```text
"arrival_airport_icao":["KRDU", null]
```

This is unfortunate, and there are no params we can pass to `bq load` to have it coerce such cases.

The only fix here is for us to convert true `null` values in our log message outputs to string literal `"null"`.
This would be a good logging enhancement/change to the TWJD, to be reflected in future runs, 
but won't help us for the existing 2024 inventory run.

## Playbook
Here is an example flow.

### Step 1: load all logs into BQ
Load all the newline JSON log files for a given run into a BQ table.
See this [bq load command](bq_load_example.sh).

We use the `twjd_logs_bq_schema.json`, which may need to be updated if any of the log messages to be captured change.

Even with those fields missing, we can do some powerful initial analysis (and if those fields were added in the future, we could extend BQ to handle those fields).

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