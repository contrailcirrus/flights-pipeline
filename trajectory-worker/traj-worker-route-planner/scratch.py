import pickle

import xarray as xr
import numpy as np

flight_id = "5149f41e-cdc6-45fe-8a96-4cfe1c076a9b"

# ln.47 trajectory-worker::main.py
with open(f"traj-worker-route-planner/job_{flight_id}.p", "rb") as fp:
    job = pickle.load(fp)

# ln.99 trajectory-worker::main.py
with open(f"traj-worker-route-planner/cocip_fleet_result_{flight_id}.p", "rb") as fp:
    cocip_fleet_result = pickle.load(fp)


# mirrors ln. 100-103 trajectory-worker::main.py
cocip_fleet_result_lookup = {
    flight.attrs["flight_id"]: flight for flight in cocip_fleet_result
}
target_flight_result = cocip_fleet_result_lookup[job.flight_info.flight_id]

# -----------------
# DISCUSSION
# -----------------
# The fleet above is composed of a single target ("actual") flight, and several
# synthetic flights, each of the synthetic flights mirroring the target flight's
# lat/lon positioning, but pinned at fixed flight levels.
# This creates the grid of CoCiP outputs used to visualize the contrail-forming regions
# (gray clouds) in the per-flight view of the Explorer (https://explore.contrails.org/explorer).
#
# Here, we consider using both the met values and the cocip values of this grid as our variable
# space for navigating a contrail-optimal counterfactual flight path.
# --
# The variable space grid is built from the fixed-altitude synthetic flights only, excluding
# the target (non-fixed-altitude) flight. Each synthetic flight mirrors the target's
# lat/lon/time track but is pinned to a single altitude, so:
#   - waypoint (912): the shared horizontal path; lat/lon/time ride along it
#   - altitude (22):  one value per synthetic flight (the fixed flight levels)
# Variables are therefore (waypoint, altitude) == 912 x 22.

# Each synthetic flight is pinned to one altitude, so altitude_ft is constant along
# its waypoints -> the fixed altitude is just the first element.
# Exclude the target flight; sort the remaining fixed-altitude flights by altitude.
synthetic_flights = sorted(
    (fl for fl in cocip_fleet_result if fl is not target_flight_result),
    key=lambda fl: fl["altitude_ft"][0],
)

# lat/lon/time are aligned across all flights
ref = synthetic_flights[0]
altitudes = np.array([fl["altitude_ft"][0] for fl in synthetic_flights])


def _grid(key: str) -> np.ndarray:
    """Stack a per-waypoint key across synthetic flights -> (waypoint, altitude)."""
    return np.column_stack([fl[key] for fl in synthetic_flights])


# cocip energy forcing per metre of flight path (J/m)
# TODO: should this be center-difference instead of right-facing difference?
ef_per_m = np.column_stack(
    [fl["ef"] / fl["segment_length"] for fl in synthetic_flights]
)

ds = xr.Dataset(
    data_vars={
        "ef_per_m": (("waypoint", "altitude"), ef_per_m),
        "air_temperature": (("waypoint", "altitude"), _grid("air_temperature")),
        "u_wind": (("waypoint", "altitude"), _grid("u_wind")),
        "v_wind": (("waypoint", "altitude"), _grid("v_wind")),
    },
    coords={
        "longitude": ("waypoint", ref["longitude"]),
        "latitude": ("waypoint", ref["latitude"]),
        "time": ("waypoint", ref["time"]),
        "altitude": ("altitude", altitudes),
        "waypoint": ("waypoint", ref["waypoint"]),
    },
)

print(ds)
