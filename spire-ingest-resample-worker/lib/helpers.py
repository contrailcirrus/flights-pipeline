"""
Helper functions.
"""

import math

import numpy as np
from pycontrails.physics import geo

from lib.schemas import SpireWaypointPositional, SpireFlightInfo
from lib.log import logger
from datetime import datetime

IN_FLIGHT_SPEED_THRESHOLD_KPH = 200
LANDING_TO_TAKEOFF_DELAY_HR = 0.25


def verify_temporal_order(
    cached_waypoint: SpireWaypointPositional,
    record_waypoint: SpireWaypointPositional,
    flight_info: SpireFlightInfo,
):
    """
    Verifies that the batch window of records trails the cached records in time.
    Failure to meet this criteria may indicate out-of-order delivery of records.

    Parameters
    ----------
    cached_waypoint
        The most recent cached waypoint for the flight instance
    record_waypoint
        The first waypoint in the batch window of waypoints for the flight instance
    flight_info
        Flight info object as extracted from the SpireWaypointsRecord w/ the window of waypoints
    """
    max_cached_waypoints_ts = datetime.fromisoformat(cached_waypoint.timestamp)
    min_records_ts = datetime.fromisoformat(record_waypoint.timestamp)

    # possible out-of-order delivery
    if min_records_ts < max_cached_waypoints_ts:
        raise Exception(
            f"records must have timestamp after cached timestamp. "
            f"received records for icao_address {flight_info.icao_address} "
            f"with timestamp {record_waypoint.timestamp} occurring before "
            f"cached timestamp {max_cached_waypoints_ts.isoformat()}"
        )


def is_same_flight_instance(
    cached_flight_id: str,
    record_flight_id: str | None,
    cached_waypoint: SpireWaypointPositional,
    record_waypoint: SpireWaypointPositional,
    flight_info: SpireFlightInfo,
) -> bool:
    """
    Applies basic heuristics to infer whether the record waypoints
    belong to the same flight instance as the cached waypoints.

    Cached waypoints and record waypoints share the same icao_address (aircraft).
    If the aircraft touches down and takes off, it is a different flight instance.

    The flight_id provided by Spire is a measure of the flight instance.
    If this flight_id changes, then we invalidate the cache.

    If the flight_id is missing in the records,
    then we infer based on the aircraft's motion whether it was in-flight
    between cache and records (thus still the same flight instance.

    Parameters
    ----------
    cached_flight_id
        The flight id as extracted from the cache
    record_flight_id
        The flight id as extracted from the records batch window
    cached_waypoint
        The most recent cached waypoint for the flight instance
    record_waypoint
        The first waypoint in the batch window of waypoints for the flight instance
    flight_info
        Flight info object as extracted from the SpireWaypointsRecord
        w/ the window of waypoints

    Returns
    -------
    True if the same flight instance, else false.
    """

    if record_flight_id and record_flight_id == cached_flight_id:
        return True
    elif record_flight_id:
        return False

    max_cached_waypoints_ts = datetime.fromisoformat(cached_waypoint.timestamp)
    min_records_ts = datetime.fromisoformat(record_waypoint.timestamp)
    cache_to_records_elapsed_hr = (
        min_records_ts - max_cached_waypoints_ts
    ).seconds / 3600
    cache_to_records_distance_km = 0.001 * math.sqrt(
        (0.3048 * (record_waypoint.altitude_baro - cached_waypoint.altitude_baro)) ** 2
        + geo.haversine(
            lons1=np.array(record_waypoint.longitude),
            lats1=np.array(record_waypoint.latitude),
            lons0=np.array(cached_waypoint.longitude),
            lats0=np.array(cached_waypoint.latitude),
        )
        ** 2
    )
    cache_to_records_avg_kph = (
        cache_to_records_distance_km / cache_to_records_elapsed_hr
    )

    # different flight instance if avg speed too low to be flying between cache and records
    if (cache_to_records_elapsed_hr >= LANDING_TO_TAKEOFF_DELAY_HR) and (
        cache_to_records_avg_kph <= IN_FLIGHT_SPEED_THRESHOLD_KPH
    ):
        logger.info(
            f"new flight instance inferred for icao_address {flight_info.icao_address} "
            f"at {record_waypoint.timestamp}. invalidating cache."
        )
        return False
