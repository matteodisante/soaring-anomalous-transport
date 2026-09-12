import importlib.util
from pathlib import Path

import numpy as np
import pytest

PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts/reporting/ch3_global_transport/generate_channel_wind_comparison.py"
)
spec = importlib.util.spec_from_file_location("channel_wind", PATH)
wind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wind)


def test_meteorological_from_directions_give_air_motion_components():
    u, v = wind.components(np.ones(4), [0, 90, 180, 270])
    np.testing.assert_allclose(u, [0, -1, 0, 1], atol=1e-14)
    np.testing.assert_allclose(v, [-1, 0, 1, 0], atol=1e-14)


def test_mean_crossing_north_does_not_become_south():
    u, v = wind.components(np.ones((1, 2)), [[350, 10]])
    result = wind.summarise(u, v, [1])
    assert result["meteorological_from_deg"] == pytest.approx(0)
    assert result["direction_to_from_east_deg"] == pytest.approx(270)
    assert result["axis_deg"] == pytest.approx(90)
    assert result["resultant_fraction"] == pytest.approx(np.cos(np.deg2rad(10)))


def test_cell_weights_act_on_components_before_extracting_the_angle():
    result = wind.summarise(
        np.array([[1.0, 1.0], [0.0, 0.0]]), np.array([[0.0, 0.0], [1.0, 1.0]]), [3, 1]
    )
    assert result["axis_deg"] == pytest.approx(np.rad2deg(np.arctan2(1, 3)))
    assert result["mean_east_ms"] == 0.75
    assert result["mean_north_ms"] == 0.25


def test_exact_cancellation_has_no_defined_mean_direction():
    with pytest.raises(ValueError, match="undefined"):
        wind.summarise(np.array([[1.0, -1.0]]), np.zeros((1, 2)), [1])
