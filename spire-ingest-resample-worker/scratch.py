import pandas as pd

from pycontrails.core.flight import Flight

from lib.schemas import SpireWaypointsRecord, WaypointCache
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
w0, w1 = WaypointCache.from_flatmap(redis_response)
cached_flight_id, cached_wp = SpireWaypointsRecord.from_waypoint_cache(w1)

df = pd.DataFrame([cached_wp, *recs.records])
df.rename(columns={"altitude_baro": "altitude_ft", "timestamp": "time"}, inplace=True)

pyc_flight = Flight(df)
pyc_flight_df = pyc_flight.dataframe
flight_resampled: pd.DataFrame = pyc_flight.resample_and_fill(
    keep_original_index=True, drop=False
).dataframe

# the following non-numeric fields were lost in the interpolation:
#     source, collection_type, imputed
#
# we forward fill these values ONLY for the rows
# that were interpolated within the spire waypoints record window
# essentially, we say that if the interpolated waypoint happened
# within a minute or so of the actual observation,
# then it inherits the source, collection_type, etc.
# (i.e. between the spire waypoints record window and the cached waypoint)
# ----------------
# index range for records interpolated within our spire waypoints window
# note: index 0 of pyc_flight is our cached waypoint
#       index 1: of pyc_flight is our spire waypoint records window
ix_waypoint_records = flight_resampled["time"] >= pyc_flight.dataframe["time"][1]
ffill_cols = ["source", "collection_type", "imputed"]
ffill = flight_resampled.loc[ix_waypoint_records, ffill_cols].ffill()
flight_resampled.loc[ix_waypoint_records, ffill_cols] = ffill

# for waypoints backward interpolated over the inter-window interval
# we assign imputed=True,
# and we do not assign source or collection_type
flight_resampled.fillna({"imputed": "True"}, inplace=True)

# drop the rows with non-interpolated values (note: we retained these for the ffill)
flight_resampled = flight_resampled[flight_resampled["ingestion_time"].isna()]

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
