#!/usr/bin/env python3

"""
Scripting and CLI interface for building flight trajectories from Spire raw data,
submitting those trajectories for CoCip processing,
and aggregating the resulting values into a report.
"""

import argparse
from services import FlightsSubmitSvc, FlightsReportFetchSvc, FlightsReinjectSvc


parser = argparse.ArgumentParser(prog="gaia")
subparser = parser.add_subparsers()

# --------------
# FLIGHTS parser
# --------------
flights_parser = subparser.add_parser("flights")
flights_subparser = flights_parser.add_subparsers()
flights_submit_parser = flights_subparser.add_parser("submit")

# must provide either airline & day, or flight_id
# we enforce these required combinations of flags in our svc code, not here
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
    "--flight_id",
    required=False,
    help="flight_id for target flight to submit",
    dest="flight_id",
)
flights_submit_parser.add_argument(
    "-c",
    "--icao_address",
    required=False,
    help="icao_address for target flight to submit",
    dest="icao_address",
)
flights_submit_parser.add_argument(
    "-e",
    "--export-waypoints",
    action="store_true",
    help="exports (to file) resampled trajectory waypoints",
    dest="export_waypoints",
)
flights_submit_parser.add_argument(
    "-r",
    "--dry-run",
    action="store_true",
    help="fetches records and build trajectory, but does not submit for processing",
    dest="dryrun",
)
flights_submit_parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="verbose printout",
    dest="verbose",
)
flights_submit_parser.set_defaults(func=FlightsSubmitSvc)

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

# --------------
# REPORT parser
# --------------
flights_parser = subparser.add_parser("report")
flights_subparser = flights_parser.add_subparsers()

flights_submit_parser = flights_subparser.add_parser("fetch")
flights_submit_parser.add_argument(
    "-a",
    "--airline",
    required=True,
    help="airline IATA code",
    dest="airline",
)
flights_submit_parser.add_argument(
    "-d",
    "--day",
    required=True,
    help="calendar day (UTC) or date-range (inclusive) for fetching report. "
    "e.g. `2024-01-01` or `2024-01-01_2024-01-10`",
    dest="day",
)
flights_submit_parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="verbose printout",
    dest="verbose",
)
flights_submit_parser.add_argument(
    "-g",
    "--goog_fp",
    help="file path to google dataset",
    dest="goog_fp",
)
flights_submit_parser.set_defaults(func=FlightsReportFetchSvc)


if __name__ == "__main__":
    args = parser.parse_args()
    svc = args.func(args)
    svc.run()
