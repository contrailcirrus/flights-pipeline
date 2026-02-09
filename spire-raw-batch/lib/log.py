"""
Logging utilities.
"""

import logging
import traceback

from lib import environment


def format_traceback() -> str:
    """Format current exception traceback as string."""
    tb_fmt_str = traceback.format_exc()
    return tb_fmt_str.replace("\n", " ")


log_fmt = '{"timestamp":"%(asctime)s", "severity": "%(levelname)s", "textPayload": "%(message)s", "labels":{"pid":"%(process)d", "thread":"%(thread)d", "asyncio_taskname":"%(taskName)s"}}'
log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

try:
    log_level = log_level_map[environment.LOG_LEVEL]
except KeyError:
    raise Exception(
        f"Log level must be specified as an env var, one of: {log_level_map.keys()}. "
        f"Got: {environment.LOG_LEVEL}"
    )


logging.basicConfig(encoding="utf-8", level=log_level, format=log_fmt)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("spire-raw-batch")
