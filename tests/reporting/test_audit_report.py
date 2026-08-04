"""The reductions in audit_msd_report.py that carry a number into the thesis."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_msd_report", _ROOT / "scripts" / "reporting" / "audit_msd_report.py"
)
amr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(amr)


def test_the_departure_time_is_read_inside_the_cell_not_at_its_edge():
    """A threshold crossing snapped to the lag grid is never early and always a bit late.

    The grid is logarithmic at about thirteen per cent a step, so reading the crossing with
    an argmax biased the reported departure by of order two hundred seconds at the values
    this archive shows -- on a number Chapter 3 sets beside the peak of the local slope, at
    a separation of the same order. Here the answer is known exactly: a radius growing as a
    pure power law crosses its threshold at a time the interpolation must return.
    """
    lags = np.geomspace(1.0, 43200.0, 90)
    truth = 1723.0
    # r(t) = 5000 * (t / truth)^0.8 crosses 5000 m exactly at t = truth.
    radius = 5000.0 * (lags / truth) ** 0.8
    times, leaves, early = amr.departure_times(lags, radius[None, :], 5000.0)

    assert leaves.all()
    assert early == 0.0
    assert times[0] == pytest.approx(truth, rel=1e-6)

    # And the snapped reading, which is what it replaced, is late by the better part of a cell.
    snapped = lags[(radius > 5000.0).argmax()]
    assert snapped > truth
    assert snapped / truth > 1.05


def test_flights_that_never_reach_the_radius_are_excluded_not_defaulted():
    lags = np.geomspace(1.0, 1000.0, 40)
    near = np.full((3, lags.size), 100.0)
    far = 5000.0 * (lags / 500.0)
    radius = np.vstack([near, far[None, :]])
    times, leaves, _ = amr.departure_times(lags, radius, 4000.0)
    assert leaves.tolist() == [False, False, False, True]
    assert times.size == 1


def test_a_flight_already_outside_at_the_first_lag_is_counted_as_such():
    """No cell brackets its crossing, so it is reported at the grid's own start and flagged."""
    lags = np.geomspace(10.0, 1000.0, 30)
    radius = np.full((1, lags.size), 9000.0)
    times, leaves, early = amr.departure_times(lags, radius, 5000.0)
    assert leaves.all()
    assert times[0] == pytest.approx(lags[0])
    assert early == 1.0
