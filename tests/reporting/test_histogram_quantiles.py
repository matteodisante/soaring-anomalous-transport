"""Histogram quantiles use bin edges and preserve symmetric distributions."""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables.propagator import linear_histogram_quantiles


@pytest.mark.parametrize("probability", [0.1, 0.25, 0.5, 0.75, 0.9])
def test_a_uniform_histogram_returns_its_own_quantiles(probability):
    """On a uniform distribution the quantile is the probability, at any bin width."""
    edges = np.linspace(0.0, 1.0, 21)
    counts = np.full(20, 1000.0)
    got = linear_histogram_quantiles(counts, edges, [probability])[0]
    assert got == pytest.approx(probability, abs=1e-9)


def test_a_symmetric_histogram_has_its_median_at_the_centre():
    """The vertical grid the chapter uses, on a distribution centred on zero.

    The failing version returned -0.0625 here -- half a bin -- and the band it produced
    looked symmetric only because both ends were displaced by the same amount.
    """
    edges = np.linspace(-15.0, 15.0, 241)
    centres = 0.5 * (edges[:-1] + edges[1:])
    counts = np.exp(-0.5 * (centres / 2.0) ** 2)
    low, median, high = linear_histogram_quantiles(counts, edges, [0.1, 0.5, 0.9])
    assert median == pytest.approx(0.0, abs=1e-9)
    assert low == pytest.approx(-high, abs=1e-9)


def test_an_empty_histogram_is_nan_rather_than_a_number():
    edges = np.linspace(0.0, 1.0, 11)
    assert all(
        np.isnan(v) for v in linear_histogram_quantiles(np.zeros(10), edges, [0.5])
    )
