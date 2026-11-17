# Spire Data Notes

Our ADS-B dataset from Spire has had issues over time. The original ETL pipeline had some holes and there are therefore missing data before the modern-era pipeline was introduced in 2024 which breaks queries into small chunks and tracks progress with a Firebase progress marker.

# Known Issues

## 2022-2023 Flight Numbers Missing
The `flight_number` values are all missing from the Spire dataset from 2022-02-11 through 2023-03-30.

## Before ~2024-04 flight_id imputation
Before 2024-04, there was no good identifier of flights from Spire. We imputed our own.  These imputed `flight_id` values all end with `==` and the `flight_id` values can contain forward slashes (`/`), which can make saving files using flight_id problematic. These records are all given `src_id = "spire_legacy"`. More recent data have `src_id = "spire"`.

## 2026-09-27 Gap
A schema break and service gap happened on 2026-09-27 resulting in loss of most data for the day. Spire supplied us with data to patch in. There seemed to be a fair bit of overlapping data, and our data through the supposed outage time wasn't blank - we had some data (~2M records after 30sec sampling) - even though Spire claimed the outage to be complete between 00:30–09:20 UTC. 

The dataset they provided is in [this bucket](gs://breakthrough_energy-ju39z608odzckkkz/backfill-27-09-26), and we copied it into this BQ table: `gs://contrails-301217.flights_pipeline_prod.spire_backfill_20260927` which has 421,862,718 records and takes up 88.3GB.

We noted steps taken to patch this into our `spire_flights_raw_prod` BQ table in [this issue](https://github.com/contrailcirrus/flights-pipeline/issues/709). The basic steps taken were to copy all data from `spire_flights_raw_prod` into a backup table, copy the Spire patch data in, downsample to 30-seconds, remove the existing day of data from `spire_flights_raw_prod`, then copy in the merged table containing our existing records and the patch data Spire provided. There is no apparent drop in number of flights day over day (incident was a Sunday) or week over week.

