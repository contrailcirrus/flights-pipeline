"""
Entrypoint for nat-track-cacher CronJob.
"""

import sys

from lib.log import logger, format_traceback

if __name__ == "__main__":
    try:
        logger.info("Starting nat-track-cacher service")

    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)
