"""
Helper funcs.
"""

import pandas as pd
from lib.schemas import FLIGHT_LEVELS


def key_max_value_count(dfx: pd.DataFrame, column_name: str):
    """
    This is effectively a wrapper around Pandas.mode() to handle some of the oddities around strings.
    If multiple unique values exist in a column, return the value with the highest count (mode).
    Null values are not considered in the stack rank.
    """
    keys = dfx[column_name].mode()
    val = keys[0] if not pd.isna(keys).all() else None
    return val


def altitude_ft_to_flight_level(alt_ft: int):
    """
    Converts altitude in feet MSL to flight level (100s of ft), snapped to the nearest level.
    """
    if alt_ft < (FLIGHT_LEVELS[0] * 100) - 500:
        return -999
    diff = lambda i: abs(FLIGHT_LEVELS[i] - alt_ft // 100)  # noqa:E731
    min_ix = min(range(len(FLIGHT_LEVELS)), key=diff)
    return FLIGHT_LEVELS[min_ix]
