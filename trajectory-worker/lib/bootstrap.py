import time
from typing import NamedTuple

import google.auth.exceptions  # type: ignore

from lib import handlers
from lib.log import format_traceback, logger


class Handlers(NamedTuple):
    trajectory_cocip_bq_publisher: handlers.PubSubPublishHandler
    job_handler: handlers.PubSubSubscriptionHandler


def create_handlers_from_env() -> Handlers:
    """Construct infra handlers from environment, retrying auth related errors."""
    from lib import environment as env

    min_retry_interval = 1.0
    max_retry_interval = 10.0

    max_retry_count = 10
    retry_multiplier = 1.5

    retry_interval = min_retry_interval
    retry_count = 0
    while retry_count < max_retry_count:
        try:
            return Handlers(
                trajectory_cocip_bq_publisher=handlers.PubSubPublishHandler(
                    topic_id=env.TRAJECTORY_COCIP_BQ_TOPIC_ID,
                    ordered_queue=False,
                ),
                job_handler=handlers.PubSubSubscriptionHandler(
                    subscription=env.TRAJECTORY_CHUNK_SUBSCRIPTION_ID
                ),
            )

        except google.auth.exceptions.GoogleAuthError:
            logger.warning("Failed to construct infra handlers: " + format_traceback())

        retry_count += 1
        time.sleep(retry_interval)
        retry_interval = min(retry_interval * retry_multiplier, max_retry_interval)

    raise EnvironmentError("Failed to create required infra handlers")
