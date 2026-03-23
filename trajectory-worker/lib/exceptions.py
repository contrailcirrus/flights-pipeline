class FlightTooLowError(Exception):
    """
    Flight trajectory is too low.
    """


class AircraftUnrecognizedError(Exception):
    """
    Flight icao type is not recognized.
    """
