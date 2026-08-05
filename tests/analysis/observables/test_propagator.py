"""The propagator estimator, against processes whose exponent and shape are known.

This is the one route to H in the project that goes through neither a moment nor the common
origin, so it is the one that has to be validated hardest: if it agreed with the second
moment because it *is* the second moment in disguise, it would be no check at all.
"""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables import propagator as P
from soaring.analysis.observables import synthetic as S


def _accumulate(make, lags, reps=12, n=2**15, order=1):
    acc = P.PropagatorAccumulator(lags, order=order)
    for k in range(reps):
        acc.add(np.asarray(make(n, k)))
    return acc


@pytest.mark.parametrize("hurst", [0.5, 0.7, 0.9])
def test_the_quantiles_recover_the_exponent_without_touching_a_moment(hurst):
    """Every quantile of |dx| grows as lag^H, and the median of the four is the estimate."""
    lags = np.unique(np.round(np.geomspace(4, 256, 12)).astype(int))
    acc = _accumulate(lambda n, k: S.fractional_brownian(n, hurst, seed=k), lags)
    quantiles = np.array(
        [P.quantiles_from_histogram(acc.counts[0, i], acc.edges) for i in range(lags.size)]
    )
    fitted = P.scaling_from_quantiles(lags.astype(float), quantiles)
    assert fitted["hurst"] == pytest.approx(hurst, abs=0.04)


@pytest.mark.parametrize("hurst", [0.5, 0.9])
def test_the_four_quantiles_agree_when_the_process_is_self_similar(hurst):
    """Their spread is a test of the scaling form, not an error bar on the exponent."""
    lags = np.unique(np.round(np.geomspace(4, 256, 12)).astype(int))
    acc = _accumulate(lambda n, k: S.fractional_brownian(n, hurst, seed=k), lags)
    quantiles = np.array(
        [P.quantiles_from_histogram(acc.counts[0, i], acc.edges) for i in range(lags.size)]
    )
    fitted = P.scaling_from_quantiles(lags.astype(float), quantiles)
    assert fitted["spread"] < 0.05


def test_the_quantiles_disagree_when_the_shape_changes_with_the_scale():
    """A process whose distribution is not self-similar must fail the test that says so.

    A persistent walk is near-deterministic below its correlation time and diffusive above
    it, so across a lag range that straddles the crossover the low and high quantiles grow
    at visibly different rates. If the spread did not open up here it would not be measuring
    anything on the archive either.
    """
    lags = np.unique(np.round(np.geomspace(4, 512, 14)).astype(int))
    acc = _accumulate(lambda n, k: S.persistent_walk(n, 60.0, seed=k), lags)
    quantiles = np.array(
        [P.quantiles_from_histogram(acc.counts[0, i], acc.edges) for i in range(lags.size)]
    )
    straddling = P.scaling_from_quantiles(lags.astype(float), quantiles)

    acc_ss = _accumulate(lambda n, k: S.fractional_brownian(n, 0.7, seed=k), lags)
    q_ss = np.array(
        [P.quantiles_from_histogram(acc_ss.counts[0, i], acc_ss.edges) for i in range(lags.size)]
    )
    self_similar = P.scaling_from_quantiles(lags.astype(float), q_ss)

    assert straddling["spread"] > 3 * self_similar["spread"]


@pytest.mark.parametrize("hurst", [0.6, 0.85])
def test_the_rescaled_histograms_collapse_for_a_self_similar_process(hurst):
    """The direct test of the scaling form: rescale, overlay, measure the scatter."""
    lags = np.unique(np.round(np.geomspace(8, 256, 10)).astype(int))
    acc = _accumulate(lambda n, k: S.fractional_brownian(n, hurst, seed=k), lags, reps=16)
    residual = P.collapse_residual(lags.astype(float), acc.counts[0], acc.edges, hurst)
    assert residual < 0.06, "a self-similar process must collapse to counting noise"


