"""What the two ways of handling a drift actually cost.

The archive's flights each carry their own course, so every scaling estimator has to
dispose of a drift before it can measure anything. There are two ways, and these tests are
what decide between them: subtract it, or filter it out. The second wins, and by a margin
that is worth having in a test rather than in a memory.
"""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables import synthetic as S
from soaring.analysis.observables import variations as V

LAGS = np.unique(np.round(np.geomspace(2, 512, 24)).astype(int))


def _hurst(track, order):
    return V.hurst_from_variations(LAGS, V.filtered_variation(track, LAGS, order=order))[0]


@pytest.mark.parametrize("order", [1, 2, 3])
def test_every_order_recovers_the_exponent_on_a_clean_process(order):
    hurst = [_hurst(S.fractional_brownian(8192, 0.75, seed=s), order) for s in range(6)]
    assert np.mean(hurst) == pytest.approx(0.75, abs=0.04)


def test_order_one_is_contaminated_by_a_drift_and_higher_orders_are_not():
    """The whole case for filtering rather than subtracting, in one comparison.

    An 8 m/s course on an H = 0.75 process reads as H = 0.94 -- an exponent of 1.89 where
    the truth is 1.50 -- through a plain increment. The second-order difference annihilates
    a constant velocity identically, so it does not notice.
    """
    tracks = [
        S.with_drift(S.fractional_brownian(8192, 0.75, seed=s), (8.0, 0.0))
        for s in range(6)
    ]
    contaminated = np.mean([_hurst(t, 1) for t in tracks])
    filtered = np.mean([_hurst(t, 2) for t in tracks])
    assert contaminated > 0.90
    assert filtered == pytest.approx(0.75, abs=0.04)


def test_higher_orders_agree_once_the_polynomial_is_gone():
    """H2 == H3 is the certificate that nothing polynomial is left to remove."""
    tracks = [
        S.with_drift(S.fractional_brownian(8192, 0.75, seed=s), (8.0, -3.0))
        for s in range(6)
    ]
    assert np.mean([_hurst(t, 2) for t in tracks]) == pytest.approx(
        np.mean([_hurst(t, 3) for t in tracks]), abs=0.02
    )


def test_in_sample_centring_biases_the_exponent_down():
    """Subtracting a flight's own net velocity is not a free operation.

    The velocity is estimated from the endpoint, so the centred series is a bridge: its
    increments must sum to zero over the record. That pulls the variation down at every
    lag, not only at long ones, and the exponent with it.
    """
    result = V.centring_bias(0.75, n=2048, n_flights=80, seed=11)
    assert result["alpha_raw"] == pytest.approx(1.5, abs=0.06)
    assert result["alpha_centred"] < result["alpha_raw"] - 0.08
    # The distortion has no safe range: it is already several per cent at the shortest lag.
    assert result["ratio"][0] < 0.99
    assert result["ratio"][-1] < 0.4


def test_out_of_sample_drift_removal_is_much_gentler():
    """Estimating the drift on other data removes the bridge, which is the fix."""
    lags = np.unique(np.round(np.geomspace(2, 256, 20)).astype(int))
    biased, honest = [], []
    for s in range(8):
        track = S.with_drift(S.fractional_brownian(4096, 0.75, seed=s), (6.0, 2.0))
        first_half = V.net_drift(track[: len(track) // 2])
        biased.append(
            V.hurst_from_variations(lags, V.filtered_variation(V.remove_drift(track), lags))[0]
        )
        honest.append(
            V.hurst_from_variations(
                lags, V.filtered_variation(V.remove_drift(track, velocity=first_half), lags)
            )[0]
        )
    assert np.mean(honest) > np.mean(biased)


def test_wavelet_variance_is_a_straight_line_for_a_self_similar_process():
    scales, variance, counts = V.wavelet_variance(
        S.fractional_brownian(8192, 0.7, seed=2), order=2
    )
    usable = counts > 32
    slope = np.polyfit(np.log2(scales[usable]), np.log2(variance[usable]), 1)[0]
    # <d^2> ~ scale^(2H) for this normalisation of the cascade.
    assert slope / 2 == pytest.approx(0.7, abs=0.08)


def test_net_drift_is_the_endpoint_velocity_not_the_mean_speed():
    """A flight that returns home has a large mean speed and almost no net drift."""
    time = np.arange(1000, dtype=float)
    loop = np.column_stack([np.sin(2 * np.pi * time / 1000), np.cos(2 * np.pi * time / 1000)])
    assert np.hypot(*V.net_drift(loop * 1000.0)) < 0.05
