
from pycontrails.core import airports

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