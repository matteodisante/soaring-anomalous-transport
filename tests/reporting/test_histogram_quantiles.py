"""The quantile of a histogram has to be the quantile, not half a bin below it.

Twelve numbers printed in Chapter 3 -- the turning-angle median, three speed percentiles and
a decile band of vertical velocity, for both disciplines -- came out of one call. The
estimator paired ``cumsum(counts)``, which is the mass below each bin's *upper edge*, with
the bin *centres*, so every quantile was low by exactly half a bin. There is no symptom: the
numbers stay ordered, stay inside the grid, and move smoothly. Only an answer known in
advance catches it, which is what these tests are.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    """Import the generator by path: ``scripts/`` is not a package."""
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    path = ROOT / "scripts" / "reporting" / "generate_propagator_figure.py"
    spec = importlib.util.spec_from_file_location("_propfig", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("probability", [0.1, 0.25, 0.5, 0.75, 0.9])
def test_a_uniform_histogram_returns_its_own_quantiles(probability):
    """On a uniform distribution the quantile is the probability, at any bin width."""
    module = _load()
    edges = np.linspace(0.0, 1.0, 21)
    counts = np.full(20, 1000.0)
    got = module._from_histogram(counts, edges, [probability])[0]
    assert got == pytest.approx(probability, abs=1e-9)


def test_a_symmetric_histogram_has_its_median_at_the_centre():
    """The vertical grid the chapter uses, on a distribution centred on zero.

    The failing version returned -0.0625 here -- half a bin -- and the band it produced
    looked symmetric only because both ends were displaced by the same amount.
    """
    module = _load()
    edges = np.linspace(-15.0, 15.0, 241)
    centres = 0.5 * (edges[:-1] + edges[1:])
    counts = np.exp(-0.5 * (centres / 2.0) ** 2)
    low, median, high = module._from_histogram(counts, edges, [0.1, 0.5, 0.9])
    assert median == pytest.approx(0.0, abs=1e-9)
    assert low == pytest.approx(-high, abs=1e-9)


def test_an_empty_histogram_is_nan_rather_than_a_number():
    module = _load()
    edges = np.linspace(0.0, 1.0, 11)
    assert all(np.isnan(v) for v in module._from_histogram(np.zeros(10), edges, [0.5]))
