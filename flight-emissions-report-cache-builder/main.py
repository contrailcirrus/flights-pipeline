import os
from google.cloud import bigquery
import sqlalchemy
import pg8000
from google.cloud.sql.connector import Connector, IPTypes

INSTANCE_CONNECTION_NAME = "contrails-301217:us-east1:flight-emissions-report-dev"
BIGQUERY_SOURCE = "contrails-301217.flights_pipeline_dev.trajectory_cocip_dev"
# BIGQUERY_SOURCE = "flights_pipeline_prod.trajectory_cocip_prod"


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


def query_bigquery_and_insert_into_postgres():
    client = bigquery.Client()
    query = f"""
        SELECT airline_iata, arrival_airport_icao, arrival_scheduled_time, departure_airport_icao, departure_scheduled_time, flight_id, flight_number, sum_ef_mj, time_end, time_start
        FROM `{BIGQUERY_SOURCE}`
        WHERE DATE(departure_scheduled_time) = DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
    """
    query_job = client.query(query)

    for page in query_job.result(page_size=1000).pages:
        for row in page:
            # insert into postgres
            # row_dict = dict(row)
            # cursor.execute(
            #     """
            # INSERT INTO your_postgres_table (column1, column2, column3)
            # VALUES (%s, %s, %s)
            # """,
            #     (row_dict["column1"], row_dict["column2"], row_dict["column3"]),
            # )
            print(row)


def handler():
    query_bigquery_and_insert_into_postgres()
