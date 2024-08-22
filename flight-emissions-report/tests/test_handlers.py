"""
handlers.py unit tests.
"""

import pytest

from handlers import TrajectoryValidationHandler


# -------------
# TrajectoryValidationHandler
# -------------


def test_calc_distance():
    """Test helper func for great circle distance calculation"""
    # lat, lon, altitude_ft
    denver_airport = (39.856799, -104.684585, 5_500)
    somewhere_over_kansas = (39.109061, -101.792234, 5_500)
    dist_m = TrajectoryValidationHandler._calc_distance_m(
        lat_0=denver_airport[0],
        lon_0=denver_airport[1],
        alt_ft_0=denver_airport[2],
        lat_f=somewhere_over_kansas[0],
        lon_f=somewhere_over_kansas[1],
        alt_ft_f=somewhere_over_kansas[2],
    )
    assert 261_750 == pytest.approx(dist_m, rel=0.01)


def test_trajectory_validation_handler_1(flight_instance_3):
    """
    Test for FlightInvariantFieldViolation in flight trajectory.
    """
