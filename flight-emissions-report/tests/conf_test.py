import os

import pandas as pd
import pytest

os.environ["LOG_LEVEL"] = "DEBUG"


def _import_flight_instance(fn: str) -> pd.DataFrame:
    """
    Helper to import a target flight instance file.
    """
    df = pd.read_csv(f"tests/datasets/flight_instances/{fn}")
    df.loc[:, "timestamp"] = pd.to_datetime(df["timestamp"])
    df.loc[:, "ingestion_time"] = pd.to_datetime(df["ingestion_time"])
    df.loc[:, "departure_scheduled_time"] = pd.to_datetime(
        df["departure_scheduled_time"]
    )
    df.loc[:, "arrival_scheduled_time"] = pd.to_datetime(df["arrival_scheduled_time"])
    df.sort_values("timestamp", ascending=True, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


@pytest.fixture(scope="session")
def flight_instance_1() -> pd.DataFrame:
    fn = "2717a152-da73-493e-87a2-83ab5ea18365.csv"
    return _import_flight_instance(fn)


@pytest.fixture(scope="session")
def flight_instance_2() -> pd.DataFrame:
    fn = "8f4d0cd7-e823-47ef-86e3-3d37d1ac2ff2.csv"
    return _import_flight_instance(fn)
