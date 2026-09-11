r"""Finite-record velocity correlation and descriptive power-law slope.

For a stationary centered velocity with covariance K, the centered displacement obeys
MSD(t)=2 integral_0^t (t-tau) K(tau) d tau. A normalized correlation C=K/K(0)
therefore requires the additional factor K(0). A finite-lag fitted slope does not
establish nonintegrability, an asymptotic exponent, or a one-sided bound: subtracting
an estimated segment mean introduces finite-record bias whose shape is process dependent.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "vacf_tail_exponent",
    "velocity_autocorrelation",
]


def velocity_autocorrelation(
    velocity: np.ndarray, max_lag: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Return the centered vector correlation normalized to one at zero lag.

    The mean is estimated from this record. This removes its constant velocity but
    introduces finite-record bias, especially at long lags. It neither identifies
    wind nor guarantees a bound on an underlying correlation exponent.

    Args:
        velocity: Velocity vectors on a uniform time grid.
        max_lag: Largest lag in samples, by default one quarter of the record.

    Returns:
        Sample lags and their normalized correlations.
    """
    velocity = np.asarray(velocity, dtype=float)
    n = len(velocity)
    if n < 8:
        return np.empty(0, dtype=int), np.empty(0)
    # `max_lag or n // 4` would read an explicit 0 as "unset", and would let a negative
    # value through to return a lag array and a correlation array of different lengths.
    max_lag = n // 4 if max_lag is None else max(0, min(int(max_lag), n - 1))
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


def vacf_tail_exponent(
    lags: np.ndarray,
    correlation: np.ndarray,
    fit_range: tuple[float, float] | None = None,
) -> tuple[float, float, int]:
    """Fit a finite-window power law to the positive correlation values.

    Returns ``(gamma, 2-gamma, n_lags)``. The second number is only the algebraic
    Green--Kubo scaling prediction under stationary velocity and a genuinely
    asymptotic nonintegrable tail with 0 < gamma < 1. The fit itself establishes
    neither those assumptions nor an upper or lower bound.

    Args:
        lags: Separations in seconds.
        correlation: Correlation at those separations.
        fit_range: Optional inclusive interval in seconds.

    Returns:
        The fitted exponent, conditional scaling prediction, and usable lag count.
    """
    lags = np.asarray(lags, dtype=float)
    correlation = np.asarray(correlation, dtype=float)
    good = np.isfinite(lags) & np.isfinite(correlation) & (correlation > 0) & (lags > 0)
    if fit_range is not None:
        good &= (lags >= fit_range[0]) & (lags <= fit_range[1])
    if good.sum() < 4:
        return float("nan"), float("nan"), 0
    slope = float(np.polyfit(np.log(lags[good]), np.log(correlation[good]), 1)[0])
    return -slope, 2.0 + slope, int(good.sum())
