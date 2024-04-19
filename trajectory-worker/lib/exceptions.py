class FlightTooLowError(Exception):
    """
    Flight trajectory is too low.
    """


class AircraftTypeUnrecognizedError(Exception):
    """
    Flight icao type is not recognized.
    """
