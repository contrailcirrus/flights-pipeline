"""
Helper funcs.
"""

from pycontrails.core import airports

airport_df = airports.global_airport_database()

# pull lookups into a hashmap for more efficient lookup
# note: there are many airports with icao code, but no iata code
airport_code_map = airport_df[["iata_code", "icao_code"]]
airport_code_map = airport_code_map.dropna()
airport_iata_to_icao_lookup = airport_code_map.set_index("iata_code")[
    "icao_code"
].to_dict()
airport_icao_to_iata_lookup = airport_code_map.set_index("icao_code")[
    "iata_code"
].to_dict()
del airport_code_map


def key_max_value_count(dfx, column_name):
    """
    If multiple unique values exist in a column, return the value with the highest count.
    Note that null values are not considered in the stack rank.
    """
    keys = list(dfx[column_name].value_counts().sort_values(ascending=False).keys())
    val = keys[0] if keys else None
    return val
