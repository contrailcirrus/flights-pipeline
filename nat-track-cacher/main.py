"""
Entrypoint for nat-track-cacher CronJob.
"""

import sys
import requests
import json
from google.cloud import bigquery

from lib.log import logger, format_traceback
import lib.environment as env

if __name__ == "__main__":
    try:
        logger.info("Starting nat-track-cacher service")

        # fetch geoJSON blob from API
        resp = requests.get(env.NAT_TRACK_API_URL)
        geojson_blob = resp.json()
        updated_at_iso_str = geojson_blob["features"][0]["properties"]["updated_at"]

        # write features to BigQuery
        bigquery_client = bigquery.Client()

        insert_rows: list[dict] = []
        for feature in geojson_blob["features"]:
            geo_str = json.dumps(feature["geometry"])
            props = feature["properties"]
            insert_rows.append(
                {
                    "waypoint_id": props.get("id"),
                    "updated_at": updated_at_iso_str,
                    "nat": geo_str,
                }
            )
        err = bigquery_client.insert_rows_json(env.BQ_TABLE_ID, insert_rows)
        if err:
            raise RuntimeError(f"row insert failed: {err}")
        logger.info(
            f"wrote {len(insert_rows)} records to BQ for NATs updated on {updated_at_iso_str}"
        )
    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)
