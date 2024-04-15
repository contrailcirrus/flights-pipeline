""" Data Object Models & Schemas"""

from dataclasses import dataclass, asdict
import json
from typing import TypedDict
from uuid import UUID
from datetime import datetime, UTC
import hashlib


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
            ingestion_time=None,
            latitude=wp["latitude"],
            longitude=wp["longitude"],
            collection_type=None,
            altitude_baro=wp["altitude_ft"],
            timestamp=datetime.fromtimestamp(wp["timestamp"], UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            imputed=False,
        )
        return flight_id, swp

    def to_bq_flatmap(self, source_id: str) -> list[bytes]:
        """
        Flattens records into a list of utf-8 encoded json string literals,
        ready for egress to big query.


        Converts temporal string fields (ingestion_time, timestamp, ...)  to microseconds epoch.

        Adds an `_instance_hash` k-v, of type int,
        generated as a hash of the composite <icao_address><timestamp>,
        where timestamp is epoch time in microseconds

        Parameters
        ----------
        source_id
            An identifier appended to the biq query record, indicating the origin of these records
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
                "src_id": source_id,
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
                "aircraft_type_icao": self.flight_info.aircraft_type_icao,
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


@dataclass
class WaypointCache:
    """
    A record living in shared cache, indicating the last known waypoint for a flight instance.
    Our CoCip calculation requires at minimum two segments (three waypoints),
    in order to compute CoCip outputs.
    i.e. suppose we wanted to calculate CoCip on a segment s0, formed by waypoints (w0, w1)
         this requires taking [w0, w1, w2], forming segments {s0: (w0, w1), s1: (w1, w2)}
         note that segment s1 is necessary, but CoCip is only calculated/available on s0.

    As such, the WaypointCache object endeavors to retain the _two_ most recent waypoints
    for a given flight instance.
    """

    class Waypoint(TypedDict):
        flight_id: bytes  # UUID
        latitude: float  # WSG ESPG:4326
        longitude: float  # WSG ESPG:4326
        altitude_ft: int  # feet MSL
        timestamp: int  # unixtime

    key: str  # <source_identifier>:<icao_address>, e.g. `spr:4B0293`
    waypoints: tuple[Waypoint]  # record[0].timestamp < record[1].timestamp

    def to_flatmap(self) -> dict[str, object]:
        """
        Returns
        -------
        dict
            Waypoints tuple flattened into a dict.
            Tuple indexes prefixed to dict key as 'w{N}_'
        """
        out = {}
        for n, waypoint in enumerate(self.waypoints):
            for k, v in waypoint.items():
                out.update({f"w{n}_{k}": v})
        return out

    @staticmethod
    def from_flatmap(rec: dict[bytes, bytes]):
        """
        Parameters
        ----------
        rec
            A dictionary object representing a flattened set of two WaypointCache.Waypoint objects.
            Dictionary has bytes k-v, as is the flatmap when returned from redis.

        Returns
        -------
        List[WaypointCache.Waypoint]
            Waypoint objects extracted from the flatmap,
            ordered by flatmap key prefixes w0_, w1_
        """
        extracted: list[dict] = [{}, {}]
        ix = {"w0": 0, "w1": 1}
        for k, v in rec.items():
            prefix = k.decode("utf-8").split("_")[0]
            key = "_".join(k.decode("utf-8").split("_")[1:])
            try:
                extracted[ix[prefix]].update({key: v})
            except KeyError:
                raise KeyError(
                    f"cannot marshal flatmap with key prefix: {prefix}. "
                    f"expected one of {list(ix.keys())}"
                )

        def type_cast(w: dict[str, bytes]) -> WaypointCache.Waypoint:
            return WaypointCache.Waypoint(
                flight_id=w["flight_id"],
                latitude=float(w["latitude"].decode("utf-8")),
                longitude=float(w["longitude"].decode("utf-8")),
                altitude_ft=int(w["altitude_ft"].decode("utf-8")),
                timestamp=int(w["timestamp"].decode("utf-8")),
            )

        out = [type_cast(w) for w in extracted if w]
        return out

    @staticmethod
    def from_spire_waypoint_positional(
        key: str,
        flight_id: str,
        spire_wps: tuple[SpireWaypointPositional, ...],
    ):
        """
        Builds a cache object from SpireWaypointPositional objects.
        Parameters
        ----------
        key
            the key to use for the cache lookup
        flight_id
            the unique flight identifier for the flight_instance
        spire_wps
            the 1 or two waypoints to cache
        """
        waypoints: list[WaypointCache.Waypoint] = []
        wp: SpireWaypointPositional
        for wp in spire_wps:
            waypoints.append(
                WaypointCache.Waypoint(
                    flight_id=UUID(flight_id).bytes,
                    latitude=wp.latitude,
                    longitude=wp.longitude,
                    altitude_ft=wp.altitude_baro,
                    timestamp=int(datetime.fromisoformat(wp.timestamp).timestamp()),
                )
            )

        return WaypointCache(key=key, waypoints=tuple(waypoints))


@dataclass
class FlightInfoWide(SpireFlightInfo):
    """
    Flight info object expanding on those values provided in Spire.
    """

    engine_uid: str | None  # icao edb engine uid identifier


@dataclass
class WaypointsRecord:
    """
    A representation of a series of waypoints and flight metadata,
    expanded and generalized from the SpireWaypointsRecord.
    """

    flight_info: FlightInfoWide
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
            flight_info=FlightInfoWide(**json.loads(blob)["flight_info"]),
            records=[SpireWaypointPositional(**r) for r in json.loads(blob)["records"]],
        )
