"""
Helper funcs.
"""

import pandas as pd

from pycontrails.core import airports

airport_df = airports.global_airport_database()


def key_max_value_count(dfx, column_name):
    """
    If multiple unique values exist in a column, return the value with the highest count.
    Note that null values are not considered in the stack rank.
    """
    keys = list(dfx[column_name].value_counts().sort_values(ascending=False).keys())
    val = keys[0] if keys else None
    return val


def lookup_airport_iata_to_icao(iata: str) -> str | None:
    """
    Given an airport's iata code, find the airport's icao code.
    """
    match = airport_df[airport_df["iata_code"] == iata]
    if len(match) == 0:
        return
    if len(match) > 1:
        raise ValueError(f"found multiple airport matches for iata code: {iata}")

    icao = match.iloc[0]["icao_code"]
    if pd.isnull(icao):
        return
    return icao


def lookup_airport_icao_to_iata(icao: str) -> str | None:
    """
    Given an airport's icao code, find the airport's iata code.
    """
    match = airport_df[airport_df["icao_code"] == icao]
    if len(match) == 0:
        return
    if len(match) > 1:
        raise ValueError(f"found multiple airport matches for icao code: {icao}")

    iata = match.iloc[0]["iata_code"]
    if pd.isnull(iata):
        return
    return iata
