# Pipeline CLI
A basic CLI for manually minting Trajectory Worker Job Descriptors (TWJDs), and submitting 
them to the work queue for the Trajectory Worker Job Factory (TWJF).

## Use
The CLI can be used to create the following job types.

### all flight on an airline-day
Example:
```bash
# all flights with airline iata designator AA (American Airlines) on 2025-01-01
./cli.py -a AA -d 2025-01-01 -s era5
```

```bash
# all flights with ... over date range (inclusive) 2025-01-01 -> 2025-02-12
./cli.py -a AA -d 2025-01-01_2025-02-12 -s era5
```

Note: this finds all flights that originate on (first waypoint timestamp) within the calendar day specified

### flights matching one or more flight id values
Example:
```bash
# one flight with matching flight id
./cli.py jobworker submit -d 2025-05-16 -i 60e21ddd-b87f-423e-a5db-a2f12d5dd40a -s era5

# two flights with matching flight id
./cli.py jobworker submit -d 2025-05-16 -i 60e21ddd-b87f-423e-a5db-a2f12d5dd40a 2eefb1a9-28b1-4a7b-ac7c-343d7fdc7a30 -s era5
```

Note: the `flight_id` passed to the CLI _must originate (first waypoint timestamp)_ on the calendar day specified.  
If multiple `flight_id` are submitted, all must fall on the calendar day.

### General args
The following arguments can be used with either job submission type:
- `-r` dry-run mode. Will run the TWJF, but the TWJF will not submit the processed flights onward to the trajectory workers
- `-t` instructs trajectory worker to export the per-segment CoCiP outputs to BQ, as well as the flight data protobuf blob in GCS
- `-w` telemetry source for fetching the ADS-B records.  Must be either of `bq` (default) or `gcs`
- `-s` (REQUIRED) meteorological data type. Must be either `era5` or `hres`.

## Create Large Batch Jobs
The CLI also supports minting TWJDs that tell the TWJF to process large batch jobs.

A large batch job is a list of target `flight_id` values, with a `job_id` reference.
In order for this to work, 
the TWJF expects there to be a lookup table in the `flights_pipeline_prod` BigQuery dataset, 
that provides `job_id` -> `flight_id` lookups.

That lookup table must have the following columns:
```text
job_id: STRING  # e.g. 7151bdb1-8487-4d0b-b22a-df33c79dd6b0
day: STRING  # e.g. 2025-01-01
flight_id_list ARRAY[STRING]
```

At present, there is no convenient tooling to generate this lookup.  
The following, however, is an example end-to-end process.

### Setup
First, create a new table in `flights_pipeline_prod`, with your custom job batch lookup.

Here is an example of how to create that table based on some SQL jiujitsu against the raw spire data (`flights_pipeline_prod.spire_flights_raw_prod`).

This creates a table with a single row that contains:
- `job_id` a unique job identifier (in the below example `7151bdb1-8487-4d0b-b22a-df33c79dd6b0`)
- `day` a string with the calendar day, on which all the flight ids are known to have begun (first timestamp)
- `flight_id_list` a list (BQ array) with 10000 flight ids (that have at least one waypoint above 20k ft)

```sql
CREATE TABLE `contrails-301217.flights_pipeline_prod.job_batch_nbm_05152026_example` AS
    WITH flight_id_candidate_tb AS
             (SELECT flight_id, min(timestamp) AS min_ts, max(altitude_baro) AS max_alt_ft
              FROM `contrails-301217.flights_pipeline_prod.spire_flights_raw_prod`
              WHERE timestamp BETWEEN "2025-02-01" AND "2025-02-03" AND flight_id IS NOT NULL
              GROUP BY flight_id),
         flight_list AS (SELECT flight_id
                         FROM flight_id_candidate_tb
                         WHERE TIMESTAMP_TRUNC(min_ts, DAY) = "2025-02-02"
                           AND max_alt_ft > 20000
                         LIMIT 10000)
    SELECT GENERATE_UUID() AS job_id, "2025-02-02" AS day, ARRAY_AGG(flight_id) AS flight_id_list
    FROM flight_list
```

Running the CLI with a job ID generated from the above table will look something like:
```bash
# -j <job_id> -l <lookup_table_name>
./cli.py jobworker submit -j 507e8983-63a7-47d3-a359-36b14b5c4754 -l job_batch_nbm_05152026_example -w gcs -s era5 -r 
```

```bash
(cli) (base) nickmasson@BE-VY2VXKTWH9 pipeline-cli % ./cli.py jobworker submit -j 507e8983-63a7-47d3-a359-36b14b5c4754 -l job_batch_nbm_05152026_example -w gcs -s era5 -r 

{"timestamp":"2026-05-18 09:42:32,099", "severity": "INFO", "textPayload": "🛠️submitting TWJDs with 🔎 job_id: 507e8983-63a7-47d3-a359-36b14b5c4754 from ⊞ job_lookup_table: job_batch_nbm_05152026_example using met data source 📊era5", "labels":{"pid":"18901"}}
{"timestamp":"2026-05-18 09:42:32,099", "severity": "INFO", "textPayload": "⏲️ waiting for publish to finish...", "labels":{"pid":"18901"}}
{"timestamp":"2026-05-18 09:42:33,547", "severity": "INFO", "textPayload": "🙌 DONE!", "labels":{"pid":"18901"}}
```

Alternatively, you can pass the filepath to a list of newline delimited job-ids in a text file:

```bash
# -j <job_id_list_filepath> -l <lookup_table_name>
./cli.py jobworker submit -j job_id_list.txt -l job_batch_nbm_05152026_example -w gcs -s era5 -r 
```

`job_id_list.txt`:
```text
507e8983-63a7-47d3-a359-36b14b5c4754
28f0180c-fbea-4b7f-8fe4-6f96091ba4b3
c3b7b439-9ba5-4c11-8a9a-091b2c0afeed
```

```text
⚠️ The file MUST have suffix .txt
```
 