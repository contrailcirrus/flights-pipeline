import json
import signal

from pycontrails.models.ps_model import PSFlight
from pycontrails_bada.bada_model import BADAFlight

from lib.log import logger
from pycontrails.core.aircraft_performance import AircraftPerformance

DEFAULT_ENGINE_UID_LOOKUP_FP = "lib/default_engine_uid_lookup_041824.json"

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


def get_default_perf_model(
    aircraft_type_icao: str, **perf_kwargs
) -> AircraftPerformance | None:
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
            perf_model = PSFlight(params=perf_kwargs)
        case "BADA3":
            perf_model = BADAFlight(
                params=perf_kwargs,
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
