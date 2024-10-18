"""
Application handlers.
"""

import concurrent.futures
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable

import google.api_core.exceptions
import google.api_core.retry
from google.cloud import pubsub_v1  # type: ignore
from lib.log import format_traceback, logger


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
