# Pipeline Cheatsheet

Overview of tasks for running a pipeline.

1. Empty ERA5 staging bucket. Load ERA5 data for relevant timeframe -1day + 2days into bucket with `copy_era5_gcs_to_staging.sh` 
2. Create hyperdisk.
3. Clear results table `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`.
4. Clear logs sink buckets in `gs://contrails-301217-fp-prod-trajectory-*`.
5. Warm GCS Spire Cache.
6. Create jobs BQ table. Export jobs list as text file.
7. Update hyperdisk bandwidth to 120000MB/s.
8. Run CLI against jobs list.
9. Scale up TWJF workers when queue builds up.
10. Add 55 k8s standard cluster nodes.
11. Scale TW workers to 7750.
12. Monitor Hyperdisk bandwidth usage, log errors, queue depth and drain rate, and ack rate. A good run rate is ~ 4 acks/min/CPU.
13. When TWJF is done, scale back, verify no deadletter jobs.
14. When TW is done, verify no deadletter jobs remaining, return nodes to 0, remove hyperdisk.
15. Load data from `trajectory_cocip_prod` into new summary and segments BQ tables.
16. Copy logs to `gs://contrails-301217-flights-pipeline-prod/logs`
17. Load TWJF, TW, and TW-Backup logs into new log table.
18. Remove logs from `gs://contrails-301217-fp-prod-trajectory-worker*` buckets.
19. Clear out `trajectory_cocip_prod` BQ table in preparation for next run.
20. Run `total_time_and_skipped.sql` and `skipped_reasons_by_year_all_counts.sql` and put results into `DATASETS.md`.
21. Run `bq-to-postgres` tool into dev with e.g. `./main.py --db_user "postgres" --db_password $PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES_DEV --db_host "34.23.237.52" --gcs_paths "flights-pipeline/emissions-export/2026Q3/20261019"  2>&1 | tee 2026Q3-dev.log`
22. Refresh materialized views in dev postgres.
23. Check record count against BQ, noting that a few records usually start before or start after the nominal cutoffs for the dataset.
24. Add dataset to contrails-api in `app/internal/schemas.py` and `app/v1/inventory.py`.
25. Add extended cutoff and adjust default date view in impact-explorer `src/constants/index.ts`.
26. Run `bq-to-postgres` tool into prod.
27. Refresh materialized views in prod postgres.
28. Check record count against dev.
29. Merge impact-explorer and api changes into main branches to deploy the update.
30. Export data from BQ to CSV in `gs://contrails-301217-bq-sandbox-transfer-tmp-src/google-tim/` for Google TIM.
31. SFTP CSV files to Google server.
32. E-mail Google TIM team about data update.
33. Commit and push notes from inventory run.