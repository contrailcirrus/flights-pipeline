# Flight Emissions Report

## Description
This repo houses src code for invoking a command line tool.
The CLI (`gaia_cli.py`) is used for

### Manual Job Dispatch
A "job" in this context is a flight instance.
Submitting a job means enqueueing it for the trajectory worker.
The trajectory worker runs CoCip against the trajectory for the flight instance, and writes the outputs to BigQuery.

The CLI is designed to help with dispatching batches of jobs.

Currently, this includes making a single call to the CLI to:
- submit all flights for a given airline, where those flights originated on a given calendar day
- submit all flights for a given `icao_address`, where those flights originated on a given calendar day
- submit a single flight instance, based on the `flight_id` and calendar day on which the flight originated

### Report Generation
The CLI can be used to fetch outputs from the trajectory worker, and download those data locally (for composing the final emissions report).

At present, the CLI can be invoked to pull and aggregate flight data for a given airline on a given calendar day.

### Job Reinjection
The CLI can be used to automate the reinjection of failed jobs, 
which get quarantined to a dead-letter queue if the trajectory worker fails to process a given flight instance.

## Setup
This CLI is not (at present) build to be installable/deployable.

First, set up a local enviornment, similar to our other services, installing dependencies from the `Pipfile.lock`.

Next, run the CLI by calling the entrypoint script as an executable: `./gaia-cli.py <COMMANDS>`

### Operations

#### `flights submit`
```bash
./gaia-cli.py flights submit <ARGS>
```

Submit trajectories for flight instances to the trajectory worker.

Example call:
```bash
./gaia-cli.py flights submit -a KL -d 2024-07-01 --export-waypoints --dry-run --verbose
```
This call would submit all flights for KLM (airline iata `KL`), where those flights originated on 2024-07-01.

The `--export-waypoints` option is used to download a CSV that include the 1-min resampled trajectories for those flights.
The CLI pull raw waypoints from the spire raw BQ table, and resamples locally.
Outputting these resampled waypoints serves as a source-of-truth of the trajectory that was submitted to the trajectory worker.

The `--dry-run` option will run all src code, downloading the raw data, resampling and preparing jobs for submission.
But, it will stop short of actually publishing those jobs to the trajectory worker job queue.

The `--verbose` option will output additional information about the set of flights instances being processed.

#### `flights reinject`

Reinject jobs from the dead letter queue back into the job queue.

Example call:
```bash
./gaia_cli.py flights reinject -c 1 --dry-run --verbose
```

This call will pull up to but not exceeding `-c <COUNT>` jobs from the dead letter queue.


If the optional `--dry-run` flag is included, the job is not reinjected into the worker queue,
nor is the job ack'ed and removed from the dead letter queue.


#### `report fetch`
``` bash
./gaia-cli.py report fetch <ARGS>
```

Fetch outputs from the trajectory worker, and compose output assets (CSVs, JSON) of those data.

Example call:
```bash
./gaia-cli.py report fetch -a KL -d 2024-07-01 --verbose
```

This call would fetch the outputs from the previously-processed flights for KLM (iata: `KL`) on `2024-07-01`.

The CLI will write locally three files:
- a CSV file, one row per flight instance, including all outputs stored in the BQ table
- a CSV file, one row per flight instance, with renamed and minified content, suitable for sharing externally
- a JSON file, with summary stats on the full corpus of flights

The `--verbose` option will output additional summary information on the flights retrieved from BQ.

