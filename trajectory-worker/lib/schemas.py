""" Data Object Models & Schemas"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TypedDict
from uuid import UUID

import pandas as pd
import pytz
from timezonefinder import TimezoneFinder
from astral import LocationInfo
from astral.sun import sun
from google.protobuf import json_format

import numpy as np
import pycontrails.core
from pycontrails.models.cocip import Cocip

from lib.log import logger
from lib import trajectory_pb2 as traj_pb

tf = TimezoneFinder()


@dataclass(frozen=True)
class PubSubMessage:
    data: bytes
    ack_id: str
    delivery_attempt: int
    ordering_key: str


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
        latitude: float  # WGS ESPG:4326
        longitude: float  # WGS ESPG:4326
        altitude_ft: int  # feet MSL
        timestamp: int  # unixtime

    key: str  # <source_identifier>:<icao_address>, e.g. `spr:4B0293`
    waypoints: tuple[Waypoint, ...]  # record[0].timestamp < record[1].timestamp

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


class MetSource(str, Enum):
    HRES = "hres"
    ERA5 = "era5"


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
class CocipTrajectoryChunk:
    """
    Object that holds chunk-level summary values from running Cocip against the flight traj chunk.
    """

    seg_cnt: int  # total number of segments in the chunk
    seg_ef_cnt: int  # number of segments with non-zero ef in chunk
    seg_pos_ef_cnt: int  # number of segs with positive ef in chunk
    seg_ef_nan_cnt: int  # number of segments with nan ef values in chunk
    chunk_len_km: float  # total length of the flight chunk
    lat_start: float  # latitude of first waypoint in chunk
    lon_start: float  # lon of " " "
    lat_end: float  # lat of last waypoint in chunk
    lon_end: float  # lon of " " "
    time_start: str  # timestamp of first waypoint in chunk; e.g. "2024-03-01T17:40:00Z"
    time_start_tz: (
        str  # timezone representation as an integer offset from UTC e.g. "-08"
    )
    time_start_sunrise_offset_mins: int  # minutes from sunrise; clockwise positive
    time_start_sunset_offset_mins: int  # minutes from sunset; clockwise positive
    time_end: str  # timestamp of last waypoint in chunk; e.g. "2024-03-01T17:40:00Z"
    time_end_tz: str  # timezone representation as an integer offset from UTC e.g. "-08"
    median_altitude_ft: int  # median altitude across all waypoints in trajectory chunk
    total_persistent_contrail_length_km: float
    total_pos_ef_persistent_contrail_length_km: float
    total_contrail_length_sac_km: float
    max_contrail_lifetime_h: float
    median_contrail_lifetime_h: float

    pycontrails_ver: str  # version of pycontrails used in model run
    perf_model_id: str  # identifier of the perf model
    nvpm_data_source: str
    source_id: str  # the source identifier for the trajectory chunk job
    git_sha: str  # git sha of the trajectory-worker
    zarr_uri: str  # zarr store identifier; e.g. '<HRES/ERA5>/2024041506<,...>'

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
    mean_aircraft_mass_kg: float
    mean_engine_efficiency: float

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

    @classmethod
    def _utc_to_local_tz(cls, ts_str: str, lng: float, lat: float) -> tuple[str, str]:
        """
        Helper func to determine the local timezone given a datetime string.

        Parameters
        ----------
        ts_str
            A datetime represented as an ISO format datestring e.g. "2024-03-01T17:40:00Z"
        lng
            Longitude position of object at ts.
        lat
            Latitude position of object at ts.

        Returns
        ---------
        tuple(str, str)
            itm0: A string representation of the integer hours offset from UTC for the local timezone. e.g. "-08"
            itm1: A string representation of the timezone in `<region>/<city>` convention, e.g. "America/Denver"
        """
        ts = datetime.fromisoformat(ts_str)
        tz_str = tf.timezone_at(lng=lng, lat=lat)
        ts_local = ts.astimezone(pytz.timezone(tz_str))
        hr_offset = int(ts_local.utcoffset().total_seconds() / 3600)
        if hr_offset >= 0:
            sign = "+"
        else:
            sign = "-"

        return f"{sign}{abs(hr_offset):02d}", tz_str

    @classmethod
    def sunrise_sunset_mins_offset(
        cls, ts_str: str, timezone_str: str, lat: float, lon: float
    ) -> tuple[int | None, int | None]:
        """
        Calculates the offset in minutes to sunrise/sunset from a timestamp.
        By convention, clockwise is positive.
        A positive sunset offset and negative sunrise offset means daytime.
        A negative sunset offset and positive sunrise offset means nighttime.

        Parameters
        ----------
        ts_str
            An iso-formatted UTC datetime string literal for the target time. e.g. "2024-03-01T17:40:00Z"
        timezone_str
            A string representing the timezone of the object with `ts` timestamp. e.g. "America/Denver"
        lat
            Latitude location of the object with `ts` timestamp
        lon
            Longitude location of the object with `ts` timestamp

        Returns
        --------
        tuple[str,str]
            itm0: sunrise offset in minutes; negative value means daytime
            itm1: sunset offset in minutes; negative value means nighttime
        """

        sr_offset_mins = None
        ss_offset_mins = None

        try:
            ts = datetime.fromisoformat(ts_str)
            loc = LocationInfo(
                name=timezone_str.split("/")[1],
                region=timezone_str.split("/")[0],
                timezone=timezone_str,
                longitude=lon,
                latitude=lat,
            )

            s = sun(observer=loc.observer, date=ts.date())
            sunrise = s["sunrise"]
            sunset = s["sunset"]

            ts_mod = ts.minute + 60 * ts.hour
            sr_mod = sunrise.minute + 60 * sunrise.hour
            ss_mod = sunset.minute + 60 * sunset.hour

            # rotate coord sys to zero ts_mod
            sr_mod = sr_mod - ts_mod
            ss_mod = ss_mod - ts_mod
            ts_mod = 0

            # rotate negative coord positions to positive coord positions
            mins_per_day = 24 * 60
            sr_mod = sr_mod if sr_mod >= 0 else mins_per_day + sr_mod
            ss_mod = ss_mod if ss_mod >= 0 else mins_per_day + ss_mod

            # sunrise, ts, sunset minute-of-day breakpoints
            breakpts = [
                ["ts_mod", ts_mod],
                ["sr_mod", sr_mod],
                ["ss_mod", ss_mod],
            ]
            breakpts.sort(key=lambda itm: itm[1])  # order by mod asc

            # ts_mod will be zero index
            # ix[1] will be the right-hand breakpoint
            # ix[2] is the left-hand breakpoint
            if breakpts[1][0] == "sr_mod":
                # nighttime
                sr_offset_mins = breakpts[1][1]
                ss_offset_mins = breakpts[2][1] - mins_per_day  # rotate to lhs
            elif breakpts[1][0] == "ss_mod":
                # daytime
                ss_offset_mins = breakpts[1][1]
                sr_offset_mins = breakpts[2][1] - mins_per_day  # rotate to lhs
            else:
                logger.warning(
                    "unhandled case. did not generate daytime/nighttime offsets."
                )
        except ValueError as e:
            msg = str(e)
            even_offset_min = (24 * 60) / 2
            if msg == "Sun is always below the horizon on this day, at this location.":
                # nighttime
                # ---------
                # by convention, nighttime means positive offset to sunset
                # hence, here we will set an evenly spaced sunset/sunrise offset
                # that meets our sign convention
                sr_offset_mins = even_offset_min
                ss_offset_mins = -1 * even_offset_min
            elif (
                msg == "Sun is always above the horizon on this day, at this location."
            ):
                # daytime
                # -------
                sr_offset_mins = -1 * even_offset_min
                ss_offset_mins = even_offset_min
            else:
                logger.warning("failed to generate daytime/nighttime offsets.")
        except Exception as _:
            logger.warning("failed to generate daytime/nighttime offsets.")

        return sr_offset_mins, ss_offset_mins

    @classmethod
    def from_cocip_result(
        cls,
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
            e.g. `ERA5/202404-202405`
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

        tot_contrail_len = np.nansum(df_sl[df_sl["cocip"] != 0]["segment_length"])
        tot_contrail_len = (
            None if np.isnan(tot_contrail_len) else float(tot_contrail_len / 1000.0)
        )

        tot_pos_contrail_len = np.nansum(df_sl[df_sl["cocip"] > 0]["segment_length"])
        tot_pos_contrail_len = (
            None
            if np.isnan(tot_pos_contrail_len)
            else float(tot_pos_contrail_len / 1000.0)
        )

        tot_sac_len = np.nansum(df_sl[df_sl["sac"] == 1]["segment_length"])
        tot_sac_len = None if np.isnan(tot_sac_len) else float(tot_sac_len / 1000.0)

        max_contrail_age_hr = float(
            np.nanmax(df_sl["contrail_age"]) / np.timedelta64(1, "h")
        )
        max_contrail_age_hr = (
            None
            if (max_contrail_age_hr == 0 or np.isnan(max_contrail_age_hr))
            else max_contrail_age_hr
        )

        median_contrail_age_hr = np.nanmedian(
            df_sl[df_sl["contrail_age"] > np.timedelta64(0)]["contrail_age"]
        )
        median_contrail_age_hr = (
            None
            if np.isnan(median_contrail_age_hr)
            else float(median_contrail_age_hr / np.timedelta64(1, "h"))
        )

        mean_aircraft_mass_kg = float(np.nanmean(df_sl["aircraft_mass"]))
        mean_engine_efficiency = float(np.nanmean(df_sl["engine_efficiency"]))

        median_altitude_ft = int(np.nanmedian(df_sl["altitude_ft"]))

        tz_start_offset, tz_start_str = cls._utc_to_local_tz(
            input_chunk.records[0].timestamp,
            input_chunk.records[0].longitude,
            input_chunk.records[0].latitude,
        )

        tz_end_offset, tz_end_str = cls._utc_to_local_tz(
            input_chunk.records[0].timestamp,
            input_chunk.records[0].longitude,
            input_chunk.records[0].latitude,
        )

        (
            time_start_sunrise_offset_mins,
            time_start_sunset_offset_mins,
        ) = cls.sunrise_sunset_mins_offset(
            input_chunk.records[0].timestamp,
            tz_start_str,
            input_chunk.records[0].latitude,
            input_chunk.records[0].longitude,
        )

        def nan_to_null(x):
            if np.isnan(x):
                return None
            else:
                return x

        return CocipTrajectoryChunk(
            seg_cnt=len(segs_ef_j),
            seg_ef_cnt=int(sum(np.abs(segs_ef_j) > 0)),
            seg_pos_ef_cnt=int(sum(segs_ef_j > 0)),
            seg_ef_nan_cnt=int(np.isnan(segs_ef_j).sum()),
            chunk_len_km=float(np.nansum(result["segment_length"][sl]) / 1000.0),
            lat_start=input_chunk.records[0].latitude,
            lon_start=input_chunk.records[0].longitude,
            lat_end=input_chunk.records[-1].latitude,
            lon_end=input_chunk.records[-1].longitude,
            time_start=input_chunk.records[0].timestamp,
            time_start_tz=tz_start_offset,
            time_start_sunrise_offset_mins=time_start_sunrise_offset_mins,
            time_start_sunset_offset_mins=time_start_sunset_offset_mins,
            time_end=input_chunk.records[-1].timestamp,
            time_end_tz=tz_end_offset,
            median_altitude_ft=median_altitude_ft,
            total_persistent_contrail_length_km=tot_contrail_len,
            total_pos_ef_persistent_contrail_length_km=tot_pos_contrail_len,
            total_contrail_length_sac_km=tot_sac_len,
            max_contrail_lifetime_h=max_contrail_age_hr,
            median_contrail_lifetime_h=median_contrail_age_hr,
            pycontrails_ver=pycontrails.__version__,
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
            mean_aircraft_mass_kg=nan_to_null(mean_aircraft_mass_kg),
            mean_engine_efficiency=nan_to_null(mean_engine_efficiency),
            icao_address=input_chunk.flight_info.icao_address,
            flight_id=input_chunk.flight_info.flight_id,
            callsign=input_chunk.flight_info.callsign,
            tail_number=input_chunk.flight_info.tail_number,
            flight_number=input_chunk.flight_info.flight_number,
            airline_iata=input_chunk.flight_info.airline_iata,
            departure_airport_icao=input_chunk.flight_info.departure_airport_icao,
            departure_scheduled_time=input_chunk.flight_info.departure_scheduled_time,
            arrival_airport_icao=input_chunk.flight_info.arrival_airport_icao,
            arrival_scheduled_time=input_chunk.flight_info.arrival_scheduled_time,
        )

    @classmethod
    def from_cocip_result_all_segs(
        cls,
        source_id: str,
        git_sha: str,
        input_chunk: WaypointsRecord,
        zarr_uri: str,
        result: pycontrails.core.Flight,
    ):
        """
        Generate a list of CocipTrajectoryChunk objs from
        the output/result of a cocip trajectory model run.
        This builds one CoipTrajectoryChunk per flight segment in the result.

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

        df = result.dataframe

        def nan_to_null(x):
            if np.isnan(x):
                return None
            else:
                return x

        outputs: list[CocipTrajectoryChunk] = []
        for seg_ix in range(0, len(df) - 1):
            # segments are forward looking in the dataframe
            # the table has N_waypoints
            # thus N_segs = N_waypoints - 1 and the last seg spans [-2:]
            ds = df.iloc[seg_ix, :]
            ds_next = df.iloc[seg_ix + 1, :]

            tot_contrail_len = (
                float(ds["segment_length"] / 1000.0) if ds["cocip"] != 0 else None
            )
            tot_pos_contrail_len = (
                float(ds["segment_length"] / 1000.0) if ds["cocip"] > 0 else None
            )

            tot_sac_len = float(ds["segment_length"]) / 1000.0 if ds["sac"] == 1 else 0
            max_contrail_age_hr = float(ds["contrail_age"] / np.timedelta64(1, "h"))
            max_contrail_age_hr = (
                None
                if (np.isnan(max_contrail_age_hr) or max_contrail_age_hr == 0)
                else max_contrail_age_hr
            )

            median_contrail_age_hr = float(ds["contrail_age"] / np.timedelta64(1, "h"))
            median_contrail_age_hr = (
                None
                if (np.isnan(median_contrail_age_hr) or median_contrail_age_hr == 0)
                else median_contrail_age_hr
            )

            mean_aircraft_mass = np.nanmean(
                [ds["aircraft_mass"], ds_next["aircraft_mass"]]
            )

            median_altitude_ft = int(
                np.nanmedian([ds["altitude_ft"], ds_next["altitude_ft"]])
            )

            tz_start_offset, tz_start_str = cls._utc_to_local_tz(
                ds["time"].isoformat() + "Z",
                float(ds["longitude"]),
                float(ds["latitude"]),
            )

            tz_end_offset, tz_end_str = cls._utc_to_local_tz(
                ds_next["time"].isoformat() + "Z",
                float(ds_next["longitude"]),
                float(ds_next["latitude"]),
            )

            time_start_str = ds["time"].isoformat() + "Z"
            lat_start = float(ds["latitude"])
            lon_start = float(ds["longitude"])
            (
                time_start_sunrise_offset_mins,
                time_start_sunset_offset_mins,
            ) = cls.sunrise_sunset_mins_offset(
                time_start_str, tz_start_str, lat_start, lon_start
            )

            seg = CocipTrajectoryChunk(
                seg_cnt=1,
                seg_ef_cnt=1 if np.abs(ds["ef"]) > 0 else 0,
                seg_pos_ef_cnt=1 if ds["ef"] > 0 else 0,
                seg_ef_nan_cnt=1 if np.isnan(ds["ef"]) else 0,
                chunk_len_km=float(ds["segment_length"] / 1000.0),
                lat_start=lat_start,
                lon_start=lon_start,
                lat_end=float(ds_next["latitude"]),
                lon_end=float(ds_next["longitude"]),
                time_start=time_start_str,
                time_start_tz=tz_start_offset,
                time_start_sunrise_offset_mins=time_start_sunrise_offset_mins,
                time_start_sunset_offset_mins=time_start_sunset_offset_mins,
                time_end=ds_next["time"].isoformat() + "Z",
                time_end_tz=tz_end_offset,
                median_altitude_ft=median_altitude_ft,
                total_persistent_contrail_length_km=tot_contrail_len,
                total_pos_ef_persistent_contrail_length_km=tot_pos_contrail_len,
                total_contrail_length_sac_km=tot_sac_len,
                max_contrail_lifetime_h=max_contrail_age_hr,
                median_contrail_lifetime_h=median_contrail_age_hr,
                pycontrails_ver=pycontrails.__version__,
                perf_model_id=attrs["aircraft_performance_model"],
                nvpm_data_source=attrs["nvpm_data_source"],
                source_id=source_id,
                git_sha=git_sha,
                zarr_uri=zarr_uri,
                sum_ef_mj=int(ds["ef"] // 10**6) if not np.isnan(ds["ef"]) else 0,
                total_fuel_burn_kg=(
                    int(ds["fuel_burn"]) if not np.isnan(ds["fuel_burn"]) else 0
                ),
                total_co2_kg=int(ds["co2"]) if not np.isnan(ds["co2"]) else 0,
                total_h2o_kg=int(ds["h2o"]) if not np.isnan(ds["h2o"]) else 0,
                total_so2_kg=float(ds["so2"]) if not np.isnan(ds["so2"]) else 0,
                total_sulphates_kg=(
                    float(ds["sulphates"]) if not np.isnan(ds["sulphates"]) else 0
                ),
                total_oc_kg=float(ds["oc"]) if not np.isnan(ds["oc"]) else 0,
                total_nox_kg=float(ds["nox"]) if not np.isnan(ds["nox"]) else 0,
                total_co_kg=float(ds["co"]) if not np.isnan(ds["co"]) else 0,
                total_hc_kg=float(ds["hc"]) if not np.isnan(ds["hc"]) else 0,
                total_nvpm_kg=(
                    float(ds["nvpm_mass"]) if not np.isnan(ds["nvpm_mass"]) else 0
                ),
                total_nvpm_giga_cnt=(
                    int(ds["nvpm_number"] // 10**9)
                    if not np.isnan(ds["nvpm_number"])
                    else 0
                ),
                aircraft_type_icao=attrs["aircraft_type"],
                engine_uid=attrs["engine_uid"],
                mean_aircraft_mass_kg=nan_to_null(mean_aircraft_mass),
                mean_engine_efficiency=(
                    float(ds["engine_efficiency"])
                    if not np.isnan(ds["engine_efficiency"])
                    else None
                ),
                icao_address=input_chunk.flight_info.icao_address,
                flight_id=input_chunk.flight_info.flight_id,
                callsign=input_chunk.flight_info.callsign,
                tail_number=input_chunk.flight_info.tail_number,
                flight_number=input_chunk.flight_info.flight_number,
                airline_iata=input_chunk.flight_info.airline_iata,
                departure_airport_icao=input_chunk.flight_info.departure_airport_icao,
                departure_scheduled_time=input_chunk.flight_info.departure_scheduled_time,
                arrival_airport_icao=input_chunk.flight_info.arrival_airport_icao,
                arrival_scheduled_time=input_chunk.flight_info.arrival_scheduled_time,
            )
            outputs.append(seg)

        return outputs

    def to_bq_flatmap(self, processed_at: datetime) -> bytes:
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

        Parameters
        -------
        processed_at a datetime object indicating the server side processing time for this record.
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
            "_processed_at": iso_to_microseconds(processed_at.isoformat()),
            "seg_cnt": self.seg_cnt,
            "seg_ef_cnt": self.seg_ef_cnt,
            "seg_pos_ef_cnt": self.seg_pos_ef_cnt,
            "seg_ef_nan_cnt": self.seg_ef_nan_cnt,
            "chunk_len_km": self.chunk_len_km,
            "lat_start": self.lat_start,
            "lon_start": self.lon_start,
            "lat_end": self.lat_end,
            "lon_end": self.lon_end,
            "time_start": time_start_us,
            "time_start_tz": self.time_start_tz,
            "time_start_sunrise_offset_mins": self.time_start_sunrise_offset_mins,
            "time_start_sunset_offset_mins": self.time_start_sunset_offset_mins,
            "time_end": time_end_us,
            "time_end_tz": self.time_end_tz,
            "median_altitude_ft": self.median_altitude_ft,
            "total_persistent_contrail_length_km": self.total_persistent_contrail_length_km,
            "total_pos_ef_persistent_contrail_length_km": self.total_pos_ef_persistent_contrail_length_km,
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
            "mean_aircraft_mass_kg": self.mean_aircraft_mass_kg,
            "mean_overall_efficiency": self.mean_engine_efficiency,
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
            "arrival_airport_icao": self.arrival_airport_icao,
            "arrival_scheduled_time": iso_to_microseconds(self.arrival_scheduled_time),
        }
        try:
            json_out = json.dumps(blob).encode("utf-8")
        except Exception as e:
            logger.warning(f"could not JSON serialize output: {blob}")
            raise Exception from e
        return json_out


@dataclass
class CocipTrajectoryProto:
    """
    Object that encapsulates data transfer methods for a cocip trajectory protobuf object.

    The trajectory proto object includes both per-segment summary values and per-segment
    contrail evolution values.

    Cocip model outputs are downsampled (as documented below), and compressed (as documented below).
    """

    trajectory: traj_pb.Trajectory

    @classmethod
    def _get_traj_contrail_freq_ix(
        cls,
        df: pd.DataFrame,
        freq: str = "10min",
    ) -> pd.core.indexes.base.Index:
        """
        Get indexes for a freq resample of df.
        Given a dataframe with the per-segment cocip outputs,
        get the indexes at the fixed frequency resample.

        Parameters
        ----------
        df
            dataframe from result.dataframe where result is an output of a cocip model() run
        freq
            frequency indicator for resampling; must be a string value recognized by pandas resample

        Returns
        -------
        pd.core.indexes.base.Index
            list of indexes of df that fall on a frequency interval
        """
        df_tmp = df[["waypoint", "time"]]
        df_tmp.set_index("time", inplace=True)
        df_tmp_resample = df_tmp.resample(freq).first()
        df_tmp_resample = df_tmp_resample.set_index("waypoint")
        df_tmp_resample.index.name = None
        resample_index = df_tmp_resample.index
        # add in rhs index to close upper bound
        max_ix = df.index.max()
        resample_index = resample_index.union(pd.Index([max_ix]))
        return resample_index

    @classmethod
    def _get_traj_contrail_boundary_ix(
        cls, df: pd.DataFrame
    ) -> pd.core.indexes.base.Index:
        """
        Find indexes in df where contrails are formed.
        Given a dataframe with the per-segment cocip model output,
        find the boundaries where the `cocip` value is non-zero.

        Parameters
        ----------
        df
            dataframe from result.dataframe where result is an output of a cocip model() run

        Returns
        -------
        pandas.core.indexes.base.Index
            The list of pandas indexes matching start and ends of contrail segments.
            Each row of df represents values for a forward-looking segment from geo-position ix -> ix+1.
            The indexes returned here represent the first occurrence index
            and last occurrence _slice_ index of a non-zero cocip value in
            each continuous sequence of contrail segments.
        """

        contrail = df["cocip"] != 0
        starts = (contrail == True) & (contrail.shift(1) == False)  # noqa:E712
        ends = (contrail == True) & (contrail.shift(-1) == False)  # noqa:E712
        starts_ix = (starts[starts == True]).index  # noqa:E712
        ends_ix = (ends[ends == True]).index  # noqa:E712
        ends_ix += (
            1  # set index to slice (non-inclusive) index for right hand side of range
        )
        boundaries_ix = starts_ix.union(ends_ix)
        boundaries_ix = boundaries_ix.drop_duplicates()
        return boundaries_ix

    @classmethod
    def _resample_cocip_result(cls, result: pycontrails.core.Flight) -> pd.DataFrame:
        """
        Resample the per-segment cocip result.

        Resamples to 10min fixed frequency, but preserves contrail start and stop boundaries.

        Parameters
        ----------
        result
            a pandas dataframe as returned from a pycontrails model.eval()

        Returns
        -------
        pd.DataFrame
            a pandas dataframe with resampled data.
            fields included in the return dataframe encompass those itemized in the
            `sum_fields` and `first_fields` lists below
        """
        df = result.dataframe
        contrail_boundaries_ix = cls._get_traj_contrail_boundary_ix(df)
        freq_boundaries_ix = cls._get_traj_contrail_freq_ix(df)
        all_resample_boundaries = freq_boundaries_ix.union(contrail_boundaries_ix)

        bin_ranges = pd.cut(
            df.index, all_resample_boundaries, include_lowest=True, right=False
        )
        # fields of dataframe to resample with sum() method
        sum_fields = ["ef"]

        # fields of dataframe to resample with first() method
        first_fields = [
            "time",
            "altitude_ft",
            "longitude",
            "latitude",
            "waypoint",
        ]

        df_first = df[first_fields]
        df_first = df_first.groupby(bin_ranges, observed=False).first()
        df_sum = df[sum_fields]
        df_sum = df_sum.groupby(bin_ranges, observed=False).sum()
        df_all = pd.merge(df_sum, df_first, left_index=True, right_index=True)

        # convert ef -> sum_ef_mj
        df_all["sum_ef_mj"] = df_all["ef"] / 10**6
        df_all = df_all.drop(columns=["ef"])

        # append positional information for second to last waypoint
        # (that included in the open-bounded range of the last resampling interval)
        # so we can create segments for each row
        last_waypoint = pd.DataFrame(
            [[np.nan] * len(df_all.columns)], columns=df_all.columns
        )
        last_waypoint["time"] = df.iloc[-2]["time"]
        last_waypoint["latitude"] = df.iloc[-2]["latitude"]
        last_waypoint["longitude"] = df.iloc[-2]["longitude"]
        last_waypoint["altitude_ft"] = df.iloc[-2]["altitude_ft"]
        df_all = pd.concat([df_all, last_waypoint], ignore_index=True)
        return df_all

    @classmethod
    def _group_contrails(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Group continuous ranges of waypoints into contrail instances.

        Given a pandas dataframe representing a group of waypoints
        for a contrail evolution at a given time,
        append a column (waypoint_bin) where each bin represents a continuous linestring
        for a given contrail.

        Parameters
        ----------
        df
            a dataframe from a pycontrails CoCiP result (model.contrail) grouped by `time`

        Return
        ------
        pd.DataFrame
            mirror of input dataframe, with a `waypoint_bin`
        """
        df = df.copy()
        # extract each continuous multiline from evolution step
        df.sort_values(
            "waypoint", ascending=True, inplace=True
        )  # guarantee waypoints are ordered
        # find breaks in continuous contrail segments
        df["waypoint_bin"] = (df["waypoint"].diff() > 1).cumsum()
        return df

    @classmethod
    def from_cocip_result(
        cls, input_chunk: WaypointsRecord, result: pycontrails.core.Flight, model: Cocip
    ):
        """
        Build a trajectory protobuf object from a cocip result.

        Parameters
        ----------
        input_chunk
            the flight trajectory and flight metadata
        result
            the pycontrails Flight model output from running CoCiP
        model
            instance of a CoCiP model from which result is generated

        Returns
        -------
        CocipTrajectoryProto
            an instance of this dataclass, with a protobuf trajectory built from the inputs
        """
        df = cls._resample_cocip_result(result)

        traj = traj_pb.Trajectory()
        traj.flight_id = input_chunk.flight_info.flight_id

        # ----------
        # package PER SEGMENT CoCiP outputs
        # ----------
        for seg_ix in range(0, len(df) - 1):
            # segments are forward looking in the dataframe
            # the table has N_waypoints
            # thus N_segs = N_waypoints - 1 and the last seg spans [-2:]
            ds = df.iloc[seg_ix, :]
            ds_next = df.iloc[seg_ix + 1, :]

            seg = traj.path.add()
            seg.time_start = ds["time"]
            seg.duration_start_to_end = ds_next["time"] - ds["time"]
            seg.geometry.coord_start.lon = int(ds["longitude"] * 20)
            seg.geometry.coord_start.lat = int(ds["latitude"] * 20)
            seg.geometry.coord_start.alt_ft = int(ds["altitude_ft"] / 16)
            seg.geometry.coord_end.lon = int(ds_next["longitude"] * 20)
            seg.geometry.coord_end.lat = int(ds_next["latitude"] * 20)
            alt_ft = ds_next["altitude_ft"]
            if alt_ft < 0:
                alt_ft = 0
            seg.geometry.coord_end.alt_ft = int(alt_ft / 16)
            seg.sum_ef_mj = int(ds["sum_ef_mj"] / 100)

        # ----------
        # package CONTRAIL EVOLUTION CoCiP outputs
        # ----------
        contrail_evol = model.contrail
        if contrail_evol is None:
            # if model.contrail is set but None, then no contrail was formed on model.eval()
            return CocipTrajectoryProto(trajectory=traj)

        contrail_evol_tm_grps = contrail_evol.groupby("time")
        evolution_timestep = pd.Timedelta(model.params["dt_integration"])

        # handle each evolution timestep independently
        for ts, grp in contrail_evol_tm_grps:
            # identify continuous contrail line-strings within timestep of evolution
            grp = cls._group_contrails(grp)
            contrails_in_grp = grp.groupby("waypoint_bin", observed=True)
            for wp_bin, contrail_df in contrails_in_grp:
                if len(contrail_df) == 1:
                    # this is always the case for the single waypoint
                    # which coincides with the t_0 of contrail evolution for a given timestamp
                    # and that waypoint will always have the column `continuous` w/ value False
                    continue
                # -------
                # construct multi-line object from sequence of waypoints
                # --
                # by convention, the values in a given row are left-handed
                # i.e. the line formed by coords defined in row[i] -> row[i+1]
                # take the values defined in row[i].
                # by extension, the last row is expected to provide the right-hand
                # coords for the last line object, and that row's values are expected to be null
                # (these "points of discontinuity" are also identifiable by having the col `continuous`== False)
                contrail = traj.contrails.add()
                contrail.avg_age = contrail_df.age.mean().round("s")
                # by convention, the timestamp is that following the evolution timestep
                contrail.time_start = contrail_df.iloc[0]["time"] - evolution_timestep
                contrail.duration_start_to_end = evolution_timestep
                # sum of ef across all segments of multi-line contrails FOR THE EVOLUTION TIMESTEP
                sum_ef_mj = contrail_df.ef.sum() / 10**6
                contrail.sum_ef_mj = int(sum_ef_mj / 100)
                # build multi-line geometry
                for _, row in contrail_df.iterrows():
                    coord = contrail.geometry.coords.add()
                    coord.lon = int(row["longitude"] * 20)
                    coord.lat = int(row["latitude"] * 20)
                    alt_ft = row["altitude"] * 3.28
                    if alt_ft < 0:
                        alt_ft = 0
                    coord.alt_ft = int(alt_ft / 16)
        return CocipTrajectoryProto(trajectory=traj)

    def to_bytes(self) -> bytes:
        """Serialize the protobuf trajectory belonging to an instance of this class."""
        return self.trajectory.SerializeToString()

    @classmethod
    def from_bytes(cls, traj_bytes: bytes):
        """Decode a protobuf trajectory into an object of this class."""
        trajectory = traj_pb.Trajectory()
        trajectory.ParseFromString(traj_bytes)
        return CocipTrajectoryProto(trajectory=trajectory)

    def as_dict(self) -> dict:
        """Convert the protobuf trajectory in an instance of this class to a python dict."""
        return json_format.MessageToDict(self.trajectory)
