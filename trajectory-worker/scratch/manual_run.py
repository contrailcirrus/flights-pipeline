import pandas as pd
from dataclasses import asdict

from lib.schemas import SpireFlightInfo, SpireWaypointsRecord, SpireWaypointPositional
from scratch.handlers import ResampleHandler
from main import _open_met_rad, _create_flight, _create_cocip_model, _perf_lookup


EXPORT_WINDOW_START_TIME = pd.to_datetime("2024-04-15T22:00:00Z")
INSTANCE_ORIGIN_OFFSET = pd.to_timedelta(6, "hours")

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

# -------------------
# resample and run
# for tg_ix, target in enumerate(flights_list):
target = flights_list[6]

flight_info: SpireFlightInfo
records: list[SpireWaypointPositional]
job: SpireWaypointsRecord

target.reset_index(inplace=True)
flight_info = SpireFlightInfo(  # todo: invariance handling
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
job = SpireWaypointsRecord(flight_info=flight_info, records=target_resampled)

# ---------------
# run model on trajectory

try:
    performance_model, engine_uid = _perf_lookup(job)
    met, rad = _open_met_rad(
        job, "gs://contrails-301217-ecmwf-hres-forecast-v2-short-term"
    )
    flight = _create_flight(job, engine_uid)
    model = _create_cocip_model(met, rad, performance_model)
    result = model.eval(flight)
except Exception as e:
    print(f"failed to run model. {e}")
result_ef = result["ef"]
result_seg_lens = result["segment_length"]

if (result_ef > 0).sum():
    print(f"found non-zero cocip values for flight_id: {job.flight_info.flight_id}")

sl = slice(1, -1)  # assuming we want to drop the first segment?
cocip_output = result["ef"][sl] / result["segment_length"][sl]

sum_ef = sum(cocip_output)
