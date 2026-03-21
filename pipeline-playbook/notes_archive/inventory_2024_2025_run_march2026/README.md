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

## VM run cmd ref
```bash
cat cli_runlist_run_<B/C>.txt | xargs -I % ./cli.py jobworker submit -a % -d 2024-01-01_2024-12-31 -w gcs -s era5 -t > my_airline_iatas.log 2>&1 &

```