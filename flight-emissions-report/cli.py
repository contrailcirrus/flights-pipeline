#!/usr/bin/env python3

"""
Scripting and CLI interface for building flight trajectories from Spire raw data,
submitting those trajectories for CoCip processing,
and aggregating the resulting values into a report.
"""

import argparse
from services import JobWorkerSubmitSvc, FlightsReportFetchSvc, FlightsReinjectSvc


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

# --------------
# REPORT FETCH parser
# --------------
report_parser = subparser.add_parser("report")
report_subparser = report_parser.add_subparsers()
report_fetch_parser = report_subparser.add_parser("fetch")
report_fetch_parser.add_argument(
    "-a",
    "--airline",
    required=True,
    help="airline IATA code",
    dest="airline",
)
report_fetch_parser.add_argument(
    "-d",
    "--day",
    required=True,
    help="calendar day (UTC) or date-range (inclusive) for fetching report. "
    "e.g. `2024-01-01` or `2024-01-01_2024-01-10`",
    dest="day",
)
report_fetch_parser.add_argument(
    "-s",
    "--met-data-src",
    required=True,
    help="met data source used in rendering model outputs. One of: 'hres', 'era5'",
    dest="met_data_src",
)
report_fetch_parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="verbose printout",
    dest="verbose",
)
report_fetch_parser.add_argument(
    "-r",
    "--dry-run",
    action="store_true",
    help="fetches records and applies data manipulations. does not write content to file.",
    dest="dryrun",
)
report_fetch_parser.add_argument(
    "-g",
    "--goog-fp",
    help="file path to google dataset",
    dest="goog_fp",
)
report_fetch_parser.add_argument(
    "-c",
    "--case-study-fids",
    help="comma delimited set of flight ids for full-trajectory analysis",
    dest="case_study_fids",
)

report_fetch_parser.set_defaults(func=FlightsReportFetchSvc)


if __name__ == "__main__":
    args = parser.parse_args()
    svc = args.func(args)
    svc.run()
