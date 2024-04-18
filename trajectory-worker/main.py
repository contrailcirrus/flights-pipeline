"""Entrypoint for the Spire Ingest Resample Worker."""

import sys

import lib.environment as env
from lib import utils
from lib.handlers import (
    PubSubSubscriptionHandler,
    PubSubPublishHandler,
)
from lib.log import format_traceback, logger
from lib.schemas import (
    WaypointsRecord,
    CocipTrajectoryChunk,
)

import pandas as pd
import xarray as xr
import numpy as np

from pycontrails.core.aircraft_performance import AircraftPerformance
from pycontrails.core import MetDataset, Flight
from pycontrails.models.cocip import Cocip
from pycontrails.models.humidity_scaling import (
    ExponentialBoostLatitudeCorrectionHumidityScaling,
)
from pycontrails.models.ps_model.ps_model import PSFlight

# matched to values used by api-preprocessor
STATIC_PARAMS = dict(
    humidity_scaling=ExponentialBoostLatitudeCorrectionHumidityScaling(),
    dt_integration="5min",
    max_altitude_m=None,
    min_altitude_m=None,
    interpolation_use_indices=True,
    interpolation_bounds_error=False,
    filter_sac=True,
    copy_source=True,
    met_longitude_buffer=(10.0, 10.0),  # default; potential perf gains fomr reducing
    met_latitude_buffer=(10.0, 10.0),  # default; potential perf gains from reducing
    met_level_buffer=(20, 20),  # reduced to same buffer used in api preprocessor
    max_age=np.timedelta64(1, "h"),
)

MET_MIN_ALTITUDE_FT = 30_000  # hard-coding allows more efficient skip-over


def _perf_lookup(job: WaypointsRecord) -> tuple[AircraftPerformance, str]:
    """
    Look up performance model and engine type for a job's aircraft type.

    Currently defaults to PSFlight for the performance model
    (open-source Poll-Schumann model designed for entire flights)
    and None for the engine type
    (which assigns responsibility to pycontrails for determining an appropriate value).

    Both should be replaced by a static lookup. Once this is done, the engine type
    will be represented by a str engine_uid, and the type hint in the
    function signature will match the actual return type.
    """
    return PSFlight(), None


def _aircraft_type_is_recognized(
    job: WaypointsRecord,
    performance_model: AircraftPerformance,
) -> bool:
    """Check if the aircraft type is supported by the selected performance model.

    Returns True if aircraft type is supported by the specified perf model. False otherwise.
    """
    # checking if an aircraft type is supported is not a method of
    # the abstract `AircraftPerformance` class, so have to check by subtype
    if isinstance(performance_model, PSFlight):
        return performance_model.check_aircraft_type_availability(
            job.flight_info.aircraft_type_icao,
            raise_error=False,
        )
    else:
        raise ValueError(f"Unexpected performance model {type(performance_model)}")


def _alt_below_met_data(job: WaypointsRecord) -> bool:
    """Check if the maximum segment altitude is high enough for intersection with met data.

    To avoid opening met data before short-circuiting, this check relies on a hard-coded value
    for the minimum altitude included in met data.

    Returns True if the entire flight segment is below the minimum
    altitude included in met data.
    """
    if max(w.altitude_baro for w in job.records) < MET_MIN_ALTITUDE_FT:
        return True
    return False


def _open_met_rad(
    job: WaypointsRecord, zarr_store: str
) -> tuple[MetDataset, MetDataset]:
    """Open forecast zarr stores.

    Will choose the most recent useable forecast.

    Note that the first forecast step must be at least half an hour before the earliest
    waypoint to provide a buffer for differencing accumulated radiative fluxes.

    Checks that the selected forecast extends long enough into the future to
    cover the entire simulation (requires half an hour beyond latest waypoint + max age)
    and raises an exception if it does not.

    Logic currently assumes that the zarr store will include a forecast
    initialized every 6h (0z, 6z, 12z, 18z each day).
    """
    earliest = pd.Timestamp(
        job.records[0].timestamp
    )  # is jobs.records guaranteed to be sorted by time?
    forecast_time = (earliest - pd.Timedelta(30, "m")).floor("6h")
    forecast_path = f"{zarr_store}/{forecast_time.strftime('%Y%m%d%H')}"

    pl = xr.open_zarr(f"{forecast_path}/pl.zarr")
    met = MetDataset(pl, provider="ECMWF", dataset="HRES", product="forecast")
    variables = (v[0] if isinstance(v, tuple) else v for v in Cocip.met_variables)
    met.standardize_variables(variables)

    sl = xr.open_zarr(f"{forecast_path}/sl.zarr")
    rad = MetDataset(sl, provider="ECMWF", dataset="HRES", product="forecast")
    variables = (v[0] if isinstance(v, tuple) else v for v in Cocip.rad_variables)
    rad.standardize_variables(variables)

    latest = pd.Timestamp(job.records[-1].timestamp)
    latest_possible = (
        pd.Timestamp(
            rad.data["time"]
            .max()
            .item(),  # rad will be limiting because of required buffer
            tz="UTC",
        )
        - pd.Timedelta(30, "min")
        - STATIC_PARAMS["max_age"]
    )
    if latest_possible < latest:
        raise ValueError("Latest waypoint is after latest possible prediction time")

    return met, rad


