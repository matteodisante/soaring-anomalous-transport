"""Every figure must render from plausible inputs, and from imperfect ones.

The drawing modules had no test at all, and both bugs found in them survived for weeks
because of it: a name the drawing/computing split left unimported, which raised on the
first discipline drawn, and a single non-finite sample in the vertical channel, which
turned a quantile into nan and a bin edge into "arange: cannot compute length". Neither
needs a real archive to catch -- only a call.

These are smoke tests. They assert that a figure is produced, not what it looks like: the
numbers behind every panel are the estimators' and are tested where those live.
"""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from soaring.analysis.config import load_preproc_config
from soaring.analysis.figures.preproc import (
    make_fixlevel_diagnostics_figure,
    make_flightlevel_diagnostics_figure,
    make_gap_diagnostics_figure,
    make_sampling_figure,
)
from soaring.analysis.figures.transport import make_msd_figure
from soaring.analysis.observables.transport import MSDResult


@pytest.fixture(scope="module")
def config():
    return load_preproc_config()


def _scan(n=4000, seed=0):
    """A census table with the columns the diagnostics read."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "duration_s": rng.uniform(600, 40000, n),
            "path_km": rng.uniform(1, 300, n),
            "baro_alt_min_m": rng.uniform(0, 500, n),
            "baro_alt_max_m": rng.uniform(600, 4000, n),
            "baro_present_frac": rng.choice([0.0, 1.0], n, p=[0.3, 0.7]),
            "max_gap_ratio": rng.uniform(1, 40, n),
            "dt_s": rng.choice([1.0, 2.0, 5.0, 10.0], n),
            "missing_fraction": rng.uniform(0, 0.3, n),
        }
    )


@pytest.fixture
def scans():
    return {"paragliders": _scan(), "hang gliders": _scan(500, seed=1)}


def _distributions(nan_every=0):
    """Per-fix channels, optionally with the gaps a real vertical channel carries."""
    rng = np.random.default_rng(2)
    out = {}
    for disc in ("paragliders", "hang gliders"):
        v_z = rng.normal(0, 2, 5000).round()
        if nan_every:
            v_z[::nan_every] = np.nan
        out[disc] = {
            "v_xy": rng.normal(12, 4, 5000),
            "v_z": v_z,
            "altitude": rng.normal(1500, 500, 5000),
        }
    return out


def test_the_flightlevel_diagnostics_render(scans, config):
    figure = make_flightlevel_diagnostics_figure(scans, config.flight, config.alt_channel)
    assert figure.axes


def test_the_gap_diagnostics_render(scans, config):
    assert make_gap_diagnostics_figure(scans, config.sampling).axes


def test_the_sampling_figure_renders(scans):
    assert make_sampling_figure(scans).axes


@pytest.mark.parametrize("nan_every", [0, 97, 1])
def test_the_fixlevel_diagnostics_survive_a_gapped_channel(nan_every, config):
    """nan_every=1 is the whole channel missing, which must degrade rather than raise.

    The vertical speed is a difference of altitudes, so a fix without one leaves a nan
    behind. Every range in the panel is a quantile, and one nan makes all of them nan.
    """
    figure = make_fixlevel_diagnostics_figure(_distributions(nan_every), config.fix)
    assert figure.axes


def test_the_msd_figure_renders_both_estimators():
    t = np.geomspace(1, 1000, 40)
    msd = 100 * t**0.85
    n_flights = np.full(t.size, 500)
    n_flights[0] = 400  # a non-empty joining region, which panel (a) shades
    result = MSDResult(
        t=t, msd=msd, n_flights=n_flights, sem=msd * 0.01,
        p10=msd * 0.5, p50=msd * 0.9, p90=msd * 2.0,
    )
    figure = make_msd_figure({"paragliders": result}, {}, {"paragliders": result}, {})
    assert len(figure.axes) == 4
