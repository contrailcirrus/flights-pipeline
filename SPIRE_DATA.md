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


Here is the data source change table we pass along with the data to customers:

## Changes in inputs over time

| Date | Change | What it means for the data |
|---|---|---|
| 2019--2021 | The historical archive. Gaps in a track are filled with a great-circle path. More flights are excluded for airport mismatches([§9](#9-flights-excluded-from-the-dataset)). |
| 2022-01-01 | Switch from the historical archive to Spire's own data feed. Nearly 10x terrestrial sampling density. | Denser sampling. Track splitting and identifier by Spire ([§8.1](#81-flight_id)). The airline code is supplied by Spire instead of being taken from the flight number. |
| 2022-02-11 → 2023-03-30 | Flight numbers missing from the Spire data. | `flight_number` is empty for this period ([§8.2](#82-flight-number-and-callsign)). |
| 2024-04-24 | Spire starts supplying its own flight identifier. | `flight_id` changes format ([§8.1](#81-flight_id)). A short period around the changeover may be missing ([§4.1](#41-coverage-gaps)). |
| 2025-04-09 | Spire moves to a combined ("fused") data feed. | More positions per flight. Identifiers of flights in the air at the switch were carried over to the new feed. |
| 2025-09-23 | Sampling increased to one position per 30 seconds. | Subtly better aliasing performance around small data gaps. |
| 2025-12-13 | Spire's satellite data completely drops out. | Large portions of trans-oceanic flights missing and had to be interpolated. |
| 2024-04-04 | Spire's satellite data returns very marginally with ~10x less data than before. | Still large portions of trans-oceanic flights missing and interpolated. |
| 2026-05-01 | Spire's satellite data coverage returns to pre 2025-levels. | Approximate date. |
| 2026-09-27 | Spire outage (about 00:30–09:20 UTC). | Filled with data supplied by Spire afterwards. Daily flight counts show no visible drop. |
| 2026-10-01 onward | `time_end_tz` corrected | Datasets prior to this had end timezone set based on the trajectory starting point by mistake. Final datapoint in each trajectory included; previously it was erroneously removed. |