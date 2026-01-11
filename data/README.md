# Data Directory

This directory contains data submodules used by the flights-pipeline.

## Contents

### `airports/` (Git Submodule)

The `airports/` directory is a git submodule containing airport data from the [OurAirports](https://ourairports.com/) database.

**Submodule Details:**
- **Repository**: https://github.com/contrailcirrus/ourairports-data.git
- **Path**: `data/airports`
- **Source**: Fork of the [ourairports-data repository](https://github.com/davidmegginson/ourairports-data)

**Data Contents:**
The submodule contains CSV files with global airport information, including:
- Airport ICAO codes
- Airport IATA codes
- Airport names and locations (latitude/longitude)
- Country information (`iso_country`)
- Continent and region information
- Airport types (large_airport, medium_airport, small_airport, heliport, etc.)
- Elevation and other metadata

**Primary File:**
- `airports.csv` - Main airport database with ICAO codes, country mappings, and location data

## Submodule Management

### Syncing the Submodule

To update the submodule to the latest commit from the remote repository:

```bash
# From the flights-pipeline directory
git submodule update --remote data/airports
```

This will fetch the latest changes from the `contrailcirrus/ourairports-data` repository and update the submodule to point to the latest commit.

### Checking Submodule Status

To see the current status of all submodules:

```bash
git submodule status
```

### Committing Submodule Updates

After updating the submodule, you need to commit the change in the parent repository:

```bash
# Update the submodule
git submodule update --remote data/airports

# Stage the submodule update
git add data/airports

# Commit the update
git commit -m "Update airports data submodule"
```

## Data Source

The airport data comes from [OurAirports](https://ourairports.com/), an open-source airport database that is updated daily.

For more information about the data format and structure, see:
- [OurAirports Data Documentation](https://ourairports.com/data/)
- [Original ourairports-data Repository](https://github.com/davidmegginson/ourairports-data)

## Airport ICAO ↔ Country Lookup

The `airports.csv` file provides the primary mapping between airport ICAO codes and countries. The `iso_country` column contains ISO 3166-1 alpha-2 country codes (e.g., "US", "GB", "FR").

