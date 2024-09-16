# Flight Emissions Report (FER)

## Description

## CLI
This repo houses src code for invoking a command line tool.
The CLI is invoked by running `./gaia_cli.py` (it is _not_, by design, an installable CLI).

## Daily FER Cronjob
This repo also houses a kubernetes CronJob wrapper ([`main_cron.py`](main_cron.py)).
The cronjob iterates through a list of targets (either airlines, or individual aircraft),
and submits jobs to the trajectory worker for all flights from those targets that originated
(takeoff time) two days prior.  Each job represents a single flight instance, 
the output being a single flights summary stats.

This cron runs daily.

The output from those jobs is written to the big query table `trajectory_cocip_prod` 
(as are all other jobs from the trajectory workers).
The outputs from the daily FER cronjob can be disambiguated from other trajectory worker records
by including `source_id="flightsreport"`.

# Using the CLI
 
### Manual Job Dispatch (`flights submit` )
A "job" in this context represents a single flight instance.
Submitting a job means enqueueing it for the trajectory worker.
The trajectory worker runs CoCip against the trajectory for the flight instance, and writes the outputs to BigQuery.

The output to bigquery can either be a single row (summary stats) for the flight instance (default), or,
one-row per flight segment (1min) of the flight instance (include the flag `-t` in the CLI invocation).

The CLI is designed to help with dispatching batches of jobs.

Required flag combinations:
- `-a <airline_iata> -d <day>` this submits multiple jobs representing all flights originating 
for `<airline_iata>` originating on day (utc) of `<day>`. 
Originating means the first waypoint in the trajectory falls on `<day>`.
- `-c <icao_addr>` this submits multiple jobs representing all flights for 
a single aircraft (`<icao_addr>`) originating on day (utc) of `<day>`.
- `-i <flight_id>` this submits a single job representing a single 
flight instance (`<flight_id>`) which has origination on day (utc) of `<day>`.

Optional flags:
- `-e` this writes to file the resampled ADS-B data for each flight instance.
The data written locally represents exactly the ADS-B trajectory submitted to the trajectory worker.
This is a useful flag for fetching input data when investigating and reproducing behavior of the trajectory worker,
or, can be used as a convenient way to fetch clean, resampled data for groups of flights.
- `-t` this tells the trajectory worker to export to big query per-segment data in 
addition to the full flight trajectory summary.  Records written to BQ using this flag show up 
with `source_id="flightsreport_full"` rather than the default of 
per flight summary data only (`"flightsreport"`).
- `-v` this runs the CLI in verbose mode. This writes to stderr additional info such as the
number of waypoints retrieved from bigquery for each flight (terrestrial vs. sat), 
the number of waypoints ejected during trajectory validation, etc.
- `-r` this runs the CLI in dry-run mode. This will go through all the steps of 
fetching, resampling, packaging etc... of jobs,
but will _not_ publish the jobs to the job queue.

**Examples**

```bash
# submit all flights for American Airlines that originate on Jan 12, 2024 (UTC), printout verbose
./gaia_cli.py flights submit -a AA -d 2024-01-12 -v
```

```bash
# submit all flights for aircraft w/ icao 3C6565 that originate on Jun 06, 2024 (UTC)
# tell trajectory worker to write-off both per-flight summaries, as well as per-flight-segment values
./gaia_cli.py flights submit -c 3C6565 -d 2024-06-01 -t
```

```bash
# fetch all flights for KLM that originate on Apr 02, 2024, printout verbose
# save CSVs for the resampled ADS-B flight trajectories to local disk
# does NOT submit the jobs
./gaia_cli.py flights submit -a KL -d 2024-04-02 -e -v -r
```

### Job Re-injection (`flights reinject`)
This method is used for re-injected dead-lettered jobs back into the worker queue.

Optional flags:
- `-c <COUNT>` specify the number of messages to dequeue from the dead-letter subscription 
and reinject into the trajectory worker topic. Setting `-c <COUNT>` does not guarantee that
`<COUNT>` messages are re-injected (it attempts to dequeue this many, sometimes gets less). 
Defaults to 1.
- `-v` verbose mode. Includes some information about the message(s) dequeued from the dead-letter.
- `-r` dry run mode. Dequeue the message from the dead-letter queue, but do not reinject into the trajectory worker topic.
Note that these messages are nack'ed, so they remain in the dead-letter queue 
(they do _not_ get dropped from the dead letter queue).

**Examples**

```bash
# fetch up to 50 dead-lettered jobs and reinject them into the trajectory worker job queue
./gaia_cli.py flights reinject -c 50
```

```bash
# fetch a single message from the dead-letter queue, printout info on that job, but do not reinject
./gaia_cli.py fights reinject -v -r
```

### Report Generation (`report fetch`)
The CLI can be used to fetch outputs from the trajectory worker's big query table, 
and download those data locally (for composing a final emissions report).

Exported assets include:
- `flights_report_external_*.csv` per-flight summary data, sanitized for external sharing
- `flights_report_internal_*.csv` per-flight summary data, including all outputs
- `flights_report_summary_*.json` summary stats across all flights
- `*.png` assortment of visual assets

Required flags:
- `-a <airline_iata>` airline iata for which to pull outputs.
- `-d <date_or_range>` date or date range for which to pull outputs. Can be of the form `2024-04-01`,
which pulls data for all flights originating on that date (UTC), or, `2024-04-01_2024-04-30` which 
pulls data for all flights originating between those two date (UTC), inclusive.

Optional flags:
- `-v` verbose mode. Includes sterr logs w/ additional summary stats on those data fetched from BQ.
- `-r` dry run mode. This will dispatch a query to BQ, pull the data, apply the report-generation
data mongering, but, will _not_ write any assets to local file.
- `-g <FILEPATH>` google synthesis.  This expects a `<FILEPATH>` pointing to a local file containing
Google's flight-matching outputs.  If this flag is used, then the output assets will include summary
stats that use Google's flight matching for the target airline/date(s).


## Setup
This CLI is not (at present) build to be installable/deployable.

First, set up a local environment, similar to our other services, installing dependencies from the `Pipfile.lock`.

Note:
Depending on your terminal/IDE, you may need to source your environment to the current shell
before invoking the CLI (`pipenv shell`).

Next, run the CLI by calling the entrypoint script as an executable: `./gaia-cli.py <ARGS>`

