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
    "VARIABLES",
    "KinematicAccumulator",
    "PropagatorAccumulator",
    "collapse_residual",
    "hurst_bootstrap_error",
    "peak_scaling",
    "quantiles_from_histogram",
    "scaling_from_quantiles",
    "turning_angles",
]

# Five decades of increment magnitude, from a metre to a hundred kilometres, at about two
# per cent a bin. Below a metre is the smoothing scale and above a hundred kilometres is
# longer than any leg this archive holds.
EDGES = np.geomspace(1.0, 1.0e5, 241)

QUANTILES = (0.25, 0.50, 0.75, 0.90)


#: The three variables histogrammed at each lag, in the order stored. ``E`` and
#: ``N`` are the two horizontal components; ``R`` is the modulus of the same vector
#: difference. The modulus is the one commensurate with the rest of the chapter -- the
#: ensemble MSD sums ``E**2 + N**2`` and the filtered variation sums over the components
#: to stay rotation invariant, so both are statements about ``|dr|`` and only a modulus
#: exponent can be set beside them. The components are kept because this archive is
#: anisotropic and their *difference* is the finding; they are not interchangeable with
#: the modulus, and on an anisotropic ensemble the modulus is not a power law of either.
VARIABLES = ("E", "N", "R")


class PropagatorAccumulator:
    """Histograms of ``|dx|``, ``|dy|`` and ``|dr|`` at each lag, one flight at a time.

    Args:
        lags: Lags in samples, one column of the histogram per entry.
        order: Difference order. 1 is the plain increment, which is what the scaling form
            above is written for.
        edges: Bin edges in metres; :data:`EDGES` by default.
        n_blocks: Keep a separate histogram per block as well as the pooled one, so that
            the reduction can resample blocks and get an uncertainty that is not the
            least-squares error of a fit whose points are not independent. One by
            default, which allocates nothing extra.
    """

    def __init__(
        self,
        lags: np.ndarray,
        *,
        order: int = 1,
        edges: np.ndarray = EDGES,
        n_blocks: int = 1,
    ):
        self.lags = np.asarray(lags, dtype=int)
        self.order = int(order)
        self.edges = np.asarray(edges, dtype=float)
        self.n_blocks = max(int(n_blocks), 1)
        n_bins = self.edges.size - 1
        # [variable, lag, bin], variables in the order of VARIABLES.
        self.counts = np.zeros((3, self.lags.size, n_bins), dtype=np.int64)
        self.totals = np.zeros((3, self.lags.size), dtype=np.int64)
        # int32 because this is the array that scales with the block count, and a
        # block's busiest bin holds a few million counts -- far below the limit.
        self.block_counts = (
            np.zeros((self.n_blocks, 3, self.lags.size, n_bins), dtype=np.int32)
            if self.n_blocks > 1
            else None
        )

    def add(self, positions: np.ndarray, block: int | None = None) -> None:
        """Accumulate one uniformly sampled record.

        Args:
            positions: ``(n, 2)`` positions on a uniform grid.
            block: Which resampling block this record belongs to. Records sharing a
                cluster must share a block or the resampling breaks the clustering it
                exists to respect.
        """
        from soaring.analysis.observables.moments import _KERNELS

        positions = np.asarray(positions, dtype=float)
        kernel = _KERNELS[self.order]
        block_counts = self.block_counts
        slot = (
            None if block_counts is None or block is None
            else int(block) % self.n_blocks
        )
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
            east, north = acc[:, 0], acc[:, 1]
            magnitudes = (np.abs(east), np.abs(north), np.hypot(east, north))
            for variable, magnitude in enumerate(magnitudes):
                magnitude = magnitude[magnitude > 0]
                if magnitude.size == 0:
                    continue
                binned = np.histogram(magnitude, bins=self.edges)[0]
                self.counts[variable, i] += binned
                self.totals[variable, i] += magnitude.size
                if slot is not None and block_counts is not None:
                    block_counts[slot, variable, i] += binned

    def block_quantiles(self, probabilities=QUANTILES) -> np.ndarray:
        """Each block's own quantiles, ``[block, variable, lag, probability]``.

        What the reduction resamples. The per-block histograms are not written out: a
        block holds enough increments to place a quantile precisely, so its quantiles
        carry everything the resampling needs at a thousandth of the size.

        Returns:
            The array, or an empty one when no blocks were kept.
        """
        if self.block_counts is None:
            return np.zeros((0, 3, self.lags.size, len(probabilities)))
        out = np.full(
            (self.n_blocks, 3, self.lags.size, len(probabilities)), np.nan, dtype=float
        )
        for b in range(self.n_blocks):
            for variable in range(3):
                for i in range(self.lags.size):
                    out[b, variable, i] = quantiles_from_histogram(
                        self.block_counts[b, variable, i], self.edges, probabilities
                    )
        return out

    def to_dict(self) -> dict:
        return {
            "lags": self.lags,
            "edges": self.edges,
            "counts": self.counts,
            "totals": self.totals,
            "order": np.array([self.order]),
            "block_quantiles": self.block_quantiles(),
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
    lags_s: np.ndarray,
    quantiles: np.ndarray,
    *,
    fit_range: tuple[float, float] | None = None,
) -> dict:
    """``H`` from each quantile's growth with the lag, and how far the four disagree.

    For a self-similar process every quantile of ``|x|`` grows as ``lag^H`` with the same
    ``H``. Fitting each separately therefore gives one exponent four times, and their spread
    is a test of the scaling form rather than an error bar on it: quantiles that march at
    different rates are a distribution changing shape, which no single exponent describes.

    ``per_quantile_err`` is the least-squares standard error of each slope
    (``np.polyfit(..., cov=True)``, the same convention as :func:`~soaring.analysis.
    observables.transport.fit_msd_exponent`). It is the precision of the log-log fit
    itself and nothing else: on this pass every lag's quantile is read off a
    histogram of millions of increments, so the fit is essentially noiseless and the
    error is small almost by construction. It answers "is this line straight to the
    resolution of the fit", not "how much would this exponent move on another sample
    of flights". For the second question use :func:`hurst_bootstrap_error`, which is
    what the chapter quotes.

    Args:
        lags_s: Lags in seconds.
        quantiles: ``(n_lags, n_quantiles)`` from :func:`quantiles_from_histogram`.
        fit_range: ``(low, high)`` in seconds; the whole range by default.

    Returns:
        ``{"hurst", "spread", "per_quantile", "per_quantile_err", "lags_used"}``.
    """
    lags_s = np.asarray(lags_s, dtype=float)
    quantiles = np.asarray(quantiles, dtype=float)
    good = np.isfinite(lags_s) & (lags_s > 0)
    if fit_range is not None:
        good &= (lags_s >= fit_range[0]) & (lags_s <= fit_range[1])

    slopes: list[float] = []
    errors: list[float] = []
    for column in range(quantiles.shape[1]):
        usable = good & np.isfinite(quantiles[:, column]) & (quantiles[:, column] > 0)
        if usable.sum() < 4:
            slopes.append(float("nan"))
            errors.append(float("nan"))
            continue
        coefficients, covariance = np.polyfit(
            np.log10(lags_s[usable]), np.log10(quantiles[usable, column]), 1, cov=True
        )
        slopes.append(float(coefficients[0]))
        errors.append(float(np.sqrt(covariance[0, 0])))
    per = np.array(slopes)
    per_err = np.array(errors)
    finite = np.isfinite(per)
    return {
        "hurst": float(np.median(per[finite])) if finite.any() else float("nan"),
        "spread": float(per[finite].max() - per[finite].min()) if finite.sum() > 1 else float("nan"),
        "per_quantile": per,
        "per_quantile_err": per_err,
        "lags_used": int(good.sum()),
    }


