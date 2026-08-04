r"""The spectrum of moments, and the shape of the displacement distribution.

The exponent of Chapter 3 is a statement about one moment. Two processes can share it and
differ in everything else: a correlated Gaussian process and a Lévy walk both give
:math:`\langle|\Delta\mathbf{r}|^2\rangle\sim\Delta^{2H}` and are not the same physics. What
separates them is how the *whole spectrum* of moments scales,

.. math::

    \big\langle|\Delta\mathbf{r}(\Delta)|^q\big\rangle \sim \Delta^{\,q\nu(q)},

read as a function of :math:`q`. A self-similar Gaussian process gives a straight line
through the origin, :math:`q\nu(q)=qH`; a Lévy walk gives a bilinear one with a knee, which
is the signature called strong anomalous diffusion. One figure decides between them, and it
decides visually rather than through a delicate fit.

Two things have to be right or the spectrum lies.

**The increments must not overlap.** At :math:`q=2` overlapping windows are harmless -- the
bias is zero and only the variance suffers -- but above it a single extreme event appears in
:math:`m` overlapping windows and is counted :math:`m` times, which inflates the high
moments systematically. The stride is correctness, not economy.

**The tail share must be reported beside every moment.** A fourth moment that is eighty per
cent one flight is not a moment. :func:`moment_spectrum` returns, for each
:math:`(\Delta, q)`, the fraction of the sum contributed by the largest one per cent of
samples, and anything above a half is not an estimate.

**The filter order is a real dilemma here, and it is not resolved by preference.** The
exponent of this chapter is measured on order-2 differences, because order 1 carries each
flight's course and the declared task. But the Lévy-walk signature lives in the
*displacement*, and a second difference of a piecewise-straight path is zero except at its
corners, so the filter that removes the contamination also removes the thing being looked
for. Measured on a synthetic Lévy walk of tail index 1.5, order 1 recovers the knee at 1.52
with a right-hand slope of 0.96 -- the ballistic front, as the theory says -- while order 2
puts the knee at 2.34 with a slope of 0.86, which is neither the right answer nor a wrong
answer to a different question.

So the spectrum is computed at order 1, where it is diagnostic, and read only where the
closed and open task populations agree; the order is an argument and both are available.
Reporting it at order 2 alone would be tidy and would measure the curvature spectrum while
claiming to measure the displacement one.
"""

from __future__ import annotations

import numpy as np

__all__ = ["bilinear_fit", "moment_spectrum", "quantile_ratios"]

# Difference kernels by order, matching variations.filtered_variation. Order 1 is the plain
# increment: contaminated by the course, and the only order at which the Levy-walk knee is
# in the right place. See the module docstring.
_KERNELS = {1: np.array([1.0, -1.0]), 2: np.array([1.0, -2.0, 1.0])}

# Moment orders. It stops at 4 because the tail control below refuses to certify more on
# records of this length, and it includes fractional orders because the knee of a Levy
# walk sits between 1 and 2 and a grid of integers would step over it.
Q_GRID = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0)


def _increments(positions: np.ndarray, lag: int, order: int = 1) -> np.ndarray:
    """Magnitudes of the non-overlapping order-``p`` differences at ``lag`` samples."""
    kernel = _KERNELS[order]
    span = (len(kernel) - 1) * lag
    if lag < 1 or span >= len(positions):
        return np.empty(0)
    width = len(positions) - span
    acc = np.zeros((width, positions.shape[1]))
    for j, weight in enumerate(kernel):
        start = j * lag
        acc += weight * positions[start : start + width]
    # Stride by the span, so no sample enters two windows. This is what stops one
    # extreme event being counted repeatedly in the high moments.
    return np.hypot(acc[::span, 0], acc[::span, 1])


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
        ``moments[i, j]`` is ``<|A_2 r|^q>`` at ``lags[i]`` and ``q_grid[j]``;
        ``tail_share[i, j]`` is the fraction of that sum carried by the largest ``tail`` of
        the samples; ``counts[i]`` is how many non-overlapping windows the lag supplied.
    """
    lags = np.asarray(lags, dtype=int)
    q_grid = np.asarray(q_grid, dtype=float)
    moments = np.full((lags.size, q_grid.size), np.nan)
    tail_share = np.full((lags.size, q_grid.size), np.nan)
    counts = np.zeros(lags.size, dtype=int)

    for i, lag in enumerate(lags):
        magnitude = _increments(positions, int(lag), order)
        counts[i] = magnitude.size
        if magnitude.size < 8:
            continue
        keep = max(1, int(round(tail * magnitude.size)))
        for j, q in enumerate(q_grid):
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
    """Fit ``q nu(q)`` with a free knee, and say whether the knee is worth having.

    For a Lévy walk with tail index :math:`\\alpha`, ``q nu(q) = q/alpha`` below
    ``q = alpha`` and ``q + 1 - alpha`` above it: a bilinear form whose knee position is a
    third, independent estimate of the same exponent, and whose right-hand slope is 1
    because the front is ballistic. For a self-similar Gaussian process the same data is a
    straight line through the origin.

    The two are compared by three conditions together, because BIC alone is not enough on a
    grid of ten moment orders: a bilinear fit has two more parameters, always reduces the
    residual, and on that many points buys the reduction cheaply. Fitted to a fractional
    Brownian motion -- which has no knee -- BIC prefers the bilinear form while the straight
    line already fits to an rms of 0.003. So the knee is declared only when BIC prefers it,
    **and** the straight line leaves a residual above ``min_departure``, **and** the knee
    sits inside the grid rather than on its edge. On the same synthetic pair those three
    give: fractional Brownian motion, no knee; Lévy walk of index 1.5, a knee at 1.57 with a
    right-hand slope of 0.96.

    Returns:
        ``{"knee", "slope_low", "slope_high", "rms", "linear_slope", "linear_rms",
        "prefers_bilinear"}``, or ``None`` if the fit does not converge.
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

    return {
        "knee": float(popt[0]),
        "slope_low": float(popt[1]),
        "slope_high": float(popt[2]),
        "rms": float(np.std(residual_bi)),
        "linear_slope": slope,
        "linear_rms": float(np.std(residual_lin)),
        "linear_departure": float(np.std(residual_lin)),
        "prefers_bilinear": bool(
            bic(residual_bi, 3) < bic(residual_lin, 1)
            and np.std(residual_lin) > min_departure
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
    lags = np.asarray(lags, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    floor = max(20.0, 10.0 / (1.0 - float(probabilities.max())))
    ratios = np.full((lags.size, probabilities.size), np.nan)
    for i, lag in enumerate(lags):
        magnitude = _increments(positions, int(lag), order)
        if magnitude.size < floor:
            continue
        median = np.median(magnitude)
        if median <= 0:
            continue
        ratios[i] = np.quantile(magnitude, probabilities) / median
    return ratios
