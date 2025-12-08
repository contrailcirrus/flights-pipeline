#!/usr/bin/env python3

"""
Scripting and CLI interface for building flight trajectories from Spire raw data,
and submitting that trajectory as a "job" (WaypointsRecord) to the trajectory worker queue.
"""

import os
from pycontrails.datalib.spire import ValidateTrajectoryHandler

os.environ["TWJD_SUBSCRIPTION_ID"] = "foobar"
os.environ[
    "TRAJECTORY_CHUNK_TOPIC_ID"
] = "projects/contrails-301217/topics/prod-fp-gaia-trajectory-chunk"
os.environ["LOG_LEVEL"] = "INFO"

from lib.handlers import (  # noqa:E402
    BigQueryHandler,
    HealTrajectoryHandler,
    ResampleHandler,
    PubSubPublishHandler,
    CloudStorageHandler,
)
from lib.schemas import TrajectoryWorkerJobDescriptor  # noqa:E402
import argparse  # noqa:E402
from lib.services import TrajectoryBuilderSvc  # noqa:E402
import lib.environment as env  # noqa:E402


class TrajectoryBuilderSvcWrapper:
    """
    Wrapper class to conform to argparse interface spec.
    Wraps the TrajectoryBuilderSvc, passing thru an argparse.Namespace input.
    """

    def __init__(self, input: argparse.Namespace):
        self._twjd = TrajectoryWorkerJobDescriptor(
            day=input.day,
            met_source=input.met_data_src,
            telemetry_source=input.telemetry_src,
            full_traj=input.full_traj,
            airline_iata=input.airline,
            flight_id=input.flight_id,
            icao_address=input.icao_address,
            dry_run=input.dryrun,
            export_waypoints=input.export_waypoints,
        )

    def run(self):
        """
        CLI entrypoint. Wraps TrajectoryWorkerBuilderSvc().run()
        """

        # this field is missing when pulling data from the Spire parquet file cache
        validation_traj_handler = ValidateTrajectoryHandler()
        validation_traj_handler.SCHEMA.pop("ingestion_time")

        svc = TrajectoryBuilderSvc(
            cache_handler=None,
            bq_handler=BigQueryHandler(),
            gcs_handler=CloudStorageHandler(),
            validate_traj_handler=validation_traj_handler,
            heal_traj_handler=HealTrajectoryHandler(),
            resample_handler=ResampleHandler(),
            job_out_handler=PubSubPublishHandler(
                topic_id=env.TRAJECTORY_CHUNK_TOPIC_ID,
                ordered_queue=False,
            ),
        )
        print(f"🚀 Running flights for: {self._twjd}")
        svc.run(twjd=self._twjd)
        print(f"finished flights for: {self._twjd}")


parser = argparse.ArgumentParser(prog="twjf-cli")
subparser = parser.add_subparsers()

flights_parser = subparser.add_parser("flights")
flights_subparser = flights_parser.add_subparsers()
flights_submit_parser = flights_subparser.add_parser("submit")

flights_submit_parser.add_argument(
    "-a",
    "--airline",
    required=False,
    help="airline IATA code",
    dest="airline",
)
flights_submit_parser.add_argument(
    "-d",
    "--day",
    required=False,
    help='calendar day (UTC) for fetching flights. Format "%Y-%m-%d". e.g. "2024-01-12"',
    dest="day",
)
flights_submit_parser.add_argument(
    "-i",
    "--flight-id",
    required=False,
    help="flight_id for target flight to submit",
    dest="flight_id",
)
flights_submit_parser.add_argument(
    "-c",
    "--icao-address",
    required=False,
    help="icao_address for target flight to submit",
    dest="icao_address",
)
flights_submit_parser.add_argument(
    "-s",
    "--met-data-src",
    required=True,
    help="met data source for running model. One of: 'hres', 'era5'",
    dest="met_data_src",
)
flights_submit_parser.add_argument(
    "-w",
    "--telemetry-src",
    default="bq",
    help="data source to use for ads-b telemetry data. Defaults to BigQuery. One of: 'bq', 'gcs'",
    dest="telemetry_src",
)
flights_submit_parser.add_argument(
    "-e",
    "--export-waypoints",
    action="store_true",
    help="exports (to file) resampled trajectory waypoints",
    dest="export_waypoints",
)
flights_submit_parser.add_argument(
    "-t",
    "--full-traj",
    action="store_true",
    help="write the per-segment values to BQ",
    dest="full_traj",
)
flights_submit_parser.add_argument(
    "-r",
    "--dry-run",
    action="store_true",
    help="fetches records and build trajectory, but does not submit for processing",
    dest="dryrun",
)
flights_submit_parser.set_defaults(func=TrajectoryBuilderSvcWrapper)

if __name__ == "__main__":
    args = parser.parse_args()
    svc = args.func(args)
    svc.run()
