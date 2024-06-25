""" Data Object Models & Schemas"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID

import numpy as np
import pycontrails.core


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
            longitude=wp["latitude"],
            collection_type=None,
            altitude_baro=wp["altitude_ft"],
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
                return None
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
            export_cocip_trajectory=json.loads(blob)["export_cocip_trajectory"],
            flight_info=FlightInfoWide(**json.loads(blob)["flight_info"]),
            records=[SpireWaypointPositional(**r) for r in json.loads(blob)["records"]],
        )


@dataclass
class CocipTrajectoryChunk:
    """
    Object that holds chunk-level summary values from running Cocip against the flight traj chunk.
    """

    seg_cnt: int  # total number of segments in the chunk
    seg_ef_cnt: int  # number of segments with non-zero ef in chunk
    seg_ef_nan_cnt: int  # number of segments with nan ef values in chunk
    chunk_len_km: float  # total length of the flight chunk
    lat_start: float  # latitude of first waypoint in chunk
    lon_start: float  # lon of " " "
    lat_end: float  # lat of last waypoint in chunk
    lon_end: float  # lon of " " "
    time_start: str  # timestamp of first waypoint in chunk; e.g. "2024-03-01T17:40:00Z"
    time_end: str  # timestamp of last waypoint in chunk; e.g. "2024-03-01T17:40:00Z"
    total_persistent_contrail_length_km: float
    total_contrail_length_sac_km: float
    max_contrail_lifetime_h: float
    median_contrail_lifetime_h: float

    pycontrails_ver: str  # version of pycontrails used in model run
    perf_model_id: str  # identifier of the perf model
    nvpm_data_source: str
    source_id: str  # the source identifier for the trajectory chunk job
    git_sha: str  # git sha of the trajectory-worker
    zarr_uri: str  # zarr store model_run_at identifier; e.g. '2024041506'

    sum_ef_mj: int  # sum of the calculated ef values, units 10^6*[J]
    total_fuel_burn_kg: int  # total kg of fuel burn for chunk
    total_co2_kg: int  # total kg of co2 from fuel combustion for chunk
    total_h2o_kg: int  # total kg of h20 from fuel combustion " "
    total_so2_kg: float  # total kg of so2 " " "
    total_sulphates_kg: float  # total kg of sulphates  " " "
    total_oc_kg: float  # total kg of organic carbon " " "
    total_nox_kg: float  # total kg of nox " " "
    total_co_kg: float  # total kg of CO " " "
    total_hc_kg: float  # total kg of hydrocarbon " " "
    total_nvpm_kg: float  # total kg non-volatile PM  " " "
    total_nvpm_giga_cnt: int  # total cnt (*10^9) of non-volatile PM " " "

    aircraft_type_icao: str  # icao aircraft type identifier used in model e.g. B788
    engine_uid: str  # engine uid used in model

    icao_address: str  # e.g. 4B0293
    flight_id: str  # e.g. ef9fb457-0f70-4780-9154-6a5362e39862
    callsign: str | None  # e.g. SWR64C
    tail_number: str | None  # e.g. HB-AZJ
    flight_number: str | None  # e.g. LX644
    airline_iata: str | None  # e.g. LX
    departure_airport_icao: str | None  # e.g. LSZH
    departure_scheduled_time: str | None  # e.g. 2024-03-01T16:25:00Z
    arrival_airport_icao: str | None  # e.g. LFPG
    arrival_scheduled_time: str | None  # e.g. 2024-03-01T17:40:00Z

    @staticmethod
    def from_cocip_result(
        source_id: str,
        git_sha: str,
        input_chunk: WaypointsRecord,
        zarr_uri: str,
        result: pycontrails.core.Flight,
    ):
        """
        Generate a CocipTrajectoryChunk from the output/result of a cocip trajectory model run.

        Parameters
        ----------
        source_id
            the source identifier for the job injected into the trajectory worker
        git_sha
            the git_sha for the trajectory worker
        input_chunk
            the job (list of waypoints) passed to the trajectory worker, w/ flightinfo metadata
        zarr_uri
            the identifier specifying the model run at time of the zarr store used in running cocip
            e.g. `2024041506`
        result
            the model result from running the cocip trajectory model
        """

        class CocipFlightAttributes(TypedDict):
            aircraft_type: str  # B788 (icao aircraft type)
            engine_uid: str  # 01P17GE210 (icao engine id)
            aircraft_performance_model: str  # PSFlight
            nvpm_data_source: str  # "ICAO EDB"
            total_fuel_burn: float
            total_co2: float
            total_h2o: float
            total_so2: float
            total_sulphates: float
            total_oc: float
            total_nox: float
            total_co: float
            total_hc: float
            total_nvpm_mass: float
            total_nvpm_number: float
            pycontrails_version: str

        attrs: CocipFlightAttributes = dict(result.attrs)
        if not attrs.get("aircraft_performance_model"):
            # fix for cocip result when using bada
            attrs["aircraft_performance_model"] = attrs["bada_model"]

        # FIX
        # ------
        # the `result` object when running CoCip trajectory with BADA does not include
        # the `aircraft_performance_model` attribute
        # as such, if that attribute is missing, we fetch the `bada_model` attribute instead
        # and assign it to `aircraft_performance_model`
        # Reference
        # ---------
        # cocip result attributes | BADA
        # dict_keys(['flight_id', 'aircraft_type', 'engine_uid', 'crs', 'bada_model', 'aircraft_type_bada', 'engine_type_bada', 'engine_type_edb', 'wingspan', 'max_mach', 'max_altitude', 'n_engine', 'total_fuel_burn', 'gaseous_data_source', 'nvpm_data_source', 'total_co2', 'total_h2o', 'total_so2', 'total_sulphates', 'total_oc', 'total_nox', 'total_co', 'total_hc', 'total_nvpm_mass', 'total_nvpm_number', 'humidity_scaling_name', 'humidity_scaling_formula', 'pycontrails_version'])
        #
        # cocip result attributes | PSFlight
        # dict_keys(['flight_id', 'aircraft_type', 'engine_uid', 'crs', 'aircraft_performance_model', 'n_engine', 'wingspan', 'max_mach', 'max_altitude', 'total_fuel_burn', 'gaseous_data_source', 'nvpm_data_source', 'total_co2', 'total_h2o', 'total_so2', 'total_sulphates', 'total_oc', 'total_nox', 'total_co', 'total_hc', 'total_nvpm_mass', 'total_nvpm_number', 'humidity_scaling_name', 'humidity_scaling_formula', 'pycontrails_version'])

        # we drop the last segment in the cocip outputs
        # because the resample-worker guarantees a leading edge overlap of 1 segment
        # between consecutive jobs
        sl = slice(0, -2)
        segs_ef_j = result["ef"][sl]
        df_sl = result.dataframe[sl]

        tot_contrail_len = float(
            np.nansum(df_sl[df_sl["cocip"] != 0]["segment_length"]) / 1000.0
        )
        tot_sac_len = float(
            np.nansum(df_sl[df_sl["sac"] == 1]["segment_length"]) / 1000.0
        )

        max_contrail_age_hr = float(
            np.nanmax(df_sl["contrail_age"]).astype(int) / (10**9 * 60 * 60)
        )
        median_contrail_age_hr = float(
            np.nanmedian(
                df_sl[df_sl["contrail_age"] > np.timedelta64(0)]["contrail_age"]
            ).astype(int)
            / (10**9 * 60 * 60)
        )

        return CocipTrajectoryChunk(
            seg_cnt=len(segs_ef_j),
            seg_ef_cnt=int(sum(np.abs(segs_ef_j) > 0)),
            seg_ef_nan_cnt=int(np.isnan(segs_ef_j).sum()),
            chunk_len_km=float(np.nansum(result["segment_length"][sl]) / 1000.0),
            lat_start=input_chunk.records[0].latitude,
            lon_start=input_chunk.records[0].longitude,
            lat_end=input_chunk.records[-1].latitude,
            lon_end=input_chunk.records[-1].longitude,
            time_start=input_chunk.records[0].timestamp,
            time_end=input_chunk.records[-1].timestamp,
            total_persistent_contrail_length_km=tot_contrail_len,
            total_contrail_length_sac_km=tot_sac_len,
            max_contrail_lifetime_h=max_contrail_age_hr,
            median_contrail_lifetime_h=median_contrail_age_hr,
            pycontrails_ver=attrs["pycontrails_version"],
            perf_model_id=attrs["aircraft_performance_model"],
            nvpm_data_source=attrs["nvpm_data_source"],
            source_id=source_id,
            git_sha=git_sha,
            zarr_uri=zarr_uri,
            sum_ef_mj=int(np.nansum(segs_ef_j) // 10**6),
            total_fuel_burn_kg=int(attrs["total_fuel_burn"]),
            total_co2_kg=int(attrs["total_co2"]),
            total_h2o_kg=int(attrs["total_h2o"]),
            total_so2_kg=float(attrs["total_so2"]),
            total_sulphates_kg=float(attrs["total_sulphates"]),
            total_oc_kg=float(attrs["total_oc"]),
            total_nox_kg=float(attrs["total_nox"]),
            total_co_kg=float(attrs["total_co"]),
            total_hc_kg=float(attrs["total_hc"]),
            total_nvpm_kg=float(attrs["total_nvpm_mass"]),
            total_nvpm_giga_cnt=int(attrs["total_nvpm_number"] // 10**9),
            aircraft_type_icao=attrs["aircraft_type"],
            engine_uid=attrs["engine_uid"],
            icao_address=input_chunk.flight_info.icao_address,
            flight_id=input_chunk.flight_info.flight_id,
            callsign=input_chunk.flight_info.callsign,
            tail_number=input_chunk.flight_info.tail_number,
            flight_number=input_chunk.flight_info.flight_number,
            airline_iata=input_chunk.flight_info.airline_iata,
            departure_airport_icao=input_chunk.flight_info.departure_airport_icao,
            departure_scheduled_time=input_chunk.flight_info.departure_scheduled_time,
            arrival_airport_icao=input_chunk.flight_info.departure_airport_icao,
            arrival_scheduled_time=input_chunk.flight_info.arrival_scheduled_time,
        )

    def to_bq_flatmap(self) -> bytes:
        """
        Flattens records into a single utf-8 encoded json string literals,
        ready for egress to big query.


        Converts temporal string fields (time_start, time_end, ...)  to microseconds epoch.

        Adds an `_instance_hash` k-v, of type int,
        generated as a hash of composite record fields.
        Specifically:

        <pycontrails_ver><aircraft_type_icao><engine_uid>
        <perf_model_id><icao_address>
        <time_start><time_end>
        """

        def iso_to_microseconds(timestamp: str | None) -> int | None:
            if not timestamp:
                return None
            ts: int = int(datetime.fromisoformat(timestamp).timestamp() * 1e6)
            return ts

        time_start_us = iso_to_microseconds(self.time_start)
        time_end_us = iso_to_microseconds(self.time_end)

        # _instance_hash is an int64 in bq
        hash = hashlib.md5(
            f"{self.pycontrails_ver}{self.aircraft_type_icao}{self.engine_uid}"
            f"{self.perf_model_id}{self.icao_address}"
            f"{time_start_us}{time_end_us}".encode("utf-8")
        )
        # truncate as to be equal or smaller than int64 space when represented as signed int
        hash_trunc = hash.hexdigest()[:8]
        hash_int = int(hash_trunc, 16)
        blob = {
            "_chunk_hash": hash_int,
            "_processed_at": iso_to_microseconds(datetime.now(tz=UTC).isoformat()),
            "seg_cnt": self.seg_cnt,
            "seg_ef_cnt": self.seg_ef_cnt,
            "seg_ef_nan_cnt": self.seg_ef_nan_cnt,
            "chunk_len_km": self.chunk_len_km,
            "lat_start": self.lat_start,
            "lon_start": self.lon_start,
            "lat_end": self.lat_end,
            "lon_end": self.lon_end,
            "time_start": time_start_us,
            "time_end": time_end_us,
            "total_persistent_contrail_length_km": self.total_persistent_contrail_length_km,
            "total_contrail_length_sac_km": self.total_contrail_length_sac_km,
            "max_contrail_lifetime_h": self.max_contrail_lifetime_h,
            "median_contrail_lifetime_h": self.median_contrail_lifetime_h,
            "pycontrails_ver": self.pycontrails_ver,
            "perf_model_id": self.perf_model_id,
            "nvpm_data_source": self.nvpm_data_source,
            "source_id": self.source_id,
            "git_sha": self.git_sha,
            "zarr_uri": self.zarr_uri,
            "sum_ef_mj": self.sum_ef_mj,
            "total_fuel_burn_kg": self.total_fuel_burn_kg,
            "total_co2_kg": self.total_co2_kg,
            "total_h2o_kg": self.total_h2o_kg,
            "total_so2_kg": self.total_so2_kg,
            "total_sulphates_kg": self.total_sulphates_kg,
            "total_oc_kg": self.total_oc_kg,
            "total_nox_kg": self.total_nox_kg,
            "total_co_kg": self.total_co_kg,
            "total_hc_kg": self.total_hc_kg,
            "total_nvpm_kg": self.total_nvpm_kg,
            "total_nvpm_giga_cnt": self.total_nvpm_giga_cnt,
            "aircraft_type_icao": self.aircraft_type_icao,
            "engine_uid": self.engine_uid,
            "icao_address": self.icao_address,
            "flight_id": self.flight_id,
            "callsign": self.callsign,
            "tail_number": self.tail_number,
            "flight_number": self.flight_number,
            "airline_iata": self.airline_iata,
            "departure_airport_icao": self.departure_airport_icao,
            "departure_scheduled_time": iso_to_microseconds(
                self.departure_scheduled_time
            ),
            "arrival_airport_icao": self.departure_airport_icao,
            "arrival_scheduled_time": iso_to_microseconds(self.arrival_scheduled_time),
        }
        return json.dumps(blob).encode("utf-8")
