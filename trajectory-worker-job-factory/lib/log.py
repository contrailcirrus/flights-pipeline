"""
Module for configuring and managing application-wide logger.
"""

import logging
import sys
import traceback
import warnings

import lib.environment as env

from pythonjsonlogger import jsonlogger


def format_traceback():
    """
    Fetches traceback from sys and formats it.
    Formatting such that it can be packaged as a single-line string literal
        with escapes on double-quotes (as to be a valid str in a json k-v)
    """
    tb_fmt_str = traceback.format_exc().replace("\n", "\\n").replace('"', '\\"')
    return tb_fmt_str


log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

try:
    log_level = log_level_map[env.LOG_LEVEL]
except KeyError:
    raise Exception(
        f"Log level must be specified as an env var, one of: {log_level_map.keys()}. "
        f"Got: {env.LOG_LEVEL}"
    )

# Get a logger instance
# logging.basicConfig(encoding="utf-8", level=log_level)
logger = logging.getLogger("trajectory-worker-job-factory")
logger.setLevel(log_level)
# Create a handler
logHandler = logging.StreamHandler(sys.stderr)
# Define the log format using standard LogRecord attributes
# The format string defines the order and inclusion of fields
log_format = '%(timestamp)s, %(levelname)s, %(message)s, %(process)d, %(thread)d, %(taskName)s'
formatter = jsonlogger.JsonFormatter(log_format,rename_fields={"levelname": "severity", "process": "pid", "taskName": "asyncio_taskname"}, timestamp=True)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

# capture and redirect warnings from the `warn` pkg to our logger
def log_warn(message, category, filename, lineno, file=None, line=None):
    logger.debug(message)


warnings.showwarning = log_warn
