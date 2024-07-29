"""
main_cron.py

Application entrypoint for cronjob automation of flight submission.

Invocation of this entrypoint effectively calls `gaia_cli.py flights submit -a <A> -d <D>
for a list of target airlines: `A`, for two days prior from now: `d`.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, UTC, timedelta

from log import logger
from services import FlightsSubmitSvc
from argparse import Namespace
import environment as env

# we overwrite the class variable of FlightSubmitSvc here...
# we'd prefer to inject it when instantiating,
# but we do it this way to maintain conformity with the class obj as expected
# by argsparse in the CLI implementation

if not env.TRAJECTORY_WORKER_TOPIC:
    raise ValueError("TRAJECTORY_WORKER_TOPIC must be set in env vars.")
FlightsSubmitSvc.TRAJECTORY_WORKER_TOPIC = env.TRAJECTORY_WORKER_TOPIC


@dataclass
class Input:
    day: str  # date string e.g. `2023-01-01`
    airline: str | None = None  # airline iata
    flight_id: str | None = None
    icao_address: str | None = None
    dryrun: bool = False
    verbose: bool = False
    export_waypoints: bool = False


AIRLINE_IATAS = ["KL", "BY", "HV", "AA"]

if __name__ == "__main__":
    now = datetime.now(tz=UTC)
    now_less_two_days = now - timedelta(days=2)
    target_dtstr = now_less_two_days.strftime("%Y-%m-%d")

    for airline_iata in AIRLINE_IATAS:
        logger.info(f"submitting flights for {airline_iata} on {target_dtstr}")
        args = Input(
            day=target_dtstr,
            airline=airline_iata,
        )
        svc = FlightsSubmitSvc(Namespace(**asdict(args)))
        svc.run()
