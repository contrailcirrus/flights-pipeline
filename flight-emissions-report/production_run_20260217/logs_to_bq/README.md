# (TWJF) logs to BQ

Some initial exploration work looking at how we could load log files from the Trajectory Worker Job Factory
GCS file sync into BQ, and use BQ tooling to do some/all of our (pre-)aggregation analysis.

## Limitations
There is one know hard-block limitation.
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

Note that we use the `twjd_logs_bq_schema_lean.json`, which drops several of the `jsonPayload` fields (those affected by [#Limitations](#limitations)).

Even with those fields missing, we can do some powerful initial analysis (and if those fields were added in the future, we could extend BQ to handle those fields).

### Step 2: jiujitsu

The [example_analysis.sql](example_analysis.sql) query will build from this table of logs.

This example query will (TL;DR):
- create a CTE with a record of the initial state of all flights entering the TWJF (`start work`), calculating the initial flight duration from the raw ADS-B
- create a CTE with a record of the flights post-resample, with a calculation of the final duration of the flight
- create a CTE segregating the flights that were ejected/skipped
- create a CTE with those flights that passed (i.e. were present entering the TWJF, and _not_ found in the skipped records)
- create a CTE, calculating and binning the total ejected flight time per month, based on the skipped flights CTE & the initial duration of those flights
- create a CTE, calculating and binning the total passed flight time per month, based on the passed flights CTE & the post-resample duration of those flights
- create a final summary output, joining the skipped and passed data

The output of this query looks like:
![](bq_load_example.sh)

