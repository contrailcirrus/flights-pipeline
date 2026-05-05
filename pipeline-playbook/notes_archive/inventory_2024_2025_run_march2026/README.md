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
notes: run on nick's VM
```

#### Run 1.3
```text
start: March 25 02:27 UTC
airline_iata: runlist_C.txt
range: 2024-01-01_2025-12-31
notes: run on nick's VM
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
or being in the PS/BADA list of accepted aircraft types.  If we are concerned with improving perf, we may want to filter these at 
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
