import concurrent.futures
from concurrent.futures import TimeoutError, CancelledError
from typing import Callable

from lib.log import logger

from google.cloud import pubsub_v1  # type: ignore


def _get_futures_callback(**kwargs) -> Callable[[concurrent.futures.Future], None]:
    """
    returns a function to use as a callback.
    Constructs a log message annotating with any k-vs passed to this method.
    """

    msg = ""
    for k, v in kwargs.items():
        msg += f" {k}={v} "

    def _raise_exception_if_failed(future: concurrent.futures.Future) -> None:
        """Re-raise any exceptions raised by the future's execution thread.

        This should be registered as a callback that will only be invoked when the future
        has already completed using:
            future.add_done_callback(_raise_exception_if_failed)
        """
        try:
            future.result(timeout=55)
        except TimeoutError:
            logger.error(f"timeout. failed to publish blob. {msg}")
            # TODO: raise this to our main application, and exit
        except CancelledError:
            logger.error(f"publish future cancelled. failed to publish blob. {msg}")
            # TODO: raise ...
        except Exception:
            logger.error(f"publish future failed. {msg}")
            # TODO: ...

    return _raise_exception_if_failed


class QueueClient:
    def __init__(self, topic_id: str, ordered_queue: bool = False) -> None:
        self._topic_id = topic_id

        # Uses default retry policy which uses exponential backoff to manage retries.
        # The backoff is limited to [0.1, 60] seconds and increases by *1.3 on each
        # publish error. Retries are managed separately for each ordering key.
        # See: https://cloud.google.com/pubsub/docs/retry-requests
        self._publisher = pubsub_v1.PublisherClient(
            # Batch settings increase payload size to execute fewer, larger requests.
            # See: https://cloud.google.com/pubsub/docs/batch-messaging
            batch_settings=pubsub_v1.types.BatchSettings(
                max_messages=2500,
                max_bytes=20 * 1000 * 1000,  # 20 MB max server-side request size
                max_latency=5,  # default: 10 ms
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
            ),
        )

        self._publish_futures: list[concurrent.futures.Future] = []

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
            payloads sharing the same ordering_key are guaranteed to be delivered to
            consumers in the order they are published. the publisher client,
            and the subscription bound to the receiving topic,
            must be configured to use ordered messages.
        metadata
            any additional k-vs that contextualize the publish event.
            these will be added as context to the publisher callback,
            which includes them in any failure logs.
        """
        future: concurrent.futures.Future = self._publisher.publish(
            topic=self._topic_id,
            data=data,
            ordering_key=ordering_key,
        )
        future.add_done_callback(_get_futures_callback(**metadata))
        self._publish_futures.append(future)

    def wait_for_publish(self, timeout: float) -> None:
        """Block until all current publish batches are received by server.

        Raises
        ------
        concurrent.futures.TimeoutError: server did not respond
        Exception: will re-raise exceptions raised by the batch execution threads
        """
        concurrent.futures.wait(self._publish_futures, timeout=timeout)
        self._publish_futures = []
