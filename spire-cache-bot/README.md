# Spire Cache Bot

## Description
A simple cron service, triggered hourly, which hits the [`v1/adsb/telemetry` endpoint](https://api.contrails.org/openapi#/ADS-B/get_telemetry_v1_adsb_telemetry_get) 
with the intention of having the API populate the spire cache in GCS (`gs://contrails-301217-spire-cache-prod`).

