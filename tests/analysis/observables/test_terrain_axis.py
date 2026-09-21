import itertools

import numpy as np
import pytest

from soaring.analysis.observables.terrain_axis import (
    BOX_RULES,
    axis_spread,
    chain_bend,
    footprint_axis,
    select_boxes,
)


def ridge(angle_deg, half_width_km=4.0):
    lat, lon = np.meshgrid(
        np.linspace(45.0, 46.0, 201), np.linspace(6.0, 7.5, 301), indexing="ij"
    )
    e = (lon - 6.75) * 111.32 * np.cos(np.deg2rad(45.5))
    n = (lat - 45.5) * 110.57
    a = np.deg2rad(angle_deg)
    across = -e * np.sin(a) + n * np.cos(a)
    along = e * np.cos(a) + n * np.sin(a)
    height = np.where((abs(across) < half_width_km) & (abs(along) < 40), 2500.0, 300.0)
    return lon, lat, height


@pytest.mark.parametrize("angle", [20.0, 65.0, 130.0])
def test_a_synthetic_ridge_returns_its_direction(angle):
    lon, lat, height = ridge(angle)
    out = footprint_axis(lon, lat, height, (6.0, 7.5, 45.0, 46.0), 2000)
    diff = abs((out["angle_deg"] - angle + 90) % 180 - 90)
    assert diff < 1.5
    assert out["ratio"] > 10


def test_terrain_below_the_threshold_and_outside_the_box_is_ignored():
    lon, lat, height = ridge(65.0)
    inside = footprint_axis(lon, lat, height, (6.0, 7.5, 45.0, 46.0), 2000)
    assert inside["cells"] == (height >= 2000).sum()
    small = footprint_axis(lon, lat, height, (6.5, 7.0, 45.3, 45.7), 2000)
    assert small["cells"] < inside["cells"]
    with pytest.raises(ValueError):
        footprint_axis(lon, lat, height, (6.0, 7.5, 45.0, 46.0), 5000)


def test_axis_spread_is_zero_for_equal_axes_and_wraps_at_180():
    assert axis_spread([40.0, 40.0]) == pytest.approx(0)
    assert axis_spread([179.0, 1.0]) == pytest.approx(1.0)


def bent_grid(bent):
    lat, lon = np.meshgrid(
        np.linspace(45.0, 46.0, 201), np.linspace(6.0, 7.5, 301), indexing="ij"
    )
    e = (lon - 6.75) * 111.32 * np.cos(np.deg2rad(45.5))
    n = (lat - 45.5) * 110.57
    along = e * np.cos(np.deg2rad(20.0)) + n * np.sin(np.deg2rad(20.0))
    turn = np.where(along > 0, np.deg2rad(70.0 if bent else 0.0), 0.0)
    across = -e * np.sin(np.deg2rad(20.0) + turn) + n * np.cos(np.deg2rad(20.0) + turn)
    return lon, lat, np.where((abs(across) < 5) & (abs(along) < 45), 2500.0, 300.0)


def test_a_turning_ridge_has_a_larger_bend_than_a_straight_one():
    box = (6.0, 7.5, 45.0, 46.0)
    straight = chain_bend(*bent_grid(False), box, 2000)
    turned = chain_bend(*bent_grid(True), box, 2000)
    assert straight < 5
    assert turned > 20


def test_selection_keeps_the_straight_box_and_returns_disjoint_boxes():
    lon, lat, height = bent_grid(False)
    rules = dict(BOX_RULES, min_cells=100, min_area_deg2=0.5, grid_step_deg=0.25)
    chosen = select_boxes(lon, lat, height, (6.0, 7.5, 45.0, 46.0), rules=rules)
    assert chosen
    for a, b in itertools.combinations(chosen, 2):
        assert not (
            min(a["box"][1], b["box"][1]) > max(a["box"][0], b["box"][0])
            and min(a["box"][3], b["box"][3]) > max(a["box"][2], b["box"][2])
        )
    assert all(abs((r["angle_deg"] - 20 + 90) % 180 - 90) < 3 for r in chosen)
