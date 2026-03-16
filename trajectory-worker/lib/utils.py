import json
import signal

import pandas as pd
from pycontrails.models.ps_model import PSFlight
from pycontrails_bada.bada_model import BADAFlight

from lib.log import logger
from pycontrails.core.aircraft_performance import AircraftPerformance

DEFAULT_ENGINE_UID_LOOKUP_FP = "lib/default_engine_uid_lookup_041824.json"
ENGINE_UID_LOOKUP_FP = "lib/engine_uid_lookup_032026.csv"

# default engine uid lookup, based on aircraft type
with open(DEFAULT_ENGINE_UID_LOOKUP_FP, "r") as fp:
    default_engine_uid_lookup = json.load(fp)


def get_default_engine_uid(aircraft_type_icao: str) -> str | None:
    """
    Find a default engine uid for a given aircraft type.
    """
    target = default_engine_uid_lookup.get(aircraft_type_icao)
    if target:
        engine_uid = target["engine_uid"]
    else:
        return None
    return engine_uid


def get_default_perf_model(aircraft_type_icao: str) -> AircraftPerformance | None:
    """
    Find a default performance model for a given aircraft type, and return instance of that model.
    """
    target = default_engine_uid_lookup.get(aircraft_type_icao)
    if target:
        perf_model_id = target["perf_model_id"]
    else:
        return None

    match perf_model_id:
        case "PS":
            perf_model = PSFlight(
                fill_low_altitude_with_isa_temperature=True,
                fill_low_altitude_with_zero_wind=True,
            )
        case "BADA3":
            perf_model = BADAFlight(
                fill_low_altitude_with_isa_temperature=True,
                fill_low_altitude_with_zero_wind=True,
                bada3_path="bada3",
            )
        case _:
            return None
    return perf_model


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


def import_engine_uid_lookup() -> (dict[str, str], dict[str, str]):
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
    df_tail_num = df_lk[~has_icao_addr]
    df_tail_num.set_index("tail_number", inplace=True)

    return df_icao_addr["engine_uid"].to_dict(), df_tail_num["engine_uid"].to_dict()


# engine uid lookup, based on icao address or tail number
tail_num_engine_uid_lookup: dict[str, str]
icao_addr_engine_uid_lookup: dict[str, str]
icao_addr_engine_uid_lookup, tail_num_engine_uid_lookup = import_engine_uid_lookup()
