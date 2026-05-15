from abc import ABC, abstractmethod
import argparse
from datetime import datetime, timedelta
from typing import Union

import pendulum

from handlers import (
    PubSubSubscriptionHandler,
    PubSubPublishHandler,
)

from schemas import (
    WaypointsRecord,
    MetSource,
    TrajectoryWorkerJobDescriptor,
    TelemetrySource,
)
from log import logger


class BaseSvc(ABC):
    @abstractmethod
    def run(self) -> Union[dict, None]:
        """
        Entrypoint for running the service.
        Expected to return nothing, or, a dict that can be json serialized and printed.
        """


class JobWorkerSubmitSvc(BaseSvc):
    """
    Service backing calls to the flights submit parser.
    """

    TWJD_TOPIC_ID = "projects/contrails-301217/topics/dev-fp-twjd-ingress"

    def __init__(self, input: argparse.Namespace):
        """
        Parameters
        ----------
        input
            namespace object returned from the parser.
            expected to contain members:
            - airline
            - day; can be single day, or date range inclusive
            - flight_id
            - met_data_src
            - telemetry_src
            - full_traj
            - dry_run
        """
        self._airline = input.airline
        self._day = input.day
        self._flight_id: list[str] | None = input.flight_id if input.flight_id else None
        self._met_data_src = input.met_data_src
        self._telemetry_src = input.telemetry_src
        self._full_traj = input.full_traj
        self._dry_run = input.dry_run
        self._publish_handler = PubSubPublishHandler(
            self.TWJD_TOPIC_ID,
            ordered_queue=False,
        )

        # caller must provide ONE OF the following sets of flags
        valid_flag_combos = {
            (self._day, self._airline, self._met_data_src),
            (self._day, self._flight_id, self._met_data_src),
        }
        is_valid = sum([all(itm) for itm in valid_flag_combos]) == 1

        if not is_valid:
            raise ValueError(
                "Must provide flags: "
                "(1) --flight-id & --day & --met-data-src OR "
                "(2) --airline & --day & --met-data-src OR "
            )

        if self._met_data_src not in MetSource:
            raise ValueError(
                f"--met-data-src must be one of {[i.value for i in MetSource]}"
            )

        if self._flight_id and len(self._flight_id) > 0 and "_" in self._day:
            raise ValueError(
                f"cannot specify a date range ({self._day}) with flight ids. "
                f"all flight ids must fall (start time UTC) on same day."
            )

    def run(self):
        if self._day and self._airline:
            logger.info(
                f"🛠️submitting TWJDs for ✈️ {self._airline} using met data source 📊{self._met_data_src}"
            )
        elif self._day and self._flight_id:
            logger.info(
                f"🛠️submitting TWJDs with 🛂 flight_id: {self._flight_id} using met data source 📊{self._met_data_src}"
            )
        else:
            raise NotImplementedError("unhandled runtime case.")

        if "_" in self._day:
            start_day = self._day.split("_")[0]
            end_day = self._day.split("_")[-1]
            logger.info(
                f"found date range. submitting records from {start_day} to {end_day}"
            )
            dt_rg = pendulum.interval(
                pendulum.parse(start_day), pendulum.parse(end_day)
            )
            dt_rg_strs = [dt.strftime("%Y-%m-%d") for dt in dt_rg.range("days")]
        else:
            dt_rg_strs = [self._day]

        # submit twjds for dates in date range
        for dt_str in dt_rg_strs:
            # logger.info(f"🛠️TWJD created for 🗓️day: {dt_str}")
            twjd = TrajectoryWorkerJobDescriptor(
                day=dt_str,
                met_source=MetSource(self._met_data_src),
                telemetry_source=TelemetrySource(self._telemetry_src),
                full_traj=self._full_traj,
                airline_iata=self._airline,
                flight_id=self._flight_id,
                dry_run=self._dry_run,
                export_waypoints=False,
            )

            self._publish_handler.publish_async(
                twjd.as_utf8_json(),
                timeout_seconds=10,
            )

        logger.info("⏲️ waiting for publish to finish...")
        self._publish_handler.wait_for_publish(timeout_seconds=300)
        logger.info("🙌 DONE!")


class FlightsReinjectSvc(BaseSvc):
    """
    Service for extracting dead-lettered jobs, and re-injecting them into the worker queue.
    """

    WORKER_JOB_DEAD_LETTER_SUBSCRIPTION = "projects/contrails-301217/subscriptions/prod-fp-trajectory-gaia-chunk-ingress-dead-letter"
    DEAD_LETTER_ACK_DEADLINE_SEC = 60  # reference subscriber settings
    TRAJECTORY_WORKER_TOPIC = (
        "projects/contrails-301217/topics/prod-fp-gaia-trajectory-chunk"
    )

    def __init__(self, input: argparse.Namespace):
        """
        Parameters
        ----------
        input
            namespace object returned from the parser.
            expected to contain members:
            - airline
            - day
            - dryrun
            - verbose
        """
        self._count: str = input.count
        self._verbose = input.verbose
        self._dryrun = input.dryrun
        self._subscriber_handler = PubSubSubscriptionHandler(
            self.WORKER_JOB_DEAD_LETTER_SUBSCRIPTION,
        )
        self._publish_handler = PubSubPublishHandler(
            self.TRAJECTORY_WORKER_TOPIC,
            ordered_queue=True,
        )

    def run(self):
        """
        Pulls messages from the dead-letter subscription,
        and dispatches jobs back to the worker queue
        based on the flight_id of the dead-lettered job.
        """
        messages = self._subscriber_handler.fetch(int(self._count))
        start_time = datetime.now()
        logger.info(f"📜 fetched {len(messages)} messages from dead-letter queue.")
        msg: PubSubSubscriptionHandler.Message
        for msg in messages:
            record = WaypointsRecord.from_utf8_json(msg.data)
            logger.info(
                f"💦 re-injecting job for flight_id: {record.flight_info.flight_id}"
                f" with {len(record.records)} "
                f"waypoints from {record.flight_info.airline_iata} "
                f"with start on: {record.records[0].timestamp}"
            )
            if not self._dryrun:
                self._publish_handler.publish_async(
                    msg.data,
                    timeout_seconds=45,
                    ordering_key=msg.ordering_key,
                )
        if self._dryrun:
            logger.info("🌵dry run... exiting before submission")
            return

        logger.info("⏲️ waiting for publish to finish...")
        self._publish_handler.wait_for_publish(timeout_seconds=300)
        for msg in messages:
            self._subscriber_handler.ack(msg)
        if (datetime.now() - start_time) > timedelta(
            seconds=self.DEAD_LETTER_ACK_DEADLINE_SEC
        ):
            logger.warning(
                f"pull to ack period exceeded {self.DEAD_LETTER_ACK_DEADLINE_SEC} seconds."
            )
        logger.info("🙌 DONE!")
