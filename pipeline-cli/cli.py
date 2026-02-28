#!/usr/bin/env python3

"""
Scripting and CLI interface for building flight trajectories from Spire raw data,
submitting those trajectories for CoCip processing,
and aggregating the resulting values into a report.
"""

import argparse
from services import JobWorkerSubmitSvc, FlightsReinjectSvc

parser = argparse.ArgumentParser(prog="fer-cli")
subparser = parser.add_subparsers()

# --------------
# JOBWORKER SUBMIT parser
# --------------
jobworker_parser = subparser.add_parser("jobworker")
jobworker_subparser = jobworker_parser.add_subparsers()
jobworker_submit_parser = jobworker_subparser.add_parser("submit")

jobworker_submit_parser.add_argument(
    "-a",
    "--airline",
    required=False,
    help="airline IATA code",
    dest="airline",
)
jobworker_submit_parser.add_argument(
    "-d",
    "--day",
    required=False,
    help='calendar day (UTC) for fetching flights. Format "%Y-%m-%d". e.g. "2024-01-12"',
    dest="day",
)
jobworker_submit_parser.add_argument(
    "-i",
    "--flight-id",
    required=False,
    help="flight_id for target flight to submit",
    dest="flight_id",
)
jobworker_submit_parser.add_argument(
    "-c",
    "--icao-address",
    required=False,
    help="icao_address for target flight to submit",
    dest="icao_address",
)
jobworker_submit_parser.add_argument(
    "-s",
    "--met-data-src",
    required=True,
    help="met data source for running model. One of: 'hres', 'era5'",
    dest="met_data_src",
)
jobworker_submit_parser.add_argument(
    "-w",
    "--telemetry-src",
    default="bq",
    help="data source to use for ads-b telemetry data. Defaults to BigQuery. One of: 'bq', 'gcs'",
    dest="telemetry_src",
)
jobworker_submit_parser.add_argument(
    "-t",
    "--full-traj",
    action="store_true",
    help="write the per-segment values to BQ",
    dest="full_traj",
)
jobworker_submit_parser.add_argument(
    "-r",
    "--dry_run",
    action="store_true",
    help="run trajectory worker in dry-run mode",
    dest="dry_run",
)
jobworker_submit_parser.set_defaults(func=JobWorkerSubmitSvc)

# --------------
# FLIGHTS REINJECT parser
# --------------
flights_parser = subparser.add_parser("flights")
flights_subparser = flights_parser.add_subparsers()
flights_reinject_parser = flights_subparser.add_parser("reinject")
flights_reinject_parser.add_argument(
    "-c",
    "--count",
    required=False,
    help="max message count to re-inject into trajectory worker queue. Default: 1",
    dest="count",
)
flights_reinject_parser.add_argument(
    "-r",
    "--dry-run",
    action="store_true",
    help="fetches records and build trajectory, but does not submit for processing",
    dest="dryrun",
)
flights_reinject_parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="verbose printout",
    dest="verbose",
)
flights_reinject_parser.set_defaults(func=FlightsReinjectSvc)


if __name__ == "__main__":
    args = parser.parse_args()
    svc = args.func(args)
    svc.run()
