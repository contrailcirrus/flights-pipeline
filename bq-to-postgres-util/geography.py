
import country_converter as coco
from pycontrails.core import airports

cc = coco.CountryConverter()
country_df = cc.data
country_iso_to_continent = dict(zip(country_df["ISO2"], country_df["Continent_7"]))
continent_name_to_iso = {
    "Africa": "AF",
    "Antarctica": "AN",
    "Asia": "AS",
    "Europe": "EU",
    "North America": "NA",
    "Oceania": "OC",
    "South America": "SA",
}

airport_df = airports.global_airport_database()
airport_icao_to_country = dict(zip(airport_df["icao_code"], airport_df["iso_country"]))

# Country ISO codes of countries in the European Economic Area.
EEA_COUNTRIES = {
    # 27 EU Member States
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",

    # 3 EFTA States (EEA Members)
    "IS", "LI", "NO"
}

# Outermost regions that are part of EU countries (and thereby the EU MRV) but could have their own country codes.
OUTERMOST_REGIONS = {
    "GF",  # French Guiana
    "GP",  # Guadeloupe
    "MQ",  # Martinique
    "RE",  # Réunion
    "YT",  # Mayotte
    "MF",  # Saint-Martin (French part)
}

EEA_COUNTRIES.update(OUTERMOST_REGIONS)

# Countries that are allowed to be the target of a flight originating in the EEA.
ALLOWED_DESTINATIONS = {'CH', 'GB'}

def is_eu_mrv(departure_airport_icao: str | None, arrival_airport_icao: str | None) -> bool:
    """Check whether an origin destination airport pair falls within the EU MRV system.

    It does if any of these conditions are met:
    - Intra European Economic Area area: EEA -> EEA
    - European Economic Area to UK or Switzerland (one direction): EEA -> CH/GB
    """

    departure_country_iso = airport_icao_to_country.get(departure_airport_icao)
    if departure_country_iso not in EEA_COUNTRIES:
        return False

    arrival_country_iso = airport_icao_to_country.get(arrival_airport_icao)
    if arrival_country_iso not in EEA_COUNTRIES and arrival_country_iso not in ALLOWED_DESTINATIONS:
        return False

    return True


def airport_icao_to_iso_country(airport_icao: str | None) -> str | None:
    """Map the airport ICAO code to the 2-letter ISO country code."""
    return airport_icao_to_country.get(airport_icao)


def airport_icao_to_iso_continent(airport_icao: str | None) -> str | None:
    """Map the airport ICAO code to the 2-letter ISO continent code."""
    iso_country = airport_icao_to_iso_country(airport_icao)
    continent_name = country_iso_to_continent.get(iso_country)
    return continent_name_to_iso.get(continent_name)
