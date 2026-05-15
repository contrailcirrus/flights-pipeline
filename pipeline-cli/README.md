# Pipeline CLI
A basic CLI for manually minting Trajectory Worker Job Descriptors (TWJDs), and submitting 
them to the work queue for the Trajectory Worker Job Factory (TWJF).

## Use
The CLI can be used to create the following job types.

### all flight on an airline-day
Example:
```bash
# all flights with airline iata designator AA (American Airlines) on 2025-01-01
./cli.py -a AA -d 2025-01-01
```

```bash
# all flights with ... over date range (inclusive) 2025-01-01 -> 2025-02-12
./cli.py -a AA -d 2025-01-01
```

Note: this finds all flights that originate on (first waypoint timestamp) within the calendar day specified

### flights matching one or more flight id values
Example:
```bash
# one flight with matching flight id
./cli.py jobworker submit -d 2025-05-16 -i 60e21ddd-b87f-423e-a5db-a2f12d5dd40a

# two flights with matching flight id
./cli.py jobworker submit -d 2025-05-16 -i 60e21ddd-b87f-423e-a5db-a2f12d5dd40a 2eefb1a9-28b1-4a7b-ac7c-343d7fdc7a30
```

Note: the `flight_id` passed to the CLI _must originate (first waypoint timestamp)_ on the calendar day specified.  
If multiple `flight_id` are submitted, all must fall on the calendar day.

### General args
The following arguments can be used with either job submission type:
- `-r` dry-run mode. Will run the TWJF, but the TWJF will not submit the processed flights onward to the trajectory workers
- `-w` telemetry source for fetching the ADS-B records.  Must be either of `bq` (default) or `gcs`
- `-s` meteorological data type. Must be either `era5` or `hres`

