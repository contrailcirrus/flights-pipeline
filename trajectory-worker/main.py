"""Entrypoint for the Spire Ingest Resample Worker."""

import sys
import time

import lib.environment as env
from lib import utils
from lib.handlers import (
    PubSubSubscriptionHandler,
)
from lib.log import format_traceback, logger
from lib.schemas import (
    SpireWaypointsRecord,
)

import pandas as pd
import xarray as xr
import numpy as np

from pycontrails.core.aircraft_performance import AircraftPerformance
from pycontrails.core import MetDataset, Flight
from pycontrails.models.cocip import Cocip
from pycontrails.models.humidity_scaling import ExponentialBoostLatitudeCorrectionHumidityScaling
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
    met_level_buffer=(20, 20),
    max_age=np.timedelta64(1, "h")
)

def _perf_lookup(job: SpireWaypointsRecord) -> tuple[AircraftPerformance, str]:
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
    performance_model = PSFlight()

    # checking if an aircraft type is supported is not a method of
    # the abstract `AircraftPerformance` class, so have to check by subtype
    if isinstance(performance_model, PSFlight):
        performance_model.check_aircraft_type_availability(
            job.flight_info.aircraft_type_icao,
            raise_error=True
        )
    else:
        raise ValueError(f"Unexpected performance model {type(performance_model)}")

    engine_uid = None  # TODO: replace with str from static lookup
    return performance_model, engine_uid


def _open_met_rad(job: SpireWaypointsRecord, zarr_store: str) -> tuple[MetDataset, MetDataset]:
    """Open forecast zarr stores.

    Will choose the most recent useable forecast.

    Note that the first forecast step must be at least half an hour before the earliest
    waypoint to provide a buffer for differencing accumulated radiative fluxes.

    Checks that the selected forecast extends long enough into the future to
    cover the entire simulation (requires half an hour beyond latest waypoint)
    and raises an exception if it does not.

    Logic currently assumes that the zarr store will include a forecast 
    initialized every 6h (0z, 6z, 12z, 18z each day).
    """
    earliest = job.records[0].timestamp  # is jobs.records guaranteed to be sorted by time?
    forecast_time = (pd.Timestamp(earliest) - pd.Timedelta(30, "m")).floor("6h")
    forecast_path = f"{zarr_store}/{forecast_time.strftime('%Y%m%d%H')}"

    pl = xr.open_zarr(f"{forecast_path}/pl.zarr")
    met = MetDataset(pl, provider="ECMWF", dataset="HRES", product="forecast")

    breakpoint()

    variables = (v[0] if isinstance(v, tuple) else v for v in Cocip.met_variables)
    met.standardize_variables(variables)
    
    sl = xr.open_zarr(f"{forecast_path}/sl.zarr")
    rad = MetDataset(sl, provider="ECMWF", dataset="HRES", product="forecast")
    variables = (v[0] if isinstance(v, tuple) else v for v in Cocip.rad_variables)
    met.standardize_variables(variables)

    breakpoint()

    return met, rad


def _create_flight(job: SpireWaypointsRecord, engine_uid: str) -> Flight:
    """Create Flight from job waypoints.

    Aircraft and engine type are associated with the flight here.
    """
    return Flight(
        longtiude=[w.longitude for w in job.records],
        latitude=[w.latitude for w in job.records],
        altitude=[w.altitude for w in job.records],
        time=[w.time for w in job.records],
        attrs=dict(
            flight_id=job.flight_info.flight_id,
            aircraft_type=job.flight_info.aircraft_type_icao,
            engine_uid=engine_uid
        )
    )


def _create_cocip_model(met: MetDataset, rad: MetDataset, perf: AircraftPerformance) -> Cocip:
    """Create Cocip model.

    The chosen performance model is attached to the Cocip instance here.
    """
    return Cocip(
        met=met,
        rad=rad,
        aircraft_performance=perf,
        **STATIC_PARAMS
    )


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
        job: SpireWaypointsRecord = job_handler.fetch()
        if not job:
            # if the queue is empty -> we get back [], then pause before retry
            logger.info("job empty. sleeping... ")
            time.sleep(10)
            return

        logger.info(
            f"got job with {len(job.records)} records. "
            f"icao_address: {job.flight_info.icao_address}. "
            f"spanning: {job.records[0].timestamp} to {job.records[-1].timestamp}"
        )

        # ===================
        # apply CoCip Trajectory model
        # ===================

        # gs://contrails-301217-ecmwf-hres-forecast-v2-short-term
        zarr_store = env.HRES_SOURCE_PATH  # noqa:F841

        # look up performance model and engine uid to use with job's aircraft type
        # will raise an exception if aircraft type isn't supported by selected
        performance_model, engine_uid = _perf_lookup(job)
        
        # set up and run CoCiP
        met, rad = _open_met_rad(job, zarr_store)
        flight = _create_flight(job, engine_uid)
        model = _create_cocip_model(met, rad, performance_model)
        result = model.eval(flight)

        breakpoint()

        # list of len(job.records) - 2; one cocip ef [J/segment] value
        cocip_output: list[float]  # noqa:F842

        time.sleep(500)
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
