import pandas as pd
from dataclasses import asdict

from lib.schemas import (
    FlightInfoWide,
    WaypointsRecord,
    SpireWaypointPositional,
    CocipTrajectoryChunk,
)
from scratch.handlers import ResampleHandler
from lib.handlers import CocipTrajectoryHandler

from pycontrails_bada.bada_model import BADAFlight

# static export from spire_flights_raw_dev
df_raw = pd.read_csv("scratch/BA_spire_raw_sample.csv")
df_raw["ingestion_time"] = pd.to_datetime(df_raw["ingestion_time"])
df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"])

# print some summary observations
# ---------------
# collection-type
print(df_raw["collection_type"].value_counts())

# missing flight_uuid
print(f"missing flight_id count: {df_raw['flight_id'].isna().sum()}")

# impute missing flight_uuids
df_raw.sort_values(by=["icao_address", "timestamp"], inplace=True)
df_raw["flight_id"] = df_raw["flight_id"].ffill()

# prune full flight_instances
flight_instances = df_raw.groupby("flight_id")
target: pd.DataFrame
flights_list = []

for flight_id, waypoints in flight_instances:
    flight_id_start_at = waypoints["timestamp"].min()
    # if flight_id_start_at < EXPORT_WINDOW_START_TIME + INSTANCE_ORIGIN_OFFSET:
    #    print(f"flight_id: {flight_id}, starting at {waypoints["timestamp"].min()}, "
    #          f"occurred too early to consider as the flight origin.")
    #    continue
    flights_list.append(waypoints)
    print(f"got flight {flight_id} with {len(waypoints)} waypoints.")

# -------------------
# resample and run
# for tg_ix, target in enumerate(flights_list):
target = flights_list[1]

flight_info: FlightInfoWide
records: list[SpireWaypointPositional]
job: WaypointsRecord

target.reset_index(inplace=True)
flight_info = FlightInfoWide(  # todo: invariance handling
    icao_address=target["icao_address"][0],
    flight_id=target["flight_id"][0],
    callsign=target["callsign"][0],
    tail_number=target["tail_number"][0],
    flight_number=target["flight_number"][0],
    aircraft_type_icao=target["aircraft_type_icao"][0],
    airline_iata=target["airline_iata"][0],
    departure_airport_icao=target["departure_airport_icao"][0],
    departure_scheduled_time=target["departure_scheduled_time"][0],  # todo: fmt
    arrival_airport_icao=target["arrival_airport_icao"][0],
    arrival_scheduled_time=["arrival_scheduled_time"][0],  # todo: fmt
    engine_uid=None,
)

records = []
for ix, ln in target.iterrows():
    record = SpireWaypointPositional(
        ingestion_time=ln["ingestion_time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        timestamp=ln["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        latitude=ln["latitude"],
        longitude=ln["longitude"],
        collection_type=ln["collection_type"],
        imputed=False,
        altitude_baro=int(ln["altitude_baro"]),
    )
    records.append(record)

resample_handler = ResampleHandler(cache=[], records_window=records)
resample_handler.interpolate()

target_resampled = resample_handler.waypoints_resampled
target_resampled_df = pd.DataFrame([asdict(ln) for ln in target_resampled])
job = WaypointsRecord(flight_info=flight_info, records=target_resampled)

# ---------------
# run model on trajectory

try:
    cocip_handler = CocipTrajectoryHandler(
        job, "gs://contrails-301217-ecmwf-hres-forecast-v2-short-term"
    )
    # manual override of bada3 model
    perf_model = BADAFlight(
        bada3_path="/Users/nickmasson/dev/flights-pipeline/trajectory-worker/bada3"
    )
    cocip_handler._perf_model = perf_model
    cocip_handler.load()
    result = cocip_handler.run()
except Exception as e:
    print(f"failed to run model. {e}")

egress_dto = CocipTrajectoryChunk.from_cocip_result("", "", job, "foo", result)
bq_blob = egress_dto.to_bq_flatmap()
