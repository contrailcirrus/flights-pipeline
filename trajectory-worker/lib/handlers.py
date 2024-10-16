"""
Application handlers.
"""

import concurrent.futures
import json
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable

import google.api_core.exceptions
import google.api_core.retry
import numpy as np
import pandas as pd  # type: ignore
import pycontrails
import xarray as xr
from google.cloud import pubsub_v1  # type: ignore
from pycontrails import Flight, MetDataset
from pycontrails.core.aircraft_performance import AircraftPerformance
from pycontrails.models.cocip import Cocip
from pycontrails.models.humidity_scaling import (
    ExponentialBoostLatitudeCorrectionHumidityScaling,
)
from pycontrails.models.ps_model import PSFlight
from pycontrails_bada.bada_model import BADAFlight

from lib.exceptions import (
    AircraftTypeUnrecognizedError,
    FlightTooLowError,
    PerfModelUnsupportedError,
)
from lib.log import format_traceback, logger
from lib.schemas import WaypointsRecord
import lib.environment as env


@dataclass(frozen=True)
class Message:
    data: bytes
    ack_id: str
    ordering_key: str


class PubSubSubscriptionHandler:
    """
    Handler for managing consumption and marshalling of jobs from a pubsub subscription queue.
    """

    def __init__(
        self,
        subscription: str,
        ack_extension_sec: float = 30,
        pull_timeout_sec: float = 60.0,
    ):
        """
        Parameters
        ----------
        subscription
            The fully-qualified URI for the pubsub subscription.
            e.g. 'projects/contrails-301217/subscriptions/api-preprocessor-sub-dev'
        ack_extension_sec
            Seconds the lease management thread will periodically extend the ack
            deadline for outstanding messages.
        pull_timeout_sec
            Seconds the subscriber client will block for messages before retrying.
        """
        self.subscription = subscription
        self.pull_timeout_sec = pull_timeout_sec
        self.ack_extension_sec = ack_extension_sec

        self._client = pubsub_v1.SubscriberClient()

        self._outstanding_messages: set[Message] = set()

    def _fetch(self) -> Message:
        """Fetch a message from the subscription queue.

        This method will hang and wait until a message is available. If an exception is
        raised, it will retry indefinitely.

        Returns
        -------
        Message
            The dequeued message from the pubsub subscription.
        """
        while True:
            logger.info(f"fetching message from {self.subscription}")

            resp = self._client.pull(
                request={"subscription": self.subscription, "max_messages": 1},
                timeout=self.pull_timeout_sec,  # default: 60
                retry=google.api_core.retry.Retry(
                    initial=0.1,  # default: 0.1
                    maximum=60.0,  # default: 60
                    multiplier=1.3,  # default: 1.3
                    predicate=google.api_core.retry.if_exception_type(
                        # Non-default exceptions:
                        google.api_core.exceptions.DeadlineExceeded,
                        # Default exceptions:
                        google.api_core.exceptions.Aborted,
                        google.api_core.exceptions.InternalServerError,
                        google.api_core.exceptions.ServiceUnavailable,
                        google.api_core.exceptions.Unknown,
                    ),
                    deadline=60.0,  # default: 60
                ),
            )

            if len(resp.received_messages) == 0:
                # it is possible there are no messages available,
                # or, pubsub returned zero when there are in fact some messages
                logger.info("zero messages received.")
                continue

            pubsub_msg = resp.received_messages[0]
            logger.info(
                f"received 1 message from {self.subscription}. "
                f"published_time: {pubsub_msg.message.publish_time}, "
                f"message_id: {pubsub_msg.message.message_id}"
            )

            message = Message(
                data=pubsub_msg.message.data,
                ack_id=pubsub_msg.ack_id,
                ordering_key=pubsub_msg.message.ordering_key,
            )
            return message

    def subscribe(self) -> Iterator[Message]:
        """Yields messages from the subscription.

        This method returns an iterator to loop over messages in the subscription. While
        iterating over the result, a sidecar thread will periodically extend the ack
        deadlines associated with outstanding messages to avoid redelivery while work
        is in progress.
        """
        # Start lease manager thread to periodically extend ack deadline.
        exit_when_set = threading.Event()
        lease_manager = threading.Thread(
            target=self._ack_management_worker,
            kwargs=dict(exit_when_set=exit_when_set),
            daemon=True,
        )
        lease_manager.start()

        try:
            while True:
                message = self._fetch()
                self._outstanding_messages.add(message)
                yield message
                # Guard against user failing to call ack() or nack()
                if message in self._outstanding_messages:
                    logger.warning(f"Message was never ack'ed or nack'ed: {message}")
                    self._outstanding_messages.discard(message)
        except GeneratorExit:
            pass

        # Signal lease manager thread exit
        exit_when_set.set()
        # Block until lease manager thread exits
        lease_manager.join()

    def ack(self, message: Message):
        """Acknowledge the message to remove from the queue."""
        # Stop extending lease before server-side ack. This avoids cases where the lease
        # management worker fails to extend the ack deadline for an already ack'ed
        # message, at the cost of a small probability of redelivery.
        try:
            self._outstanding_messages.remove(message)
        except KeyError:
            logger.warning(f"Message ack'ed or nack'ed multiple times: {message}")

        self._client.acknowledge(
            request={"subscription": self.subscription, "ack_ids": [message.ack_id]},
            timeout=30.0,  # default: 60
            retry=google.api_core.retry.Retry(
                initial=0.1,  # default: 0.1
                maximum=60.0,  # default: 60
                multiplier=1.3,  # default: 1.3
                predicate=google.api_core.retry.if_exception_type(
                    # Non-default exceptions:
                    google.api_core.exceptions.DeadlineExceeded,
                    # Default exceptions:
                    google.api_core.exceptions.ServiceUnavailable,
                ),
            ),
        )
        logger.info("successfully ack'ed message.")

    def nack(self, message: Message):
        """Not-acknowledge the message to stop extending ack deadline.

        Does not nack the message server-side, so the message will be retried based on
        the server-side redelivery configuration rather than immediately redelivered to
        another worker.
        """
        try:
            self._outstanding_messages.remove(message)
        except KeyError:
            logger.warning(f"Message ack'ed or nack'ed multiple times: {message}")

    def _ack_management_worker(self, exit_when_set: threading.Event):
        """
        Extends the ack deadline for the currently outstanding message.
        """
        logger.info("starting ack lease management worker...")
        while True:
            should_exit = exit_when_set.wait(self.ack_extension_sec / 2)
            if should_exit:
                break

            # Avoid iterating over a mutable set.
            messages = self._outstanding_messages.copy()
            for message in messages:
                ack_id = message.ack_id
                logger.info(f"extending ack deadline on ack_id: {ack_id[0:-150]}...")
                try:
                    self._client.modify_ack_deadline(
                        request={
                            "subscription": self.subscription,
                            "ack_ids": [ack_id],
                            "ack_deadline_seconds": self.ack_extension_sec,
                        }
                    )
                except Exception:
                    logger.warning(
                        "failed to extend ack deadline for message. "
                        f"traceback: {format_traceback()}"
                    )

        logger.info("terminated ack lease management worker")


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
                    message_limit=1000,
                    byte_limit=1024 * 1024 * 1024,  # 1 GiB
                    limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
                ),
                # Retry defaults depend on gRPC method, see default for publish here:
                # https://github.com/googleapis/python-pubsub/blob/ff229a5fdd4deaff0ac97c74f313d04b62720ff7/google/pubsub_v1/services/publisher/transports/base.py#L164-L183
                retry=google.api_core.retry.Retry(
                    initial=0.1,
                    maximum=10,
                    multiplier=2,
                    predicate=google.api_core.retry.if_exception_type(
                        google.api_core.exceptions.Aborted,
                        google.api_core.exceptions.Cancelled,
                        google.api_core.exceptions.DeadlineExceeded,
                        google.api_core.exceptions.InternalServerError,
                        google.api_core.exceptions.ResourceExhausted,
                        google.api_core.exceptions.ServiceUnavailable,
                        google.api_core.exceptions.Unknown,
                    ),
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
    PERF_MODEL_LOOKUP_FP = "lib/perf_model_aircraft_lookup_041824.json"
    BADA3_DATASET_FP = "bada3"
    LOW_MEM_WAYPOINT_COUNT = (
        300  # use low-mem cocip trajectory if traj length is above this val
    )

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

    def __init__(self, job: WaypointsRecord, hres_src: str, era5_src: str):
        """
        Parameters
        ----------
        job
            A list of flight waypoints, sampled at contiguous, 1min intervals.
        hres_src
            Fully-qualified uri for the source path the hres zarr store.
            e.g. 'gs://contrails-301217-ecmwf-hres-forecast-v2-short-term'
        era5_src
            Fully-qualified uri for the source path the era5 zarr store.
            e.g. 'gs://contrails-301217-ecmwf-era5-zarr-v2'
        """
        self._hres_src = hres_src
        self._era5_src = era5_src
        self._job = job
        self._zarr_src_fn: str | list[str] | None = None
        self._met_dataset: MetDataset | None = None
        self._rad_dataset: MetDataset | None = None

        self._verify_altitude(self._job)
        self._perf_model, self._engine_uid = self._perf_lookup(self._job)
        self._flight: pycontrails.Flight = self._create_flight(
            self._job, self._engine_uid
        )
        logger.debug("instantiated cocip handler.")

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
        (it is for BADA). However, we still return a single, default engine_uid for aircraft
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
                perf_model = PSFlight(
                    fill_low_altitude_with_isa_temperature=True,
                    fill_low_altitude_with_zero_wind=True,
                )
            case "BADA3":
                perf_model = BADAFlight(
                    bada3_path=cls.BADA3_DATASET_FP,
                    fill_low_altitude_with_isa_temperature=True,
                    fill_low_altitude_with_zero_wind=True,
                )
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
    def _find_nearest_hres_zarr_store(job: WaypointsRecord) -> str:
        """
        Method for inferring the target HRES zarr store, based on now() and the job's flight
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

    @classmethod
    def _find_era5_zarr_stores(cls, job: WaypointsRecord) -> list[str]:
        """
        Method for identifying the target zarr stores needed to run the given job.

        The ERA5 zarr stores are sharded on a per-day basis, meaning each store holds
        meteorological data for the file namesake day (UTC).

        For example, this store: gs://contrails-301217-ecmwf-era5-zarr-v2/20230510_sl.zarr
        holds surface level data for 2023-05-10T00:00:00Z -> 2023-05-10:23:00:00Z,
        data being available on an hourly basis.

        This method returns a list of date-string objects,
        e.g. the "20230510" in "gs://contrails-301217-ecmwf-era5-zarr-v2/20230510_sl.zarr"
        such that the zarr stores represented by the set of those dates is sufficient
        to run CoCiP trajectory on the given job.

        Parameters
        ----------
        job
            Trajectory worker job w/ list of waypoints constituting the trajectory chunk

        Returns
        -------
        List of filename prefixes representing the era5 zarr stores needed to run the job.
        e.g. ['20240411', '20240412', ...]
         in "gs://contrails-301217-ecmwf-era5-zarr-v2/<fn_prefix>_<sl/pl>.zarr
        """
        earliest_waypoint = pd.Timestamp(job.records[0].timestamp)
        latest_waypoint = pd.Timestamp(job.records[-1].timestamp)
        latest_contrail = (
            latest_waypoint + cls.STATIC_PARAMS["max_age"] + np.timedelta64(30, "m")
        )
        date_range = pd.date_range(
            start=earliest_waypoint.strftime("%Y-%m-%d"),
            end=latest_contrail.strftime("%Y-%m-%d"),
            freq="D",
        ).to_list()

        return [dt.strftime("%Y%m%d") for dt in date_range]

    def load(self):
        """
        Open met data zarr stores.

        HRES: Will choose the most recent _usable_ forecast.
        ERA5: Will choose store(s) that overlap entire flight traj + contrail evolution time.
        """
        if self._job.met_source == WaypointsRecord.MetSource.HRES:
            self._zarr_src_fn: str = self._find_nearest_hres_zarr_store(self._job)
            zarr_path = f"{self._hres_src}/{self._zarr_src_fn}"
            logger.debug(f"opening HRES PL zarr store at: {zarr_path}")
            pl = xr.open_zarr(
                f"{zarr_path}/pl.zarr",
                storage_options={"token": env.GCP_SVC_ACCT_KEY},
            )
            met = MetDataset(pl, provider="ECMWF", dataset="HRES", product="forecast")
            variables = (
                v[0] if isinstance(v, tuple) else v for v in Cocip.met_variables
            )
            met.standardize_variables(variables)

            logger.debug(f"opening HRES SL zarr store at: {zarr_path}")
            sl = xr.open_zarr(
                f"{zarr_path}/sl.zarr",
                storage_options={
                    "token": env.GCP_SVC_ACCT_KEY,
                },
            )
            rad = MetDataset(sl, provider="ECMWF", dataset="HRES", product="forecast")
            variables = (
                v[0] if isinstance(v, tuple) else v for v in Cocip.rad_variables
            )
            rad.standardize_variables(variables)

            self._met_dataset = met
            self._rad_dataset = rad
        elif self._job.met_source == WaypointsRecord.MetSource.ERA5:
            self._zarr_src_fn: list[str] = self._find_era5_zarr_stores(self._job)
            pl_ds: list[xr.Dataset] = []
            sl_ds: list[xr.Dataset] = []
            for src_fn in self._zarr_src_fn:
                zarr_path = f"{self._era5_src}/{src_fn}"
                logger.debug(f"opening ERA5 PL zarr store at: {zarr_path}")
                pl = xr.open_zarr(
                    f"{zarr_path}_pl.zarr",
                    storage_options={"token": env.GCP_SVC_ACCT_KEY},
                )
                pl_ds.append(pl)
                logger.debug(f"opening ERA5 SL zarr store at: {zarr_path}")
                sl = xr.open_zarr(
                    f"{zarr_path}_sl.zarr",
                    storage_options={
                        "token": env.GCP_SVC_ACCT_KEY,
                    },
                )
                sl_ds.append(sl)
            pl_ds_agg = xr.concat(pl_ds, dim="time")
            sl_ds_agg = xr.concat(sl_ds, dim="time")

            # TODO - remove tmp fix below
            sl_ds_agg["ttr"].attrs["units"] = "J m**-2"
            sl_ds_agg["tsr"].attrs["units"] = "J m**-2"

            met = MetDataset(
                pl_ds_agg, provider="ECMWF", dataset="ERA5", product="reanalysis"
            )
            variables = (
                v[0] if isinstance(v, tuple) else v for v in Cocip.met_variables
            )
            met.standardize_variables(variables)

            rad = MetDataset(
                sl_ds_agg, provider="ECMWF", dataset="ERA5", product="reanalysis"
            )
            variables = (
                v[0] if isinstance(v, tuple) else v for v in Cocip.rad_variables
            )
            rad.standardize_variables(variables)

            self._met_dataset = met
            self._rad_dataset = rad

        else:
            raise ValueError(
                "Unrecognized met source specified in trajectory worker job."
            )

    def run(self) -> Flight:
        """
        Run the cocip trajectory model.
        """
        logger.debug("running cocip model.")
        if not self._met_dataset or not self._rad_dataset:
            raise ValueError(
                "met dataset or rad dataset have not been loaded. Run load()."
            )

        if len(self._job.records) < self.LOW_MEM_WAYPOINT_COUNT:
            model = Cocip(
                met=self._met_dataset,
                rad=self._rad_dataset,
                aircraft_performance=self._perf_model,
                **self.STATIC_PARAMS,
            )
        else:
            logger.info(
                f"using low-mem cocip implementation for flight "
                f"w/ {len(self._job.records)} waypoints"
            )
            model = Cocip(
                met=self._met_dataset,
                rad=self._rad_dataset,
                aircraft_performance=self._perf_model,
                **self.STATIC_PARAMS,
                preprocess_lowmem=True,
            )
        logger.debug("evaluating cocip model.")
        result: Flight = model.eval(self._flight)
        logger.debug("finished evaluating cocip model.")
        return result

    @property
    def zarr_uri(self):
        """
        Returns the subdirectory that houses the hres zarr data
        and uniquely identifies the store based on the model_run_at time.
        """
        return self._zarr_src_fn
