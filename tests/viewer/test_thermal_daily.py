"""Saved height lattice agrees with native edge intersections and civil time."""

import numpy as np
import pandas as pd

from soaring.viewer.thermal_daily import height_levels, lattice_points, local_bounds
from soaring.viewer.thermal_geometry import ThermalCell, plane_intersections
from soaring.viewer.thermal_store import EDGE_COLUMNS


def test_lattice_matches_native_edges():
    cell = ThermalCell(0, 0, "Plains", 1, 1, 100, 153)
    # Ascending, descending, terminal/shared vertices, coplanar, and spatial cuts.
    values = np.array(
        [
            [0, 0, 100, 0, 100, 100, 130, 30],
            [100, 100, 130, 30, 6000, 100, 120, 60],
            [0, 100, 120, 70, 100, 100, 120, 80],
            [100, 100, 120, 80, 100, 100, 153, 90],
            [-100, 100, 99, 100, 5100, 100, 155, 110],
        ],
        dtype=float,
    )
    frame = pd.DataFrame(values, columns=EDGE_COLUMNS)
    frame["flight_id"], frame["discipline"] = "one", "paragliders"
    prepared = lattice_points(values, cell)
    for i, z in enumerate(height_levels(cell.max_agl_m)):
        expected = plane_intersections(frame, cell, z, -np.inf, np.inf)
        np.testing.assert_allclose(
            prepared[prepared[:, 0] == i, 1:], expected[["x", "y", "utc"]].to_numpy()
        )


def test_step_and_dst():
    assert height_levels(53, 20).tolist() == [0, 20, 40, 53]
    assert height_levels(50, 10).tolist() == [0, 10, 20, 30, 40, 50]
    assert np.diff(local_bounds("2026-03-29"))[0] == 23 * 3600
    assert np.diff(local_bounds("2026-10-25"))[0] == 25 * 3600
    assert np.diff(local_bounds("2026-07-01", (11, 15)))[0] == 4 * 3600
