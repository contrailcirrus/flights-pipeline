"""
Entrypoint for nat-track-cacher CronJob.
"""

import sys
import requests

from lib.log import logger, format_traceback
import lib.environment as env

if __name__ == "__main__":
    try:
        logger.info("Starting nat-track-cacher service")

        # fetch geoJSON blob from API
        resp = requests.get(env.NAT_TRACK_API_URL)
        geojson_blob = resp.json()
        updated_at = geojson_blob["features"][0]["properties"]["updated_at"]

        # write features to BigQuery

    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)
