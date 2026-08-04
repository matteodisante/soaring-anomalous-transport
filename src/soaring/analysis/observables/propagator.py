r"""The distribution of the increments, and the exponent read from its bulk.

Every exponent this project has measured so far comes from a *moment*: the mean square of a
displacement, or of a filtered difference of one. That has cost it twice. A moment is
sensitive to the tail, where the fewest flights contribute; and the ensemble-averaged
version of it is sensitive to the common origin, which on this archive turned out to measure
the geometry of the launch site rather than the motion. The first-passage time was tried as
an escape and shares the second fault, since it too is measured from take-off.

What escapes both is the distribution of the **increments** themselves. For a self-similar
process of exponent :math:`H`,

.. math::

    P(x,\Delta) = \Delta^{-H} F\!\left(\frac{x}{\Delta^{H}}\right),

so every quantile of :math:`|x|` grows as :math:`\Delta^{H}` and the peak height falls as
:math:`\Delta^{-H}`. Three things follow, and they are why this module exists.

**An exponent from the bulk.** The median absolute increment is an order statistic, not a
moment: it is set by the middle of the distribution, where every flight contributes, and a
heavy tail moves it not at all. Its log--log slope is :math:`H`.

**A test of self-similarity rather than an assumption of it.** The same slope read at the
25th, 50th, 75th and 90th percentiles must be the *same* slope. If the quantiles march at
different rates the process is not self-similar and no single :math:`H` describes it,
whatever a second moment returns. Nothing else in this project can say that.

**The collapse.** Plotting :math:`\Delta^{H}P` against :math:`x/\Delta^{H}` puts every lag
on one curve if the scaling form holds, and the curve is :math:`F` --- the shape the second
moment only summarises.

The accumulation is a histogram per lag per component, which is what makes it affordable in
one streaming pass: the archive is :math:`1.4\times10^{9}` fixes and no quantile of it can
be taken by sorting. The bins are logarithmic in :math:`|x|`, so their resolution is a fixed
fraction of the value rather than a fixed number of metres, which is the right thing for a
quantity that ranges over five decades.

The components are kept apart. Sec. 2.8 measures the archive as anisotropic --- the
east--west and north--south mean squares differ by about a quarter --- so a propagator pooled
over both would be a mixture of two scales and its collapse would fail for that reason alone.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "PropagatorAccumulator",
    "collapse_residual",
    "quantiles_from_histogram",
    "scaling_from_quantiles",
]

# Five decades of increment magnitude, from a metre to a hundred kilometres, at about two
# per cent a bin. Below a metre is the smoothing scale and above a hundred kilometres is
# longer than any leg this archive holds.
EDGES = np.geomspace(1.0, 1.0e5, 241)

QUANTILES = (0.25, 0.50, 0.75, 0.90)


class PropagatorAccumulator:
    """Histograms of ``|dx|`` and ``|dy|`` at each lag, accumulated one flight at a time.

    Args:
        lags: Lags in samples, one column of the histogram per entry.
        order: Difference order. 1 is the plain increment, which is what the scaling form
            above is written for.
        edges: Bin edges in metres; :data:`EDGES` by default.
    """

    def __init__(self, lags: np.ndarray, *, order: int = 1, edges: np.ndarray = EDGES):
        self.lags = np.asarray(lags, dtype=int)
        self.order = int(order)
        self.edges = np.asarray(edges, dtype=float)
        # [component, lag, bin]
        self.counts = np.zeros((2, self.lags.size, self.edges.size - 1), dtype=np.int64)
        self.totals = np.zeros((2, self.lags.size), dtype=np.int64)

    def add(self, positions: np.ndarray) -> None:
        """Accumulate one uniformly sampled record."""
        from soaring.analysis.observables.moments import _KERNELS

        positions = np.asarray(positions, dtype=float)
        kernel = _KERNELS[self.order]
        for i, lag in enumerate(self.lags):
            span = (len(kernel) - 1) * int(lag)
            if lag < 1 or span >= len(positions):
                continue
            width = len(positions) - span
            acc = np.zeros((width, positions.shape[1]))
            for j, weight in enumerate(kernel):
                start = j * int(lag)
                acc += weight * positions[start : start + width]
            # Stride by the span so no sample enters two windows, for the same reason the
            # moment spectrum does: an overlapping window counts one excursion many times.
            acc = acc[::span] if span > 0 else acc
            for component in range(2):
                magnitude = np.abs(acc[:, component])
                magnitude = magnitude[magnitude > 0]
                if magnitude.size == 0:
                    continue
                self.counts[component, i] += np.histogram(magnitude, bins=self.edges)[0]
                self.totals[component, i] += magnitude.size

    def to_dict(self) -> dict:
        return {
            "lags": self.lags,
            "edges": self.edges,
            "counts": self.counts,
            "totals": self.totals,
            "order": np.array([self.order]),
        }


def quantiles_from_histogram(
    counts: np.ndarray, edges: np.ndarray, probabilities=QUANTILES
) -> np.ndarray:
    """Quantiles of ``|x|`` read off a histogram, interpolated within the containing bin.

    The bins are logarithmic, so the interpolation is in ``log x``: the count is assumed
    uniform in log within a bin, which is the right assumption for a density falling like a
    power of ``x`` and is exact when the bins are narrow. At two per cent a bin the error is
    below the width of the bin either way.

    Returns:
        One quantile per entry of ``probabilities``; ``nan`` where the histogram is empty
        or the quantile falls outside the binned range.
    """
    counts = np.asarray(counts, dtype=float)
    edges = np.asarray(edges, dtype=float)
    total = counts.sum()
    out = np.full(len(probabilities), np.nan)
    if total <= 0:
        return out
    cumulative = np.concatenate([[0.0], np.cumsum(counts)]) / total
    for k, p in enumerate(probabilities):
        if p <= 0 or p >= 1 or cumulative[-1] < p:
            continue
        i = int(np.searchsorted(cumulative, p, side="left"))
        if i <= 0 or i >= len(edges):
            continue
        lower, upper = cumulative[i - 1], cumulative[i]
        if upper <= lower:
            out[k] = edges[i]
            continue
        frac = (p - lower) / (upper - lower)
        out[k] = np.exp(np.log(edges[i - 1]) + frac * (np.log(edges[i]) - np.log(edges[i - 1])))
    return out


def scaling_from_quantiles(
    lags_s: np.ndarray, quantiles: np.ndarray, *, fit_range=None
) -> dict:
    """``H`` from each quantile's growth with the lag, and how far the four disagree.

    For a self-similar process every quantile of ``|x|`` grows as ``lag^H`` with the same
    ``H``. Fitting each separately therefore gives one exponent four times, and their spread
    is a test of the scaling form rather than an error bar on it: quantiles that march at
    different rates are a distribution changing shape, which no single exponent describes.

    Args:
        lags_s: Lags in seconds.
        quantiles: ``(n_lags, n_quantiles)`` from :func:`quantiles_from_histogram`.
        fit_range: ``(low, high)`` in seconds; the whole range by default.

    Returns:
        ``{"hurst", "spread", "per_quantile", "lags_used"}``.
    """
    lags_s = np.asarray(lags_s, dtype=float)
    quantiles = np.asarray(quantiles, dtype=float)
    good = np.isfinite(lags_s) & (lags_s > 0)
    if fit_range is not None:
        good &= (lags_s >= fit_range[0]) & (lags_s <= fit_range[1])

    per = []
    for column in range(quantiles.shape[1]):
        usable = good & np.isfinite(quantiles[:, column]) & (quantiles[:, column] > 0)
        if usable.sum() < 4:
            per.append(np.nan)
            continue
        per.append(
            float(np.polyfit(np.log10(lags_s[usable]), np.log10(quantiles[usable, column]), 1)[0])
        )
    per = np.array(per)
    finite = np.isfinite(per)
    return {
        "hurst": float(np.median(per[finite])) if finite.any() else float("nan"),
        "spread": float(per[finite].max() - per[finite].min()) if finite.sum() > 1 else float("nan"),
        "per_quantile": per,
        "lags_used": int(good.sum()),
    }


def collapse_residual(
    lags_s: np.ndarray,
    counts: np.ndarray,
    edges: np.ndarray,
    hurst: float,
    *,
    fit_range=None,
    probes=(0.25, 0.5, 1.0, 2.0, 4.0),
) -> float:
    """How well ``Delta^H P`` against ``x/Delta^H`` falls on one curve, in dex.

    The scaling form is a statement that the rescaled histograms coincide, so the direct
    test is to rescale them and measure the scatter. Each lag's histogram is converted to a
    density in the rescaled variable ``u = x / lag^H``, read at a set of probe values of
    ``u``, and the spread across lags at each probe is taken in the log. A self-similar
    process gives a number set by counting noise; a process whose shape drifts with the
    scale gives one that does not fall as the sample grows.

    The probes are given in units of the rescaled distribution's own median, taken **once**
    over all the lags together and not per lag: probing at absolute values of ``u`` puts them
    wherever the process's amplitude happens to fall --- for a generator of scale 10 they land
    in the far left tail, where the log-density is counting noise and the test measures that
    instead. Normalising each lag by its *own* median would be the opposite error, since it
    would divide out the very scaling being tested.

    Returns:
        The median across probes of the standard deviation across lags of ``log10`` of the
        rescaled density, or ``nan`` if fewer than three lags are usable.
    """
    lags_s = np.asarray(lags_s, dtype=float)
    counts = np.asarray(counts, dtype=float)
    edges = np.asarray(edges, dtype=float)
    centres = np.sqrt(edges[:-1] * edges[1:])
    widths = np.diff(edges)

    usable = np.isfinite(lags_s) & (lags_s > 0) & (counts.sum(axis=1) > 0)
    if fit_range is not None:
        usable &= (lags_s >= fit_range[0]) & (lags_s <= fit_range[1])
    rows = np.flatnonzero(usable)
    if rows.size < 3:
        return float("nan")

    # One reference width for the whole family, from the pooled rescaled histogram.
    pooled = np.zeros(counts.shape[1])
    for i in rows:
        pooled += counts[i] / counts[i].sum()
    reference = quantiles_from_histogram(pooled, edges, (0.5,))[0]
    if not np.isfinite(reference) or reference <= 0:
        return float("nan")
    reference /= float(np.median(lags_s[rows] ** hurst))
    targets = np.asarray(probes, dtype=float) * reference

    curves = []
    for i in rows:
        scale = lags_s[i] ** hurst
        density = counts[i] / counts[i].sum() / widths      # per metre
        rescaled_u = centres / scale
        rescaled_p = density * scale                        # Delta^H P
        keep = rescaled_p > 0
        if keep.sum() < 5:
            continue
        curves.append(
            np.interp(
                np.log10(targets),
                np.log10(rescaled_u[keep]),
                np.log10(rescaled_p[keep]),
                left=np.nan,
                right=np.nan,
            )
        )
    if len(curves) < 3:
        return float("nan")
    stacked = np.vstack(curves)
    with np.errstate(invalid="ignore"):
        spread = np.nanstd(stacked, axis=0)
    return float(np.nanmedian(spread))
