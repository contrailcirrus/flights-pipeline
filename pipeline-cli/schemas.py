"""Data Object Models & Schemas"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


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
class FlightInfoWide(SpireFlightInfo):
    """
    Flight info object expanding on those values provided in Spire.
    """

    engine_uid: str | None  # icao edb engine uid identifier


class MetSource(str, Enum):
    HRES = "hres"
    ERA5 = "era5"


class TelemetrySource(str, Enum):
    BIG_QUERY = "bq"
    GOOGLE_CLOUD_STORAGE = "gcs"


@dataclass
class WaypointsRecord:
    """
    A representation of a series of waypoints and flight metadata,
    expanded and generalized from the SpireWaypointsRecord.
    """

    flight_info: FlightInfoWide
    records: list[SpireWaypointPositional]
    met_source: MetSource = MetSource.ERA5
    export_cocip_trajectory: bool = False

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
        return WaypointsRecord(
            flight_info=FlightInfoWide(**json.loads(blob)["flight_info"]),
            records=[SpireWaypointPositional(**r) for r in json.loads(blob)["records"]],
            met_source=MetSource(json.loads(blob)["met_source"]),
            export_cocip_trajectory=json.loads(blob)["export_cocip_trajectory"],
        )


@dataclass
class TrajectoryWorkerJobDescriptor:
    """
    A unit of work with instructions for how
    to compose/build a trajectory worker job (WaypointsRecord).
    """

    day: str  # "%Y-%m-%d"
    met_source: MetSource
    telemetry_source: TelemetrySource  # src from which to fetch ads-b data
    full_traj: bool  # export per-seg cocip to bq
    airline_iata: str | None = None
    flight_id: list[str] | None = None
    job_id: str | None = None
    job_lookup_table: str | None = None
    dry_run: bool = False  # cli (local) use only
    export_waypoints: bool = False  # cli (local) use only

    @staticmethod
    def from_utf8_json(blob: bytes):
        """
        Takes a utf8 json blob and marshals to an instance of this class.
        """
        return TrajectoryWorkerJobDescriptor(
            day=json.loads(blob)["day"],
            met_source=MetSource(json.loads(blob)["met_source"]),
            telemetry_source=TelemetrySource(json.loads(blob)["telemetry_source"]),
            full_traj=json.loads(blob)["full_traj"],
            airline_iata=json.loads(blob)["airline_iata"],
            flight_id=json.loads(blob)["flight_id"],
            job_id=json.loads(blob)["job_id"],
            job_lookup_table=json.loads(blob)["job_lookup_table"],
            dry_run=json.loads(blob)["dry_run"],
            export_waypoints=json.loads(blob)["export_waypoints"],
        )

    def as_utf8_json(self) -> bytes:
        """
        Builds a utf-8 encoded JSON blob from the class' attributes.
        """
        js = json.dumps(asdict(self))
        return js.encode("utf-8")

    def verify(self):
        """
        Check that the TJWD describes a valid job.
        """
        # caller must provide ONE OF the following sets of flags
        valid_arg_combos = {
            (self.day, self.airline_iata, self.met_source),
            (self.day, bool(self.flight_id), self.met_source),
            (self.job_id, self.job_lookup_table),
        }
        is_valid = sum([all(itm) for itm in valid_arg_combos]) == 1

        if not is_valid:
            raise ValueError(
                "TJWD not valid. Must provide only one of ("
                "1) flight_id, or (2) airline_iata"
            )

        if self.met_source not in MetSource:
            raise ValueError(
                f"TJWD not valid. met_source must be one of {[i.value for i in MetSource]}"
            )

        # verify datestr parsing w/o exc
        if self.day:
            _ = datetime.strptime(self.day, "%Y-%m-%d")
