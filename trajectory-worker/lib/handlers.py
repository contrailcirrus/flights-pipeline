"""
Application handlers.
"""

import concurrent.futures
import json
import os
import threading
import warnings
from threading import Thread
from typing import Any, Callable, Union

import numpy as np
import pandas as pd
import pycontrails
import xarray as xr
from google.api_core import retry
from google.cloud import pubsub_v1  # type: ignore
from pycontrails import Flight, MetDataset
from pycontrails.core.aircraft_performance import AircraftPerformance
from pycontrails.models.cocip import Cocip
from pycontrails.models.humidity_scaling import (
    ExponentialBoostLatitudeCorrectionHumidityScaling,
)
from pycontrails.models.ps_model import PSFlight

from lib.exceptions import (
    AircraftTypeUnrecognizedError,
    FlightTooLowError,
    PerfModelUnsupportedError,
)
from lib.log import format_traceback, logger
from lib.schemas import WaypointsRecord


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

    def fetch(self) -> tuple[WaypointsRecord, str]:
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
        if self._ack_id is not None:
            raise RuntimeError("fetch called multiple times without acking message")

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
    def __init__(self, topic_id: str, ordered_queue: bool) -> None:
        self._topic_id = topic_id

        self._publisher = pubsub_v1.PublisherClient(
            # Batch settings increase payload size to execute fewer, larger requests.
            # See: https://cloud.google.com/pubsub/docs/batch-messaging
            batch_settings=pubsub_v1.types.BatchSettings(
                max_messages=1000,
                max_bytes=20 * 1000 * 1000,  # 20 MB max server-side request size
                max_latency=0.1,  # default: 10 ms
            ),
            publisher_options=pubsub_v1.types.PublisherOptions(
                enable_message_ordering=ordered_queue,
                # Flow control applies rate limits by blocking any time the staged data
                # exceeds the following settings. Once the records are received by GCP
                # PubSub, additional publish calls are unblocked.
                # See: https://cloud.google.com/pubsub/docs/flow-control-messages
                flow_control=pubsub_v1.types.PublishFlowControl(
                    message_limit=100 * 1000,
                    byte_limit=1024 * 1024 * 1024,  # 1 GiB
                    limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
                ),
                retry=retry.Retry(
                    initial=0.1,  # default: 0.1
                    maximum=10,  # default: 60
                    multiplier=1.3,  # default: 1.3
                ),
            ),
        )

        self._publish_futures: list[concurrent.futures.Future] = []

    def publish_async(
        self,
        data: bytes,
        timeout_seconds: float,
        ordering_key: str = "",
        log_context: dict[str, Any] | None = None,
    ) -> None:
        """Add data to the current publish batch.

        Batches are pushed asynchronously to GCP PubSub in a separate thread. To wait
        for one or more publish calls until they have been received by the server, call
        wait_for_publish.

        Parameters
        ----------
        data
            byte encoded string payload
        ordering_key
            payloads sharing the same ordering_key are guaranteed to be delivered to
            consumers in the order they are published. the publisher client,
            and the subscription bound to the receiving topic,
            must be configured to use ordered messages.
        timeout_seconds
            timeout applied to each gRPC call to the PubSub API
        metadata
            any additional k-vs that contextualize the publish event.
            these will be added as context to the publisher callback,
            which includes them in any failure logs.
        """
        future: concurrent.futures.Future = self._publisher.publish(
            topic=self._topic_id,
            data=data,
            ordering_key=ordering_key,
            timeout=timeout_seconds,
        )

        done_callback = self._done_callback_factory(log_context)
        future.add_done_callback(done_callback)
        self._publish_futures.append(future)

    def wait_for_publish(self, timeout_seconds: float | None = None) -> None:
        """Block until all current publish batches are received by server.

        Parameters
        ----------
        timeout_seconds
            Duration to wait for all publish jobs to complete. If timeout_seconds is
            exceeded, the process will be force exited with os._exit(1).
        """
        _, not_done = concurrent.futures.wait(
            self._publish_futures,
            timeout=timeout_seconds,
        )

        # Exit if any publish futures have not completed before configured timeout.
        #
        # We cannot raise an exception or invoke sys.exit from the parent while child
        # threads are still running, because cpython configures a shutdown handler to
        # wait for spawned threads to complete before exiting:
        # https://github.com/python/cpython/blob/8f25cc992021d6ffc62bb110545b97a92f7cb295/Lib/concurrent/futures/thread.py#L18-L37
        #
        # Errors in child threads trigger a separate exit using a future done_callback.
        if not_done:
            logger.error("Futures did not complete before timeout: %s", not_done)
            os._exit(1)

        # All futures completed without error, reset pending futures state.
        self._publish_futures = []

    @staticmethod
    def _done_callback_factory(
        log_context: dict[str, Any] | None,
    ) -> Callable[[concurrent.futures.Future], None]:
        """
        returns a function to use as a callback.
        Constructs a log message annotating with any k-vs passed to this method.
        """
        msg = ""
        if log_context:
            for k, v in log_context.items():
                msg += f" {k}={v} "

        def _exit_on_error(future: concurrent.futures.Future) -> None:
            """Re-raise any exceptions raised by the future's execution thread.

            This should be registered as a callback that will only be invoked when the future
            has already completed using:
                future.add_done_callback(_raise_exception_if_failed)
            """
            try:
                future.result(timeout=0)
            except Exception:
                logger.error(
                    f"Publish future failed: {msg}. Unhandled exception:"
                    + format_traceback()
                )
                os._exit(1)

        return _exit_on_error


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
        max_age=np.timedelta64(12, "h"),
    )

    def __init__(self, job: WaypointsRecord, hres_src: str):
        """
        Parameters
        ----------
        job
            A list of flight waypoints, sampled at contiguous, 1min intervals.
        hres_src
            Fully-qualified uri for the source path the hres zarr store.
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
