# Spire Data Notes

Our ADS-B dataset from Spire has had issues over time. The original ETL pipeline had some holes and there are therefore missing data before the modern-era pipeline was introduced in 2024 which breaks queries into small chunks and tracks progress with a Firebase progress marker.

# Known Issues

## 2022-2023 Flight Numbers Missing
The `flight_number` values are all missing from the Spire dataset from 2022-02-11 through 2023-03-30.

## Before ~2024-04 flight_id imputation
Before 2024-04, there was no good identifier of flights from Spire. We imputed our own.  These imputed `flight_id` values all end with `==` and the `flight_id` values can contain forward slashes (`/`), which can make saving files using flight_id problematic. These records are all given `src_id = "spire_legacy"`. More recent data have `src_id = "spire"`.

## 2026-09-27 Gap
A schema break and service gap happened on 2026-09-27 resulting in loss of most data for the day. Spire will update us with the range of the outage and should provide data to patch the gap.
