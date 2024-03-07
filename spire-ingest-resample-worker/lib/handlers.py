"""
Application handlers.
"""

import time
from threading import Thread
from typing import Union

from lib.log import logger, format_traceback
from lib.schemas import SpireWaypointRecords
from lib.schemas import WaypointCache
import lib.environment as env

from google.api_core import retry
from google.cloud import pubsub_v1

import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff

import warnings


class PubSubSubscriptionHandler:
    """
    Handler for managing consumption and marshalling of jobs from a pubsub subscription queue.
    """

    # the number of seconds the subscriber client will hang, waiting for available messages
    MSG_WAIT_TIME_SEC = 60.0
    ACK_EXTENSION_SEC = 300.0

    def __init__(self, subscription: str):
        """
        Parameters
        ----------
        subscription
            The fully-qualified URI for the pubsub subscription.
            e.g. 'projects/contrails-301217/subscriptions/api-preprocessor-sub-dev'
        ack_extension_sec
            This handler will indefinitely extend the active message's ack deadline by
            ack_extension_sec until self.ack() is called
        """
        self.subscription = subscription
        self._client = None
        self._ack_id: Union[None, str] = None
        self._kill_ack_manager = False
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
        while not self._kill_ack_manager:
            time.sleep(self.ACK_EXTENSION_SEC // 2)
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

    def fetch(self) -> SpireWaypointRecords:
        """
        Fetch a message from the subscription queue.
        This method will hang and wait until a message is available.
        This method, in case of exception, will hang, backoff and retry indefinitely.

        Returns
        -------
        str
            The dequeued message from the pubsub subscription.
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
            logger.info(
                f"received 1 message from {self.subscription}. "
                f"published_time: {msg.message.publish_time}, "
                f"message_id: {msg.message.message_id}"
            )
            return SpireWaypointRecords.from_utf8_json(msg.message.data)

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
        self._kill_ack_manager = True
        self._client.close()


class CacheHandler:
    """
    Handler for interfacing with the remote cache.
    The remote cache stores the (2) last-known waypoints on a per flight-instance basis.
    """

    KEY_EXPIRY_SEC = 18 * 60 * 60  # seconds before a key expires

    def __init__(self, host: str, port: int):
        """
        Parameters
        ----------
        host
            the remote Redis host address (ipv4)
        port
            the remote Redis host port
        """
        self._host = host
        self._port = port

    def push(self, cache_entry: WaypointCache):
        """
        Parameters
        ----------
        cache_entry:
            A WaypointCache object.
            Contains the key to use for the redis index.
            Contains the last two known waypoints for the flight instance.
        """
        # TODO: error handling
        # TODO: do we want to persist a client class instance level? I think better to release conn.
        redis_retry = Retry(ExponentialBackoff(), 3)
        redis_client = redis.Redis(
            host=env.REDIS_HOST,
            port=env.REDIS_PORT,
            retry=redis_retry,
            retry_on_timeout=True,
        )
        # try writing single record w/ expiry as an atomic transaction
        transaction = redis_client.pipeline()
        transaction.hset(cache_entry.key, mapping=cache_entry.to_flatmap())
        transaction.expire(cache_entry.key, self.KEY_EXPIRY_SEC)
        transaction.execute()
