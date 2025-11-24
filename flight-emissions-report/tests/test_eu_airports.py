"""
EU airports functionality unit tests.
"""

import pandas as pd

from helpers import EUAirports


def test_airports_csv_has_eu_data():
    """Test that the airports.csv file contains EU airports."""
    eu_airports = EUAirports()
    airports_df = pd.read_csv(eu_airports._csv_path)

    required_columns = ["continent", "icao_code"]
    for col in required_columns:
        assert (
            col in airports_df.columns
        ), f"Required column '{col}' not found in airports.csv"

    eu_airports_data = airports_df[airports_df["continent"] == "EU"]
    # Current count: 1447 EU airports + 10 buffer for data variations
    assert (
        len(eu_airports_data) >= 1437
    ), f"Expected at least 1437 EU airports, found {len(eu_airports_data)}"

    eu_airports_with_icao = eu_airports_data[
        (eu_airports_data["icao_code"].notna())
        & (eu_airports_data["icao_code"] != "")
        & (eu_airports_data["icao_code"] != "no")
    ]
    assert len(eu_airports_with_icao) > 0, "No EU airports with valid ICAO codes found"


def test_eu_airport_identification():
    """Test that EU airport identification works correctly."""
    eu_airports = EUAirports()

    # Test known EU airports
    known_eu_airports = ["LFPG", "EDDF", "EHAM", "LEMD"]
    for airport in known_eu_airports:
        assert eu_airports.is_eu_airport(
            airport
        ), f"Airport {airport} should be identified as EU"

    # Test known non-EU airports
    known_non_eu_airports = ["KJFK", "KLAX", "RJAA", "ZBAA"]
    for airport in known_non_eu_airports:
        assert not eu_airports.is_eu_airport(
            airport
        ), f"Airport {airport} should not be identified as EU"
