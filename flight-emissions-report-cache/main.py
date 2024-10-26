import sys
from datetime import datetime, UTC, timedelta
from typing import TypedDict

import pandas as pd
import sqlalchemy
from google.cloud import bigquery
from google.cloud.sql.connector import Connector, IPTypes

import lib.environment as env
from lib.log import logger
from lib.handlers import BigQueryHandler

SYNC_OFFSET_DAYS = (
    2  # lag, in days, between now() and the target day for sync'ing records
)

BQ_FER_AIRLINES_DAY_QUERY_FILENAME = "sql/bq_fer_by_airlines_day.sql"


class ResponseObject(TypedDict):
    airline_iata: str
    arrival_airport_icao: str
    arrival_scheduled_time: int
    departure_airport_icao: str
    departure_scheduled_time: int
    flight_id: str
    flight_number: str
    sum_ef_mj: int
    time_end: int
    time_start: int


ErrorResponse = dict[str, str]

# AIRLINES = [
#     "klm",  # {"airline": "KL"},
#     "tui",  # {"airline": "BY"},
#     "transavia",  # {"airline": "HV"},
#     "american airlines",  # {"airline": "AA"},
#     "united airlines",  # {"airline": "UA"},
#     "delta airlines",  # {"airline": "DL"},
#     "virgin atlantic",  # {"airline": "VS"},
#     "southwest airlines",  # {"airline": "WN"},
#     "alaska airlines",  # {"airline": "AS"},
#     "swiss airlines",  # {"airline": "LX"},
#     "british airways",  # {"airline": "BA"},
#     "air france",  # {"airline": "AF"},
#     "dhl",  # {"airline": "D0"},
#     "discover airlines",  # {"icao_address": "3C6565"},  # iagos tail_number: "D-AIKE"
#     "cathay pacific",  # {"icao_address": "780192"},  # iagos tail_number: "B-HLR"
#     "china airlines",  # {"icao_address": "8991BD"},  # iagos tail_number: "B-18316", # {"icao_address": "8991BE"},  # iagos tail_number: "B-18317"
#     "hawaiian airlines",  # {"icao_address": "A46AD6"},  # iagos tail_number: "N384HA"
#     "air france",  # {"icao_address": "39644E"},  # iagos tail_number: "F-GZCO"
#     "lufthansa",  # {"icao_address": "3C64F4"},  # iagos tail_number: "D-AIGT"
#     "iberia",  # {"icao_address": "3455C1"},  # iagos tail_number: "EC-MSY", # {"icao_address": "3C656F"},  # iagos tail_number: "D-AIKO"
#     "air canada",  # {"icao_address": "C04FBB"},  # iagos tail_number: "C-GEFA"
# ]

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

instance_connection_uri = f"contrails-301217:us-east1:{env.PSDB_INSTANCE_NAME}"

connector = Connector()


def getconn():
    conn = connector.connect(
        instance_connection_uri,
        "psycopg2",
        user=env.PSDB_USER,
        password=env.PSDB_PASS,
        db=DATABASE_NAME,
        ip_type=IPTypes.PUBLIC,
    )
    return conn


pool = sqlalchemy.create_engine(
    "postgresql+psycopg2://",
    creator=getconn,
    # pool_size=5,  # Optional: specify the size of the connection pool
    # max_overflow=2,  # Optional: specify the maximum overflow size of the connection pool
    # pool_timeout=30,  # Optional: specify the timeout for getting a connection from the pool
    # pool_recycle=1800,  # Optional: specify the recycle time for connections in the pool
    # pool_pre_ping=True,  # Optional: enable pre-ping to check the connection before using it
)

with pool.connect() as db_conn:
    result = db_conn.execute(
        sqlalchemy.text(f'SELECT * FROM "{TABLE_NAME}"')
    ).fetchall()
    db_conn.commit()
    print(f"got {len(result)} rows.")
    for row in result:
        print(f"got row: {row}")

records_df: pd.DataFrame = pd.DataFrame()
with pool.connect() as db_conn:
    records_df.to_sql(
        TABLE_NAME, con=db_conn, if_exists="append", index=False, chunksize=5000
    )
    db_conn.commit()

connector.close()

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

    except Exception as e:
        logger.error(
            f"failed to sync {target_date_str} between BQ table and PSDB table. {e}"
        )
        sys.exit(1)
