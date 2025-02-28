"""
main_cron.py

Application entrypoint for cronjob automation of flight submission.

Invocation of this entrypoint effectively calls `cli.py flights submit -a <A> -d <D>
for a list of target airlines: `A`, for two days prior from now: `d`.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, UTC, timedelta
import sys

from log import logger, format_traceback
from services import JobWorkerSubmitSvc
from argparse import Namespace
import environment as env

# we overwrite the class variable of FlightSubmitSvc here...
# we'd prefer to inject it when instantiating,
# but we do it this way to maintain conformity with the class obj as expected
# by argsparse in the CLI implementation

if not env.TWJD_TOPIC_ID:
    raise ValueError("TWJD_TOPIC_ID must be set in env vars.")
JobWorkerSubmitSvc.TWJD_TOPIC_ID = env.TWJD_TOPIC_ID


@dataclass
class Input:
    day: str  # date string e.g. `2023-01-01`
    airline: str | None = None  # airline iata
    flight_id: str | None = None
    icao_address: str | None = None
    met_data_src: str | None = None
    full_traj: bool = False
    dry_run: bool = False


DAILY_TARGETS = [
    {"airline": "FR"},
    {"airline": "CZ"},
    {"airline": "MU"},
    {"airline": "CA"},
    {"airline": "TK"},
    {"airline": "QR"},
    {"airline": "6E"},
    {"airline": "EK"},
    {"airline": "OO"},
    {"airline": "LH"},
    {"airline": "B6"},
    {"airline": "AC"},
    {"airline": "SQ"},
    {"airline": "1L"},
    {"airline": "FX"},
    {"airline": "QF"},
    {"airline": "5X"},
    {"airline": "NK"},
    {"airline": "NH"},
    {"airline": "KE"},
    {"airline": "CX"},
    {"airline": "U2"},
    {"airline": "HU"},
    {"airline": "F9"},
    {"airline": "JJ"},
    {"airline": "JL"},
    {"airline": "ZH"},
    {"airline": "YX"},
    {"airline": "KL"},
    {"airline": "BY"},
    {"airline": "HV"},
    {"airline": "AA"},
    {"airline": "UA"},
    {"airline": "DL"},
    {"airline": "VS"},
    {"airline": "WN"},
    {"airline": "AS"},
    {"airline": "LX"},
    {"airline": "BA"},
    {"airline": "AF"},
    {"airline": "D0"},
    {"icao_address": "3C6565"},  # iagos tail_number: "D-AIKE"
    {"icao_address": "780192"},  # iagos tail_number: "B-HLR"
    {"icao_address": "8991BD"},  # iagos tail_number: "B-18316"
    {"icao_address": "8991BE"},  # iagos tail_number: "B-18317"
    {"icao_address": "A46AD6"},  # iagos tail_number: "N384HA"
    {"icao_address": "39644E"},  # iagos tail_number: "F-GZCO"
    {"icao_address": "3C64F4"},  # iagos tail_number: "D-AIGT"
    {"icao_address": "3455C1"},  # iagos tail_number: "EC-MSY"
    {"icao_address": "C04FBB"},  # iagos tail_number: "C-GEFA"
    {"icao_address": "3C656F"},  # iagos tail_number: "D-AIKO"
]


if __name__ == "__main__":
    try:
        now = datetime.now(tz=UTC)
        now_less_two_days = now - timedelta(days=2)
        target_dtstr = now_less_two_days.strftime("%Y-%m-%d")
        for target_kwarg in DAILY_TARGETS:
            logger.info(f"submitting flights for {target_kwarg} on {target_dtstr}")
            args = Input(day=target_dtstr, met_data_src="hres", **target_kwarg)
            svc = JobWorkerSubmitSvc(Namespace(**asdict(args)))
            svc.run()
    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)
