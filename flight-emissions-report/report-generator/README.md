# Flight Emissions Report v2

## Overview

This module generates detailed PDF reports on airline contrail and CO₂ emissions, using modeled and observed data.

## Requirements
- Python 3.12 (see [Pipfile](../Pipfile) for exact version)
- All dependencies listed in the main `flight-emissions-report/Pipfile`

Install dependencies using [pipenv](https://pipenv.pypa.io/en/latest/):
```bash
pipenv install --dev
```

## Data Requirements
- For each IATA code, a directory must exist in `../out/<IATA_CODE>/` containing at least:
  - `data_summary.json` (main summary data for the airline/IATA code)
  - `data_case_study_0.csv` and other CSVs for case studies
- The report generator will create a `figs/` subdirectory for generated charts.

**How to generate the `out/` directory:**

Use the CLI to fetch and prepare the required data. For example:

```bash
./cli.py report fetch -a IATA_CODE -d START_DATE_END_DATE -s MET_SOURCE -c FLIGHT_ID
```

- Replace `IATA_CODE` with your airline code (e.g., `TK`)
- Replace `START_DATE_END_DATE` with your date range (e.g., `2024-01-01_2024-12-31`)
- Replace `MET_SOURCE` with the meteorological data source (`era5` or `hres`)
- Replace `FLIGHT_ID` with a comma-separated list of case study flight IDs.

This will populate the `out/IATA_CODE/` directory with the necessary files for report generation.

**Example:**
```bash
./cli.py report fetch -a TK -d 2024-01-01_2024-12-31 -s era5 -c 6132cff6-8aa0-4cc7-9c08-dcc633c7e9f3
```

## Usage

### Command Line
Run the report generator from the `report-generator` directory or project root:

```bash
python generate_report.py --iata_codes <IATA1,IATA2,...> --airline_name "<Airline Name>" [--debug]
```

#### Arguments
- `--iata_codes` (required): Comma-separated list of IATA codes (e.g., `AA,DL,UA` or `TK`)
- `--airline_name` (required): Friendly name for the airline (e.g., "Turkish Airlines")
- `--debug` (optional): Enable verbose debug output

#### Example
```bash
python generate_report.py --iata_codes TK --airline_name "Turkish Airlines"
```

The generated PDF will be saved to `../out/<IATA_CODES>_flights_report.pdf`.

### Data Preparation Example
Ensure you have a directory structure like:
```
out/
  TK/
    data_summary.json
    data_case_study_0.csv
  DL/
    data_summary.json
```

### Output
- PDF report: `out/<IATA_CODES>_flights_report.pdf`
- Figures: `out/<IATA_CODE>/figs/*.png`
