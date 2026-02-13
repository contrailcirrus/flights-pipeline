Log Processor
=============

Utility to process Flights-Pipeline Trajectory-Worker-Job-Factory Logs from the json files in the GCS bucket log sink of the TWJF GKE pod.

Features
- Reads JSON arrays or newline-delimited JSON (NDJSON).
- Extracts all JSON fields: timestamp, severity, message, flight_id, etc.
- Methods to pull unique, skipped, error, and all non-processed flight_ids