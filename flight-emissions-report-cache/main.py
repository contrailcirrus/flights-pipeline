from flask import Request, jsonify, Response
import functions_framework
from typing import List, Dict, Tuple
from typing_extensions import TypedDict
from datetime import datetime, date
from fakedb import query

import os

from google.cloud.sql.connector import Connector, IPTypes
import pg8000

import sqlalchemy


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


ErrorResponse = Dict[str, str]


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

AIRLINE_IATA_CODES = {
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

INSTANCE_CONNECTION_NAME = "contrails-301217:us-east1:flight-emissions-report-dev"
TABLE_NAME = "flight-emissions-report-dev.flights-pipeline.trajectory-cocip"
# TABLE_NAME = "flight-emissions-report-prod.flights-pipeline.trajectory-cocip"


def connect_with_connector() -> sqlalchemy.engine.base.Engine:
    """
    Initializes a connection pool for a Cloud SQL instance of Postgres.

    Uses the Cloud SQL Python Connector package.
    """

    instance_connection_name = os.environ[INSTANCE_CONNECTION_NAME]
    db_user = os.environ["DB_USER"]  # e.g. 'my-db-user'
    db_pass = os.environ["DB_PASS"]  # e.g. 'my-db-password'
    db_name = os.environ["DB_NAME"]  # e.g. 'my-database'

    ip_type = IPTypes.PRIVATE if os.environ.get("PRIVATE_IP") else IPTypes.PUBLIC

    # initialize Cloud SQL Python Connector object
    connector = Connector()

    def getconn() -> pg8000.dbapi.Connection:
        conn: pg8000.dbapi.Connection = connector.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=db_pass,
            db=db_name,
            ip_type=ip_type,
        )
        return conn

    # The Cloud SQL Python Connector can be used with SQLAlchemy
    # using the 'creator' argument to 'create_engine'
    pool = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
        # pool_size=5,  # Optional: specify the size of the connection pool
        # max_overflow=2,  # Optional: specify the maximum overflow size of the connection pool
        # pool_timeout=30,  # Optional: specify the timeout for getting a connection from the pool
        # pool_recycle=1800,  # Optional: specify the recycle time for connections in the pool
        # pool_pre_ping=True,  # Optional: enable pre-ping to check the connection before using it
    )
    return pool


def query_db(
    connection,
    airline_iata: str,
    flight_number: str,
    date: date,
) -> List[ResponseObject]:
    result = connection.execute(
        sqlalchemy.text(
            f"""
            SELECT * FROM {TABLE_NAME}
            WHERE flight_number = :flight_number
            AND airline_iata = :airline_iata
            AND DATE(departure_scheduled_time) = :date
        """
        ),
        {
            "flight_number": flight_number,
            "airline_iata": airline_iata,
            "date": date,
        },
    )
    rows = result.fetchall()
    return rows


@functions_framework.http
def handler(req: Request) -> Tuple[Response, int, Dict[str, str]]:
    # Set CORS headers for the preflight request
    if req.method == "OPTIONS":
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            "Access-Control-Allow-Origin": "http://localhost:5173/",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }

        return (jsonify([]), 204, headers)

    # Set CORS headers for the main request
    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        query_params = req.args
        airline_name = query_params.get("airline")
        date_str = query_params.get("date")
        flight_number = query_params.get("flightNumber")

        if not airline_name or not date_str or not flight_number:
            missing = []

            if not airline_name:
                missing.append("airline")
            if not date_str:
                missing.append("date")
            if not flight_number:
                missing.append("flightNumber")

            raise ValueError(f"Missing required query parameters: {missing}")

        if airline_name and airline_name.lower() not in AIRLINE_IATA_CODES:
            raise ValueError(f"Invalid airline: {airline_name}")

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD"
            )

        today = datetime.today().date()
        if date_obj > today:
            raise ValueError("The date cannot be in the future")

        # airline_iata = AIRLINE_IATA_CODES[airline_name.lower()]

        # # Initialize the SQLAlchemy engine
        # engine = connect_with_connector()

        # # Query the database
        # with engine.connect() as connection:
        #     response_data = query_db(connection, airline_iata, flight_number, date_obj)
        response_data = query(airline_name, flight_number, date_obj)

        return jsonify(response_data), 200, headers

    except ValueError as e:
        return jsonify({"error": str(e)}), 400, headers
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500, headers
