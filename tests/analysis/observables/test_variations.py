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


def test_the_second_order_variation_is_unbiased_across_exponents():
    """alpha_2 = 2H, so a measured 2.0 means H = 1 and not "the estimator saturates"."""
    lags = np.unique(np.round(np.geomspace(4, 400, 20)).astype(int))
    for hurst in (0.6, 0.8, 0.95):
        measured = np.mean(
            [
                2
                * V.hurst_from_variations(
                    lags, V.filtered_variation(S.fractional_brownian(8192, hurst, seed=s), lags, order=2)
                )[0]
                for s in range(4)
            ]
        )
        assert measured == pytest.approx(2 * hurst, abs=0.06)


def test_a_straight_line_gives_no_second_order_variation_at_all():
    """The second difference annihilates constant velocity exactly, not approximately."""
    line = np.column_stack([np.arange(4000.0) * 12.0, np.zeros(4000)])
    lags = np.unique(np.round(np.geomspace(4, 400, 20)).astype(int))
    assert np.nanmax(V.filtered_variation(line, lags, order=2)) == 0.0


def test_a_locally_smooth_process_reads_above_two_not_at_it():
    """The calibration that stops alpha_2 = 2 being misread as "ballistic".

    A persistent walk is differentiable below its correlation time, so over lags well
    inside it the second-order variation scales as lag^4 in the limit and reads close to
    3 in practice. A measured 2.0 therefore says the motion is *not* locally straight over
    the fitted range -- it is the H = 1 boundary of fractional Brownian motion, which is
    persistent and still rough.
    """
    lags = np.unique(np.round(np.geomspace(4, 400, 20)).astype(int))

    def alpha_two(track):
        return 2 * V.hurst_from_variations(lags, V.filtered_variation(track, lags, order=2))[0]

    assert alpha_two(S.persistent_walk(20000, 3000.0, seed=2)) > 2.7
    assert alpha_two(S.persistent_walk(20000, 30.0, seed=2)) < 2.4


def test_the_ratio_of_the_two_orders_matches_the_closed_form():
    """V_2/V_1 = 4 - 2^(2H) exactly, for any process with stationary increments.

    Derived by hand and owing nothing to the implementation: with X and Y the two
    consecutive increments at spacing D, A_2 = Y - X, so
    <|A_2|^2> = 2 S(D) - 2<X.Y> and S(2D) = 2 S(D) + 2<X.Y>, whence
    V_2 = 4 S(D) - S(2D) = S(D) (4 - 2^(2H)). This pins the filter kernel itself, which a
    comparison against another convolution cannot: the order-2 kernel is symmetric, so a
    np.convolve route performs the same three products in the same order and agrees
    bitwise whether or not the kernel is right.
    """
    lags = np.array([4, 8, 16, 32, 64, 128])
    for hurst, tolerance in ((0.5, 0.02), (0.7, 0.03)):
        first = np.zeros(lags.size)
        second = np.zeros(lags.size)
        for k in range(24):
            positions = np.asarray(S.fractional_brownian(2**14, hurst, seed=500 + k))
            first += V.filtered_variation(positions, lags, order=1)
            second += V.filtered_variation(positions, lags, order=2)
        ratio = float(np.median(second / first))
        assert ratio == pytest.approx(4 - 2 ** (2 * hurst), rel=tolerance)


def test_the_estimator_is_unbiased_where_the_archive_sits():
    """H near 1 is the boundary of the family and is exactly where alpha_2 is measured.

    The archive returns alpha_2 close to 2, so a bias that only appears as H approaches 1
    would land on the headline number and nowhere else. It does not: the exponent is
    recovered to better than 0.03 at H = 0.99.
    """
    lags = np.array([4, 8, 16, 32, 64, 128])
    pooled = np.zeros(lags.size)
    for k in range(24):
        positions = np.asarray(S.fractional_brownian(2**14, 0.99, seed=700 + k))
        pooled += V.filtered_variation(positions, lags, order=2)
    exponent = float(np.polyfit(np.log(lags), np.log(pooled), 1)[0])
    assert exponent == pytest.approx(1.98, abs=0.03)


@pytest.mark.parametrize("hurst", [0.5, 0.7, 0.99])
def test_the_wavelet_diagram_has_slope_two_h_and_is_unbiased_where_the_archive_sits(hurst):
    """Slope 2H, not the textbook 2H+1, and no low bias once the first octaves are dropped.

    Two things this pins, both of which were wrong before. The cascade coarse-grains by
    averaging adjacent pairs, whose DC gain is 1, so the orthonormal 1/sqrt(2) that puts the
    +1 in the textbook logscale diagram is absent: reading the output by that rule returns
    H - 1/2. And a block average of 1, 2 or 4 samples is not yet its own continuous limit, so
    fitting from octave 0 comes out low - by 0.036 at H = 0.99, which is where this archive
    sits and is enough to read as a disagreement with the filtered-variation exponent.
    """
    pooled = None
    for k in range(16):
        scales, variance, counts = V.wavelet_variance(
            np.asarray(S.fractional_brownian(8192, hurst, seed=900 + k))
        )
        pooled = variance.copy() if pooled is None else pooled + variance
    pooled /= 16
    keep = counts > 64
    slope = float(np.polyfit(np.log2(scales[keep]), np.log2(pooled[keep]), 1)[0])
    assert slope / 2 == pytest.approx(hurst, abs=0.02)


def test_including_the_first_octaves_is_what_biased_it():
    """The default is not a preference: min_octave=0 reproduces the bias it was set to avoid."""
    pooled = None
    for k in range(16):
        scales, variance, counts = V.wavelet_variance(
            np.asarray(S.fractional_brownian(8192, 0.99, seed=900 + k)), min_octave=0
        )
        pooled = variance.copy() if pooled is None else pooled + variance
    pooled /= 16
    keep = counts > 64
    slope = float(np.polyfit(np.log2(scales[keep]), np.log2(pooled[keep]), 1)[0])
    assert slope / 2 < 0.97, "the whole cascade should read low; if not, the fix is unneeded"
