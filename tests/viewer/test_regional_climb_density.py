"""Regional maps retain plane crossings and the viewer's native continuity."""

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from soaring.viewer.data import phases_on_cleaned_fixes
from soaring.viewer.thermal_geometry import ThermalCell, climb_edges, plane_intersections
from soaring.viewer.thermal_store import EDGE_COLUMNS


path = Path(__file__).resolve().parents[2] / "presentations/offsite2026/render_regional_climb_density.py"
spec = importlib.util.spec_from_file_location("regional_climb_density", path)
regional = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = regional
spec.loader.exec_module(regional)


def test_one_flight_contributes_at_every_plane_in_same_bin():
    # One continuous climb wholly inside one horizontal kilometre square.
    edges = np.array([[100, 100, 5, 0, 200, 200, 505, 100]], dtype=float)
    points = regional.crossing_points(edges)
    assert len(points) == 50
    assert len(np.unique(np.floor(points[:, 1:3] / 1000), axis=0)) == 1


def test_regional_stack_matches_individual_viewer_planes():
    # Non-grid endpoints, shared vertices, repeated up/down crossings, a gap,
    # an isolated terminal vertex, and a coplanar edge.
    edges = np.array([
        [100, 100, 3, 0, 110, 110, 20, 10],
        [110, 110, 20, 10, 120, 120, 35, 20],
        [120, 120, 35, 20, 130, 130, 10, 30],
        [150, 150, 10, 40, 160, 160, 20, 50],
        [180, 180, 30, 60, 190, 190, 30, 70],
    ], dtype=float)
    frame = pd.DataFrame(edges, columns=EDGE_COLUMNS)
    frame["flight_id"], frame["discipline"] = "one", "paragliders"
    cell = ThermalCell(0, 0, "Plains", 1, 1, 0, 40)
    pooled = regional.crossing_points(edges)
    for level in range(5):
        expected = plane_intersections(frame, cell, level * 10, -np.inf, np.inf)
        np.testing.assert_allclose(
            pooled[pooled[:, 0] == level, 1:], expected[["x", "y", "utc"]].to_numpy()
        )


def test_archived_intervals_match_viewer_native_phase_mapping():
    # Half-open phase cells, missing native fixes, and a preprocessing split.
    times = np.array([0, 5, 10, 15, 20, 25, 30, 35, 55, 60, 65, 70], dtype=float)
    flight = pd.DataFrame({
        "t": times, "E": times, "N": times * .2, "z": 105 + times * 2,
        "segment_id": [1] * 10 + [2] * 2,
    })
    decisions = pd.DataFrame({
        "segment_id": [1] * 7 + [2], "t": [0, 10, 20, 30, 40, 50, 60, 70],
        "phase": ["search", "climb", "climb", "search", "climb", "climb", "climb", "climb"],
    })
    runs = pd.DataFrame({
        "segment_id": [1, 1, 2], "t_start": [5, 35, 65], "t_end": [25, 65, 75],
    })
    origin = {"lat0": 45., "lon0": 6., "alt0": 100.}
    actual = regional.native_climb_edges(flight, runs, origin)
    labelled = phases_on_cleaned_fixes(flight, decisions, decision_step_s=10)
    for key, value in origin.items():
        labelled[key] = value
    labelled["x"], labelled["y"] = regional.to_lambert(labelled)
    labelled["utc"] = labelled.t
    bounds = (-np.inf, -np.inf, np.inf, np.inf)
    cell = regional.RegionalPlanes(0, 1000, bounds)
    expected = climb_edges(labelled, cell).to_numpy()
    np.testing.assert_allclose(actual, expected)
    assert list(zip(actual[:, 3], actual[:, 7])) == [(5, 10), (10, 15), (15, 20), (55, 60), (65, 70)]
