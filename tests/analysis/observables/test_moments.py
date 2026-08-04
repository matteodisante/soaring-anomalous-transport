"""The moment spectrum has to tell a Lévy walk from a correlated Gaussian, and say so.

It also has to *refuse* to find a knee where there is none, which is the harder half: a
bilinear fit has two spare parameters and will always reduce a residual.
"""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables import moments as M
from soaring.analysis.observables import synthetic as S

# Lags that span many renewals of the synthetic walk. Inside a single ballistic leg the
# spectrum measures the leg and not the walk, which is how a first attempt put the knee of
# an index-1.5 process at 0.52.
LAGS = np.unique(np.round(np.geomspace(20, 3000, 14)).astype(int))
Q = np.array(M.Q_GRID)


def _q_nu(track, order=1):
    moments, _, counts = M.moment_spectrum(track, LAGS, order=order)
    usable = counts > 20
    return np.array(
        [np.polyfit(np.log(LAGS[usable]), np.log(moments[usable, j]), 1)[0] for j in range(Q.size)]
    )


def test_a_gaussian_process_gives_a_straight_spectrum():
    fitted = M.bilinear_fit(Q, _q_nu(S.fractional_brownian(200000, 0.75, seed=1)))
    assert fitted["prefers_bilinear"] is False
    assert fitted["linear_slope"] == pytest.approx(0.75, abs=0.05)


@pytest.mark.parametrize("alpha", [1.5, 1.8])
def test_a_levy_walk_gives_a_knee_at_its_tail_index(alpha):
    fitted = M.bilinear_fit(Q, _q_nu(S.levy_walk(200000, alpha, seed=int(10 * alpha))))
    assert fitted["prefers_bilinear"] is True
    assert fitted["knee"] == pytest.approx(alpha, abs=0.25)


def test_the_second_difference_moves_the_knee_and_the_first_does_not():
    """Why the spectrum is read at order 1 even though the exponent is read at order 2.

    A second difference of a piecewise-straight path is zero except at its corners, so the
    filter that removes each flight's course also removes the Lévy signature. This is the
    measurement behind that claim, and it is the reason the order is an argument in the
    chapter rather than a default.
    """
    track = S.levy_walk(200000, 1.5, seed=1)
    first = M.bilinear_fit(Q, _q_nu(track, order=1))
    second = M.bilinear_fit(Q, _q_nu(track, order=2))
    assert abs(first["knee"] - 1.5) < 0.25
    assert abs(second["knee"] - 1.5) > 0.5


def test_increments_do_not_overlap():
    """At q > 2 one extreme event in m overlapping windows is counted m times."""
    track = S.brownian(1000, seed=0)
    magnitude = M._increments(track, 10, order=1)
    # Non-overlapping windows of span 10 in 1000 samples: about 99 of them, not 990.
    assert magnitude.size < 120


def test_the_tail_share_flags_a_moment_carried_by_one_sample():
    rng = np.random.default_rng(0)
    track = S.brownian(20000, seed=1)
    track[10000:] += np.array([1e6, 0.0])      # one enormous jump
    _, tail_share, counts = M.moment_spectrum(track, LAGS[:6], order=1)
    usable = counts > 20
    assert np.nanmax(tail_share[usable, -1]) > np.nanmax(tail_share[usable, 0])


def test_quantile_ratios_are_flat_for_a_self_similar_process():
    """Shape held fixed while scale changes is self-similarity, whatever the exponent."""
    ratios = M.quantile_ratios(S.fractional_brownian(100000, 0.7, seed=3), LAGS)
    usable = np.isfinite(ratios[:, 0])
    spread = np.nanmax(ratios[usable, 0]) - np.nanmin(ratios[usable, 0])
    assert spread < 0.15


def test_the_non_gaussian_parameter_separates_gaussian_from_levy():
    """alpha_2 = <|dr|^4>/(2<|dr|^2>^2) - 1 is 0 for a Gaussian and clearly positive for a Levy walk.

    Chapter 3 reads the archive's alpha_2 against these two, so the two have to be pinned:
    a monofractal moment spectrum says one exponent governs every moment and says nothing
    about the shape of the distribution, and this is what supplies the shape.
    """
    from soaring.analysis.observables import synthetic as S
    from soaring.analysis.observables.moments import _increments

    lags = np.unique(np.round(np.geomspace(60, 2000, 10)).astype(int))

    def pooled_alpha_two(make, reps=30, n=2**13):
        second = np.zeros(lags.size)
        fourth = np.zeros(lags.size)
        count = np.zeros(lags.size)
        for k in range(reps):
            positions = np.asarray(make(n, k))
            for i, lag in enumerate(lags):
                magnitude = _increments(positions, int(lag), order=1)
                if magnitude.size:
                    second[i] += (magnitude**2).sum()
                    fourth[i] += (magnitude**4).sum()
                    count[i] += magnitude.size
        ok = count > 0
        return (fourth[ok] / count[ok]) / (2 * (second[ok] / count[ok]) ** 2) - 1.0

    gaussian = pooled_alpha_two(lambda n, k: S.fractional_brownian(n, 0.85, seed=k))
    levy = pooled_alpha_two(lambda n, k: S.levy_walk(n, 1.5, seed=k))

    assert abs(np.median(gaussian)) < 0.06, "an exact Gaussian must read zero"
    assert np.median(levy) > 0.3, "a Levy walk must read clearly positive"
    assert np.median(levy) > np.median(gaussian) + 0.3
