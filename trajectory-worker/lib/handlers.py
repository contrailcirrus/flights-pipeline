"""
Application handlers.
"""

import json
import threading
from concurrent import futures
from threading import Thread
from typing import Union, Callable

import numpy as np
import xarray as xr
import pandas as pd
import pycontrails
from google.cloud.pubsub_v1.types import PublishFlowControl, LimitExceededBehavior
from pycontrails import Flight, MetDataset
from pycontrails.core.aircraft_performance import AircraftPerformance
from pycontrails.models.cocip import Cocip
from pycontrails.models.humidity_scaling import (
    ExponentialBoostLatitudeCorrectionHumidityScaling,
)
from pycontrails.models.ps_model import PSFlight

from lib.log import logger, format_traceback
from lib.schemas import (
    WaypointsRecord,
)
from lib.exceptions import (
    FlightTooLowError,
    AircraftTypeUnrecognizedError,
    PerfModelUnsupportedError,
)

from google.api_core import retry
from google.cloud import pubsub_v1

import warnings


class PubSubSubscriptionHandler:
    """
    Handler for managing consumption and marshalling of jobs from a pubsub subscription queue.
    """

    # the number of seconds the subscriber client will hang, waiting for available messages
    MSG_WAIT_TIME_SEC = 60.0
    ACK_EXTENSION_SEC: int = 300

    def __init__(self, subscription: str):
        """
        Parameters
        ----------
        subscription
            The fully-qualified URI for the pubsub subscription.
            e.g. 'projects/contrails-301217/subscriptions/api-preprocessor-sub-dev'
        """
        self.subscription = subscription
        self._client = None
        self._ack_id: Union[None, str] = None
        self._kill_ack_manager = threading.Event()
        self._ack_manager = Thread(target=self._ack_management_worker, daemon=True)
        self._ack_manager.start()

    def __enter__(self):
        """
        Initialize pubsub client to be used across this class instance's lifecycle.
        """
        self._client = pubsub_v1.SubscriberClient()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ensure client connection to pubsub is closed.
        """
        self.close()

    def _ack_management_worker(self):
        """
        Extends the ack deadline for the currently outstanding message.
        """
        logger.info("starting ack lease management worker...")
        while not self._kill_ack_manager.is_set():
            self._kill_ack_manager.wait(self.ACK_EXTENSION_SEC // 2)
            if self._ack_id:
                logger.info(
                    f"extending ack deadline on ack_id: {self._ack_id[0:-150]}..."
                )
                try:
                    self._client.modify_ack_deadline(
                        request={
                            "subscription": self.subscription,
                            "ack_ids": [self._ack_id],
                            "ack_deadline_seconds": self.ACK_EXTENSION_SEC,
                        }
                    )
                except Exception:
                    logger.error(
                        f"failed to extend ack deadline for message. "
                        f"traceback: {format_traceback()}"
                    )
        logger.info("terminated ack lease management worker")

    def fetch(self) -> (WaypointsRecord, str):
        """
        Fetch a message from the subscription queue.
        This method will hang and wait until a message is available.
        This method, in case of exception, will hang, backoff and retry indefinitely.

        Returns
        -------
        str
            The dequeued message from the pubsub subscription.
        str
            The ordering key for the fetched record.
        """
        if not self._client:
            self._client = pubsub_v1.SubscriberClient()
            warnings.warn(
                "pubsub subscriber client initialized. "
                "connection will remain open until close()."
            )

        while True:
            logger.info(f"fetching message from {self.subscription}")
            resp = self._client.pull(
                request={"subscription": self.subscription, "max_messages": 1},
                retry=retry.Retry(timeout=30.0),
                timeout=self.MSG_WAIT_TIME_SEC,
            )

            if len(resp.received_messages) == 0:
                # it is possible there are no messages available,
                # or, pubsub returned zero when there are in fact some messages to fetch on retry
                logger.info("zero messages received.")
                continue
            msg = resp.received_messages[0]
            self._ack_id = msg.ack_id
            ordering_key = msg.message.ordering_key
            logger.info(
                f"received 1 message from {self.subscription}. "
                f"published_time: {msg.message.publish_time}, "
                f"message_id: {msg.message.message_id}"
            )
            return WaypointsRecord.from_utf8_json(msg.message.data), ordering_key

    def ack(self):
        """
        Acknowledge the outstanding message presently handled by the instance of this class.
        """
        if not self._ack_id:
            raise ValueError(
                "ack_id is not set. call fetch(). "
                "handler instance must be handling an outstanding message."
            )
        self._client.acknowledge(
            request={"subscription": self.subscription, "ack_ids": [self._ack_id]},
            retry=retry.Retry(timeout=30.0),
        )
        logger.info("successfully ack'ed message.")
        self._ack_id = None

    def close(self):
        """
        Close pubsub client connection.
        """
        self._ack_id = None
        self._kill_ack_manager.set()
        self._client.close()


class PubSubPublishHandler:
    def __init__(
        self,
        topic_id: str,
        ordered_queue: bool = False,
        max_message_backlog: int = 1000,
        max_mem_backlog_mb: int = 10,
    ) -> None:
        """
        Parameters
        ----------
        topic_id
            fully-qualified uri for the pubsub topic.
            e.g. `projects/contrails-301217/topics/my-topic-name-dev`
        ordered_queue
            type of queue.
            True if ordered (requires ordering key).
            False if unordered.
        max_message_backlog
            maximum number of messages backlogged for async publish.
            if number of pending messages exceeds this limit, async publish will block.
        max_mem_backlog_mb
            maximum total memory (in mb) of messages backlogged for async publish.
            if total mem exceeds this limit, async publish will block.
        """

        self._topic_id = topic_id
        self._ordered_queue = ordered_queue

        # Uses default retry policy which uses exponential backoff to manage retries.
        # The backoff is limited to [0.1, 60] seconds and increases by *1.3 on each
        # publish error. Retries are managed separately for each ordering key.
        # See: https://cloud.google.com/pubsub/docs/retry-requests
        flow_control_settings = PublishFlowControl(
            message_limit=max_message_backlog,
            byte_limit=max_mem_backlog_mb * 1024 * 1024,
            limit_exceeded_behavior=LimitExceededBehavior.BLOCK,
        )

        self._publisher = pubsub_v1.PublisherClient(
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=ordered_queue,
                flow_control=flow_control_settings,
            )
        )
        self._publish_futures: list[futures.Future] = []

    @staticmethod
    def _get_futures_callback(**kwargs) -> Callable[[futures.Future], None]:
        """
        returns a function to use as a callback.
        Constructs a log message annotating with any k-vs passed to this method.
        """

        msg = ""
        for k, v in kwargs.items():
            msg += f" {k}={v} "

        def _raise_exception_if_failed(future: futures.Future) -> None:
            """Re-raise any exceptions raised by the future's execution thread.

            This should be registered as a callback that will only be invoked when the future
            has already completed using:
                future.add_done_callback(_raise_exception_if_failed)
            """
            try:
                future.result(timeout=0)
            except Exception:
                logger.error(f"publish future failed. {msg}. {format_traceback()}")
                # TODO: raise this to our main application, and exit

        return _raise_exception_if_failed

    def publish_async(self, data: bytes, ordering_key: str = "", **metadata) -> None:
        """Add data to the current publish batch.

        Batches are pushed asynchronously to GCP PubSub in a separate thread. To wait
        for one or more publish calls until they have been received by the server, call
        wait_for_publish.

        Parameters
        ----------
        data
            byte encoded string payload
        ordering_key
            required if handler was instantiated with ordered_queue=True
            payloads sharing the same ordering_key are guaranteed to be delivered to
            consumers in the order they are published
        metadata
            any additional k-vs that contextualize the publish event.
            these will be added as context to the publisher callback,
            which includes them in any failure logs.
        """
        future: futures.Future = self._publisher.publish(
            topic=self._topic_id,
            data=data,
            ordering_key=ordering_key,
            timeout=45,
        )
        future.add_done_callback(self._get_futures_callback(**metadata))
        self._publish_futures.append(future)

    def wait_for_publish(self) -> None:
        """
        Block until all current publish batches are received by server.
        """
        futures.wait(self._publish_futures)
        self._publish_futures = []


class CocipTrajectoryHandler:
    """
    Manages the execution of the CoCip trajectory model on a flight trajectory chunk.
    """

    MET_MIN_ALTITUDE_FT = 22_664  # hard-coding allows more efficient skip-over
    PERF_MODEL_LOOKUP_FP = "lib/perf_model_aircraft_lookup_no_bada_041824.json"

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
        met_longitude_buffer=(
            10.0,
            10.0,
        ),  # default; potential perf gains fomr reducing
        met_latitude_buffer=(10.0, 10.0),  # default; potential perf gains from reducing
        met_level_buffer=(20, 20),  # reduced to same buffer used in api preprocessor
        max_age=np.timedelta64(1, "h"),
    )

    def __init__(self, job: WaypointsRecord, hres_src: str):
        """
        Parameters
        ----------
        job
            A list of flight waypoints, sampled at contiguous, 1min intervals.
        hres_src
            Fully-qualified uri for the source path the the hres zarr store.
            e.g. 'gs://contrails-301217-ecmwf-hres-forecast-v2-short-term'
        """
        self._hres_src = hres_src
        self._job = job
        self._zarr_model_run_at: str | None = None
        self._met_dataset: MetDataset | None = None
        self._rad_dataset: MetDataset | None = None

        self._verify_altitude(self._job)
        self._perf_model, self._engine_uid = self._perf_lookup(self._job)
        self._flight: pycontrails.Flight = self._create_flight(
            self._job, self._engine_uid
        )

    @classmethod
    def _verify_altitude(cls, job: WaypointsRecord):
        """
        Check if the maximum segment altitude is high enough for intersection with met data.
        """
        if max(w.altitude_baro for w in job.records) < cls.MET_MIN_ALTITUDE_FT:
            raise FlightTooLowError(
                f"no waypoints in trajectory above alt threshold "
                f"of {cls.MET_MIN_ALTITUDE_FT} feet."
            )

    @classmethod
    def _perf_lookup(cls, job: WaypointsRecord) -> tuple[AircraftPerformance, str]:
        """
        Look up performance model and engine type for a job's aircraft type.

        We provide a static, manually maintained lookup that maps one-to-one,
        between an aircraft type (icao identifier), and
        1. an aircraft performance model,
        2. an engine identifier (icao uid)

        At present, we have only implemented the PSFlight performance model.
        The BADA model may or may not be supported in the future.

        Futhermore, please note that the engine_uid is not used in running the PS perf model
        (it is for BADA). However, we still return a single, default engine_uid for aircrafts
        associated with the PS model, since the engine_uid is used in setting emission indexes
        for emissions calculations (emission calculations being separate from the perf model output)
        """

        with open(cls.PERF_MODEL_LOOKUP_FP, "r") as fp:
            lookup = json.load(fp)

        target: dict[str, str] | None = lookup.get(job.flight_info.aircraft_type_icao)

        if not target:
            raise AircraftTypeUnrecognizedError(
                f"aircraft of type {job.flight_info.aircraft_type_icao} "
                f"not in performance lookup."
            )

        engine_uid: str = target["engine_uid"]

        perf_model: AircraftPerformance
        match target["perf_model_id"]:
            case "PS":
                perf_model = PSFlight()
            case _:
                raise PerfModelUnsupportedError(
                    f"perf model lookup returned an unsupported "
                    f"perf_model_id of {target['perf_model_id']} "
                    f"for aircraft_type_icao of {job.flight_info.aircraft_type_icao}"
                )
        return perf_model, engine_uid

    @staticmethod
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

    @staticmethod
    def _nearest_zarr_store(job: WaypointsRecord) -> str:
        """
        Method for inferring the target zarr store, based on now() and the job's flight
        timestamp range.

        Guarantees that the entire flight trajectory (start_time -> end_time),
        plus requisite buffers, sit within the zarr store's forecast range.

        ---------
        Most Recently Available
        ---------
        The zarr store is generated from the ecmwf met data (by the hres-etl service).

        A given zarr store is built from a batch of ecmwf files.
        That batch _begins_ delivery approx. 6hrs after the model_run_at time.
        It can take approx. 3 hrs after batch delivery starts for delivery to end,
        and for all files to have been processed into zarr.

        Provided there are no failures in hres-etl, the earliest we should assume zarr
        availability is 6+3=9hrs after a given model_run_at.

        model_run_at is available on 6hr intervals: %H [00, 06, 12, 18]

        ---------
        Trajectory Within Zarr Store Forecast Range
        ---------

        A zarr store spans 72hours, starting at time zero (model_run_at), to model_run_at+72.

        Note that the first forecast step must be at least half an hour before the earliest
        waypoint to provide a buffer for differencing accumulated radiative fluxes.

        Checks that the selected forecast extends long enough into the future to
        cover the entire simulation (requires half an hour beyond latest waypoint + max age)
        and raises an exception if it does not.

        Parameters
        ----------
        job
            Trajectory worker job w/ list of waypoints constituting the trajectory chunk

        Returns
        -------
        The subdirectory matching the model_run_at time for the target zarr store
        i.e. `model_run_at` in 'gs://<zarr_bucket>/<model_run_at>'
        e.g. '2024041112' in 'gs://contrails-301217-ecmwf-hres-forecast-v2-short-term/2024041112'
        """

        earliest_waypoint = pd.Timestamp(job.records[0].timestamp)

        earliest_forecast = earliest_waypoint - pd.Timedelta(minutes=30)
        target_model_run_at = earliest_forecast.floor("6h")

        latest_model_run_at = (
            pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=9)
        ).floor("6h")

        if target_model_run_at > latest_model_run_at:
            # case when the job is very fresh, and we don't have the latest zarr store yet
            logger.warning(
                f"target zarr store not available ({target_model_run_at}). "
                f"fall back to latest ({latest_model_run_at}). "
                f"icao_address {job.flight_info.icao_address}, "
                f"job first waypoint {earliest_waypoint}"
            )
            target_model_run_at = latest_model_run_at

        return target_model_run_at.strftime("%Y%m%d%H")

    def load(self):
        """
        Open forecast zarr stores.

        Will choose the most recent _usable_ forecast.
        """
        self._zarr_model_run_at = self._nearest_zarr_store(self._job)
        zarr_path = f"{self._hres_src}/{self._zarr_model_run_at}"

        pl = xr.open_zarr(f"{zarr_path}/pl.zarr")
        met = MetDataset(pl, provider="ECMWF", dataset="HRES", product="forecast")
        variables = (v[0] if isinstance(v, tuple) else v for v in Cocip.met_variables)
        met.standardize_variables(variables)

        sl = xr.open_zarr(f"{zarr_path}/sl.zarr")
        rad = MetDataset(sl, provider="ECMWF", dataset="HRES", product="forecast")
        variables = (v[0] if isinstance(v, tuple) else v for v in Cocip.rad_variables)
        rad.standardize_variables(variables)

        self._met_dataset = met
        self._rad_dataset = rad

    def run(self) -> Flight:
        """
        Run the cocip trajectory model.
        """
        if not self._met_dataset or not self._rad_dataset:
            raise ValueError(
                "met dataset or rad dataset have not been loaded. Run load()."
            )

        model = Cocip(
            met=self._met_dataset,
            rad=self._rad_dataset,
            aircraft_performance=self._perf_model,
            **self.STATIC_PARAMS,
        )

        result: Flight = model.eval(self._flight)
        return result

    @property
    def zarr_uri(self):
        """
        Returns the subdirectory that houses the hres zarr data
        and uniquely identifies the store based on the model_run_at time.
        """
        return self._zarr_model_run_at
