import sys
from datetime import datetime, UTC, timedelta

import pandas as pd
from sqlalchemy import create_engine
from google.cloud import bigquery

import lib.environment as env
from lib.log import logger
from lib.handlers import BigQueryHandler

SYNC_OFFSET_DAYS = (
    2  # lag, in days, between now() and the target day for sync'ing records
)

BQ_FER_AIRLINES_DAY_QUERY_FILENAME = "sql/bq_fer_by_airlines_day.sql"


# list of target airlines to sync. fmt <friendly name>:<iata designator>
TARGET_AIRLINES = {
    "klm": "KL",
    "tui": "BY",
    "transavia": "HV",
    "american airlines": "AA",
    "united airlines": "UA",
    "delta airlines": "DL",
    "virgin atlantic": "VS",
    "southwest airlines": "WN",
    "alaska airlines": "AS",
    "swiss airlines": "LX",
    "british airways": "BA",
    "air france": "AF",
    "dhl": "D0",
}

DATABASE_NAME = "flights-pipeline"
TABLE_NAME = "trajectory-cocip"


if __name__ == "__main__":
    """
    Application entrypoint.

    Fetch CoCiP fer outputs (per-flight CoCip summaries) from BQ, for target airlines on target day.
    Target day is SYNC_OFFSET_DAYS prior to `now()`.
    Upload those records to the target postgres database.
    """

    now = datetime.now(tz=UTC)
    target_date = now - timedelta(days=SYNC_OFFSET_DAYS)
    target_date_str = target_date.strftime(
        "%Y-%m-%d"
    )  # target date str as submitted to BQ

    bq_handler = BigQueryHandler()

    try:
        query = bq_handler.import_query(BQ_FER_AIRLINES_DAY_QUERY_FILENAME)
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter(
                    "airline_iata_lst",
                    "STRING",
                    [v for k, v in TARGET_AIRLINES.items()],
                ),
                bigquery.ScalarQueryParameter(
                    "date_str",
                    "STRING",
                    "2024-09-01",
                ),
            ]
        )
        records_df: pd.DataFrame = bq_handler.query(query, cfg)
        logger.info(f"fetched {len(records_df)} records for BQ -> PSDB sync.")
        db = create_engine(
            f"postgresql://{env.PSDB_USER}:{env.PSDB_PASS}@{env.PSDB_HOST}/{DATABASE_NAME}"
        )
        with db.connect() as conn:
            records_df.to_sql(
                TABLE_NAME, con=conn, if_exists="append", index=False, chunksize=5000
            )
            conn.commit()

    except Exception as e:
        logger.error(
            f"failed to sync {target_date_str} between BQ table and PSDB table. {e}"
        )
        sys.exit(1)
