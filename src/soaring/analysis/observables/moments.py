r"""Finite-window displacement moments and descriptive spectrum comparisons.

A self-similar law with finite moments has zeta(q)=qH. The standard renewal Lévy walk
has a two-branch asymptotic spectrum for duration-tail index between one and two.
A finite-record spectrum alone cannot identify or exclude an entire model family.

Plain increments retain straight-leg displacement and are the relevant observable for
that comparison. Second differences cancel constant velocity and therefore measure a
different quantity. Nonoverlapping windows reduce duplication without establishing
independence. High-order moments remain sensitive to rare large displacements; the
reported tail share is a diagnostic, not a validity or existence test for a moment.

These helpers also reproduce legacy reports. The current Chapter 3 reporter pools its
own explicit nonoverlapping increment sample in generate_revision_diagnostics.py.
"""

from __future__ import annotations

import numpy as np

__all__ = ["bilinear_fit", "moment_spectrum", "quantile_ratios"]

# First differences here are signed backward differences; their norm is the plain
# displacement magnitude. Second differences cancel a constant velocity.
_KERNELS = {1: np.array([1.0, -1.0]), 2: np.array([1.0, -2.0, 1.0])}

# Fractional orders resolve the interval 1<q<2 of the illustrative Lévy benchmark.
# The upper order four is an analysis choice, not a certified tail-sampling bound.
Q_GRID = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0)


def _increment_vectors(positions: np.ndarray, lag: int, order: int = 1) -> np.ndarray:
    """Signed non-overlapping order-``p`` differences at ``lag`` samples, one row per window.

    Shared core of :func:`_increments`, which discards the two columns into a modulus, and
    of the per-component moments in ``measure_shape.py``, which need them signed and apart.
    """
    kernel = _KERNELS[order]
    span = (len(kernel) - 1) * lag
    if lag < 1 or span >= len(positions):
        return np.empty((0, positions.shape[1]))
    width = len(positions) - span
    acc = np.zeros((width, positions.shape[1]))
    for j, weight in enumerate(kernel):
        start = j * lag
        acc += weight * positions[start : start + width]
    # Stride by the span. Adjacent windows may share an endpoint, and their
    # increments can remain dependent; this is a sampling convention, not a bias cure.
    return acc[::span]


def _increments(positions: np.ndarray, lag: int, order: int = 1) -> np.ndarray:
    """Magnitudes of the non-overlapping order-``p`` differences at ``lag`` samples."""
    vectors = _increment_vectors(positions, lag, order)
    if vectors.shape[0] == 0:
        return np.empty(0)
    return np.hypot(vectors[:, 0], vectors[:, 1])


