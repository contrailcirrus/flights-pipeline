# Datasets
The flights pipeline has been run on Spire data from 2019-2025. Each run generates four BigQuery tables, one for job_ids to segregate work units, one for per-flight inventory summaries, per-segment inventory segments, and logs from the flights-pipeline run used to generate the dataset. The run also creates parquet file stores with flight segments for each day in `gs://contrails-301217-flights-pipeline-prod/trajectory-worker/trajectory-pq`.

Below, we have a summary of each dataset, and some top-level statistics from the dataset.

## 2019
2019 dataset runs from 2019-01-02T00:00:00 to 2019-12-31T23:59:59. It was run 2026-06-15 -- 2026-06-17. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2019_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2019_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2019_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2019_run_june2026`


Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2019 datasets, we find the following monthly flight minutes breakdown:


| month | passed_minutes | skipped_minutes | total_final_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|
| 2019-12-01 | 278795059 | 173832862 | 249214849 | 38.41 | 6.54 | 44.94 |
| 2019-11-01 | 263285976 | 173904116 | 237833031 | 39.78 | 5.82 | 45.6 |
| 2019-10-01 | 271895372 | 198465926 | 245389910 | 42.19 | 5.64 | 47.83 |
| 2019-09-01 | 266360596 | 195516407 | 241873273 | 42.33 | 5.3 | 47.63 |
| 2019-08-01 | 253382105 | 201825520 | 231335251 | 44.34 | 4.84 | 49.18 |
| 2019-07-01 | 272030927 | 197839337 | 250853074 | 42.11 | 4.51 | 46.61 |
| 2019-06-01 | 255770206 | 186482269 | 235271494 | 42.17 | 4.64 | 46.8 |
| 2019-05-01 | 248476402 | 181178100 | 228065713 | 42.17 | 4.75 | 46.92 |
| 2019-04-01 | 242963022 | 174313884 | 222660394 | 41.77 | 4.87 | 46.64 |
| 2019-03-01 | 221841314 | 164726190 | 203683040 | 42.61 | 4.7 | 47.31 |
| 2019-02-01 | 201995082 | 159631738 | 185694151 | 44.14 | 4.51 | 48.65 |
| 2019-01-01 | 219924767 | 165584158 | 203719070 | 42.95 | 4.2 | 47.16 |


Using the [skipped_reasons_by_year.sql](sql/skipped_reasons_by_year.sql) query modified for the 2019 datasets, we find the following primary skip reasons from the TWJF:


| reason | reason_count | year |
|---|---|---|
| OriginAirportError | 1340523 | 2019 |
| DestinationAirportError | 1211388 | 2019 |
| FlightTooSlowError | 1177235 | 2019 |
| FlightTooShortError | 507401 | 2019 |
| FlightAltitudeProfileError | 160349 | 2019 |
| FlightTooLongError | 14552 | 2019 |
| FlightTooFastError | 4030 | 2019 |
| FlightTooSlowError | 1 | |
| OriginAirportError | 1 | |


## 2020

The 2020 dataset runs from 2020-01-01T00:00:00 to 2020-12-31T23:59:59. It was run 2026-06-18 -- 2026-06-19. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2020_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2020 datasets, we find the following monthly flight minutes breakdown:


| month | passed_minutes | skipped_minutes | total_final_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|
| 2020-12-01 | 191310163 | 54637574 | 163979036 | 22.22 | 11.11 | 33.33 |
| 2020-11-01 | 166198695 | 61808994 | 144348160 | 27.11 | 9.58 | 36.69 |
| 2020-10-01 | 163882902 | 73290608 | 140410364 | 30.9 | 9.9 | 40.8 |
| 2020-09-01 | 151784044 | 74806494 | 130281854 | 33.01 | 9.49 | 42.5 |
| 2020-08-01 | 158672913 | 75641919 | 136794686 | 32.28 | 9.34 | 41.62 |
| 2020-07-01 | 141894444 | 69209501 | 121099661 | 32.78 | 9.85 | 42.64 |
| 2020-06-01 | 101294427 | 60549836 | 83270726 | 37.41 | 11.14 | 48.55 |
| 2020-05-01 | 80068580 | 50598892 | 67479288 | 38.72 | 9.63 | 48.36 |
| 2020-04-01 | 64049581 | 41494010 | 56269439 | 39.31 | 7.37 | 46.69 |
| 2020-03-01 | 198708575 | 94939668 | 177582386 | 32.33 | 7.19 | 39.53 |
| 2020-02-01 | 246817762 | 115159461 | 221964163 | 31.81 | 6.87 | 38.68 |
| 2020-01-01 | 279200279 | 166594386 | 253984763 | 37.37 | 5.66 | 43.03 |

Using the [skipped_reasons_by_year.sql](sql/skipped_reasons_by_year.sql) query modified for the 2020 datasets, we find the following primary skip reasons from the TWJF:


| reason | reason_count | year |
|---|---|---|
| DestinationAirportError | 731779 | 2020 |
| FlightTooSlowError | 577656 | 2020 |
| OriginAirportError | 512774 | 2020 |
| FlightTooShortError | 338199 | 2020 |
| FlightAltitudeProfileError | 132752 | 2020 |
| FlightTooLongError | 6302 | 2020 |
| FlightTooFastError | 816 | 2020 |
| FlightTooSlowError | 5 | |
| DestinationAirportError | 3 | |
| OriginAirportError | 1 | |

## 2021

The 2021 dataset runs from 2021-01-01T00:00:00 to 2021-12-31T23:59:59. It was run 2026-06-19 -- 2026-06-20. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2021_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2021 datasets, we find the following monthly flight minutes breakdown:


| month | passed_minutes | skipped_minutes | total_final_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|
| 2021-12-01 | 236085924 | 98493410 | 200391920 | 29.44 | 10.67 | 40.11 |
| 2021-11-01 | 210265249 | 83929585 | 179115155 | 28.53 | 10.59 | 39.12 |
| 2021-10-01 | 218541485 | 99522559 | 186136922 | 31.29 | 10.19 | 41.48 |
| 2021-09-01 | 230017607 | 96915753 | 197022450 | 29.64 | 10.09 | 39.74 |
| 2021-08-01 | 248045480 | 68590331 | 214666382 | 21.66 | 10.54 | 32.2 |
| 2021-07-01 | 246785585 | 81886085 | 212916167 | 24.91 | 10.3 | 35.22 |
| 2021-06-01 | 212963118 | 72299357 | 181600436 | 25.34 | 10.99 | 36.34 |
| 2021-05-01 | 204653568 | 64299316 | 174884768 | 23.91 | 11.07 | 34.98 |
| 2021-04-01 | 201690864 | 56575035 | 172949685 | 21.91 | 11.13 | 33.03 |
| 2021-03-01 | 199149730 | 56701314 | 169983782 | 22.16 | 11.4 | 33.56 |
| 2021-02-01 | 145939716 | 49234116 | 123654712 | 25.23 | 11.42 | 36.64 |
| 2021-01-01 | 165788897 | 63410725 | 142635864 | 27.67 | 10.1 | 37.77 |


Using the [skipped_reasons_by_year.sql](sql/skipped_reasons_by_year.sql) query modified for the 2021 datasets, we find the following primary skip reasons from the TWJF:

| reason | reason_count | year |
|---|---|---|
| OriginAirportError | 606565 | 2021 |
| DestinationAirportError | 585867 | 2021 |
| FlightTooSlowError | 552327 | 2021 |
| FlightTooShortError | 307716 | 2021 |
| FlightAltitudeProfileError | 98736 | 2021 |
| FlightTooLongError | 6606 | 2021 |
| FlightTooFastError | 1054 | 2021 |
| FlightTooSlowError | 2 | |
| OriginAirportError | 2 | |
| DestinationAirportError | 2 | |


## 2022

The 2022 dataset runs from 2022-01-01T00:00:00 to 2022-12-31T23:59:59. It was run 2026-06-22 -- 2026-06-23. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2022_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2022 datasets, we find the following monthly flight minutes breakdown:

| month | passed_minutes | skipped_minutes | total_final_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|
| 2022-12-01 | 294459568 | 23210622 | 274501650 | 7.31 | 6.28 | 13.59 |
| 2022-11-01 | 272421658 | 22103837 | 257740411 | 7.5 | 4.98 | 12.49 |
| 2022-10-01 | 296529369 | 21179660 | 280802072 | 6.67 | 4.95 | 11.62 |
| 2022-09-01 | 291736690 | 25387278 | 276134930 | 8.01 | 4.92 | 12.93 |
| 2022-08-01 | 322775294 | 24457817 | 306369761 | 7.04 | 4.72 | 11.77 |
| 2022-07-01 | 322531348 | 26143576 | 305776317 | 7.5 | 4.81 | 12.3 |
| 2022-06-01 | 291108606 | 25947734 | 275140577 | 8.18 | 5.04 | 13.22 |
| 2022-05-01 | 268767874 | 29716794 | 253549006 | 9.96 | 5.1 | 15.05 |
| 2022-04-01 | 250999185 | 20757845 | 236851379 | 7.64 | 5.21 | 12.84 |
| 2022-03-01 | 191182847 | 22176625 | 179096262 | 10.39 | 5.66 | 16.06 |
| 2022-02-01 | 85117694 | 27210171 | 77506101 | 24.22 | 6.78 | 31.0 |
| 2022-01-01 | 210893309 | 69963794 | 201252337 | 24.91 | 3.43 | 28.34 |


Using the [skipped_reasons_by_year.sql](sql/skipped_reasons_by_year.sql) query modified for the 2022 datasets, we find the following primary skip reasons from the TWJF:


| reason | reason_count | year |
|---|---|---|
| FlightTooSlowError | 355010 | 2022 |
| FlightTooShortError | 226676 | 2022 |
| FlightAltitudeProfileError | 215316 | 2022 |
| OriginAirportError | 75862 | 2022 |
| DestinationAirportError | 65867 | 2022 |
| FlightTooLongError | 5827 | 2022 |
| FlightTooFastError | 1138 | 2022 |


## 2023

The 2023 dataset runs from 2023-01-01T00:00:00 to 2023-12-31T23:59:59. It was run 2026-06-24 -- 2026-06-25. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2023_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2023 datasets, we find the following monthly flight minutes breakdown:

| month | passed_minutes | skipped_minutes | total_final_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|
| 2023-12-01 | 325408997 | 69163803 | 305149108 | 17.53 | 5.13 | 22.66 |
| 2023-11-01 | 307048404 | 65992373 | 291407088 | 17.69 | 4.19 | 21.88 |
| 2023-10-01 | 330987496 | 71392642 | 314223030 | 17.74 | 4.17 | 21.91 |
| 2023-09-01 | 315331972 | 86114101 | 299701283 | 21.45 | 3.89 | 25.34 |
| 2023-08-01 | 340962816 | 87851584 | 324551423 | 20.49 | 3.83 | 24.31 |
| 2023-07-01 | 350113167 | 78850212 | 332619936 | 18.38 | 4.08 | 22.46 |
| 2023-06-01 | 323886611 | 75333355 | 306806822 | 18.87 | 4.28 | 23.15 |
| 2023-05-01 | 336920060 | 54371329 | 320268391 | 13.9 | 4.26 | 18.15 |
| 2023-04-01 | 323906104 | 47562403 | 308101033 | 12.8 | 4.25 | 17.06 |
| 2023-03-01 | 324836092 | 29394649 | 308555534 | 8.3 | 4.6 | 12.89 |
| 2023-02-01 | 284856775 | 22644240 | 270445175 | 7.36 | 4.69 | 12.05 |
| 2023-01-01 | 303389246 | 24845862 | 288082598 | 7.57 | 4.66 | 12.23 |


Using the [skipped_reasons_by_year.sql](sql/skipped_reasons_by_year.sql) query modified for the 2023 datasets, we find the following primary skip reasons from the TWJF:

| reason | reason_count | year |
|---|---|---|
| FlightTooSlowError | 475552 | 2023 |
| DestinationAirportError | 435269 | 2023 |
| OriginAirportError | 368614 | 2023 |
| FlightAltitudeProfileError | 265884 | 2023 |
| FlightTooFastError | 236875 | 2023 |
| FlightTooShortError | 190130 | 2023 |
| FlightTooLongError | 5512 | 2023 |


## 2024-2025

The 2024-2025 dataset runs from 2024-01-01T00:00:00 to 2025-12-31T23:59:59. It was run 2026-03-20 -- 2026-03-26. The BQ datasets produced were:

* Note: this dataset was run before we hae a job_id run mechanism for splitting TWJD work units, so no job id table.
* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2024_2025_run_march2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2024-2025 datasets, we find the following monthly flight minutes breakdown:

| month | passed_minutes | skipped_minutes | total_final_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|
| 2025-12-01 | 438475830 | 96506692 | 371958138 | 18.04 | 12.43 | 30.47 |
| 2025-11-01 | 418469095 | 109445502 | 359384495 | 20.73 | 11.19 | 31.92 |
| 2025-10-01 | 448168031 | 129160991 | 386705930 | 22.37 | 10.65 | 33.02 |
| 2025-09-01 | 429486327 | 140798144 | 370389830 | 24.69 | 10.36 | 35.05 |
| 2025-08-01 | 402143465 | 212484648 | 345509967 | 34.57 | 9.21 | 43.79 |
| 2025-07-01 | 398873242 | 218348674 | 342548869 | 35.38 | 9.13 | 44.5 |
| 2025-06-01 | 377672188 | 202283951 | 323133470 | 34.88 | 9.4 | 44.28 |
| 2025-05-01 | 390507447 | 217417092 | 335355094 | 35.76 | 9.07 | 44.84 |
| 2025-04-01 | 396739516 | 175947971 | 342584022 | 30.72 | 9.46 | 40.18 |
| 2025-03-01 | 423296220 | 116274266 | 366816039 | 21.55 | 10.47 | 32.02 |
| 2025-02-01 | 374617704 | 89195627 | 325603798 | 19.23 | 10.57 | 29.8 |
| 2025-01-01 | 405833912 | 83201548 | 355901856 | 17.01 | 10.21 | 27.22 |
| 2024-12-01 | 408674124 | 81238236 | 356812993 | 16.58 | 10.59 | 27.17 |
| 2024-11-01 | 384325423 | 92380003 | 334496994 | 19.38 | 10.45 | 29.83 |
| 2024-10-01 | 418932848 | 111676780 | 364462151 | 21.05 | 10.27 | 31.31 |
| 2024-09-01 | 409843573 | 106288615 | 357584420 | 20.59 | 10.13 | 30.72 |
| 2024-08-01 | 430415754 | 120992009 | 377667859 | 21.94 | 9.57 | 31.51 |
| 2024-07-01 | 437215146 | 124029673 | 383402472 | 22.1 | 9.59 | 31.69 |
| 2024-06-01 | 409743148 | 113765669 | 357594334 | 21.73 | 9.96 | 31.69 |
| 2024-05-01 | 397855208 | 116679297 | 345396402 | 22.68 | 10.2 | 32.87 |
| 2024-04-01 | 331968037 | 71180693 | 305980670 | 17.66 | 6.45 | 24.1 |
| 2024-03-01 | 342458186 | 61049036 | 321970397 | 15.13 | 5.08 | 20.21 |
| 2024-02-01 | 281876050 | 93356931 | 262330049 | 24.88 | 5.21 | 30.09 |
| 2024-01-01 | 306573669 | 82911713 | 287533999 | 21.29 | 4.89 | 26.18 |


Using the [skipped_reasons_by_year.sql](sql/skipped_reasons_by_year.sql) query modified for the 2024-2025 datasets, we find the following primary skip reasons from the TWJF:

| reason | reason_count | year |
|---|---|---|
| FlightTooSlowError | 10110425 | 2025 |
| FlightTooShortError | 7885340 | 2025 |
| FlightTooSlowError | 5734970 | 2024 |
| FlightTooShortError | 4704107 | 2024 |
| FlightAltitudeProfileError | 1317970 | 2025 |
| OriginAirportError | 1254356 | 2024 |
| DestinationAirportError | 1013564 | 2024 |
| DestinationAirportError | 887326 | 2025 |
| OriginAirportError | 807727 | 2025 |
| FlightAltitudeProfileError | 283054 | 2024 |
| FlightTooFastError | 121678 | 2024 |
| FlightTooFastError | 16081 | 2025 |
| FlightTooLongError | 1828 | 2024 |
| FlightTooLongError | 319 | 2025 |