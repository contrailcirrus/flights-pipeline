from google.cloud import bigquery
import pandas as pd
import warnings


warnings.filterwarnings("ignore", module="google.auth")


class BigQueryHandler:
    def __init__(self):
        self._client = (
            bigquery.Client()
        )  # assume caller's identify from local gcloud certs

    def query(
        self, query_str: str, job_config: bigquery.QueryJobConfig
    ) -> pd.DataFrame:
        """
        Queries the BigQuery API.

        Parameters
        ----------
        query_str
            string representation of the SQL query to dispatch
        job_config
            job configuration, including parametrized values in the query (if any)

        Returns
        -------
        dataframe with one row per waypoint
        """

        query_job = self._client.query(query_str, job_config=job_config)
        rows = query_job.result()  # block until query is available
        return rows.to_dataframe()

    @staticmethod
    def import_query(filename: str) -> str:
        """
        Import a query as a single string with inline \n
        """
        with open(filename, "r") as fp:
            return fp.read()
