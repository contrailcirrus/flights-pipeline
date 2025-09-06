"""
Helper funcs.
"""

import os
import pandas as pd
from typing import Set

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


class EUAirports:
    """EU airports management class."""
    
    def __init__(self):
        self._csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "airports", "airports.csv")
        self._airports_cache = None
    
    def _load_airports(self) -> Set[str]:
        """Load EU airports from the CSV file."""
        try:
            airports_df = pd.read_csv(self._csv_path)
            
            eu_airports = airports_df[
                (airports_df['continent'] == 'EU') & 
                (airports_df['icao_code'].notna()) & 
                (airports_df['icao_code'] != '')
            ]['icao_code'].tolist()
            
            eu_airports_set = {code.strip('"') for code in eu_airports if code and code != 'no'}
            
            return eu_airports_set
            
        except Exception as e:
            print(f"Warning: Could not load EU airports from CSV: {e}")
            return set()
    
    def get_airports_set(self) -> Set[str]:
        """Get the set of EU airport ICAO codes."""
        if self._airports_cache is None:
            self._airports_cache = self._load_airports()
        
        return self._airports_cache.copy()
    
    def is_eu_airport(self, icao_code: str) -> bool:
        """Check if an airport ICAO code belongs to an EU airport."""
        if not icao_code:
            return False
        
        eu_airports = self.get_airports_set()
        return icao_code in eu_airports
    


