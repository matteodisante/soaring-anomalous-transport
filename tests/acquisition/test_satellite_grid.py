"""Tests for the satellite crop configuration and window geometry."""

import numpy as np
import pytest

# Satellite dependencies are opt-in; CI runs with --group satellite.
pytest.importorskip("blosc2")
pytest.importorskip("pyproj")
pytest.importorskip("requests")

from soaring.acquisition.satellite.config import load_config
from soaring.acquisition.satellite.grid import Axis, pixel_box, window_outline
from soaring.acquisition.satellite.ocf import SEVIRI_RSS


def test_repo_config_has_the_twelve_cells():
    cfg = load_config()
    assert len(cfg.cells) == 12
    assert cfg.window.half_size_m == 5000
    assert cfg.centre(cfg.cells[0]) == (89.5 * 5000, 1375.5 * 5000)


def test_axis_from_values_and_index():
    axis = Axis.from_values(np.array([10.0, 13.0, 16.0, 19.0]))
    assert (axis.origin, axis.step, axis.size) == (10.0, 3.0, 4)
    assert axis.index(np.array([10.4, 14.6, 19.0])).tolist() == [0, 2, 3]
    assert axis.values(1, 3).tolist() == [13.0, 16.0]
    with pytest.raises(ValueError):
        Axis.from_values(np.array([0.0, 1.0, 3.0]))


def test_window_box_holds_the_cell_and_reaches_further_north():
    cfg = load_config()
    cell = cfg.cells[9]  # 190/1306, near Annecy
    x = Axis(-5567248.07, 3000.403, 3712)
    y = Axis(1393687.27, 3000.403, 1392)
    box = pixel_box(SEVIRI_RSS, *window_outline(cfg, cell), x, y)
    import pyproj

    lon, lat = pyproj.Transformer.from_crs(
        "EPSG:2154", "EPSG:4326", always_xy=True
    ).transform(*cfg.centre(cell))
    cx, cy = SEVIRI_RSS(lon, lat)
    col, row = int(x.index(cx)), int(y.index(cy))
    assert box.r0 <= row < box.r1 and box.c0 <= col < box.c1
    assert box.r1 - 1 - row > row - box.r0  # the parallax margin is on the north side
    assert 3 <= box.c1 - box.c0 <= 8 and 3 <= box.r1 - box.r0 <= 8
