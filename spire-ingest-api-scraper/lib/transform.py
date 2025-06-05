import pandas as pd

from lib.log import logger

pd.set_option("future.no_silent_downcasting", True)

# Spire reported that the following icao_address values are not unique to a specific
# aircraft. We drop related records to avoid downstream inconsistencies.
IGNORE_ICAO_ADDRESS = {"000000", "00000a", "0000BA"}


def _downsample_icao_address_minutes_first_last(df: pd.DataFrame) -> pd.DataFrame:
    """Retains only the first and last rows for each [icao_address, minute].

    Parameters
    ----------
    df
        pd.DataFrame with required columns `icao_address` and `timestamp`. Other columns
        will be retained in the result but are not required.

    Returns
    -------
    pd.DataFrame
        If a icao_address has only one observation timestamp during a given minute, only
        one row will be returned per minute. If an icao_address has two or more
        observation timestamps during a given minute, only two rows will be returned per
        minute.
    """
    timestamp = pd.to_datetime(df["timestamp"])
    minute = timestamp.dt.floor("1 min")

    grouped = df.sort_values("timestamp").groupby(["icao_address", minute])
    first = grouped.head(1)
    last = grouped.tail(1)

    # Spire truncates millis from the observation timestamp, so each is floored to the
    # nearest second. Ensure the first and last points are not during the same second.
    result = pd.concat([first, last]).drop_duplicates(["icao_address", "timestamp"])
    return result


def filter_ingest_rules(spire_df: pd.DataFrame) -> pd.DataFrame:
    """Drops rows which are not useful downstream.

    This applies several filtering rules including:

    1. remove rows where position is on_ground
    2. remove rows where altitude_baro is null
    3. remove rows with icao_address in our keep-out list
    4. remove rows which are not the first or last record per-minute per-icao_address

    Parameters
    ----------
    spire_df
        position data returned by SpireAPIClient(...).get_data_between(...)

    Returns
    -------
        pd.DataFrame
            data containing same columns as spire_df but only rows which meet the
            filtering criteria
    """
    # Retain records when aircraft is not on ground. on_ground is a nullable boolean
    # type which may be nan if unknown.
    is_on_ground = spire_df["on_ground"].fillna(False).astype(bool)
    drop_count_on_ground = is_on_ground.sum()
    if drop_count_on_ground > 0:
        logger.info(f"Dropped {drop_count_on_ground} records on ground")
    is_flying = ~is_on_ground
    spire_df = spire_df.loc[is_flying, :]

    # Drop any records missing altitude data.
    is_missing_altitude = spire_df["altitude_baro"].isna()
    drop_count_missing_altitude = is_missing_altitude.sum()
    if drop_count_missing_altitude > 0:
        logger.info(
            f"Dropped {drop_count_missing_altitude} records where altitude_baro is "
            + "null but on_ground is false or null."
        )
    has_altitude = ~is_missing_altitude
    spire_df = spire_df.loc[has_altitude, :]

    # drop records with an icao address in our keep-out list
    is_ignored_icao_address = spire_df["icao_address"].isin(IGNORE_ICAO_ADDRESS)
    spire_df = spire_df.loc[~is_ignored_icao_address, :]

    drop_count_ignored_icao_address = is_ignored_icao_address.sum()
    if drop_count_ignored_icao_address > 0:
        logger.info(
            f"Drop {drop_count_ignored_icao_address} records with "
            f"icao_address in: {IGNORE_ICAO_ADDRESS}"
        )

    # Reduce size of egress data by dropping records that have no use downstream.
    # The first and last record for each minute (observation time, not ingest time)
    # provide the relevant position data
    # to interpolate values for :00 second of each minute but drop records between
    # the first and last which do not influence interpolation downstream.
    spire_df = _downsample_icao_address_minutes_first_last(spire_df)

    return spire_df
