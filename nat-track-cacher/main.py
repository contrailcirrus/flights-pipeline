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
        if resp.status_code != 200:
            raise Exception("failed to fetch from NAT track contrails API.")
        geojson_blob = resp.json()

        # write features to BigQuery
        bigquery_client = bigquery.Client()

        insert_rows: list[dict] = []
        for feature in geojson_blob["features"]:
            geo_str = json.dumps(feature["geometry"])
            props = feature["properties"]
            geo_type = feature["geometry"]["type"]

            if geo_type == "LineString":
                # this is the full NAT track geo object
                insert_rows.append(
                    {
                        "nat_identifier": props["name"],
                        "updated_at": props["updated_at"],
                        "nat": geo_str,
                        "flight_levels_west": props["flight_levels_west"],
                        "flight_levels_east": props["flight_levels_east"],
                        "valid_dates": props["valid_dates"],
                    }
                )
            elif geo_type == "Point":
                # this is a waypoint in a NAT track geo object
                insert_rows.append(
                    {
                        "nat_identifier": props["id"],
                        "updated_at": props["updated_at"],
                        "nat": geo_str,
                        "flight_levels_west": [],
                        "flight_levels_east": [],
                        "valid_dates": [],
                    }
                )
            else:
                raise ValueError(f"found unrecognized geojson Feature type: {type}")

        err = bigquery_client.insert_rows_json(env.BQ_TABLE_ID, insert_rows)
        if err:
            raise RuntimeError(f"row insert failed: {err}")
        logger.info(f"wrote {len(insert_rows)} records to BQ for NATs.")
    except Exception:
        logger.error("Unhandled exception:" + format_traceback())
        sys.exit(1)
