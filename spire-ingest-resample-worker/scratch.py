import pandas as pd

from pycontrails.core.flight import Flight

from lib.schemas import SpireWaypointsRecord, WaypointCache, SpireWaypointPositional
from stub import pubsub_message, redis_response

FLIGHT_LEVELS = [
    270,
    280,
    290,
    300,
    310,
    320,
    330,
    340,
    350,
    360,
    370,
    380,
    390,
    400,
    410,
    420,
    430,
    440,
]

recs = SpireWaypointsRecord.from_utf8_json(pubsub_message)
# TODO: logic as to whether or not to use cache
cached = WaypointCache.from_flatmap(redis_response)
cached = [w for w in cached if w is not None]  # prune null WaypointCache.Waypoint objs
cached_flight_ids: list[str] = [
    SpireWaypointsRecord.from_waypoint_cache(w)[0] for w in cached
]
cached_waypoints: list[SpireWaypointPositional] = [
    SpireWaypointsRecord.from_waypoint_cache(w)[1] for w in cached
]


df_cached = pd.DataFrame(cached_waypoints)
df_cached.rename(
    columns={"altitude_baro": "altitude_ft", "timestamp": "time"}, inplace=True
)
# note: pycontrails resample_and_fill returns df w/ naive timestamps, hence:
df_cached["time"] = pd.to_datetime(df_cached["time"]).apply(
    lambda r: r.tz_localize(None)
)
max_cache_ts = df_cached["time"].max()


df_records = pd.DataFrame([*recs.records])
df_records.rename(
    columns={"altitude_baro": "altitude_ft", "timestamp": "time"}, inplace=True
)
# note: pycontrails resample_and_fill returns df w/ naive timestamps, hence:
df_records["time"] = pd.to_datetime(df_records["time"]).apply(
    lambda r: r.tz_localize(None)
)
min_records_ts = df_records["time"].min()

df = pd.concat([df_cached, df_records])

pyc_flight = Flight(df)
pyc_flight_df = pyc_flight.dataframe
flight_resampled: pd.DataFrame = pyc_flight.resample_and_fill().dataframe

# add imputation flags
flight_resampled["imputed"] = True
is_cached = flight_resampled["time"] <= max_cache_ts
is_records_window = flight_resampled["time"] >= min_records_ts
flight_resampled.loc[(is_cached | is_records_window), "imputed"] = False

# compute the altitude_ft from altitude (note: pycontrails Flight operates on altitude [m])
flight_resampled.loc[:, "altitude_ft"] = (flight_resampled["altitude"] * 3.28).astype(
    int
)


# compute the flight level from altitude_ft
def altitude_ft_to_flight_level(alt_ft: int):
    """
    Converts altitude in feet MSL to flight level (100s of ft), snapped to the nearest level.
    """
    diff = lambda i: abs(FLIGHT_LEVELS[i] - alt_ft // 100)  # noqa:E731
    min_ix = min(range(len(FLIGHT_LEVELS)), key=diff)
    return FLIGHT_LEVELS[min_ix]


flight_resampled["flight_level"] = flight_resampled["altitude_ft"].apply(
    altitude_ft_to_flight_level
)

# flight_resampled at this point will include minute data
# the first row will match what was pulled from cache
# the last row will have a timestamp that is the bottom of the minute
# for the right-most minutes data in the spire waypoints record window ingested from pubsub
# -------------------

# Cleanup
flight_resampled.drop(columns=["altitude"], inplace=True)
