"""Flight weighting and class standardization checked against explicit populations."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "duration_equipment",
    ROOT / "scripts/reporting/ch3_global_transport/generate_duration_equipment.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_flight_curve_pools_admissible_origins_and_never_counts_a_gap():
    # Two disjoint straight segments in flight a: squared increments are 1 and 9.
    # Directly enumerate each segment's origins to form the expected flight value.
    segments = pd.DataFrame(
        {
            "flight_id": ["a", "a", "b", "c"],
            "dt_s": [1.0, 1.0, 1.0, 20.0],
            "n_fixes": [8, 12, 8, 12],
            "total_retained_duration_s": [18.0, 18.0, 7.0, 220.0],
        }
    )
    samples = np.array([[1.0, np.nan], [9.0, 225.0], [4.0, np.nan], [100.0, 200.0]])
    frame, result = MODULE.flight_curves(samples, segments, np.array([1.0, 5.0]))
    expected = np.r_[
        np.diff(np.arange(8.0)) ** 2, np.diff(3 * np.arange(12.0)) ** 2
    ].mean()
    assert frame.flight_id.tolist() == ["a", "b"]
    np.testing.assert_allclose(result[0], [expected, 225.0])
    assert result[1, 0] == 4 and np.isnan(result[1, 1])
    # Between flights the means have equal weight, regardless of flight a's 18 origins.
    mean, count = MODULE.mean_curve(result, [True, True])
    np.testing.assert_allclose(mean, [(expected + 4) / 2, 225.0])
    np.testing.assert_array_equal(count, [2, 1])


def test_composition_control_removes_a_pure_mixture_change(monkeypatch):
    monkeypatch.setattr(MODULE, "MIN_FLIGHTS", 1)
    classes = list(MODULE.EQUIPMENT_CLASSES)
    labels = [classes[0]] * 4 + [classes[1]] * 2 + [""]
    durations = [
        18000.0,
        2000.0,
        2000.0,
        2000.0,
        18000.0,
        18000.0,
        18000.0,
    ]
    frame = pd.DataFrame({"equipment": labels, "total_retained_duration_s": durations})
    values = np.array(
        [{"": 1000.0, classes[0]: 1.0, classes[1]: 9.0}[x] for x in labels]
    )[:, None] * np.array([[1.0, 2.0]])
    reference, cohorts = MODULE.composition_control(values, frame)
    np.testing.assert_allclose(reference, [4 / 6, 2 / 6])
    np.testing.assert_allclose(cohorts[0]["standardized"], cohorts[-1]["standardized"])
    assert np.all(cohorts[-1]["known_class_raw"] > cohorts[0]["known_class_raw"])
    np.testing.assert_allclose(
        cohorts[0]["known_class_raw"], [(4 + 18) / 6, 2 * (4 + 18) / 6]
    )
    assert cohorts[0]["other_flights"] == 1
    # Missing support in one class forbids the fixed mixture at that lag.
    values[np.array(labels) == classes[1], 1] = np.nan
    _, incomplete = MODULE.composition_control(values, frame)
    assert np.isnan(incomplete[-1]["standardized"][1])


def test_noncontiguous_or_missing_segment_identity_fails():
    frame = pd.DataFrame(
        {
            "flight_id": ["a", "b", "a"],
            "dt_s": [1] * 3,
            "n_fixes": [8] * 3,
            "total_retained_duration_s": [7] * 3,
        }
    )
    with pytest.raises(ValueError, match="contiguous"):
        MODULE.flight_curves(np.ones((3, 1)), frame, [1.0])
    with pytest.raises(ValueError, match="rows differ"):
        MODULE.flight_curves(np.ones((2, 1)), frame, [1.0])
