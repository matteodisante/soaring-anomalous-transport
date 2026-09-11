"""Paired support and equipment metadata must not change the scientific estimand."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "kinematic_report",
    ROOT
    / "scripts/reporting/ch3_global_transport/generate_kinematic_isotropy_figure.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PRELIM = MODULE.prelim


def test_equipment_labels_do_not_assign_tandem_or_unknown_to_experts():
    classes = ["EN A", "EN B", "EN C", "EN D", "CCC", "tandem / non-certified", None]
    assert MODULE.equipment_group(classes).tolist() == [
        "EN A/B",
        "EN A/B",
        "EN C/D/CCC",
        "EN C/D/CCC",
        "EN C/D/CCC",
        "",
        "",
    ]


def test_component_ratio_uses_identical_finite_flights_and_observed_point(monkeypatch):
    frame = pd.DataFrame(
        {"date": ["2026-09-10"] * 42, "takeoff": [f"site-{i // 3}" for i in range(42)]}
    )
    east = np.arange(1, 43, dtype=float)[:, None] * np.ones((1, 2))
    north = np.ones_like(east)
    north[0, 0] = np.nan
    east[1, 0] = np.nan
    north[2, 0] = (
        100  # Large denominator contribution must retain its paired east value.
    )
    east[:20, 1] = np.nan  # Too few paired flights for this time.
    valid = np.isfinite(east[:, 0]) & np.isfinite(north[:, 0])
    expected = np.sum(east[valid, 0] ** 2) / np.sum(north[valid, 0] ** 2)
    point = PRELIM.directional_ratio(east, north, frame)
    np.testing.assert_allclose(point[0], expected)
    assert np.isnan(point[1])
    monkeypatch.setattr(PRELIM, "ISO_BOOT_RESAMPLES", 19)
    lo, plotted, hi = PRELIM.iso_ratio_band(east, north, frame)
    np.testing.assert_allclose(plotted, point)
    assert np.isfinite(lo[0]) and np.isfinite(hi[0])
    assert np.isnan(lo[1]) and np.isnan(hi[1])


def test_cluster_support_counts_groups_with_at_least_one_paired_flight():
    frame = pd.DataFrame(
        {"date": ["2026-09-10"] * 6, "takeoff": ["a", "a", "b", "b", "c", "c"]}
    )
    east = np.ones((6, 2))
    north = np.ones_like(east)
    east[2:4, 0] = np.nan
    north[4:, 0] = np.nan
    counts, groups = PRELIM.iso_support(east, north, frame)
    np.testing.assert_array_equal(counts, [2, 6])
    np.testing.assert_array_equal(groups, [1, 3])
