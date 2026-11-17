# Flight Contrail Inventory: Summary Dataset Guide

This guide accompanies the flight-level contrail inventory summary dataset. Each row in the dataset is one flight with identifiers, aircraft and route information, and modelled contrail energy forcing.

The guide covers:
1. [Dates covered](#1-dates-covered)
2. [Data sources](#2-data-sources)
3. [Changes in inputs over time](#3-changes-in-inputs-over-time)
4. [Known gaps and inconsistencies](#4-known-gaps-and-inconsistencies)
5. [Model versions](#5-model-versions)
6. [Converting energy forcing to CO2e](#6-converting-energy-forcing-to-co2e)
7. [Data fields](#7-data-fields)
8. [Flight identifiers and flight metadata](#8-flight-identifiers-and-flight-metadata)
9. [Flights excluded from the dataset](#9-flights-excluded-from-the-dataset)

All times are UTC.

**File format.** The dataset is delivered as CSV files with a header row. Each file holds a share of the rows, in no particular order, so combine all files from a delivery before using them. Every file has the same columns, listed in [§7](#7-data-fields). Empty values mean the field is unknown for that flight, or in the case of fuel burn and emissions numbers it may be intentionally blanked. Timestamps are in UTC.

---

## 1. Dates covered

The inventory covers flights that **started** between **2019-01-02 00:00 UTC** and **2026-10-31 23:59:59 UTC**. A flight is assigned to the date of its first observed position (`time_start`), so some flights that start late on the last day end after the cutoff. Due to the processing of the dataset, some may even start after that cutoff slightly for flights where the available ADS-B data started before the data cutoff, but then was trimmed to attempt to remove artifacts or time on the ground. Similarly, a few flights start a few minutes before 2019-01-02 since their earliest waypoints were not at their origin airport and our pipeline extends short gaps to origin or destination airports using 3D haversine interpolation.

January 1st 2019 is not included, because this is the cutoff of our ADS-B dataset and meterology dataset, and flights already in the air at midnight have no earlier tracking or weather data to start from.

The data was produced in several processing batches. Each batch is internally consistent; the differences between batches are described in [§4.2](#42-differences-between-processing-batches).

| Batch | Start date range | Processed | Flights |
|---|---|---|---|
| 2019 | 2019-01-02 → 2019-12-31 | June 2026 | 18,346,795 |
| 2020 | 2020-01-01 → 2020-12-31 | June 2026 | 12,148,658 |
| 2021 | 2021-01-01 → 2021-12-31 | June 2026 | 15,617,259 |
| 2022 | 2022-01-01 → 2022-12-31 | June 2026 | 20,886,689 |
| 2023 | 2023-01-01 → 2023-12-31 | June 2026 | 26,465,836 |
| 2024–2025 | 2024-01-01 → 2025-12-31 | March 2026 | 58,381,984 |
| 2026 Q1 | 2026-01-01 → 2026-03-31 | September 2026 | 7,336,778 |
| 2026 Q2 | 2026-04-01 → 2026-06-30 | September 2026 | 7,643,105 |
| 2026 Q3 | 2026-07-01 → 2026-09-30 | October 2026 | 8,332,526 |


---

## 2. Data sources

### 2.1 Aircraft tracking: Spire ADS-B

All flight tracks come from ADS-B data supplied by Spire. ADS-B messages are broadcast by aircraft transponders and received by ground stations and, where available, satellites.

The data reached us through different routes over time, which affects how densely each flight is sampled and how flights are identified:

| Period | Source | Positions kept per aircraft |
|---|---|---|
| 2019-01-01 → 2021-12-31 | Historical Spire ADS-B archive | First position in each minute |
| 2022-01-01 → 2024-04-23 | Spire data feed, archived by us and reprocessed | First and last position in each minute |
| 2024-04-24 → 2025-09-22 | Spire live data feed | First and last position in each minute |
| 2025-09-23 → present | Spire live data feed | First position in each 30 seconds |

For all periods, data points labeled as being on the ground by Spire, data points with no barometric altitude, and data poins with placeholder transponder addresses are removed.

### 2.2 Weather: ECMWF ERA5 reanalysis

Contrail formation and evolution are modelled with ERA5 reanalysis weather data from the European Centre for Medium-Range Weather Forecasts (ECMWF), via the Copernicus Climate Data Store:
- 0.25° × 0.25° horizontal resolution, hourly.
- Temperature, humidity, wind, vertical velocity and cloud ice on 26 pressure levels from 134 to 416 hPa (roughly 47,000 ft down to 22,700 ft).
- Top-of-atmosphere solar and thermal radiation.

### 2.3 Aircraft performance and engines

- **Fuel burn and aircraft performance** are modelled with the Poll–Schumann model (pycontrails `PSFlight`) where it supports the aircraft type, and otherwise with BADA 3. Flights whose aircraft type neither model supports are excluded ([§9](#9-flights-excluded-from-the-dataset)).
- **Engine type** is matched to an ICAO aircraft engine emissions lookup table, first by the individual aircraft (transponder address, then registration) using a fleet database, and otherwise using a typical engine for the aircraft type.
- **Non-volatile particulate matter (nvPM)** emissions are estimated from the engine data. The method used for each flight is given in `nvpm_data_source`.

### 2.4 Airports

Departure and arrival airports come from Spire's matching of each flight to airline schedules. Airport positions and elevations come from the airport database in pycontrails which is from the [ourairports-data repository](https://github.com/davidmegginson/ourairports-data>).

---

## 3. Changes in inputs over time

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


No changes were made to the weather data inputs across the dataset period.

---

## 4. Known gaps and inconsistencies

### 4.1 Coverage gaps

- **1 January 2019** is not included.
- **2024–2025:** lower coverage over oceans and remote regions between 2024-12 and 2025-05 (see [§3](#3-changes-in-inputs-over-time)).
- **2022 → April 2024:** data was collected in 5-minute batches with no way to recover a failed batch, so occasional short gaps exist.
- **January–February 2022:** about 22–23% of flight time was excluded, compared with 6–9% for the rest of 2022, likely due to higher prevalence of gaps.
- **Changeover of our Spire ETL pipeline on 2024-04-23/24:** there is a short gap around 2024-04-24.
- **Flights that could not be modelled:** a small number of flights failed during contrail modelling and are absent (e.g. 108 in 2019).

Flights are also excluded for data-quality reasons; [§9](#9-flights-excluded-from-the-dataset) lists the criteria and how often each applies.

### 4.2 Differences between processing batches

The **2024–2025 batch** differs from the others in three ways. Take these into account when comparing 2024–2025 with other years:

| | 2024–2025 batch | All other batches | Notes |
|---|---|---| --- |
| "Too slow" rule ([§9](#9-flights-excluded-from-the-dataset)) | Excluded if  speed ≤ **100 m/s** | Excluded if speed ≤ **85 m/s** | Rule applied to both instantaneous (outside of first and last 10 minutes) and 30-minute average speeds |
| Engine matching | Fleet database before May 2026 | Fleet database updated May 2026 to include aircraft retired since November 2018 | Resulted in only a very few changes to database |
| Flights selected for processing | Airline flights with positions above 20,000 ft; flights with no airline code processed separately, if they had more than 30 positions and at least one above 20,000 ft | All flights with a maximum altitude above 18,000 ft | All flights with no points above about 22k ft are excluded from processing by pycontrails, so the change doesn't affect the output data, only where such flights are removed in our pipeline. |


### 4.3 Field caveats

These apply to all batches. See [§7](#7-data-fields) for the full field list.

- **The final 1-minute segment of each flight is left out of most per-flight totals.** Prior to 2026-10. This affects `seg_cnt`, `chunk_len_km`, `mean_aircraft_mass_kg`, `mean_overall_efficiency`, `median_altitude_ft`. Fuel and emission totals (`total_*_kg`) and the end position and time are **not** affected. Because every flight ends near the ground, well below contrail-forming altitudes, there should be no effect effect on `sum_ef_mj` and the contrail fields ; the main effect is that `seg_cnt` and `chunk_len_km` are about one minute (a few kilometres) short. This is fixed for data from 2026-10 onward.
- **`time_end_tz` is incorrect.** Prior to 2026-10. It gives the UTC offset at the departure point, not the arrival point. Use the arrival airport's time zone instead.
- **`sum_ef_mj` is truncated** to an integer number of megajoules.
- **`total_persistent_contrail_length_km` includes cooling contrails.** For warming contrails only, use `total_pos_ef_persistent_contrail_length_km`.

---

## 5. Model versions

All batches use the same contrail model setup:

| Component | Version / setting |
|---|---|
| Contrail model | CoCiP (Contrail Cirrus Prediction model), in pycontrails **0.60.3** |
| BADA 3 integration | pycontrails-bada 0.7.5 |
| Aircraft performance | Poll–Schumann, with BADA 3 as fallback |
| Weather | ERA5, 0.25°, hourly, 26 pressure levels 134–416 hPa |
| Humidity correction | pycontrails `ExponentialBoostLatitudeCorrectionHumidityScaling`, default settings |
| Integration time step | 5 minutes |
| Maximum contrail lifetime | 12 hours |
| Track resampling | 1 minute; gaps over 100 km filled with a great-circle path |

The pycontrails version, performance model and nvPM method are recorded for each flight in `pycontrails_ver`, `perf_model_id` and `nvpm_data_source`.

Flight tracks were cleaned and checked with pycontrails 0.60.4 for the 2024–2025 batch and 0.63.0 for all other batches. The two versions differ only in the speed threshold described in [§4.2](#42-differences-between-processing-batches).

TODO (internal): confirm the recorded `pycontrails_ver` values for each batch before sending.

---

## 6. Converting energy forcing to CO2e

The dataset reports contrail climate impact as **energy forcing (EF) in megajoules** (`sum_ef_mj`). To convert it to kilograms of CO2-equivalent over a chosen time horizon H:

```
CO2e [kg] = sum_ef_mj × 10^6 × 0.42 / AGWP_H
AGWP_H [J per kg CO2] = AGWP_H [W m⁻² yr kg⁻¹] × 5.101 × 10^14 m² × 31,536,000 s
```

| Constant | Value | Source |
|---|---|---|
| Efficacy (ERF/RF ratio) for contrail cirrus | 0.42 | Lee et al. (2021), *Atmospheric Environment* |
| Earth surface area | 5.101 × 10^14 m² | |
| Seconds per year | 31,536,000 s | |
| AGWP, 20 years | 25.2 × 10^-15 W m⁻² yr kg⁻¹ | Joos et al. (2013), Table 4 |
| AGWP, 50 years | 53.0 × 10^-15 W m⁻² yr kg⁻¹ | IPCC AR5 WG1 Ch. 8 Supplementary Material, Table 8.SM.10 |
| AGWP, 100 years | 88.0 × 10^-15 W m⁻² yr kg⁻¹ | Gaillot et al. (2023), §2.3.1 |

This gives the following factors:

| Time horizon | kg CO2e per MJ of EF |
|---|---|---|
| GWP20 | 1.0361 × 10^-3 |
| GWP50 | 4.9262 × 10^-4 |
| GWP100 | 2.9669 × 10^-4 |

`total_co2_kg` is the CO2 emitted by burning fuel (3.159 kg CO2 per kg of fuel). It is not CO2e and does not include contrails. To estimate a flight's combined impact, add `total_co2_kg` to the contrail CO2e.

---

## 7. Data fields

One row per flight. Each flight is uniquely identified by the sets of  (`flight_id`, `time_start`). Columns appear in the CSV files in the order below. TODO (internal): confirm the column order against a delivered file.

Reliability key:
- **Observed:** taken directly from the tracking data, or calculated from it.
- **Spire:** descriptive information supplied by Spire (completeness varies by period; see [§8](#8-flight-identifiers-and-flight-metadata)).
- **Modelled:** model output, carrying the uncertainty of the model.
- **Nulled Out:** intentionally omitted data.

| Field | Type | Units | Description | Availability / reliability |
|---|---|---|---|---|
| `_chunk_hash`, `_processed_at` | integer | – | Internal processing fields | Can be ignored. |
| `seg_cnt` | integer | count | Number of 1-minute flight segments (approximately the flight time in minutes) | Observed. Many final segments missing ([§4.3](#43-field-caveats)). |
| `seg_ef_cnt`, `seg_pos_ef_cnt`, `seg_ef_nan_cnt` | integer | count | Segments with non-zero, positive (warming), and undefined energy forcing | Modelled. |
| `chunk_len_km` | float | km | Distance flown along the track | Observed. Many exclude the final segment ([§4.3](#43-field-caveats)). |
| `lat_start`, `lon_start`, `lat_end`, `lon_end` | float | degrees | First and last tracked positions | Observed. May be a point added near the origin or destination airport ([§8.3](#83-departure-and-arrival-airports)). |
| `time_start`, `time_end` | timestamp | ISO8601 UTC | Times of the first and last tracked positions | Observed. |
| `total_persistent_contrail_length_km` | float | km | Length of formed persistent contrails, warming or cooling | Modelled. |
| `total_contrail_length_sac_km` | float | km | Distance along the flight where contrails could form (Schmidt–Appleman criterion met) | Modelled. |
| `max_contrail_lifetime_h`, `median_contrail_lifetime_h` | float | hours | Longest and median contrail lifetime | Modelled. At most 12 h. |
| `pycontrails_ver` | string | – | pycontrails version used ([§5](#5-model-versions)) | Always present. |
| `perf_model_id` | string | – | Aircraft performance model used | Always present. |
| `nvpm_data_source` | string | – | nvPM estimation method | Always present. |
| `source_id` | string | – | Always `flightsreport` | – |
| `git_sha` | string | – | Version of our processing software | Always present. For traceability. |
| `zarr_uri` | string | – | Weather data used (e.g. `ERA5/20230101-20230102`) | Always present. For traceability. |
| `sum_ef_mj` | integer | MJ | Total contrail energy forcing; positive is warming, negative is cooling | **Modelled.** The main contrail impact measure. Convert to CO2e with [§6](#6-converting-energy-forcing-to-co2e). Truncated from float to int. |
| `total_fuel_burn_kg` | integer | kg | Fuel burned | Nulled out. |
| `total_co2_kg`, `total_h2o_kg` | integer | kg | CO2 and water vapour from fuel combustion | Nulled out. |
| `total_so2_kg`, `total_sulphates_kg`, `total_oc_kg`, `total_nox_kg`, `total_co_kg`, `total_hc_kg`, `total_nvpm_kg` | float | kg | Emissions of SO2, sulphates, organic carbon, NOx, CO, hydrocarbons and nvPM | Nulled out.|
| `total_nvpm_giga_cnt` | integer | billions of particles | Number of nvPM particles emitted | Nulled out. |
| `aircraft_type_icao` | string | – | ICAO aircraft type code | Spire. Always present. |
| `engine_uid` | string | – | ICAO Engine UID | Nulled out.|
| `mean_aircraft_mass_kg` | float | kg | Average aircraft mass | Nulled out. |
| `mean_overall_efficiency` | float | – | Average overall propulsion efficiency | Nulled out. |
| `icao_address` | string | – | Aircraft transponder address (24-bit, hexadecimal) | Always present. Observed. |
| `flight_id` | string | – | Flight identifier | Always present. Not unique. Format depends on period ([§8.1](#81-flight_id)). |
| `callsign` | string | – | Air traffic control callsign | Spire. |
| `tail_number` | string | – | Aircraft registration | Spire. Less complete than `icao_address`. |
| `flight_number` | string | – | Commercial flight number | Spire. **Empty 2022-02-11 → 2023-03-30.** |
| `airline_iata` | string | – | Operator's IATA code | Spire. **2019–2021: first two characters of `flight_number`.** Empty when no airline is known. |
| `departure_airport_icao`, `arrival_airport_icao` | string | – | Departure and arrival airports (ICAO codes) | Spire. May be empty ([§8.3](#83-departure-and-arrival-airports)). |
| `departure_scheduled_time`, `arrival_scheduled_time` | timestamp | UTC | Scheduled departure and arrival times | Spire. |
| `median_altitude_ft` | integer | ft (barometric) | Median altitude | Observed. |
| `total_pos_ef_persistent_contrail_length_km` | float | km | Total length of warming contrails only. | Modelled. |
| `time_start_tz`, `time_end_tz` | string | e.g. `-08` | UTC offset in whole hours | Half-hour offsets are truncated. **`time_end_tz` is incorrect in much of the data ([§4.3](#43-field-caveats)).** |
| `time_start_sunrise_offset_mins`, `time_start_sunset_offset_mins` | integer | minutes | Time from local sunrise and sunset at the departure point | ±720 during polar day or night. |


---

## 8. Flight identifiers and flight metadata

### 8.1 `flight_id`

**From 2024-04-24**, `flight_id` is supplied by Spire and is a UUID, for example `997076a7-6b07-4809-9d3a-07f9c448565e`.

**Before 2024-04-24**, Spire did not supply a usable flight identifier, so we split each aircraft's track into flights ourselves:

1. Take all positions for one transponder address in time order.
2. Start a new flight when there is a stop below 15,000 ft: the aircraft is below 15,000 ft and either its speed from the previous position is below a threshold, or more than 18 hours have passed since the previous position.
3. The identifier is a hash of the transponder address and the flight's sequence number for that aircraft.

| Period | Speed threshold for a stop | Aircraft included |
|---|---|---|
| 2019–2021 | 15 m/s | All aircraft |
| 2022 → 2024-04-23 | 45 m/s | Only aircraft that ever reported an airline code. Very short fragments (6 positions or fewer) were removed. |
| From 2024-04-24 | Not applicable (Spire identifier) | All aircraft |

What this means in practice:
- **Identifiers before 2024-04-24 are 24-character strings ending in `==`**, and may contain `/` and `+`. Encode them before using them in file names or URLs.
- **From 2022 until 2024-04-23, aircraft with no airline IATA code are not included**, so private and general aviation traffic is under-represented in that period.
- The split is approximate. Two flights with a very quick turnaround can occasionally be merged into one, and slow flight below 15,000 ft can occasionally split one flight in two.
- Identifiers are only meaningful within this dataset and do not match identifiers in other data sources.

### 8.2 Flight number and callsign

- **`flight_number`** is empty for all flights from **2022-02-11 to 2023-03-30**, because Spire did not supply it. Outside that period it is usually present for scheduled airline flights and often empty for others.
- In **2019–2021**, `airline_iata` was taken from the first two characters of `flight_number`, so flights with no flight number have no airline in those years.
- **`callsign`** for 2022 to April 2024 was recovered from the original data after an initial processing error. Where an aircraft reported two different callsigns at the same moment (rare), one of them was kept.

### 8.3 Departure and arrival airports

- Airports come from Spire's matching of flights to airline schedules. They are not inferred from where the track starts and ends.
- **Flights with no airport, or an unrecognised one, are kept.**
- Where an airport is known, the flight is excluded if its track starts or ends more than 200 km from that airport ([§9](#9-flights-excluded-from-the-dataset)). 
- When a track starts or ends a short distance from a known airport (10–400 km, and no more than 10% of the route distance), a point at 1,000 ft above the airport is added to complete the track.

### 8.4 One value per flight

Spire's descriptive fields (identifiers, callsign, registration, flight number, aircraft type, airline, airports and scheduled times) can vary from one data point to the next. For each flight we keep the most common value, fill empty positions with it, and **drop data points that disagree**. Each flight therefore has a single value for each field. A field that is empty for the whole flight stays empty.

---

## 9. Flights excluded from the dataset

Every flight goes through three stages, and can be excluded at each.

### 9.1 Selection

Only flights reaching a maximum altitude above 18,000 ft are processed (for the 2024–2025 batch, see [§4.2](#42-differences-between-processing-batches)). Persistent contrails rarely form at lower altitudes and our ERA5 data starts around 22,000 ft.

### 9.2 Track cleaning and checks

Before modelling, each track is cleaned:
- Data points with altitudes outside 0–55,000 ft are removed.
- Data points implying a speed below 45 m/s or above 350 m/s are removed.

The track is then resampled to 1-minute intervals and checked. A flight is excluded if it fails any of these checks:

| Reason | Rule |
|---|---|
| Departure airport mismatch | First position more than 200 km from the departure airport |
| Arrival airport mismatch | Last position more than 200 km from the arrival airport |
| Too slow | Speed ≤ 45 m/s anywhere except the first and last 10 minutes, **or** 30-minute average speed ≤ 85 m/s (100 m/s for the 2024–2025 batch) |
| Too fast | Any speed ≥ 350 m/s |
| Too short | Shorter than 24 minutes |
| Too long | Longer than 19 hours |
| Irregular altitude profile | Crosses 15,000 ft more than twice, i.e. descends below 15,000 ft mid-flight |

Flights with unrecognised airports or unusually steep climbs or descents are **kept**.

### 9.3 Contrail modelling

| Reason | Rule |
|---|---|
| Too low | Never above 22,664 ft (the lowest weather level used, 416 hPa) |
| Aircraft not supported | No engine could be assigned, or the aircraft type is not supported by either performance model (mainly turboprops and some business jets) |
| Model failure | Modelling failed repeatedly (very rare; see [§4.1](#41-coverage-gaps)) |

### 9.4 How often flights are excluded

**Share of flight time excluded**, as the range across months in each batch:

| Batch | At cleaning and validation (% of input) | At contrail modelling (% of what remained) | Total excluded (% of input) |
|---|---|---|---|
| 2019 | 35–40 | 6–9 | 49–56 |
| 2020 | 20–36 | 9–15 | 38–54 |
| 2021 | 20–28 | 12–14 | 37–47 |
| 2022 | 6–23 (highest in Jan–Feb) | 4–8 | 19–39 |
| 2023 | 7–20 | 4–5 | 19–31 |
| 2024 | 14–24 | 6–13 | 25–35 |
| 2025 | 17–35 (highest in Apr–Aug) | 12–14 | 28–48 |
| 2026 Q1–Q3, 10 | 4–6 | 10–12 | 15–17.5 |

"Total excluded" also includes data points removed during cleaning.

**Reasons for failing the checks in §9.2.** Each column shows the percentage of excluded flights that failed each check. A flight can fail several checks, so columns add up to more than 100%.

| Reason | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 Q1 | 2026 Q2 | 2026 Q3 | 2026 10 |
|---|---|---|---|---|---|---|---|---|---|---| --- |
| Departure airport mismatch | **49.7** | 37.1 | **43.4** | 12.2 | 28.4 | 14.0 | 5.0 | 32.7 | 33.9 | 34.6 | 33.7 |
| Arrival airport mismatch | 45.1 | **48.8** | 42.1 | 10.3 | **33.9** | 10.4 | 5.6 | **37.4** | **39.5** | **40.5** | **39.2** |
| Too slow | 36.3 | 36.1 | 35.3 | **42.8** | 32.1 | **45.1** | **49.2** | 10.7 | 9.9 | 10.2   | 9.7 |
| Too short | 16.9 | 19.8 | 18.6 | 26.7 | 11.5 | 40.9 | 39.3 | 29.0 | 26.3 | 26.8 | 27.0|
| Irregular altitude profile | 7.5 | 12.9 | 10.1 | 27.9 | 18.1 | 2.9 | 6.8 | 9.6 | 9.9 | 8.1 | 6.8 |
| Too fast | 0.1 | 0.04 | 0.05 | 0.1 | 13.0 | 1.0 | 0.1 | 0.9 | 0.5 | 0.5 | 0.5 |
| Too long | 1.0 | 0.8 | 0.9 | 1.6 | 0.8 | 0.05 | 0.0 | 0.05 | 0.06 | 0.04 | 0.03 |

The largest reason in each column is in bold.
