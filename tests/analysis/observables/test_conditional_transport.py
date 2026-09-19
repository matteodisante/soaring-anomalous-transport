"""Conditional comparisons preserve flight identity and explicit exclusions."""

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.observables.conditional_transport import strata
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means, cluster_draws
from soaring.analysis.observables.fixed_transport import log_fit
from soaring.analysis.regions import REGIONAL_BOXES, region_box_masks


def test_equipment_and_terrain_intersections_keep_order_and_exclude_unknowns():
    frame = pd.DataFrame(
        {
            "wing_class": [
                "C ou 2",
                "D ou 2-3",
                "CIVL Competition Class",
                "Biplace",
                "0",
            ],
            "task": ["open", "closed", "unknown", "open", None],
            "altitude_band": [
                "Low mountains",
                "High mountains",
                "Plains",
                "Hills",
                None,
            ],
            "lon0": [6, 1, 1, 4, np.nan],
            "lat0": [45, 43, 49, 49, np.nan],
        },
        index=[19, 2, 7, 4, 100],
    )
    groups = strata(frame)
    assert groups["beginners"].tolist() == [True, False, False, False, False]
    assert groups["experts"].tolist() == [False, True, True, False, False]
    assert groups["alps"].tolist() == [True, False, False, False, False]
    assert groups["pyrenees"].tolist() == [False, True, False, False, False]
    assert groups["channel_coast"].tolist() == [False, False, True, False, False]
    assert groups["champagne_lorraine"].tolist() == [
        False,
        False,
        False,
        True,
        False,
    ]
    assert not groups["open"][-1]
    assert not groups["lowlands"][-1]
    assert frame.index.tolist() == [19, 2, 7, 4, 100]


def test_region_selection_requires_appropriate_terrain_within_box():
    frame = pd.DataFrame(
        {
            "wing_class": ["A ou 1"] * 4,
            "task": ["open"] * 4,
            "altitude_band": ["Plains", "High mountains", "Hills", "Low mountains"],
            "lon0": [6, 6, 1, 1],
            "lat0": [45, 45, 49, 49],
        }
    )
    groups = strata(frame)
    assert groups["alps"].tolist() == [False, True, False, False]
    assert groups["channel_coast"].tolist() == [False, False, True, False]


def test_pruned_cluster_columns_reproduce_paired_draws_and_population_h():
    labels = np.array([0, 1, 1, 2, 3, 3, 3])
    draws = cluster_draws(labels, 50)
    lags = np.array([10, 100, 1000])
    values = np.arange(1, 8)[:, None] * lags[None, :] ** 1.6
    selected = np.array([False, True, True, False, True, True, True])
    occupied, local = np.unique(labels[selected], return_inverse=True)
    full = bootstrap_means(values[selected], labels[selected], draws)
    pruned = bootstrap_means(values[selected], local, draws[:, occupied])
    np.testing.assert_allclose(pruned, full, equal_nan=True)
    np.testing.assert_allclose(pruned[0], values[selected].mean(axis=0))
    h = log_fit(lags, pruned)["slope"] / 2
    np.testing.assert_allclose(h[np.isfinite(h)], 0.8)


@pytest.mark.parametrize("name", list(REGIONAL_BOXES))
def test_each_region_keeps_only_its_setting_and_excludes_missing_altitude(name):
    west, east, south, north = REGIONAL_BOXES[name]
    frame = pd.DataFrame(
        {
            "wing_class": ["A ou 1"] * 5,
            "task": ["open"] * 5,
            "altitude_band": [
                "Plains",
                "Hills",
                "Low mountains",
                "High mountains",
                None,
            ],
            "lon0": [(west + east) / 2] * 5,
            "lat0": [(south + north) / 2] * 5,
        }
    )
    assert region_box_masks(frame)[name].all()
    key = name.lower().replace(" ", "_").replace("-", "_")
    expected = (
        [False, False, True, True, False]
        if name in ("Alps", "Pyrenees")
        else [True, True, False, False, False]
    )
    assert strata(frame)[key].tolist() == expected
    corners = pd.DataFrame(
        {
            "lon0": [west, east, west - 0.001, east, np.nan],
            "lat0": [south, north, south, north + 0.001, south],
        }
    )
    assert region_box_masks(corners)[name].tolist() == [True, True, False, False, False]
