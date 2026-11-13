# Pipeline Cheatsheet

Overview of tasks for running a pipeline.

1. Empty ERA5 staging bucket. Load ERA5 data for relevant timeframe -1day + 2days into bucket with `copy_era5_gcs_to_staging.sh` 
2. Create hyperdisk.
3. Clear results table `contrails-301217.flights_pipeline_prod.trajectory_cocip_prod`.
4. Clear logs sink buckets in `gs://contrails-301217-fp-prod-trajectory-*`.
5. Warm GCS Spire Cache.
6. Create jobs BQ table. Export jobs list as text file.
7. Update hyperdisk bandwidth to 80000MB/s.
8. Run CLI against jobs list.
9. Scale up TWJF workers when queue builds up.
10. Add 55 k8s standard cluster nodes.
11. Scale TW workers to 4760.
12. Monitor Hyperdisk bandwidth usage, log errors, queue depth and drain rate, and ack rate. A good run rate is ~ 4 acks/min/CPU.
13. When TWJF is done, scale back, verify no deadletter jobs.
14. When TW is done, verify no deadletter jobs remaining, return nodes to 0, remove hyperdisk.
15. Load data from `trajectory_cocip_prod` into new summary and segments BQ tables and dedupe.
16. Copy logs to `gs://contrails-301217-flights-pipeline-prod/logs`
17. Load TWJF, TW, and TW-Backup logs into new log table.
18. Remove logs from `gs://contrails-301217-fp-prod-trajectory-worker*` buckets.
19. Clear out `trajectory_cocip_prod` BQ table in preparation for next run.
20. Run `total_time_and_skipped.sql` and `skipped_reasons_by_year_all_counts.sql` and put results into `DATASETS.md`.
21. Export data for bq-to-postgres tool with [0_bigquery_export.sql](../bq-to-postgres-util/sql/0_bigquery_export.sql) to GCS at `gs://contrails-301217-sandbox-internal/flights-pipeline/emissions-export/<target_date_range>/<process_time>/*.pq`.
22. Run `bq-to-postgres` tool into dev with e.g. `./main.py --db_user "postgres" --db_password $PSDB_CONTRAILS_DEFAULT_PWD_POSTGRES_DEV --db_host "34.23.237.52" --gcs_paths "flights-pipeline/emissions-export/2026Q3/20261019"  2>&1 | tee 2026Q3-dev.log`
23. Refresh materialized views in dev postgres.
24. Check record count against BQ, noting that a few records usually start before or start after the nominal cutoffs for the dataset.
25. Add dataset to contrails-api in `app/internal/schemas.py` and `app/v1/inventory.py`.
26. Add extended cutoff and adjust default date view in impact-explorer `src/constants/index.ts`.
27. Run `bq-to-postgres` tool into prod.
28. Refresh materialized views in prod postgres.
29. Check record count against dev.
30. Merge impact-explorer and api changes into main branches to deploy the update.
31. Export data from BQ to CSV in `gs://contrails-301217-bq-sandbox-transfer-tmp-src/google-tim/` for Google TIM.
32. SFTP CSV files to Google server.
33. E-mail Google TIM team about data update.
34. Commit and push notes from inventory run.