import concurrent.futures

from google.cloud import pubsub_v1  # type: ignore


def _raise_exception_if_failed(future: concurrent.futures.Future) -> None:
    # Re-raise any exceptions raised by the future's execution thread.
    future.result(timeout=60)


class QueueClient:
    def __init__(self, topic_id: str) -> None:
        self._topic_id = topic_id
        self._publisher = pubsub_v1.PublisherClient()

        self._publish_futures: list[concurrent.futures.Future] = []

    def publish_async(self, data: bytes, ordering_key: str) -> None:
        """Add data to current publish batch.

        Batches are pushed asynchronously to GCP PubSub in a separate thread. To wait
        for one or more publish calls until they have been received by the server, call
        wait_for_publish.

        Args:
            data: byte encoded string payload
            ordering_key: payloads sharing the same ordering_key are guaranteed to be
                delivered to consumers in the order they are published
        """
        future: concurrent.futures.Future = self._publisher.publish(
            topic=self._topic_id,
            data=data,
            ordering_key=ordering_key,
        )
        future.add_done_callback(_raise_exception_if_failed)
        self._publish_futures.append(future)

    def wait_for_publish(self) -> None:
        """Block until all current publish batches are received by server.

        Raises:
            concurrent.futures.TimeoutError: server did not respond
            Exception: will re-raise exceptions raised by the batch execution threads
        """
        concurrent.futures.wait(self._publish_futures)
        self._publish_futures = []
