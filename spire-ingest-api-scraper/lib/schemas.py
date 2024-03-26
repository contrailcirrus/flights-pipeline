"""Data Object Models & Schemas"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass
class SpireWaypointPositional:
    """
    A single flight waypoint record.
    """

    ingestion_time: str | None  # e.g. 2024-03-01T16:37:56.123Z
    timestamp: str  # e.g. 2024-03-01T16:37:54Z
    latitude: float  # e.g. 47.453758
    longitude: float  # e.g. 8.555093
    # heading: float  # e.g. 334.5535
    # speed: float  # e.g. 16.0
    # on_ground: bool  # e.g. True
    # source: str  # e.g. ADSB
    collection_type: str | None  # e.g. terrestrial
    altitude_baro: int  # e.g. 26550 (MSL)
    # vertical_rate: float  # e.g. -64.0
    imputed: bool  # True if record was imputed, False is observed (i.e. in original Spire API data)
    flight_level: int | None = None  # 390 (imputed) altitude_baro//100 mapped -> list

    def as_utf8_json(self) -> bytes:
        """
        Builds a utf-8 encoded JSON blob from the class' attributes.
        """
        js = json.dumps(asdict(self))
        return js.encode("utf-8")

    @staticmethod
    def from_utf8_json(blob: bytes):
        """
        Takes a utf8 json blob and marshals to an instance of this class.
        """
        return SpireWaypointPositional(**json.loads(blob))


@dataclass
class SpireFlightInfo:
    """
    The time-invariant attributes for a flight-instance waypoint from the SpireAPI.
    """

    icao_address: str  # e.g. 4B0293
    flight_id: str | None  # e.g. ef9fb457-0f70-4780-9154-6a5362e39862
    callsign: str | None  # e.g. SWR64C
    # squawk: str  # e.g. 1000
    tail_number: str | None  # e.g. HB-AZJ
    flight_number: str | None  # e.g. LX644
    aircraft_type_icao: str | None  # e.g. E295
    # aircraft_type_name: str  # e.g. Embraer 195-400STD-E2
    airline_iata: str | None  # e.g. LX
    # airline_name: str  # e.g. Swiss International Air Lines
    # departure_utc_offset: str  # e.g. +0100
    # takeoff_time: str  # e.g. 2024-03-01T16:37:56.123Z
    # departure_estimated_time: str  # e.g. 2024-03-01T16:37:56.123Z
    # landing_time: str  # 2024-03-01T16:37:56.123Z
    departure_airport_icao: str | None  # e.g. LSZH
    # departure_airport_iata: str  # e.g. ZRH
    departure_scheduled_time: str | None  # e.g. 2024-03-01T16:25:00Z
    # arrival_utc_offset: str  # e.g. +0100
    arrival_airport_icao: str | None  # e.g. LFPG
    # arrival_airport_iata: str  # e.g. CDG
    arrival_scheduled_time: str | None  # e.g. 2024-03-01T17:40:00Z
    # arrival_estimated_time: str  # e.g. 2024-03-01T17:45:00Z

    def as_utf8_json(self) -> bytes:
        """
        Builds a utf-8 encoded JSON blob from the class' attributes.
        """
        js = json.dumps(asdict(self))
        return js.encode("utf-8")

    @staticmethod
    def from_utf8_json(blob: bytes):
        """
        Takes a utf8 json blob and marshals to an instance of this class.
        """
        return SpireFlightInfo(**json.loads(blob))


@dataclass
class SpireWaypointsRecord:
    """
    A list of temporally-contiguous flight-waypoints, belonging to a single flight instance.
    """

    flight_info: SpireFlightInfo
    records: list[SpireWaypointPositional]

    def as_utf8_json(self) -> bytes:
        """
        Builds a utf-8 encoded JSON blob from the class' attributes.
        """
        js = json.dumps(asdict(self))
        return js.encode("utf-8")

    @staticmethod
    def from_utf8_json(blob: bytes):
        """
        Takes a utf8 json blob and marshals to an instance of this class.
        """
        return SpireWaypointsRecord(
            flight_info=SpireFlightInfo(**json.loads(blob)["flight_info"]),
            records=[SpireWaypointPositional(**r) for r in json.loads(blob)["records"]],
        )

    @staticmethod
    def from_waypoint_cache(wp) -> tuple[str, SpireWaypointPositional]:
        """
        Convert a single WaypointCache.Waypoint object to a sparse SpireWaypointPositional object.
        Also, extracts and returns the flight_id.
        """
        flight_id = str(UUID(bytes=wp["flight_id"]))
        swp = SpireWaypointPositional(
            latitude=wp["latitude"],
            longitude=wp["latitude"],
            collection_type=None,
            altitude_baro=wp["altitude_ft"],
            ingestion_time=None,
            timestamp=datetime.fromtimestamp(wp["timestamp"], UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            imputed=False,
        )
        return flight_id, swp

    def to_bq_flatmap(self) -> list[bytes]:
        """
        Flattens records into a list of utf-8 encoded json string literals,
        ready for egress to big query.


        Converts temporal string fields (ingestion_time, timestamp, ...)  to microseconds epoch.

        Adds an `_instance_hash` k-v, of type int,
        generated as a hash of the composite <icao_address><timestamp>,
        where timestamp is epoch time in microseconds
        """

        def iso_to_microseconds(timestamp: str | None) -> int | None:
            if not timestamp:
                return timestamp
            ts: int = int(datetime.fromisoformat(timestamp).timestamp() * 1e6)
            return ts

        out = []
        for record in self.records:
            # _instance_hash is an int64 in bq
            ts = iso_to_microseconds(record.timestamp)
            hash = hashlib.md5(f"{self.flight_info.icao_address}{ts}".encode("utf-8"))
            # truncate as to be equal or smaller than int64 space when represented as signed int
            hash_trunc = hash.hexdigest()[:8]
            hash_int = int(hash_trunc, 16)
            blob = {
                "_instance_hash": hash_int,
                "ingestion_time": iso_to_microseconds(record.ingestion_time),
                "timestamp": ts,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "collection_type": record.collection_type,
                "altitude_baro": record.altitude_baro,
                "flight_level": record.flight_level,
                "imputed": record.imputed,
                "icao_address": self.flight_info.icao_address,
                "flight_id": self.flight_info.flight_id,
                "callsign": self.flight_info.callsign,
                "tail_number": self.flight_info.tail_number,
                "flight_number": self.flight_info.flight_number,
                "airline_iata": self.flight_info.airline_iata,
                "departure_airport_icao": self.flight_info.departure_airport_icao,
                "departure_scheduled_time": iso_to_microseconds(
                    self.flight_info.departure_scheduled_time
                ),
                "arrival_airport_icao": self.flight_info.arrival_airport_icao,
                "arrival_scheduled_time": iso_to_microseconds(
                    self.flight_info.arrival_scheduled_time
                ),
            }
            out.append(json.dumps(blob).encode("utf-8"))
        return out
