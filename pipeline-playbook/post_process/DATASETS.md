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


| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2019-12-01 | 496575665.0 | 452836472.0 | 174041413.0 | 278795059.0 | 322534252.0 | 253240464.0 | 35.05 | 7.92 | 49.0 |
| 2019-11-01 | 476094722.0 | 437405778.0 | 174119802.0 | 263285976.0 | 301974920.0 | 237833031.0 | 36.57 | 8.43 | 50.05 |
| 2019-10-01 | 502101585.0 | 470590537.0 | 198695165.0 | 271895372.0 | 303406420.0 | 245389910.0 | 39.57 | 8.74 | 51.13 |
| 2019-09-01 | 494314439.0 | 462098770.0 | 195738174.0 | 266360596.0 | 298576265.0 | 241873273.0 | 39.6 | 8.2 | 51.07 |
| 2019-08-01 | 527982775.0 | 455401053.0 | 202018948.0 | 253382105.0 | 325963827.0 | 231335251.0 | 38.26 | 6.76 | 56.19 |
| 2019-07-01 | 530249772.0 | 470074767.0 | 198043840.0 | 272030927.0 | 332205932.0 | 250853074.0 | 37.35 | 6.37 | 52.69 |
| 2019-06-01 | 499433377.0 | 442445193.0 | 186674987.0 | 255770206.0 | 312758390.0 | 235271494.0 | 37.38 | 6.55 | 52.89 |
| 2019-05-01 | 487108820.0 | 429860881.0 | 181384479.0 | 248476402.0 | 305724341.0 | 228065713.0 | 37.24 | 6.68 | 53.18 |
| 2019-04-01 | 469982280.0 | 417475971.0 | 174512949.0 | 242963022.0 | 295469331.0 | 222660394.0 | 37.13 | 6.87 | 52.62 |
| 2019-03-01 | 444411273.0 | 386737853.0 | 164896539.0 | 221841314.0 | 279514734.0 | 203683040.0 | 37.1 | 6.5 | 54.17 |
| 2019-02-01 | 413639049.0 | 361785087.0 | 159790005.0 | 201995082.0 | 253849044.0 | 185694151.0 | 38.63 | 6.42 | 55.11 |
| 2019-01-01 | 444700280.0 | 385678512.0 | 165753745.0 | 219924767.0 | 278946536.0 | 203719070.0 | 37.27 | 5.81 | 54.19 |


Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2019 datasets, we find the following primary skip reasons from the TWJF:

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| OriginAirportError | 2193736 | 6026.7 | 49.68 | 2019 | 2019 |
| DestinationAirportError | 1993003 | 5475.3 | 45.14 | 2019 | 2019 |
| FlightTooSlowError | 1600436 | 4396.8 | 36.25 | 2019 | 2019 |
| FlightTooShortError | 744789 | 2046.1 | 16.87 | 2019 | 2019 |
| FlightAltitudeProfileError | 329009 | 903.9 | 7.45 | 2019 | 2019 |
| FlightTooLongError | 44391 | 122.0 | 1.01 | 2019 | 2019 |
| FlightTooFastError | 4785 | 13.1 | 0.11 | 2019 | 2019 |

## 2020

The 2020 dataset runs from 2020-01-01T00:00:00 to 2020-12-31T23:59:59. It was run 2026-06-18 -- 2026-06-19. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2020_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2020_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2020 datasets, we find the following monthly flight minutes breakdown:


| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2020-12-01 | 268756869.0 | 246018620.0 | 54708457.0 | 191310163.0 | 214048412.0 | 166463012.0 | 20.36 | 11.61 | 38.06 |
| 2020-11-01 | 251477664.0 | 228090071.0 | 61891376.0 | 166198695.0 | 189586287.0 | 144348160.0 | 24.61 | 11.53 | 42.6 |
| 2020-10-01 | 267094980.0 | 237270902.0 | 73388000.0 | 163882902.0 | 193706980.0 | 140410364.0 | 27.48 | 12.12 | 47.43 |
| 2020-09-01 | 256427880.0 | 226685486.0 | 74901442.0 | 151784044.0 | 181526438.0 | 130281854.0 | 29.21 | 11.85 | 49.19 |
| 2020-08-01 | 265388465.0 | 234414142.0 | 75741229.0 | 158672913.0 | 189647237.0 | 136794686.0 | 28.54 | 11.54 | 48.45 |
| 2020-07-01 | 237478885.0 | 211196548.0 | 69302104.0 | 141894444.0 | 168176781.0 | 121099661.0 | 29.18 | 12.36 | 49.01 |
| 2020-06-01 | 178642484.0 | 161922715.0 | 60628288.0 | 101294427.0 | 118014196.0 | 83270726.0 | 33.94 | 15.27 | 53.39 |
| 2020-05-01 | 145289022.0 | 130725523.0 | 50656943.0 | 80068580.0 | 94632079.0 | 67479288.0 | 34.87 | 13.3 | 53.56 |
| 2020-04-01 | 116440822.0 | 105591709.0 | 41542128.0 | 64049581.0 | 74898694.0 | 56269439.0 | 35.68 | 10.39 | 51.68 |
| 2020-03-01 | 319504009.0 | 293769019.0 | 95060444.0 | 198708575.0 | 224443564.0 | 177582386.0 | 29.75 | 9.41 | 44.42 |
| 2020-02-01 | 392432053.0 | 362121826.0 | 115304064.0 | 246817762.0 | 277127989.0 | 221964163.0 | 29.38 | 8.97 | 43.44 |
| 2020-01-01 | 486344341.0 | 445983175.0 | 166782896.0 | 279200279.0 | 319561445.0 | 253984763.0 | 34.29 | 7.89 | 47.78 |

Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2020 datasets, we find the following primary skip reasons from the TWJF:

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| DestinationAirportError | 1121581 | 3064.4 | 48.76 | 2020 | 2020 |
| OriginAirportError | 853011 | 2330.6 | 37.08 | 2020 | 2020 |
| FlightTooSlowError | 831341 | 2271.4 | 36.14 | 2020 | 2020 |
| FlightTooShortError | 456413 | 1247.0 | 19.84 | 2020 | 2020 |
| FlightAltitudeProfileError | 296363 | 809.7 | 12.88 | 2020 | 2020 |
| FlightTooLongError | 18830 | 51.4 | 0.82 | 2020 | 2020 |
| FlightTooFastError | 965 | 2.6 | 0.04 | 2020 | 2020 |

## 2021

The 2021 dataset runs from 2021-01-01T00:00:00 to 2021-12-31T23:59:59. It was run 2026-06-19 -- 2026-06-20. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2021_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2021_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2021 datasets, we find the following monthly flight minutes breakdown:


| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2021-12-01 | 372792054.0 | 334673374.0 | 98587450.0 | 236085924.0 | 274204604.0 | 202904939.0 | 26.45 | 12.1 | 45.57 |
| 2021-11-01 | 325314020.0 | 294278221.0 | 84012972.0 | 210265249.0 | 241301048.0 | 179115155.0 | 25.83 | 12.91 | 44.94 |
| 2021-10-01 | 352227414.0 | 318157966.0 | 99616481.0 | 218541485.0 | 252610933.0 | 186136922.0 | 28.28 | 12.83 | 47.15 |
| 2021-09-01 | 352835812.0 | 327029697.0 | 97012090.0 | 230017607.0 | 255823722.0 | 197022450.0 | 27.49 | 12.9 | 44.16 |
| 2021-08-01 | 339578500.0 | 316722539.0 | 68677059.0 | 248045480.0 | 270901441.0 | 214666382.0 | 20.22 | 12.32 | 36.78 |
| 2021-07-01 | 357131202.0 | 328769217.0 | 81983632.0 | 246785585.0 | 275147570.0 | 212916167.0 | 22.96 | 12.31 | 40.38 |
| 2021-06-01 | 311806690.0 | 285346873.0 | 72383755.0 | 212963118.0 | 239422935.0 | 181600436.0 | 23.21 | 13.1 | 41.76 |
| 2021-05-01 | 292150738.0 | 269033741.0 | 64380173.0 | 204653568.0 | 227770565.0 | 174884768.0 | 22.04 | 13.07 | 40.14 |
| 2021-04-01 | 278465756.0 | 258339716.0 | 56648852.0 | 201690864.0 | 221816904.0 | 172949685.0 | 20.34 | 12.96 | 37.89 |
| 2021-03-01 | 275740655.0 | 255922232.0 | 56772502.0 | 199149730.0 | 218968153.0 | 169983782.0 | 20.59 | 13.32 | 38.35 |
| 2021-02-01 | 211910898.0 | 195235852.0 | 49296136.0 | 145939716.0 | 162614762.0 | 123654712.0 | 23.26 | 13.7 | 41.65 |
| 2021-01-01 | 249758423.0 | 229267417.0 | 63478520.0 | 165788897.0 | 186279903.0 | 142635864.0 | 25.42 | 12.43 | 42.89 |


Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2021 datasets, we find the following primary skip reasons from the TWJF:

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| OriginAirportError | 936633 | 2566.1 | 43.39 | 2021 | 2021 |
| DestinationAirportError | 908551 | 2489.2 | 42.08 | 2021 | 2021 |
| FlightTooSlowError | 762322 | 2088.6 | 35.31 | 2021 | 2021 |
| FlightTooShortError | 401278 | 1099.4 | 18.59 | 2021 | 2021 |
| FlightAltitudeProfileError | 217521 | 595.9 | 10.08 | 2021 | 2021 |
| FlightTooLongError | 19608 | 53.7 | 0.91 | 2021 | 2021 |
| FlightTooFastError | 1174 | 3.2 | 0.05 | 2021 | 2021 |

## 2022

The 2022 dataset runs from 2022-01-01T00:00:00 to 2022-12-31T23:59:59. It was run 2026-06-22 -- 2026-06-23. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2022_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2022_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2022 datasets, we find the following monthly flight minutes breakdown:

| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2022-12-01 | 348084283.0 | 317705727.0 | 23246159.0 | 294459568.0 | 324838123.0 | 279010842.0 | 6.68 | 4.76 | 19.84 |
| 2022-11-01 | 323173100.0 | 294558882.0 | 22137224.0 | 272421658.0 | 301035876.0 | 257740411.0 | 6.85 | 4.88 | 20.25 |
| 2022-10-01 | 346905783.0 | 317740163.0 | 21210794.0 | 296529369.0 | 325694990.0 | 280802072.0 | 6.11 | 4.83 | 19.06 |
| 2022-09-01 | 345089398.0 | 317167055.0 | 25430365.0 | 291736690.0 | 319659033.0 | 276134930.0 | 7.37 | 4.88 | 19.98 |
| 2022-08-01 | 380198528.0 | 347269630.0 | 24494336.0 | 322775294.0 | 355704192.0 | 306369761.0 | 6.44 | 4.61 | 19.42 |
| 2022-07-01 | 385352601.0 | 348712043.0 | 26180695.0 | 322531348.0 | 359171906.0 | 305776317.0 | 6.79 | 4.66 | 20.65 |
| 2022-06-01 | 349667056.0 | 317092424.0 | 25983818.0 | 291108606.0 | 323683239.0 | 275140577.0 | 7.43 | 4.93 | 21.31 |
| 2022-05-01 | 337396706.0 | 298527575.0 | 29759701.0 | 268767874.0 | 307637004.0 | 253549006.0 | 8.82 | 4.95 | 24.85 |
| 2022-04-01 | 302649396.0 | 271785585.0 | 20786400.0 | 250999185.0 | 281862996.0 | 236851379.0 | 6.87 | 5.02 | 21.74 |
| 2022-03-01 | 244653207.0 | 213383660.0 | 22200813.0 | 191182847.0 | 222452394.0 | 179096262.0 | 9.07 | 5.43 | 26.8 |
| 2022-02-01 | 126498463.0 | 112366111.0 | 27248417.0 | 85117694.0 | 99250046.0 | 77506101.0 | 21.54 | 7.67 | 38.73 |
| 2022-01-01 | 302648215.0 | 280947282.0 | 70053973.0 | 210893309.0 | 232594243.0 | 201252337.0 | 23.15 | 4.14 | 33.5 |

Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2022 datasets, we find the following primary skip reasons from the TWJF:

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| FlightTooSlowError | 404259 | 1107.6 | 42.75 | 2022 | 2022 |
| FlightAltitudeProfileError | 263835 | 722.8 | 27.9 | 2022 | 2022 |
| FlightTooShortError | 252442 | 691.6 | 26.69 | 2022 | 2022 |
| OriginAirportError | 115724 | 317.1 | 12.24 | 2022 | 2022 |
| DestinationAirportError | 97693 | 267.7 | 10.33 | 2022 | 2022 |
| FlightTooLongError | 14943 | 40.9 | 1.58 | 2022 | 2022 |
| FlightTooFastError | 1275 | 3.5 | 0.13 | 2022 | 2022 |

