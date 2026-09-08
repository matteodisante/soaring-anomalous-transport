"""Round-trip tests for soaring.viewer.geodesy against the pipeline's own forward
projection (soaring.analysis.preproc.enu) -- the two must agree, since the inverse is
built from the same WGS84 constants and rotation.
"""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.preproc.enu import LocalFrame, geodetic_to_enu
from soaring.viewer.geodesy import enu_to_geodetic

LAT0, LON0, ALT0 = 45.0, 7.0, 1000.0
FRAME = LocalFrame(lat0_deg=LAT0, lon0_deg=LON0, alt0_m=ALT0)


def test_the_origin_itself_round_trips_exactly():
    zeros = np.array([0.0])
    lat, lon = enu_to_geodetic(zeros, zeros, np.array([ALT0]), FRAME)
    assert lat[0] == pytest.approx(LAT0, abs=1e-9)
    assert lon[0] == pytest.approx(LON0, abs=1e-9)


def test_points_across_a_flights_extent_round_trip_to_within_a_metre():
    # A grid spanning roughly +-20 km in each horizontal direction and +-1000 m of
    # altitude relative to the origin -- comfortably past what any real flight covers
    # (docs/guide/data-on-disk.md: extent_km rarely exceeds a few tens of km).
    rng = np.random.default_rng(0)
    n = 500
    lat = LAT0 + rng.uniform(-0.18, 0.18, n)  # ~ +-20 km in latitude
    lon = LON0 + rng.uniform(-0.25, 0.25, n)  # ~ +-20 km in longitude at this latitude
    alt = ALT0 + rng.uniform(-1000.0, 1000.0, n)

    east, north, _up = geodetic_to_enu(lat, lon, alt, LAT0, LON0, ALT0)
    # z is the trajectory's own vertical coordinate -- the same `alt` fed into the
    # forward projection, exactly as soaring.analysis.preproc.enu.to_local_frame uses
    # it (never the rotation's "up").
    lat_est, lon_est = enu_to_geodetic(east, north, alt, FRAME)

    m_per_deg_lat = 111_320.0
    m_per_deg_lon = m_per_deg_lat * np.cos(np.radians(LAT0))
    err_m = np.hypot((lat_est - lat) * m_per_deg_lat, (lon_est - lon) * m_per_deg_lon)
    assert err_m.max() < 1.0


def test_a_raw_and_cleaned_pair_projected_from_the_same_geographic_point_agree():
    # The overlay guarantee this function exists for: a point common to both the raw
    # and cleaned trajectories must land on the same (lat, lon) whichever direction it
    # is reached from.
    lat, lon, alt = 45.02, 7.03, 1450.0
    east, north, _up = geodetic_to_enu(lat, lon, alt, LAT0, LON0, ALT0)
    lat_back, lon_back = enu_to_geodetic(
        np.array([east]), np.array([north]), np.array([alt]), FRAME
    )
    assert lat_back[0] == pytest.approx(lat, abs=1e-6)
    assert lon_back[0] == pytest.approx(lon, abs=1e-6)
