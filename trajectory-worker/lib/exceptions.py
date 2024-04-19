class FlightTooLowError(Exception):
    """
    Flight trajectory is too low.
    """


class AircraftTypeUnrecognizedError(Exception):
    """
    Flight icao type is not recognized.
    """


class PerfModelUnsupportedError(Exception):
    """
    A given performance model (PS, BADA) is not supported.
    """
