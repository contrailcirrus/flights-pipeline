#!/usr/bin/env bash

# example invocation of bq load to put twjd log files into a bq table
# ------
# https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference#bq_load
# https://docs.cloud.google.com/bigquery/docs/loading-data-cloud-storage-json

# TARGET FILES
# ----
# URI that encompasses exactly all logs for a given run
# -
# if exactly all logs for a given run can't be referenced with a single glob
# then this command may need to be executed several times over a list of globs
# that completely and exactly target logs for a given run
URI_GLOB="gs://contrails-301217-fp-prod-trajectory-worker-job-factory/stderr/2026/02/*"

# TARGET TABLE
# ---
# table in BigQuery where the raw TWJF logs are uploaded
# -
# format should be similar to twjf_{inventory_period}_logs_{run_date}
TARGET_TABLE="twjf_2024_logs_feb2026_EXAMPLE"

bq load --schema_update_option=ALLOW_FIELD_ADDITION --ignore_unknown_values --source_format=NEWLINE_DELIMITED_JSON \
--schema=twjd_logs_bq_schema_lean.json flights_pipeline_prod.${TARGET_TABLE} "${URI_GLOB}"