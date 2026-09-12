"""Check height interpolation and interrupted-flight altitude support."""

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.observables.wind_reference import (
    wind_at_height,
    window_altitude_means,
)


def test_vertical_interpolation_recovers_linear_shear_on_moving_levels():
    height = np.array(
        [[[0, 800, 1600], [100, 900, 1800]], [[50, 750, 1400], [200, 850, 1500]]],
        dtype=float,
    )
    u = 2 + 0.003 * height
    v = -1 + 0.001 * height
    east, north = wind_at_height(u, v, height, 1000)
    np.testing.assert_allclose(east, 5)
    np.testing.assert_allclose(north, 0, atol=1e-15)


def test_wind_interpolation_acts_on_vectors_across_angle_wrap():
    u, v = wind_at_height([-1, -1], [0.1, -0.1], [500, 1500], 1000)
    assert u == -1 and v == 0


def test_vertical_extrapolation_is_rejected():
    with pytest.raises(ValueError, match="not bracketed"):
        wind_at_height([1, 2], [0, 1], [500, 1000], 1100)


def test_below_ground_bracketing_is_rejected():
    with pytest.raises(ValueError, match="below"):
        wind_at_height([1, 2], [0, 1], [500, 1500], 1000, surface_height_m=600)


def test_unknown_surface_cannot_pass_above_ground_check():
    with pytest.raises(ValueError, match="surface heights must be finite"):
        wind_at_height([1, 2], [0, 1], [500, 1500], 1000, surface_height_m=np.nan)


def test_disconnected_segments_do_not_add_an_altitude_bridge():
    row = {
        "segment_ids": [0, 2],
        "segments": [[0, 3], [3, 6]],
        "segment_start_s": [0, 100],
        "length": 6,
    }
    fixes = pd.DataFrame(
        {
            "segment_id": [0, 0, 0, 2, 2, 2],
            "t": [0, 10, 20, 100, 110, 120],
            "z": [100, 200, 300, 1000, 1100, 1200],
        }
    )
    np.testing.assert_allclose(window_altitude_means(row, fixes, lag_s=20), [200, 1100])


def test_altitude_grid_cannot_extrapolate_missing_support():
    row = {
        "segment_ids": [0],
        "segments": [[0, 3]],
        "segment_start_s": [0],
        "length": 3,
    }
    fixes = pd.DataFrame(
        {"segment_id": [0, 0, 0], "t": [1, 10, 20], "z": [100, 200, 300]}
    )
    with pytest.raises(ValueError, match="outside"):
        window_altitude_means(row, fixes, lag_s=20)