def moment_spectrum(
    positions: np.ndarray,
    lags: np.ndarray,
    q_grid: tuple[float, ...] = Q_GRID,
    *,
    order: int = 1,
    tail: float = 0.01,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(moments, tail_share, counts)`` over a lag grid and a set of moment orders.

    Args:
        positions: ``(n, 2)`` positions on a uniform grid.
        lags: Lags in samples.
        q_grid: Moment orders.
        order: Difference order; 1 is the plain increment and the diagnostic choice.
        tail: Fraction of the largest samples whose share of the moment is reported.

    Returns:
        ``moments[i, j]`` is ``<|A_p r|^q>`` with ``p = order`` (1 by default, the plain
        increment) at ``lags[i]`` and ``q_grid[j]``;
        ``tail_share[i, j]`` is the fraction of that sum carried by the largest ``tail`` of
        the samples; ``counts[i]`` is how many non-overlapping windows the lag supplied.
    """
    lag_grid = np.asarray(lags, dtype=int)
    orders = np.asarray(q_grid, dtype=float)
    moments = np.full((lag_grid.size, orders.size), np.nan)
    tail_share = np.full((lag_grid.size, orders.size), np.nan)
    counts = np.zeros(lag_grid.size, dtype=int)

    for i, lag in enumerate(lag_grid):
        magnitude = _increments(positions, int(lag), order)
        counts[i] = magnitude.size
        if magnitude.size < 8:
            continue
        keep = max(1, int(round(tail * magnitude.size)))
        for j, q in enumerate(orders):
            weighted = magnitude**q
            total = weighted.sum()
            moments[i, j] = total / magnitude.size
            if total > 0:
                tail_share[i, j] = np.sort(weighted)[-keep:].sum() / total
    return moments, tail_share, counts


def bilinear_fit(
    q_grid: np.ndarray,
    q_nu: np.ndarray,
    *,
    knee0: float = 1.7,
    min_departure: float = 0.02,
) -> dict | None:
    """Compare a line through zero with a continuous broken-line spectrum.

    The returned preference combines a BIC-like score, minimum linear residual and
    an interior knee. Moment exponents share trajectories and are correlated, so
    this rule is a descriptive heuristic, not a calibrated model-selection test.
    The fitted knee and MSD exponent are not statistically independent estimates.
    The current chapter instead shows the specified theoretical spectrum directly.
    """
    from scipy.optimize import curve_fit

    q = np.asarray(q_grid, dtype=float)
    y = np.asarray(q_nu, dtype=float)
    good = np.isfinite(q) & np.isfinite(y)
    q, y = q[good], y[good]
    if q.size < 5:
        return None

    def model(x, knee, low, high):
        return np.where(x < knee, low * x, low * knee + high * (x - knee))

    try:
        popt, _ = curve_fit(
            model, q, y, p0=[knee0, 1.0 / knee0, 1.0],
            bounds=([q.min(), 0.05, 0.05], [q.max(), 5.0, 5.0]), maxfev=40000,
        )
    except (RuntimeError, ValueError):
        return None

    residual_bi = y - model(q, *popt)
    slope = float(np.sum(q * y) / np.sum(q * q))     # least squares through the origin
    residual_lin = y - slope * q

    def bic(residual, k):
        rss = float(residual @ residual)
        return q.size * np.log(max(rss, 1e-300) / q.size) + k * np.log(q.size)

    # Root mean square, not standard deviation. The least-squares line through the origin
    # sets sum(q r) = 0 and leaves sum(r) free, so the residual mean is not zero and std is
    # strictly the smaller of the two -- by about a tenth on a spectrum of this shape. Every
    # name here says rms and so does the text that quotes it, so rms is what it must be.
    def rms(residual):
        return float(np.sqrt(np.mean(residual**2)))

    return {
        "knee": float(popt[0]),
        "slope_low": float(popt[1]),
        "slope_high": float(popt[2]),
        "rms": rms(residual_bi),
        "linear_slope": slope,
        "linear_rms": rms(residual_lin),
        "linear_departure": rms(residual_lin),
        "prefers_bilinear": bool(
            bic(residual_bi, 3) < bic(residual_lin, 1)
            and rms(residual_lin) > min_departure
            and q.min() + 0.1 < popt[0] < q.max() - 0.1
        ),
    }


def quantile_ratios(
    positions: np.ndarray,
    lags: np.ndarray,
    probabilities: tuple[float, ...] = (0.75, 0.9, 0.99),
    *,
    order: int = 1,
) -> np.ndarray:
    """``q_p / q_0.5`` of the increment magnitude, per lag: a fit-free shape index.

    Flat in lag means the distribution keeps its shape and only its scale changes, which is
    self-similarity, whatever the exponent. It needs no fit, no binning and no tail cut-off,
    so it can find a change of shape where the second moment is smooth and refuse one where
    the second moment bends. Where it moves, the distribution is changing shape, and that is
    a regime boundary in a sense the variance cannot see.

    A lag is answered only when it supplies enough non-overlapping windows for the highest
    quantile asked for --- at least ``10 / (1 - p_max)``, so a 99th percentile needs a
    thousand. Without that floor the long-lag end of the curve is a handful of order
    statistics and reads as a change of shape that is only a shortage of samples: on
    fractional Brownian motion of 10^5 samples the ratio wanders by 0.18 across the full
    grid and by 0.06 across the lags that clear the floor.
    """
    lag_grid = np.asarray(lags, dtype=int)
    probs = np.asarray(probabilities, dtype=float)
    floor = max(20.0, 10.0 / (1.0 - float(probs.max())))
    ratios = np.full((lag_grid.size, probs.size), np.nan)
    for i, lag in enumerate(lag_grid):
        magnitude = _increments(positions, int(lag), order)
        if magnitude.size < floor:
            continue
        median = np.median(magnitude)
        if median <= 0:
            continue
        ratios[i] = np.quantile(magnitude, probs) / median
    return ratios
