import json
import signal

from pycontrails.models.ps_model import PSFlight
from pycontrails_bada.bada_model import BADAFlight

from lib.log import logger
from lib.exceptions import AircraftUnrecognizedError
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


def get_default_perf_model(aircraft_type_icao: str) -> AircraftPerformance | None:
    """
    Find a default performance model for a given aircraft type, and return instance of that model.
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
