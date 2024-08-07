"""
Custom exceptions.
"""


class OriginDestinationError(Exception):
    """
    Trajectory is not originating or terminating at expected location.
    """


class FlightTooShortError(Exception):
    """
    Trajectory is unreasonably short in flight time.
    """


class FlightTooLongError(Exception):
    """
    Trajectory is unreasonably long in flight time.
    """


class FlightTooSlowError(Exception):
    """
    Trajectory has period(s) of unrealistically slow speed.
    """


class FlightTooFastError(Exception):
    """
    Trajectory has period(s) of unrealistically high speed.
    """


class FlightAltitudeProfileError(Exception):
    """
    Trajectory has an unrealistic altitude profile.
    """


class FlightDuplicateTimestamps(Exception):
    """
    Trajectory contains waypoints with the same timestamp.
    """