def _create_flight(job: WaypointsRecord, engine_uid: str) -> Flight:
    """Create Flight from job waypoints.

    Aircraft and engine type are associated with the flight here.
    """
    return Flight(
        longitude=[w.longitude for w in job.records],
        latitude=[w.latitude for w in job.records],
        altitude_ft=[w.altitude_baro for w in job.records],
        time=[w.timestamp for w in job.records],
        attrs=dict(
            flight_id=job.flight_info.flight_id,
            aircraft_type=job.flight_info.aircraft_type_icao,
            engine_uid=engine_uid,
        ),
    )


def _create_cocip_model(
    met: MetDataset, rad: MetDataset, perf: AircraftPerformance
) -> Cocip:
    """Create Cocip model.

    The chosen performance model is attached to the Cocip instance here.
    """
    return Cocip(met=met, rad=rad, aircraft_performance=perf, **STATIC_PARAMS)


def run():
    """
    Main entrypoint.
    - Dequeue a set of waypoints (trajectory chunk)
    - Run cocip against trajectory
    - Export values (big query, other TBD)
    """

    with PubSubSubscriptionHandler(env.TRAJECTORY_CHUNK_SUBSCRIPTION_ID) as job_handler:
        # ===================
        # fetch records
        # ===================
        job: WaypointsRecord
        ordering_key: str
        job, ordering_key = job_handler.fetch()

        logger.info(
            f"got job with {len(job.records)} records. "
            f"icao_address: {job.flight_info.icao_address}. "
            f"spanning: {job.records[0].timestamp} to {job.records[-1].timestamp}"
        )

        # ===================
        # apply CoCip Trajectory model
        # ===================

        # skip immediately if segment is too low to intersect met data
        if _alt_below_met_data(job):
            logger.info(
                f"flight segments for icao_address {job.flight_info.icao_address} "
                f"all below met data altitude. nothing to do. skipping... "
            )
            job_handler.ack()
            return

        # look up performance model and engine uid to use with job's aircraft type
        # skip if performance model does not support aircraft type
        performance_model, engine_uid = _perf_lookup(job)
        if not _aircraft_type_is_recognized(job, performance_model):
            logger.info(
                f"aircraft type not supported by CoCip perf. model. "
                f"icao_address:{job.flight_info.icao_address}, "
                f"aircraft_type_icao:{job.flight_info.aircraft_type_icao} "
                " skipping..."
            )
            job_handler.ack()
            return

        # set up and run CoCiP
        # gs://contrails-301217-ecmwf-hres-forecast-v2-short-term
        zarr_store = env.HRES_SOURCE_PATH  # noqa:F841
        met, rad = _open_met_rad(job, zarr_store)
        flight = _create_flight(job, engine_uid)
        model = _create_cocip_model(met, rad, performance_model)
        result = model.eval(flight)

        # ===================
        # publish trajectory chunk model outputs to BQ
        # ===================
        output: CocipTrajectoryChunk = (  # noqa:F841
            CocipTrajectoryChunk.from_cocip_result(
                source_id=ordering_key.split(":")[0],
                git_sha=env.GIT_SHA,
                input_chunk=job,
                result=result,
            )
        )

        trajectory_cocip_bq_publisher = PubSubPublishHandler(
            env.TRAJECTORY_CHUNK_SUBSCRIPTION_ID
        )
        trajectory_cocip_bq_publisher.publish_async(
            data=output.to_bq_flatmap(),
            client_name="trajectory_cocip_bq_publisher",
            icao_address=output.icao_address,
            source_id=output.source_id,
            time_start=output.time_start,
        )
        trajectory_cocip_bq_publisher.wait_for_publish()

        job_handler.ack()


if __name__ == "__main__":
    logger.info("starting trajectory-worker instance")
    sigterm_handler = utils.SigtermHandler()
    while True:
        if sigterm_handler.should_exit:
            sys.exit(0)
        try:
            run()
        except Exception:
            logger.error("Unhandled exception:" + format_traceback())
            sys.exit(1)
