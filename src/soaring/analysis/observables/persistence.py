r"""How long the motion keeps going the same way, in time and in geometry.

Two observables that the mean-squared displacement cannot supply, because both are about
the *arrangement* of the motion rather than about its second moment.

The velocity autocorrelation says how long a heading survives, and it is tied to the
displacement by Green--Kubo,
:math:`\mathrm{MSD}(t)=2\int_0^t(t-\tau)\,C(\tau)\,\mathrm{d}\tau`, so computing both and
checking they agree is a consistency test that costs one extra pass and catches a whole
class of error in either.

The persistence runs say how far the wing goes before it turns, measured geometrically
rather than through a segmentation. That one carries a trap severe enough to be the reason
this module exists.

**The inspection bias.** Sampling the run length at every instant does not give the
distribution of run lengths: it gives that distribution *weighted by length*, because a long
run is crossed by more starting instants than a short one. If
:math:`P(L>\ell)\sim\ell^{-\beta}`, per-instant sampling returns :math:`\beta-1`. At the
values expected here, near 1.7, that is an error of a whole unit --- not a bias to correct
afterwards but a different number. The fix is to decompose the record into
**non-overlapping** runs, greedily from the start, which is what :func:`persistence_runs`
does; :func:`inspection_biased_runs` implements the wrong way on purpose, so the size of the
bias can be measured rather than asserted.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "green_kubo_msd",
    "tail_index",
    "inspection_biased_runs",
    "persistence_runs",
    "velocity_autocorrelation",
]


def velocity_autocorrelation(velocity: np.ndarray, max_lag: int | None = None):
    """``<v(t) . v(t+tau)>`` by FFT, normalised to 1 at zero lag.

    Args:
        velocity: ``(n, 2)`` velocity samples on a uniform grid.
        max_lag: Largest lag to return, in samples; ``n // 4`` by default, beyond which
            the estimate averages too few pairs to mean anything.

    Returns:
        ``(lags, correlation)`` with ``correlation[0] == 1``.
    """
    velocity = np.asarray(velocity, dtype=float)
    n = len(velocity)
    if n < 8:
        return np.empty(0, dtype=int), np.empty(0)
    max_lag = max_lag or n // 4
    centred = velocity - velocity.mean(axis=0)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    acf = np.zeros(n)
    for component in range(velocity.shape[1]):
        spectrum = np.fft.rfft(centred[:, component], size)
        acf += np.fft.irfft(spectrum * np.conj(spectrum), size)[:n]
    counts = np.arange(n, 0, -1)
    acf /= counts
    if acf[0] <= 0:
        return np.empty(0, dtype=int), np.empty(0)
    return np.arange(max_lag + 1), acf[: max_lag + 1] / acf[0]


def green_kubo_msd(lags: np.ndarray, correlation: np.ndarray, variance: float, dt: float):
    """The MSD implied by a velocity autocorrelation, by the Green--Kubo relation.

    Compared against the directly measured MSD this is a consistency check between the
    position and velocity channels, which the pipeline computes by different routes: the
    positions are smoothed and the velocities differentiated from them. Agreement is a
    statement that the differentiation did not invent anything.
    """
    lags = np.asarray(lags, dtype=float)
    # MSD(t) = 2 int_0^t (t-tau) C(tau) dtau = 2 int_0^t int_0^s C(tau) dtau ds, so the
    # weighting by (t-tau) is the second cumulative sum rather than an explicit weight.
    integrand = variance * correlation
    return 2.0 * dt * dt * np.cumsum(np.cumsum(integrand))[: lags.size]


def persistence_runs(positions: np.ndarray, max_sinuosity: float, min_length: int = 5):
    """Non-overlapping stretches whose sinuosity stays under ``max_sinuosity``.

    Sinuosity is arc length over chord, so it is one for a straight stretch and grows as the
    path bends. The scan is greedy from the start of the record and each run begins where
    the last one ended, so no sample belongs to two runs --- which is what makes the returned
    lengths a sample from the run-length distribution rather than from its length-biased
    cousin.

    The stopping rule is **first violation**. The condition is not monotone in the endpoint,
    since a stretch can come back inside the threshold after leaving it, so a different rule
    gives different statistics; this one is stated so the number can be reproduced.

    Args:
        positions: ``(n, 2)`` positions on a uniform grid.
        max_sinuosity: Threshold, at least 1. Roughly, 1.05, 1.15 and 1.30 correspond to
            cones of half-angle 18, 31 and 45 degrees.
        min_length: Shortest run considered, in samples.

    Returns:
        Run lengths in samples.
    """
    positions = np.asarray(positions, dtype=float)
    n = len(positions)
    if n <= min_length:
        return np.empty(0, dtype=int)
    step = np.hypot(*np.diff(positions, axis=0).T)
    arc = np.concatenate([[0.0], np.cumsum(step)])

    # The inner search is vectorised: for a fixed start, every candidate endpoint's
    # sinuosity is one array expression and the first violation is one argmax. Walking it
    # sample by sample is the same answer and costs three hours over the archive against
    # twenty minutes, because the scan is O(n x run length) in Python and O(n) in numpy.
    lengths: list[int] = []
    start = 0
    while start < n - min_length:
        tail = positions[start + min_length :]
        chord = np.hypot(tail[:, 0] - positions[start, 0], tail[:, 1] - positions[start, 1])
        with np.errstate(divide="ignore", invalid="ignore"):
            sinuosity = (arc[start + min_length :] - arc[start]) / chord
        violates = ~(chord > 0) | (sinuosity > max_sinuosity)
        offset = int(np.argmax(violates)) if violates.any() else violates.size
        end = start + min_length + offset
        lengths.append(end - start)
        start = end
    return np.asarray(lengths, dtype=int)


def inspection_biased_runs(positions: np.ndarray, max_sinuosity: float,
                           min_length: int = 5, stride: int = 1):
    """The length of the run **containing** each sampled instant: the wrong way, on purpose.

    Kept so the inspection bias can be measured on the data at hand rather than taken on
    trust. A long run contains more instants than a short one, so sampling by instant
    returns each run in proportion to its length --- the length-biased distribution, whose
    tail index is one below the true one.

    Note what this is *not*. Measuring forward from each instant to the next violation
    gives the residual life, a different biased quantity whose direction of bias depends on
    the distribution; that was the first implementation here and the test caught it. The
    containing run is obtained by decomposing once with :func:`persistence_runs` and then
    reading off which run each sampled instant falls in.
    """
    lengths = persistence_runs(positions, max_sinuosity, min_length)
    if lengths.size == 0:
        return np.empty(0, dtype=int)
    edges = np.concatenate([[0], np.cumsum(lengths)])
    instants = np.arange(0, edges[-1], max(1, int(stride)))
    index = np.clip(np.searchsorted(edges, instants, side="right") - 1, 0, lengths.size - 1)
    return lengths[index]


def tail_index(lengths: np.ndarray, *, minimum: int | None = None) -> tuple[float, int]:
    """Hill estimate of ``beta`` in ``P(L > l) ~ l^-beta``, with the cut-off it used.

    The cut-off is chosen by the Clauset--Shalizi--Newman rule: the value of ``l_min``
    minimising the Kolmogorov--Smirnov distance between the empirical tail and the fitted
    power law. Choosing it by eye is how a tail index becomes whatever the chooser expected.
    """
    lengths = np.asarray(lengths, dtype=float)
    lengths = lengths[lengths > 0]
    if lengths.size < 50:
        return float("nan"), 0
    candidates = np.unique(lengths)[:-10] if minimum is None else np.array([float(minimum)])
    best = (np.inf, np.nan, 0)
    for cut in candidates:
        tail = lengths[lengths >= cut]
        if tail.size < 25:
            continue
        beta = tail.size / np.sum(np.log(tail / cut))
        empirical = np.arange(tail.size, 0, -1) / tail.size
        model = (np.sort(tail) / cut) ** (-beta)
        distance = float(np.max(np.abs(empirical - model)))
        if distance < best[0]:
            best = (distance, float(beta), int(cut))
    return best[1], best[2]