## 2023

The 2023 dataset runs from 2023-01-01T00:00:00 to 2023-12-31T23:59:59. It was run 2026-06-24 -- 2026-06-25. The BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2023_run_jun2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2023_run_june2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2023 datasets, we find the following monthly flight minutes breakdown:


| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2023-12-01 | 418099022.0 | 394658373.0 | 69249376.0 | 325408997.0 | 348849646.0 | 309982637.0 | 16.56 | 4.42 | 25.86 |
| 2023-11-01 | 397861571.0 | 373124614.0 | 66076210.0 | 307048404.0 | 331785360.0 | 291407088.0 | 16.61 | 4.71 | 26.76 |
| 2023-10-01 | 427575912.0 | 402475297.0 | 71487801.0 | 330987496.0 | 356088110.0 | 314223030.0 | 16.72 | 4.71 | 26.51 |
| 2023-09-01 | 437215929.0 | 401572956.0 | 86240984.0 | 315331972.0 | 350974945.0 | 299701283.0 | 19.73 | 4.45 | 31.45 |
| 2023-08-01 | 454761182.0 | 428942118.0 | 87979302.0 | 340962816.0 | 366781880.0 | 324551423.0 | 19.35 | 4.47 | 28.63 |
| 2023-07-01 | 446142644.0 | 429075874.0 | 78962707.0 | 350113167.0 | 367179937.0 | 332619936.0 | 17.7 | 4.76 | 25.45 |
| 2023-06-01 | 416071955.0 | 399325057.0 | 75438446.0 | 323886611.0 | 340633508.0 | 306806822.0 | 18.13 | 5.01 | 26.26 |
| 2023-05-01 | 407410026.0 | 391369958.0 | 54449898.0 | 336920060.0 | 352960128.0 | 320268391.0 | 13.36 | 4.72 | 21.39 |
| 2023-04-01 | 387310865.0 | 371542637.0 | 47636533.0 | 323906104.0 | 339674332.0 | 308101033.0 | 12.3 | 4.65 | 20.45 |
| 2023-03-01 | 383230278.0 | 354274302.0 | 29438210.0 | 324836092.0 | 353792069.0 | 308555534.0 | 7.68 | 4.6 | 19.49 |
| 2023-02-01 | 337442274.0 | 307534654.0 | 22677879.0 | 284856775.0 | 314764394.0 | 270445175.0 | 6.72 | 4.58 | 19.85 |
| 2023-01-01 | 365532620.0 | 328271031.0 | 24881785.0 | 303389246.0 | 340650834.0 | 288082598.0 | 6.81 | 4.49 | 21.19 |

Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2023 datasets, we find the following primary skip reasons from the TWJF:

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| DestinationAirportError | 670376 | 1836.6 | 33.89 | 2023 | 2023 |
| FlightTooSlowError | 634996 | 1739.7 | 32.11 | 2023 | 2023 |
| OriginAirportError | 561274 | 1537.7 | 28.38 | 2023 | 2023 |
| FlightAltitudeProfileError | 357665 | 979.9 | 18.08 | 2023 | 2023 |
| FlightTooFastError | 256439 | 702.6 | 12.97 | 2023 | 2023 |
| FlightTooShortError | 226533 | 620.6 | 11.45 | 2023 | 2023 |
| FlightTooLongError | 16611 | 45.5 | 0.84 | 2023 | 2023 |

