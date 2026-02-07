"""
Helper funcs.
"""

from lib.schemas import FLIGHT_LEVELS


def key_max_value_count(dfx, column_name):
    """
    If multiple unique values exist in a column, return the value with the highest count.
    Note that null values are not considered in the stack rank.
    """
    keys = list(dfx[column_name].value_counts().sort_values(ascending=False).keys())
    val = keys[0] if keys else None
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
