"""Fixed cell geometry, all-year months and unchanged flight weights."""

import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer

from soaring.analysis.observables.fixed_bootstrap import bootstrap_means
from soaring.analysis.observables.grid_bootstrap import (
    cell_membership,
    grid_season_labels,
    group_composition,
    project_launches,
)


def flight_frame():
    """Provide repeated positions across years, months and altitude classes."""
    return pd.DataFrame(
        {
            "lat0": [45.0] * 5,
            "lon0": [5.0] * 5,
            "alt0": [1000.0, 1000.0, 1000.0, 1600.0, 1000.0],
            "date": [
                "2005-07-03",
                "2020-07-14",
                "2020-08-01",
                "2020-07-14",
                "2020-12-31",
            ],
        }
    )


def test_same_month_across_years_but_distinct_months_and_terrain():
    frame = flight_frame()
    cells = cell_membership(project_launches(frame))
    labels, missing = grid_season_labels(frame, cells)
    assert not missing.any()
    assert labels[0] == labels[1]
    assert len(set(labels[[0, 2, 3, 4]])) == 4
    support = group_composition(frame, labels, np.ones(5, dtype=bool))
    assert support["groups_with_multiple_years"] == 1
    assert support["singleton_groups"] == 3
    # Group means must not acquire equal weight when group sizes differ.
    means = bootstrap_means(
        np.array([[1.0], [3.0], [10.0], [20.0], [30.0]]),
        labels,
        np.ones((1, labels.max() + 1)),
    )
    assert means[0, 0] == pytest.approx(64 / 5)


def test_half_open_boundaries_and_maximum_cell_side():
    p = pd.DataFrame(
        {
            "epsg": [32631] * 5,
            "easting_m": [-1.0, 0.0, 49999.999, 50000.0, 100000.0],
            "northing_m": [0.0] * 5,
        }
    )
    cells = cell_membership(p)
    np.testing.assert_array_equal(cells.ix, [-1, 0, 0, 1, 2])
    np.testing.assert_array_equal(cells.x_max_m - cells.x_min_m, 50000)
    with pytest.raises(ValueError, match="at most 50"):
        cell_membership(p, 100)
    with pytest.raises(ValueError):
        cell_membership(p, 50, (50, 0))


def test_nearby_points_across_a_cell_edge_have_different_groups():
    inv = Transformer.from_crs(32631, 4326, always_xy=True)
    lon, lat = inv.transform([499990.0, 500010.0], [5000010.0, 5000010.0])
    f = pd.DataFrame(
        {
            "lat0": lat,
            "lon0": lon,
            "alt0": [1000.0, 1000.0],
            "date": ["2020-07-01"] * 2,
            "takeoff": ["same site"] * 2,
        }
    )
    cells = cell_membership(project_launches(f))
    labels, _ = grid_season_labels(f, cells)
    assert labels[0] != labels[1]
    shifted = cell_membership(project_launches(f), 50, (25, 0))
    labels, _ = grid_season_labels(f, shifted)
    assert labels[0] == labels[1]


def test_assignment_is_independent_of_other_flights_and_input_order():
    f = flight_frame()
    f.loc[4, ["lat0", "lon0"]] = [-30.0, 18.0]
    all_cells = cell_membership(project_launches(f))
    subset = f.iloc[[4, 1]]
    pd.testing.assert_frame_equal(
        all_cells.loc[subset.index], cell_membership(project_launches(subset))
    )
    assert all_cells.epsg.iloc[4] == 32734


def test_utm_zones_hemispheres_and_date_line_are_disjoint_and_canonical():
    f = pd.DataFrame(
        {
            "lat0": [45.0, 45.0, -30.0, 0.0, 0.0],
            "lon0": [5.99, 6.01, 5.99, 180.0, -180.0],
        }
    )
    p = project_launches(f)
    np.testing.assert_array_equal(p.epsg, [32631, 32632, 32731, 32601, 32601])
    np.testing.assert_allclose(p.iloc[3], p.iloc[4])
    with pytest.raises(ValueError, match="UTM domain"):
        project_launches(pd.DataFrame({"lat0": [89.0], "lon0": [5.0]}))


def test_adjacent_month_diagnostic_wraps_december_to_january():
    f = flight_frame().iloc[:3].copy()
    f.date = ["2005-12-01", "2020-01-01", "2020-02-01"]
    cells = cell_membership(project_launches(f))
    labels, _ = grid_season_labels(f, cells, months=2, month_offset=1)
    assert labels[0] == labels[1] != labels[2]


def test_missing_keys_and_inconsistent_archived_altitude_fail_explicitly():
    f = flight_frame()
    cells = cell_membership(project_launches(f))
    f.loc[0, "date"] = "2000-00-00"
    labels, missing = grid_season_labels(f, cells)
    assert missing.tolist() == [True, False, False, False, False]
    assert np.count_nonzero(labels == labels[0]) == 1
    f["altitude_band"] = "Plains"
    with pytest.raises(ValueError, match="disagree"):
        grid_season_labels(f, cells)


def test_exact_altitude_band_boundaries():
    f = pd.DataFrame(
        {
            "lat0": [45.0] * 4,
            "lon0": [5.0] * 4,
            "alt0": [299.9, 300.0, 800.0, 1500.0],
            "date": ["2020-07-01"] * 4,
        }
    )
    cells = cell_membership(project_launches(f))
    labels, _ = grid_season_labels(f, cells)
    assert len(set(labels)) == 4
    pooled, _ = grid_season_labels(f, cells, pool_terrain=True)
    assert len(set(pooled)) == 1
