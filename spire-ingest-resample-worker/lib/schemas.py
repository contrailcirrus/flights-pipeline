""" Data Object Models & Schemas"""

import dataclasses
from dataclasses import dataclass
import json


@dataclass
class SpireWaypoint:
    """
    A single flight waypoint record.
    """

    ingestion_time: str  # e.g. 2024-03-01T16:37:56.123Z
    icao_address: str  # e.g. 4B0293
    flight_id: str  # e.g. ef9fb457-0f70-4780-9154-6a5362e39862
    timestamp: str  # e.g. 2024-03-01T16:37:54Z
    latitude: float  # e.g. 47.453758
    longitude: float  # e.g. 8.555093
    heading: float  # e.g. 334.5535
    speed: float  # e.g. 16.0
    squawk: str  # e.g. 1000
    on_ground: bool  # e.g. True
    callsign: str  # e.g. SWR64C
    tail_number: str  # e.g. HB-AZJ
    source: str  # e.g. ADSB
    collection_type: str  # e.g. terrestrial
    flight_number: str  # e.g. LX644
    aircraft_type_icao: str  # e.g. E295
    aircraft_type_name: str  # e.g. Embraer 195-400STD-E2
    airline_iata: str  # e.g. LX
    airline_name: str  # e.g. Swiss International Air Lines
    departure_utc_offset: str  # e.g. +0100
    departure_airport_icao: str  # e.g. LSZH
    departure_airport_iata: str  # e.g. ZRH
    departure_scheduled_time: str  # e.g. 2024-03-01T16:25:00Z
    arrival_utc_offset: str  # e.g. +0100
    arrival_airport_icao: str  # e.g. LFPG
    arrival_airport_iata: str  # e.g. CDG
    arrival_scheduled_time: str  # e.g. 2024-03-01T17:40:00Z
    arrival_estimated_time: str  # e.g. 2024-03-01T17:45:00Z
    altitude_baro: float  # e.g. 26550.0
    vertical_rate: float  # e.g. -64.0
    takeoff_time: str  # e.g. 2024-03-01T16:37:56.123Z
    departure_estimated_time: str  # e.g. 2024-03-01T16:37:56.123Z
    landing_time: str  # 2024-03-01T16:37:56.123Z

    def as_utf8_json(self) -> bytes:
        """
        Builds a utf-8 encoded JSON blob from the class' attributes.
        """
        js = json.dumps(dataclasses.asdict(self))
        return js.encode("utf-8")

    @staticmethod
    def from_utf8_json(blob: bytes):
        """
        Takes a utf8 json blob and marshals to an instance of this class.
        """
        return SpireWaypoint(**json.loads(blob))


@dataclass
class SpireWaypointsRecord:
    """
    A list of temporally-contiguous flight-waypoints, belonging to a single flight instance.
    """

    record: list[SpireWaypoint]

    def as_utf8_json(self) -> bytes:
        """
        Builds a utf-8 encoded JSON blob from the class' attributes.
        """
        js = json.dumps(dataclasses.asdict(self))
        return js.encode("utf-8")

    @staticmethod
    def from_utf8_json(blob: bytes):
        """
        Takes a utf8 json blob and marshals to an instance of this class.
        """
        return SpireWaypointsRecord([SpireWaypoint(**r) for r in json.loads(blob)])
