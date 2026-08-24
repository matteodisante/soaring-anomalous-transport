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

    # The Gaussian value at this sample size is not zero but about +0.02, and that is
    # estimation bias rather than shape: a fourth moment over 1.3e4 increments is not yet
    # its own expectation. Sixteen times the data collapses it to within a hundredth of
    # zero, sign included -- so the offset is a small-sample artefact and not a floor, which
    # is what makes the archive's +0.04 a departure rather than a calibration. Chapter 3
    # quotes both, so both are pinned.
    plentiful = pooled_alpha_two(
        lambda n, k: S.fractional_brownian(n, 0.85, seed=1000 + k), reps=480
    )
    assert np.median(gaussian) == pytest.approx(0.02, abs=0.012)
    assert abs(np.median(plentiful)) < 0.015
    assert abs(np.median(plentiful)) < abs(np.median(gaussian))


def test_the_reported_departure_is_an_rms_and_not_a_standard_deviation():
    """The least-squares line through the origin does not centre its residuals.

    It sets sum(q r) = 0, which is its normal equation, and leaves sum(r) free. So the
    residual mean is not zero and np.std is strictly smaller than the root mean square --
    by about a tenth on a spectrum of this shape. Every field name here says rms, the
    docstring says rms, and the thesis quotes the number "in rms", so it has to be one.
    """
    from soaring.analysis.observables.moments import Q_GRID, bilinear_fit

    q = np.asarray(Q_GRID)
    q_nu = 0.83 * q + 0.02 * q * (q - q.mean()) / q.max()
    slope = float(np.sum(q * q_nu) / np.sum(q * q))
    residual = q_nu - slope * q

    assert abs(np.sum(q * residual)) < 1e-12
    assert abs(np.sum(residual)) > 1e-3, "if this fit centred its residuals the point is moot"

    fitted = bilinear_fit(q, q_nu)
    assert fitted["linear_departure"] == pytest.approx(np.sqrt(np.mean(residual**2)))
    assert fitted["linear_departure"] > np.std(residual)
