import pandas as pd


def downsample_icao_address_minutes_first_last(df: pd.DataFrame) -> pd.DataFrame:
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
    first_min = grouped.head(1)
    last_min = grouped.tail(1)

    result = pd.concat([first_min, last_min]).drop_duplicates()
    return result
