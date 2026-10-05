"""The 3D cloud uses the correct cell, altitude datum, saved lattice and DEM."""

import hashlib
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from soaring.viewer.thermal_3d import (
    cell_label,
    load_scene,
    points_every_20m,
    read_surface,
)
from soaring.viewer.thermal_geometry import ThermalCell
from soaring.viewer.thermal_store import CancelledError, PlaneData


@pytest.fixture
def cell():
    return ThermalCell(193, 1309, "High mountains", 100, 5, 1550.25, 1585.25)


@pytest.fixture
def points(cell):
    west, south, east, _ = cell.bounds
    return pd.DataFrame(
        {
            "level": [0, 1, 2, 3, 4, 2, 2],
            "x": [west + 100] * 6 + [east],
            "y": [south + 200] * 7,
            "utc": [100, 110, 120, 130, 140, 201, 150],
            "discipline": ["paragliders", "paragliders", "hang_gliders"]
            + ["paragliders"] * 4,
            "flight_id": ["a"] * 7,
        }
    )


def test_rank_uses_vilpellet_climbs_and_stable_cell_ties(cell):
    cells = [cell, replace(cell, ix=192, flights=1), replace(cell, ix=194, flights=900)]
    store = SimpleNamespace(
        has_climb_ranking=True,
        cells=lambda: cells,
        activity_counts={
            (193, 1309): {"climb_runs": 10},
            (192, 1309): {"climb_runs": 10},
            (194, 1309): {"climb_runs": 5},
        },
    )
    assert cell_label(store, cell) == "High mountains #2"
    assert cell_label(store, cells[1]) == "High mountains #1"
    with pytest.raises(ValueError, match="missing or changed"):
        cell_label(store, replace(cell, ground_m=cell.ground_m + 1))
    store.has_climb_ranking = False
    with pytest.raises(ValueError, match="climb-ranked"):
        cell_label(store, cell)


def test_20m_levels_exclude_irregular_ceiling_and_keep_absolute_altitude(cell, points):
    original = points.copy()
    xyz, flights = points_every_20m(points, cell, 100, 200)
    np.testing.assert_allclose(xyz, [[-2400, -2300, 1550.25], [-2400, -2300, 1570.25]])
    assert flights == 2  # Same ID in distinct disciplines means distinct flights.
    pd.testing.assert_frame_equal(points, original)
    assert xyz.dtype == np.float32
    empty, flights = points_every_20m(points, cell, 300, 400)
    assert empty.shape == (0, 3) and flights == 0


def test_regular_ceiling_is_kept_and_invalid_level_is_rejected(cell, points):
    exact = replace(cell, max_alt_m=cell.ground_m + 40)
    xyz, _ = points_every_20m(points, exact, 100, 200)
    assert xyz[:, 2].tolist() == [1550.25, 1570.25, 1590.25]
    points.loc[0, "level"] = 999
    with pytest.raises(ValueError, match="Invalid saved"):
        points_every_20m(points, cell, 100, 200)


@pytest.fixture
def raster_store(tmp_path, cell):
    z = (1500 + np.arange(200)[:, None] + np.arange(200)[None, :] / 2).astype("f4")
    cell = replace(cell, ground_m=float(z.mean(dtype=float)))
    path = tmp_path / "exploration/terrain/ign-terrain-193-1309.tif"
    path.parent.mkdir(parents=True)
    Image.fromarray(z).save(path)
    reference = {
        "response_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bounds_epsg2154": cell.bounds,
        "raster_bounds_epsg2154": cell.bounds,
    }
    store = SimpleNamespace(
        path=tmp_path / "thermal-planes.sqlite3",
        terrain_reference=lambda _: reference,
    )
    return store, cell, z, path, reference


def test_dem_rows_become_south_to_north_and_surface_covers_exact_cell(raster_store):
    store, cell, original, _, _ = raster_store
    x, y, terrain, _ = read_surface(store, cell)
    assert len(x) == len(y) == 202
    assert (x[0], x[-1], y[0], y[-1]) == (-2500, 2500, -2500, 2500)
    assert x[1] == y[1] == -2487.5
    np.testing.assert_array_equal(terrain[1:-1, 1:-1], original[::-1])
    assert terrain[0, 0] == original[-1, 0]
    assert terrain[-1, -1] == original[0, -1]


def test_changed_dem_and_inconsistent_mean_are_rejected(raster_store):
    store, cell, _, path, _ = raster_store
    with pytest.raises(ValueError, match="DEM mean"):
        read_surface(store, replace(cell, ground_m=cell.ground_m + 1))
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="missing or changed"):
        read_surface(store, cell)


@pytest.mark.parametrize(
    "terrain", ["Plains", "Hills", "Low mountains", "High mountains"]
)
def test_scene_reads_selected_cell_vilpellet_and_requested_dates(
    cell, points, monkeypatch, tmp_path, terrain
):
    cell = replace(cell, terrain=terrain)
    calls = []
    plane = PlaneData(pd.DataFrame(), 4, 3, 1, 1, 2, points=points)

    def read(selected, start, end, source, **kw):
        calls.append((selected, start, end, source))
        return plane

    store = SimpleNamespace(
        has_points=True,
        has_climb_ranking=True,
        path=tmp_path / "snapshot",
        cells=lambda: [replace(cell, ix=192, terrain="High mountains"), cell],
        activity_counts={
            (192, 1309): {"climb_runs": 20},
            (193, 1309): {"climb_runs": 10},
        },
        read_plane=read,
    )
    monkeypatch.setattr(
        "soaring.viewer.thermal_3d.read_surface",
        lambda *args: (np.arange(2), np.arange(2), np.ones((2, 2)), {}),
    )
    scene = load_scene(store, cell, 100, 200)
    assert calls == [(cell, 100, 200, "vilpellet")]
    assert scene.cell == cell
    assert scene.label == f"{terrain} #{2 if terrain == 'High mountains' else 1}"
    assert len(scene.points) == 2 and scene.contributing_flights == 2
    assert scene.climb_runs == 10 and scene.unavailable_flights == 1
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        load_scene(store, cell, 100, 200, cancel=cancel)
    assert len(calls) == 1