## 2024-2025

The 2024-2025 dataset runs from 2024-01-01T00:00:00 to 2025-12-31T23:59:59. It was run 2026-03-20 -- 2026-03-26. The BQ datasets produced were:

* Note: this dataset was run before we hae a job_id run mechanism for splitting TWJD work units, so no job id table.
* `contrails-301217.flights_pipeline_prod.inventory_2024_2025_run_march2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2024_2025_run_march2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2024_2025_run_march2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2024-2025 datasets, we find the following monthly flight minutes breakdown:

**2024**
| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2024-12-01 | 496875798.0 | 490490247.0 | 81816416.0 | 408673831.0 | 415059382.0 | 356812993.0 | 16.47 | 12.49 | 28.19 |
| 2024-11-01 | 483517578.0 | 477355313.0 | 93029096.0 | 384326217.0 | 390488481.0 | 334496994.0 | 19.24 | 12.76 | 30.82 |
| 2024-10-01 | 538079299.0 | 531396126.0 | 112462550.0 | 418933576.0 | 425616749.0 | 364462151.0 | 20.9 | 12.8 | 32.27 |
| 2024-09-01 | 523934403.0 | 516866006.0 | 107022165.0 | 409843841.0 | 416912238.0 | 357584420.0 | 20.43 | 12.53 | 31.75 |
| 2024-08-01 | 564318053.0 | 552222336.0 | 121805807.0 | 430416529.0 | 442512246.0 | 377667859.0 | 21.58 | 11.92 | 33.08 |
| 2024-07-01 | 574614972.0 | 562045659.0 | 124831565.0 | 437214094.0 | 449783406.0 | 383402472.0 | 21.72 | 11.96 | 33.28 |
| 2024-06-01 | 537548236.0 | 524270312.0 | 114527453.0 | 409742859.0 | 423020784.0 | 357594334.0 | 21.31 | 12.33 | 33.48 |
| 2024-05-01 | 530518769.0 | 515294789.0 | 117440133.0 | 397854656.0 | 413078636.0 | 345396402.0 | 22.14 | 12.7 | 34.89 |
| 2024-04-01 | 422942289.0 | 403544891.0 | 71582473.0 | 331962418.0 | 351359816.0 | 305980670.0 | 16.92 | 7.39 | 27.65 |
| 2024-03-01 | 429542129.0 | 403738701.0 | 61290890.0 | 342447811.0 | 368251239.0 | 321970397.0 | 14.27 | 5.56 | 25.04 |
| 2024-02-01 | 397580752.0 | 375484589.0 | 93607727.0 | 281876862.0 | 303973025.0 | 262330049.0 | 23.54 | 6.43 | 34.02 |
| 2024-01-01 | 412478459.0 | 389701530.0 | 83134404.0 | 306567126.0 | 329344055.0 | 287533999.0 | 20.15 | 5.78 | 30.29 |

**2025**
| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2025-12-01 | 540158930.0 | 535715142.0 | 97238573.0 | 438476569.0 | 442920357.0 | 377905377.0 | 18.0 | 13.68 | 30.04 |
| 2025-11-01 | 533135791.0 | 528745294.0 | 110274329.0 | 418470965.0 | 422861462.0 | 359384495.0 | 20.68 | 13.97 | 32.59 |
| 2025-10-01 | 583170264.0 | 578296753.0 | 130128704.0 | 448168049.0 | 453041560.0 | 386705930.0 | 22.31 | 13.57 | 33.69 |
| 2025-09-01 | 576378907.0 | 571350733.0 | 141863605.0 | 429487128.0 | 434515302.0 | 370389830.0 | 24.61 | 13.6 | 35.74 |
| 2025-08-01 | 620941294.0 | 615907141.0 | 213765341.0 | 402141800.0 | 407175953.0 | 345509967.0 | 34.43 | 13.91 | 44.36 |
| 2025-07-01 | 622930521.0 | 618498119.0 | 219624913.0 | 398873206.0 | 403305609.0 | 342548869.0 | 35.26 | 13.97 | 45.01 |
| 2025-06-01 | 589027175.0 | 581144131.0 | 203472532.0 | 377671599.0 | 385554643.0 | 323133470.0 | 34.54 | 14.15 | 45.14 |
| 2025-05-01 | 641755201.0 | 609164054.0 | 218657269.0 | 390506785.0 | 423097932.0 | 335355094.0 | 34.07 | 13.04 | 47.74 |
| 2025-04-01 | 595868017.0 | 573795564.0 | 177056239.0 | 396739325.0 | 418811779.0 | 342584022.0 | 29.71 | 12.93 | 42.51 |
| 2025-03-01 | 546842165.0 | 540443481.0 | 117147366.0 | 423296115.0 | 429694800.0 | 366816039.0 | 21.42 | 13.14 | 32.92 |
| 2025-02-01 | 472078979.0 | 464471034.0 | 89852699.0 | 374618335.0 | 382226280.0 | 325603798.0 | 19.03 | 12.82 | 31.03 |
| 2025-01-01 | 495427306.0 | 489645440.0 | 83811147.0 | 405834293.0 | 411616159.0 | 355901856.0 | 16.92 | 12.13 | 28.16 |

Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2024-2025 datasets, we find the following primary skip reasons from the TWJF:


**2024**

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| FlightTooSlowError | 5907014 | 16139.4 | 45.05 | 2024 | 2024-2025 |
| FlightTooShortError | 5357534 | 14638.1 | 40.85 | 2024 | 2024-2025 |
| OriginAirportError | 1841700 | 5032.0 | 14.04 | 2024 | 2024-2025 |
| DestinationAirportError | 1361922 | 3721.1 | 10.39 | 2024 | 2024-2025 |
| FlightAltitudeProfileError | 373485 | 1020.5 | 2.85 | 2024 | 2024-2025 |
| FlightTooFastError | 131017 | 358.0 | 1.0 | 2024 | 2024-2025 |
| FlightTooLongError | 6065 | 16.6 | 0.05 | 2024 | 2024-2025 |

**2025**

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| FlightTooSlowError | 10336012 | 28317.8 | 49.16 | 2025 | 2024-2025 |
| FlightTooShortError | 8261810 | 22635.1 | 39.29 | 2025 | 2024-2025 |
| FlightAltitudeProfileError | 1438233 | 3940.4 | 6.84 | 2025 | 2024-2025 |
| DestinationAirportError | 1167025 | 3197.3 | 5.55 | 2025 | 2024-2025 |
| OriginAirportError | 1046151 | 2866.2 | 4.98 | 2025 | 2024-2025 |
| FlightTooFastError | 20399 | 55.9 | 0.1 | 2025 | 2024-2025 |
| FlightTooLongError | 1009 | 2.8 | 0.0 | 2025 | 2024-2025 |

## 2026

The 2026 dataset is broken into several sub-datasets. We used quarterly processing for the first three quarters, then monthly for the final three months.

**Q1**
The Q1 BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2026Q1_run_sept2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2026Q1_run_sept2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2026Q1 datasets, we find the following monthly flight minutes breakdown:

| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2026-03-01 | 435937487.0 | 431975472.0 | 20633428.0 | 411342044.0 | 415304059.0 | 361099222.0 | 4.73 | 12.1 | 17.17 |
| 2026-02-01 | 407066081.0 | 403330170.0 | 16592943.0 | 386737227.0 | 390473138.0 | 342190676.0 | 4.08 | 11.41 | 15.94 |
| 2026-01-01 | 434374468.0 | 430452393.0 | 17980428.0 | 412471965.0 | 416394040.0 | 367432058.0 | 4.14 | 10.82 | 15.41 |


Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2026Q1 datasets, we find the following skip reasons from the TWJF:

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| DestinationAirportError | 193995 | 2155.5 | 37.39 | 2026 | Q1 |
| OriginAirportError | 169475 | 1883.1 | 32.67 | 2026 | Q1 |
| FlightTooShortError | 150603 | 1673.4 | 29.03 | 2026 | Q1 |
| FlightTooSlowError | 55623 | 618.0 | 10.72 | 2026 | Q1 |
| FlightAltitudeProfileError | 49784 | 553.2 | 9.6 | 2026 | Q1 |
| FlightTooFastError | 4473 | 49.7 | 0.86 | 2026 | Q1 |
| FlightTooLongError | 240 | 2.7 | 0.05 | 2026 | Q1 |

**Q2**
The Q2 BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2026Q2_run_sept2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2026Q2_run_sept2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2026Q2 datasets, we find the following monthly flight minutes breakdown:

| month | twjf_input_mins | twjf_resampled_input_mins | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2026-06-01 | 447407294.0 | 444280868.0 | 22310252.0 | 421970616.0 | 425097042.0 | 375185293.0 | 4.99 | 11.01 | 16.14 |
| 2026-05-01 | 442356044.0 | 439083570.0 | 27301255.0 | 411782315.0 | 415054789.0 | 365208920.0 | 6.17 | 11.22 | 17.44 |
| 2026-04-01 | 424702957.0 | 421443391.0 | 21572710.0 | 399870681.0 | 403130247.0 | 353800493.0 | 5.08 | 11.43 | 16.69 |

Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2026Q2 datasets, we find the following primary skip reasons from the TWJF:

| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| DestinationAirportError | 253859 | 2789.7 | 39.48 | 2026 | Q2 |
| OriginAirportError | 217997 | 2395.6 | 33.9 | 2026 | Q2 |
| FlightTooShortError | 169063 | 1857.8 | 26.29 | 2026 | Q2 |
| FlightAltitudeProfileError | 63853 | 701.7 | 9.93 | 2026 | Q2 |
| FlightTooSlowError | 63350 | 696.2 | 9.85 | 2026 | Q2 |
| FlightTooFastError | 3488 | 38.3 | 0.54 | 2026 | Q2 |
| FlightTooLongError | 387 | 4.3 | 0.06 | 2026 | Q2 |

**Q3**
The Q3 BQ datasets produced were:

* `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_jobs`
* `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_segments`
* `contrails-301217.flights_pipeline_prod.inventory_2026Q3_run_oct2026_summary`
* `contrails-301217.flights_pipeline_prod.logs_inventory_2026Q3_run_oct2026`

Using the [total_time_and_skipped.sql](sql/total_time_and_skipped.sql) query modified for the 2026Q3 datasets, we find the following monthly flight minutes breakdown:

| month | twjf_input_mins | twjf_resampled_input_mins  | twjf_skipped_minutes | twjf_passed_minutes | twjf_input_minutes_passed | tw_output_minutes | twjf_skipped_perc | tw_dropped_perc | total_dropped_perc |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-01 | 453352868.0 | 449993838.0 | 18108306.0 | 431885532.0 | 435244562.0 | 384293661.0 | 3.99 | 10.93 | 15.23 |
| 2026-08-01 | 480394425.0 | 477302805.0 | 20828655.0 | 456474150.0 | 459565770.0 | 409312056.0 | 4.34 | 10.26 | 14.8 |
| 2026-07-01 | 486998839.0 | 483770462.0 | 20923627.0 | 462846835.0 | 466075212.0 | 413931807.0 | 4.3 | 10.5 | 15.0 |


Using the [skipped_reasons_by_year_all_counts.sql](sql/skipped_reasons_by_year_all_counts.sql) query modified for the 2026Q3 datasets, we find the following primary skip reasons from the TWJF:


| reason | flights_with_reason | flights_with_reason_per_day | pct_of_skipped_flights | year | dataset |
|---|---|---|---|---|---|
| DestinationAirportError | 239534 | 2603.6 | 40.47 | 2026 | Q3 |
| OriginAirportError | 204549 | 2223.4 | 34.56 | 2026 | Q3 |
| FlightTooShortError | 158526 | 1723.1 | 26.79 | 2026 | Q3 |
| FlightTooSlowError | 60591 | 658.6 | 10.24 | 2026 | Q3 |
| FlightAltitudeProfileError | 48103 | 522.9 | 8.13 | 2026 | Q3 |
| FlightTooFastError | 3036 | 33.0 | 0.51 | 2026 | Q3 |
| FlightTooLongError | 237 | 2.6 | 0.04 | 2026 | Q3 |