def hurst_bootstrap_error(
    lags_s: np.ndarray,
    block_quantiles: np.ndarray,
    *,
    fit_range: tuple[float, float] | None = None,
    n_resamples: int = 400,
    seed: int = 0,
) -> dict:
    """Cluster-robust error on ``H``, by resampling the blocks the pass kept.

    The least-squares error of the log--log fit is not an honest uncertainty here,
    for two reasons that both push the same way. The residuals are not independent:
    consecutive lags are built from the same fixes, so a quantile that sits high at
    one lag sits high at the next, and ordinary least squares reads that shared
    displacement as a well determined line. And every lag is pooled over the same
    flights, so the sample size the fit thinks it has is the number of *lags*, when
    the number of independent things in the archive is the number of *clusters of
    flights* -- the air over one site on one day being what two flights actually have
    in common (:mod:`soaring.analysis.stats.bootstrap`).

    Blocks are resampled with replacement and the statistic recomputed on each resample.
    Since only the blocks' quantiles are kept and not their histograms, the resampled
    statistic is fitted to the mean of the drawn blocks' quantiles rather than to the
    quantiles of their pooled histogram. The two agree when the blocks are of comparable
    size, which is what assigning whole clusters to blocks by hash is for, and this
    function supplies only the *spread* -- the central value comes from the pooled
    histogram either way.

    Args:
        lags_s: Lags in seconds.
        block_quantiles: ``(n_blocks, n_lags, n_quantiles)`` for one variable, from
            :meth:`PropagatorAccumulator.block_quantiles`.
        fit_range: ``(low, high)`` in seconds, as for :func:`scaling_from_quantiles`.
        n_resamples: How many resamples to draw.
        seed: Seed for the resampling, so the reported error is reproducible.

    Returns:
        ``{"hurst_err", "per_quantile_err", "n_blocks", "n_resamples"}``; the errors are
        ``nan`` when fewer than three blocks carry usable quantiles.
    """
    lags_s = np.asarray(lags_s, dtype=float)
    block_quantiles = np.asarray(block_quantiles, dtype=float)
    if block_quantiles.ndim != 3 or block_quantiles.shape[0] < 3:
        n_q = block_quantiles.shape[-1] if block_quantiles.ndim == 3 else 0
        return {
            "hurst_err": float("nan"),
            "per_quantile_err": np.full(n_q, np.nan),
            "n_blocks": (
                int(block_quantiles.shape[0]) if block_quantiles.ndim == 3 else 0
            ),
            "n_resamples": 0,
        }

    usable = np.flatnonzero(np.isfinite(block_quantiles).any(axis=(1, 2)))
    n_q = block_quantiles.shape[2]
    if usable.size < 3:
        return {
            "hurst_err": float("nan"),
            "per_quantile_err": np.full(n_q, np.nan),
            "n_blocks": int(usable.size),
            "n_resamples": 0,
        }

    rng = np.random.default_rng(seed)
    hursts = np.full(n_resamples, np.nan)
    per = np.full((n_resamples, n_q), np.nan)
    for draw in range(n_resamples):
        picked = rng.choice(usable, size=usable.size, replace=True)
        with np.errstate(invalid="ignore"):
            resampled = np.nanmean(block_quantiles[picked], axis=0)
        fitted = scaling_from_quantiles(lags_s, resampled, fit_range=fit_range)
        hursts[draw] = fitted["hurst"]
        per[draw] = fitted["per_quantile"]

    finite = np.isfinite(hursts)
    return {
        "hurst_err": (
            float(np.std(hursts[finite], ddof=1)) if finite.sum() > 1 else float("nan")
        ),
        "per_quantile_err": np.array(
            [
                float(np.std(per[np.isfinite(per[:, k]), k], ddof=1))
                if np.isfinite(per[:, k]).sum() > 1
                else float("nan")
                for k in range(n_q)
            ]
        ),
        "n_blocks": int(usable.size),
        "n_resamples": int(finite.sum()),
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


def peak_scaling(lags_s: np.ndarray, counts: np.ndarray, edges: np.ndarray,
                 *, fit_range=None, fraction: float = 0.1) -> tuple[float, int]:
    """``H`` from the height of the propagator at its centre, ``P_0 ~ Delta^-H``.

    The third reading of the same histograms, and the one that uses least of the
    distribution: the density near zero. Where a quantile is set by the middle of the
    distribution and a moment by its tail, this is set by its very centre, so it fails
    differently from both --- which is the whole reason to compute it.

    ``P_0`` is estimated as the density averaged over the smallest ``fraction`` of the
    distribution by probability, rather than at a single bin, because a logarithmic grid has
    no bin at zero and one bin anywhere is counting noise. The estimate is therefore of the
    density near the centre, which scales the same way.

    Returns:
        ``(hurst, n_lags)``, with ``hurst`` the negative slope of ``log P_0`` against
        ``log Delta``.
    """
    lags_s = np.asarray(lags_s, dtype=float)
    counts = np.asarray(counts, dtype=float)
    edges = np.asarray(edges, dtype=float)

    usable = np.isfinite(lags_s) & (lags_s > 0) & (counts.sum(axis=1) > 0)
    if fit_range is not None:
        usable &= (lags_s >= fit_range[0]) & (lags_s <= fit_range[1])
    rows = np.flatnonzero(usable)
    if rows.size < 4:
        return float("nan"), 0

    densities: list[float] = []
    for i in rows:
        total = counts[i].sum()
        cumulative = np.cumsum(counts[i]) / total
        upto = int(np.searchsorted(cumulative, fraction, side="left"))
        if upto < 1:
            densities.append(float("nan"))
            continue
        mass = counts[i, :upto].sum() / total
        span = edges[upto] - edges[0]
        densities.append(float(mass / span) if span > 0 else float("nan"))
    peak = np.array(densities)
    good = np.isfinite(peak) & (peak > 0)
    if good.sum() < 4:
        return float("nan"), 0
    slope = np.polyfit(np.log10(lags_s[rows][good]), np.log10(peak[good]), 1)[0]
    return float(-slope), int(good.sum())


def turning_angles(positions: np.ndarray, stride: int = 1) -> np.ndarray:
    """Angles between successive displacement vectors, in radians on ``[0, pi]``.

    The microscopic origin of the persistence the velocity autocorrelation measures: a
    distribution peaked at zero is a correlated walk, a flat one is memoryless
    reorientation.

    ``stride`` is a count of **samples**, not seconds, and is meant to be the width of the
    smoothing window: ``savgol_window(5.0, dt, 3)`` returns five samples at every retained
    cadence, so a five-sample stride makes the two successive displacement vectors share no
    sample, at every cadence, which is what stops the angle from measuring the filter
    instead of the flying. Converting it to seconds would defeat that -- at a five-second
    cadence ``round(5/dt)`` is one sample, and both vectors would sit inside one window.

    Zero-length steps carry no direction and are dropped rather than assigned one.
    """
    positions = np.asarray(positions, dtype=float)
    step = max(1, int(stride))
    steps = positions[step::step] - positions[:-step:step]
    if len(steps) < 2:
        return np.empty(0)
    first, second = steps[:-1], steps[1:]
    norms = np.hypot(first[:, 0], first[:, 1]) * np.hypot(second[:, 0], second[:, 1])
    good = norms > 0
    if not good.any():
        return np.empty(0)
    dot = (first[good, 0] * second[good, 0] + first[good, 1] * second[good, 1]) / norms[good]
    return np.arccos(np.clip(dot, -1.0, 1.0))


class KinematicAccumulator:
    """Histograms of the turning angle, the horizontal speed and the vertical velocity.

    The three observables Sec. 3.1 catalogues and nothing measured. They need no lag grid
    and no scaling argument --- they are the marginal distributions of what the pipeline
    already computes --- so they cost one histogram each and are folded into a pass that is
    reading the fix table anyway.
    """

    ANGLE_EDGES = np.linspace(0.0, np.pi, 91)
    SPEED_EDGES = np.linspace(0.0, 45.0, 181)
    VERTICAL_EDGES = np.linspace(-15.0, 15.0, 241)

    def __init__(self, *, angle_stride: int = 5):
        self.angle_stride = int(angle_stride)
        self.angle = np.zeros(self.ANGLE_EDGES.size - 1, dtype=np.int64)
        # The stride is a count of samples, so the same stride is a different interval on
        # each cadence class, and the pooled histogram mixes them: 89 % of paraglider fixes
        # are at 1 Hz but only 62 % of hang-glider ones, so the discipline comparison across
        # the pooled histogram is partly a comparison of logger populations. A second
        # histogram restricted to 1 Hz segments makes that comparison at a matched stride,
        # and there the stride really is five seconds.
        self.angle_one_hz = np.zeros(self.ANGLE_EDGES.size - 1, dtype=np.int64)
        self.speed = np.zeros(self.SPEED_EDGES.size - 1, dtype=np.int64)
        self.vertical = np.zeros(self.VERTICAL_EDGES.size - 1, dtype=np.int64)

    def add(
        self,
        positions: np.ndarray,
        velocity: np.ndarray,
        vertical: np.ndarray,
        dt: float | None = None,
    ) -> None:
        angles = turning_angles(positions, self.angle_stride)
        if angles.size:
            counted = np.histogram(angles, bins=self.ANGLE_EDGES)[0]
            self.angle += counted
            if dt is not None and float(dt) == 1.0:
                self.angle_one_hz += counted
        speed = np.hypot(velocity[:, 0], velocity[:, 1])
        speed = speed[np.isfinite(speed)]
        if speed.size:
            self.speed += np.histogram(speed, bins=self.SPEED_EDGES)[0]
        vertical = vertical[np.isfinite(vertical)]
        if vertical.size:
            self.vertical += np.histogram(vertical, bins=self.VERTICAL_EDGES)[0]

    def to_dict(self) -> dict:
        return {
            "angle_counts": self.angle,
            "angle_edges": self.ANGLE_EDGES,
            "speed_counts": self.speed,
            "speed_edges": self.SPEED_EDGES,
            "vertical_counts": self.vertical,
            "vertical_edges": self.VERTICAL_EDGES,
            "angle_stride": np.array([self.angle_stride]),
            "angle_counts_one_hz": self.angle_one_hz,
        }