def test_the_collapse_fails_at_the_wrong_exponent():
    """If it collapsed at any H it would be measuring nothing."""
    lags = np.unique(np.round(np.geomspace(8, 256, 10)).astype(int))
    acc = _accumulate(lambda n, k: S.fractional_brownian(n, 0.7, seed=k), lags, reps=16)
    right = P.collapse_residual(lags.astype(float), acc.counts[0], acc.edges, 0.70)
    wrong = P.collapse_residual(lags.astype(float), acc.counts[0], acc.edges, 0.50)
    assert wrong > 3 * right


def test_quantiles_from_a_histogram_match_the_sample_they_came_from():
    """The binning must not move the answer by more than a bin."""
    rng = np.random.default_rng(3)
    sample = np.abs(rng.normal(0.0, 500.0, 400_000))
    counts = np.histogram(sample, bins=P.EDGES)[0]
    read = P.quantiles_from_histogram(counts, P.EDGES, (0.25, 0.5, 0.75, 0.9))
    exact = np.quantile(sample, [0.25, 0.5, 0.75, 0.9])
    assert np.all(np.abs(read / exact - 1.0) < 0.02)


def test_an_empty_histogram_returns_nan_rather_than_a_number():
    read = P.quantiles_from_histogram(np.zeros(P.EDGES.size - 1), P.EDGES)
    assert np.isnan(read).all()
    assert np.isnan(P.collapse_residual(np.array([1.0, 2.0]), np.zeros((2, 4)), np.geomspace(1, 5, 5), 0.5))


def test_turning_angles_are_zero_on_a_straight_line_and_uniform_on_a_random_walk():
    """The two ends of the scale the observable is meant to distinguish."""
    line = np.column_stack([np.arange(500.0), np.zeros(500)])
    assert np.allclose(P.turning_angles(line, 5), 0.0, atol=1e-9)

    angles = P.turning_angles(np.asarray(S.brownian(40000, seed=1)), 5)
    # Isotropic reorientation: theta uniform on [0, pi], so the median is pi/2.
    assert np.median(angles) == pytest.approx(np.pi / 2, abs=0.05)


def test_turning_angles_are_peaked_forward_for_a_persistent_walk():
    """A correlated walk turns less than a memoryless one, which is what the panel says."""
    persistent = P.turning_angles(np.asarray(S.persistent_walk(40000, 400.0, seed=2)), 5)
    memoryless = P.turning_angles(np.asarray(S.brownian(40000, seed=2)), 5)
    assert np.median(persistent) < 0.3 * np.median(memoryless)


def test_turning_angles_drop_steps_of_zero_length_rather_than_giving_them_a_direction():
    still = np.zeros((200, 2))
    assert P.turning_angles(still, 5).size == 0


@pytest.mark.parametrize("hurst", [0.6, 0.9])
def test_the_peak_height_gives_the_same_exponent_as_the_quantiles(hurst):
    """P_0 ~ D^-H uses the very centre of the distribution, where a quantile uses its middle.

    Two readings of the same histograms that fail differently: if they agreed by
    construction one of them would be redundant, and if they disagreed on a process of known
    exponent one of them would be wrong.
    """
    lags = np.unique(np.round(np.geomspace(8, 256, 12)).astype(int))
    acc = _accumulate(lambda n, k: S.fractional_brownian(n, hurst, seed=k), lags, reps=20)
    fitted, used = P.peak_scaling(lags.astype(float), acc.counts[0], acc.edges)
    assert used >= 8
    assert fitted == pytest.approx(hurst, abs=0.06)


def test_the_kinematic_histograms_count_what_they_are_given():
    acc = P.KinematicAccumulator(angle_stride=5)
    track = np.asarray(S.brownian(5000, seed=4))
    velocity = np.diff(track, axis=0, prepend=track[:1])
    vertical = np.full(len(track), 1.5)
    acc.add(track, velocity, vertical)
    assert acc.angle.sum() > 0
    assert acc.speed.sum() > 0
    # A constant climb of 1.5 m/s must land in one bin and only one.
    assert (acc.vertical > 0).sum() == 1
