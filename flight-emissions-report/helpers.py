"""
Helper funcs.
"""


def key_max_value_count(dfx, column_name):
    """
    If multiple unique values exist in a column, return the value with the highest count.
    Note that null values are not considered in the stack rank.
    """
    keys = list(dfx[column_name].value_counts().sort_values(ascending=False).keys())
    val = keys[0] if keys else None
    return val
