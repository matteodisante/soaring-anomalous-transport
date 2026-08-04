"""Trend-robust scaling estimators, and the cost of removing a trend by hand.

The mean-squared displacement is one estimator of one exponent, and on this archive it is
fragile in a specific way: every flight carries its own course, so a residual drift adds
:math:`|v_d|^2\\Delta^2` and turns any process ballistic at long lags. The August audit
measured exactly that on the ensemble estimator.

There are two ways to deal with it and this module implements both, because they fail
differently.

**Subtract the drift.** Estimate each flight's mean velocity and remove it. Simple, and
what ``01_fondamenta.md`` §1.4.4 prescribes -- but the estimate uses the flight's own
endpoint, so it is an in-sample, acausal detrending that forces the mean centred increment
to vanish by construction and suppresses the very long-lag correlation the analysis is
testing for. :func:`centring_bias` measures how much, on a process whose exponent is known.

**Filter the trend out.** A finite difference of order :math:`p` annihilates any
polynomial of degree :math:`p-1` identically, so the exponent can be read without ever
estimating a drift. The order scan is the useful part: :math:`\\hat H_1 - \\hat H_2` is how
much of the apparent exponent was course, and :math:`\\hat H_2 = \\hat H_3` certifies that
nothing polynomial is left. This is the estimator the chapter should quote from, and the
lag at which orders 1 and 2 separate is itself the scale above which the motion is locally
straight.

Everything here works on **within-segment increments**, never on the displacement from
take-off: the second is the contaminated ensemble observable and no amount of filtering
repairs a common origin.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "centring_bias",
    "filtered_variation",
    "hurst_from_variations",
    "net_drift",
    "remove_drift",
    "wavelet_variance",
]

# Binomial filters. Order p annihilates polynomials of degree p-1: order 1 is the plain
# increment and removes a constant offset, order 2 removes a constant velocity -- the
# drift -- and order 3 a constant acceleration.
_FILTERS = {
    1: np.array([1.0, -1.0]),
    2: np.array([1.0, -2.0, 1.0]),
    3: np.array([1.0, -3.0, 3.0, -1.0]),
}


def net_drift(positions: np.ndarray, dt: float = 1.0) -> np.ndarray:
    """The flight's mean velocity, ``[r(T) - r(0)] / T``, in m/s.

    This is *not* the wind. It is the net displacement over the duration, which is the
    wind and the pilot's intention together, and it is the quantity
    ``01_fondamenta.md`` §1.4.3 keeps distinct from the hodograph's air motion.
    """
    duration = (len(positions) - 1) * dt
    if duration <= 0:
        return np.zeros(positions.shape[1])
    return (positions[-1] - positions[0]) / duration


def remove_drift(positions: np.ndarray, dt: float = 1.0, *, velocity=None) -> np.ndarray:
    """Subtract a constant drift, by default the flight's own net velocity.

    Args:
        positions: ``(n, 2)`` positions.
        dt: Grid step, in seconds.
        velocity: The drift to remove; the flight's own net velocity if omitted. Passing a
            velocity estimated on other data -- the first half of the flight, say -- is
            what makes the operation out-of-sample and avoids the bias
            :func:`centring_bias` measures.

    Returns:
        ``(n, 2)`` positions with the drift removed.
    """
    if velocity is None:
        velocity = net_drift(positions, dt)
    time = np.arange(len(positions), dtype=float)[:, None] * dt
    return positions - np.asarray(velocity, dtype=float)[None, :] * time


def filtered_variation(
    positions: np.ndarray, lags: np.ndarray, order: int = 1, dt: float = 1.0
) -> np.ndarray:
    """``V_p(lag) = < |A_p r|^2 >``, the order-``p`` filtered variation.

    ``A_p`` is the ``p``-th order difference at spacing ``lag``, summed over the two
    components so the result is rotation invariant. For a self-similar process of exponent
    ``H`` every order scales as ``lag^(2H)``; what differs between orders is what they
    annihilate first.

    Args:
        positions: ``(n, 2)`` positions on a uniform grid.
        lags: Lags in samples.
        order: Filter order, 1 to 3.
        dt: Grid step, in seconds (used only to keep the returned lags in seconds).

    Returns:
        ``V_p`` at each lag, ``nan`` where the series is too short to supply one value.
    """
    kernel = _FILTERS[order]
    out = np.full(len(lags), np.nan)
    for i, lag in enumerate(np.asarray(lags, dtype=int)):
        span = lag * (len(kernel) - 1)
        if lag < 1 or span >= len(positions):
            continue
        width = len(positions) - span
        acc = np.zeros((width, positions.shape[1]))
        for j, weight in enumerate(kernel):
            start = j * lag
            acc += weight * positions[start : start + width]
        # Sum over the components, so the statistic is invariant under a rotation of the
        # frame: an anisotropic ensemble must not give a different exponent for being
        # measured with north somewhere else.
        out[i] = float((acc**2).sum(axis=1).mean())
    return out


def hurst_from_variations(
    lags_s: np.ndarray, variation: np.ndarray, *, fit_range=None
) -> tuple[float, float]:
    """``(H, rms residual in dex)`` from a straight line through ``log V`` vs ``log lag``.

    The exponent is half the slope, since ``V ~ lag^(2H)``.
    """
    lags_s = np.asarray(lags_s, dtype=float)
    good = np.isfinite(variation) & (variation > 0) & (lags_s > 0)
    if fit_range is not None:
        good &= (lags_s >= fit_range[0]) & (lags_s <= fit_range[1])
    if good.sum() < 3:
        return float("nan"), float("nan")
    fit = np.polyfit(np.log10(lags_s[good]), np.log10(variation[good]), 1)
    residual = np.log10(variation[good]) - np.polyval(fit, np.log10(lags_s[good]))
    return float(fit[0] / 2.0), float(np.std(residual))


def wavelet_variance(positions: np.ndarray, dt: float = 1.0, *, order: int = 2):
    """The logscale diagram: variance of the detail coefficients, octave by octave.

    A Haar-like cascade with ``order`` vanishing moments, applied within the series. Each
    octave doubles the scale, so a self-similar process gives a straight line of slope
    ``2H + 1`` in ``log2 <d^2>`` against the octave index. It is the estimator with the
    best long-scale reach per unit of data here, and unlike a fitted local slope it
    supplies a per-octave count from which an honest weight can be built.

    Args:
        positions: ``(n, 2)`` positions on a uniform grid.
        dt: Grid step, in seconds.
        order: Vanishing moments, 1 to 3.

    Returns:
        ``(scales_s, variance, count)`` -- the scale of each octave in seconds, the mean
        squared detail coefficient there, and how many coefficients it averaged.
    """
    scales, variances, counts = [], [], []
    series = np.asarray(positions, dtype=float)
    octave = 1
    while len(series) >= 2 * (len(_FILTERS[order]) - 1) + 2:
        detail = filtered_variation(series, np.array([1]), order=order)[0]
        n = len(series) - (len(_FILTERS[order]) - 1)
        if np.isfinite(detail) and n > 0:
            scales.append(octave * dt)
            variances.append(detail)
            counts.append(n)
        # Coarse-grain by averaging adjacent pairs: one octave up, and the operation a
        # discrete wavelet transform performs with its scaling filter.
        cut = len(series) - (len(series) % 2)
        series = 0.5 * (series[:cut:2] + series[1:cut:2])
        octave *= 2
    return np.array(scales), np.array(variances), np.array(counts, dtype=int)


def centring_bias(
    hurst: float,
    *,
    n: int = 4096,
    n_flights: int = 200,
    lags=None,
    seed: int = 0,
) -> dict:
    """How much in-sample drift removal moves a known exponent, as a function of lag.

    The measurement the sketches ask for and do not make. Fractional Brownian motion of a
    known exponent is generated, the mean-squared displacement is computed raw and after
    subtracting each realisation's own net velocity, and the two are compared lag by lag.

    Because the subtracted velocity is estimated from the endpoint, the centred series is
    a bridge: its increments must sum to zero over the whole record, so the centred curve
    is pulled down at lags approaching the record length whatever the process does. The
    returned ``safe_fraction`` is the largest ``lag / n`` at which the centred curve is
    still within ``5``\\% of the raw one, and it is the honest upper end of any fit made on
    centred data.

    Args:
        hurst: The exponent to generate at; the MSD exponent is ``2H``.
        n: Samples per synthetic flight.
        n_flights: How many to average over.
        lags: Lags in samples; a geometric grid to ``n/2`` if omitted.
        seed: Base seed.

    Returns:
        ``{"lags", "raw", "centred", "ratio", "alpha_raw", "alpha_centred",
        "safe_fraction"}``.
    """
    from .synthetic import fractional_brownian

    if lags is None:
        lags = np.unique(np.round(np.geomspace(2, n // 2, 30)).astype(int))
    lags = np.asarray(lags, dtype=int)

    raw = np.zeros(len(lags))
    centred = np.zeros(len(lags))
    for k in range(n_flights):
        track = fractional_brownian(n, hurst, seed=seed + k)
        raw += filtered_variation(track, lags, order=1)
        centred += filtered_variation(remove_drift(track), lags, order=1)
    raw /= n_flights
    centred /= n_flights

    ratio = centred / raw
    within = lags[ratio > 0.95]
    alpha_raw, _ = hurst_from_variations(lags, raw)
    alpha_centred, _ = hurst_from_variations(lags, centred)
    return {
        "lags": lags,
        "raw": raw,
        "centred": centred,
        "ratio": ratio,
        "alpha_raw": 2 * alpha_raw,
        "alpha_centred": 2 * alpha_centred,
        "safe_fraction": float(within.max() / n) if within.size else 0.0,
    }
