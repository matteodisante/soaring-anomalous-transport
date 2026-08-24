r"""How long a heading survives, read from the velocity channel.

The velocity autocorrelation says how long a heading survives, and it is tied to the
displacement by Green--Kubo,
:math:`\mathrm{MSD}(t)=2\int_0^t(t-\tau)\,C(\tau)\,\mathrm{d}\tau`. That relation is used
here only through its scaling corollary --- :math:`C(\tau)\sim\tau^{-\gamma}` with
:math:`0<\gamma<1` gives :math:`\mathrm{MSD}(t)\sim t^{2-\gamma}` --- and not through the
integral, for two reasons that are properties of this archive rather than of the method.
The integral runs from zero and the correlation is only estimable above the smoothing scale
of the slowest logger, so its first decade is missing; and the correlation is estimated per
flight with that flight's own mean velocity removed, which biases every lag downwards by
roughly the record-mean of :math:`C` and so steepens the tail. Both push the same way:
:func:`vacf_tail_exponent` returns a :math:`\gamma` that is an upper bound, hence a
:math:`2-\gamma` that is a **lower** bound on the displacement exponent, and it is used as
one.
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
    """``<v(t) . v(t+tau)>`` by FFT, normalised to 1 at zero lag.

    The record's own mean velocity is removed first, so what is returned is the correlation
    of the fluctuation about the flown course and not of the velocity itself. That is the
    quantity wanted --- a shared course would otherwise hold ``C`` up at every lag --- but it
    costs a bias: subtracting a mean estimated from the same record pulls every lag down by
    about the record-mean of ``C``, which matters where ``C`` is small, that is in the tail.
    The estimate is therefore trustworthy in shape and sign, and steep in its tail; see
    :func:`vacf_tail_exponent`, which uses it one-sidedly for that reason.

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


def vacf_tail_exponent(
    lags: np.ndarray,
    correlation: np.ndarray,
    fit_range: tuple[float, float] | None = None,
) -> tuple[float, float, int]:
    """``(gamma, alpha_implied, n_lags)`` from a power-law fit to the tail of ``C(tau)``.

    Green--Kubo in its scaling form: a correlation decaying as ``tau^-gamma`` with
    ``0 < gamma < 1`` is non-integrable and sustains a displacement growing as
    ``t^(2-gamma)``, so the tail of the memory and the exponent of the motion are two
    readings of one thing. Comparing them is a cross-validation between the velocity
    channel and the position channel, which the pipeline builds by different routes.

    It is one-sided. Both biases documented in the module docstring steepen the measured
    tail, so ``gamma`` is an upper bound and ``2 - gamma`` a lower bound on the exponent:
    the check passes when the displacement exponent is the larger, and fails --- meaning
    one of the two channels is wrong --- only when it is smaller.

    Args:
        lags: Lags in seconds, ascending.
        correlation: ``C(tau)``, normalised or not; only its slope in log-log is used.
        fit_range: ``(low, high)`` in seconds; the whole positive range by default.

    Returns:
        ``(gamma, 2 - gamma, n_lags)``, or ``(nan, nan, 0)`` if fewer than four lags carry
        a positive correlation inside the range.
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
