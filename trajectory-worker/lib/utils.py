import json
import signal

import pandas as pd
from pycontrails.models.ps_model import PSFlight
from pycontrails_bada.bada_model import BADAFlight

from lib.log import logger
from lib.exceptions import AircraftUnrecognizedError
from pycontrails.core.aircraft_performance import AircraftPerformance

DEFAULT_ENGINE_UID_LOOKUP_FP = "lib/default_engine_uid_lookup_032026.json"
ENGINE_UID_LOOKUP_FP = "lib/engine_uid_lookup_032026.csv"

# default engine uid lookup, based on aircraft type
with open(DEFAULT_ENGINE_UID_LOOKUP_FP, "r") as fp:
    default_engine_uid_lookup = json.load(fp)


def get_perf_model(aircraft_type_icao: str) -> AircraftPerformance:
    """
    Find a performance model for a given aircraft type, and return instance of that model.
    """
    # default to PS Flights model, if supported for the aircraft type
    ps_model = PSFlight(
        fill_low_altitude_with_isa_temperature=True,
        fill_low_altitude_with_zero_wind=True,
    )
    if ps_model.check_aircraft_type_availability(
        aircraft_type=aircraft_type_icao, raise_error=False
    ):
        return ps_model

    # use BADA3 otherwise, if supported
    bada3_model = BADAFlight(
        fill_low_altitude_with_isa_temperature=True,
        fill_low_altitude_with_zero_wind=True,
        bada3_path="bada3",
        bada_priority=3,
    )

    try:
        bada3_model.get_bada(aircraft_type=aircraft_type_icao)
        return bada3_model
    except Exception as e:
        raise AircraftUnrecognizedError(
            f"could not find aircraft type {aircraft_type_icao} in ps flights or bada lookup"
        ) from e


class SigtermManager:
    def __init__(self):
        """Ensure workload gracefully exits on SIGTERM signal.

        Examples
        --------
        sigterm_handler = SigtermHandler()
        while not sigterm_handler.should_exit:
            print('Still iterating!')
            time.sleep(1)
        """
        self.should_exit = False
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, *args, **kwargs):
        logger.debug("received sigterm")
        self.should_exit = True


sigterm_manager = SigtermManager()


def import_engine_uid_lookup() -> tuple[dict[str, str], dict[str, str]]:
    """
    Import and build mappings for icao address and tail number to engine uid.

    Mappings for icao address to engine uid take priority.
    Mappings for tail number to engine uid are only provided for aircraft where the
    icao address is unknown.
    """
    # TODO: refactor; have the mappings already in JSON format in file
    df_lk = pd.read_csv(ENGINE_UID_LOOKUP_FP)

    has_icao_addr = ~df_lk["icao_address"].isna()
    df_icao_addr = df_lk[has_icao_addr]
    df_icao_addr.set_index("icao_address", inplace=True)
    icao_to_engine_dict = df_icao_addr["engine_uid"].to_dict()
    df_tail_num = df_lk[~has_icao_addr]
    df_tail_num.set_index("tail_number", inplace=True)
    tail_num_to_engine_dict = df_tail_num["engine_uid"].to_dict()
    return icao_to_engine_dict, tail_num_to_engine_dict


# engine uid lookup, based on icao address or tail number
tail_num_engine_uid_lookup: dict[str, str]
icao_addr_engine_uid_lookup: dict[str, str]
icao_addr_engine_uid_lookup, tail_num_engine_uid_lookup = import_engine_uid_lookup()


def get_engine_uid(icao_address: str, tail_number: str, aircraft_type_icao: str) -> str:
    """
    Find an engine uid for a given aircraft by icao_adddress, or tail_number as a fallback.

    Parameters
    ----------
    icao_address: str
        ICAO address for an aircraft.
    tail_number: str
        Tail number for an aircraft.
    aircraft_type_icao: str
        Aircraft type ICAO designator.

    Returns
    -------
    str | None
        Engine UID for the aircraft if found, otherwise None. Lookups prefer icao_address, tail_number, then
         aircraft_type_icao in that order, falling back only if lookups for the more preferred designators
         miss.
    """
    if engine_uid := icao_addr_engine_uid_lookup.get(icao_address):
        logger.debug("set engine_uid from icao address")
        return engine_uid

    if engine_uid := tail_num_engine_uid_lookup.get(tail_number):
        logger.debug("set engine_uid from tail number")
        return engine_uid

    if engine_uid := default_engine_uid_lookup.get(aircraft_type_icao):
        logger.debug("set engine_uid from aircraft type icao")
        return engine_uid

    if not engine_uid:
        raise AircraftUnrecognizedError(
            f"could not find engine uid for aircraft type {aircraft_type_icao}"
        )
