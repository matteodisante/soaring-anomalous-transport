"""Global transport observables: the ones that need no segmentation (sec:obs-global).

The first of them, and the primary test for anomalous transport, is the
**ensemble-averaged mean-squared displacement**. Every flight starts at the horizontal
origin (``r(0) = 0``, sec:notation), so the position at elapsed time ``t`` *is* the
displacement from the start, and

    MSD(t) = < |r(t)|^2 >,

the average taken **over flights** at fixed ``t``. Its growth law ``MSD(t) ~ t^alpha``
fixes the transport regime: ``alpha = 1`` Brownian, ``alpha > 1`` super-diffusive,
``alpha < 1`` sub-diffusive, with the Hurst exponent ``H = alpha / 2``.

Three properties of the pre-processed data shape how it is computed here.

* **Segments do not restart the clock.** A flight split at a long gap contributes its
  position at every elapsed time some segment covers, and nothing at the times that fall
  inside the gap (sec:uniform, "Consequences of a split"): the MSD needs the position at
  a given elapsed time, not the path travelled in between, so a split costs it nothing
  but coverage.
* **Flights keep their own cadence.** A common grid is unnecessary; what is needed is
  the position *at* a lag, so a flight contributes to a lag when it has a fix within
  half its own native step of it, and abstains otherwise. Nothing is interpolated a
  second time here -- the one audited interpolation of the pipeline is at resampling.
* **The ensemble shrinks with the lag.** Only flights that lasted at least ``t``
  contribute to ``MSD(t)``, and the flights that last longest are not a random sample of
  the ensemble -- they are the ones that kept going. Every result therefore carries the
  count of contributing flights per lag, and a fit that ignores it is not to be trusted:
  the exponent is read on the range where the ensemble is still large.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# A flight contributes to a lag when it has a fix within half its native step of it.
# Half a step, and not a fixed tolerance, because the cadence spans 1 s to tens of
# seconds across the archive: any fixed value would either exclude the slow loggers or
# let a 1 Hz flight answer for a time it never sampled.
_MIN_TOLERANCE_S = 0.5

# Half-width of the window the local slope is fitted over, in decades of lag.
# See `local_slope` for why it is a window and not a difference of neighbours.
_SLOPE_HALF_WIDTH_DEX = 0.15


@dataclass(frozen=True)
class MSDResult:
    """An ensemble MSD curve and the ensemble behind it.

    Attributes:
        t: The lags, in seconds.
        msd: ``< |r(t)|^2 >`` in m^2, ``nan`` where no flight contributed.
        n_flights: How many flights contributed at each lag -- the number a fit range
            has to be chosen against.
        sem: Standard error of the mean at each lag, ``std / sqrt(n)``.
        p10: 10th percentile of ``|r(t)|^2`` across flights, ``nan`` if the samples were
            not kept. With the median and ``p90`` it is what shows that the ensemble
            average is an average over a *broad* distribution rather than a
            concentrated one, and how much of the mean one flight can carry.
        p50: Median of ``|r(t)|^2`` across flights. Not the same observable as the mean
            -- the MSD *is* the mean -- but the robust companion to it: where the two
            part company, the mean is being set by a tail.
        p90: 90th percentile.
    """

    t: np.ndarray
    msd: np.ndarray
    n_flights: np.ndarray
    sem: np.ndarray
    p10: np.ndarray | None = None
    p50: np.ndarray | None = None
    p90: np.ndarray | None = None

    def to_frame(self) -> pd.DataFrame:
        """The curve as a tidy table, one row per lag."""
        columns = {
            "t_s": self.t,
            "msd_m2": self.msd,
            "n_flights": self.n_flights,
            "sem_m2": self.sem,
        }
        for name, values in (
            ("p10_m2", self.p10),
            ("p50_m2", self.p50),
            ("p90_m2", self.p90),
        ):
            if values is not None:
                columns[name] = values
        return pd.DataFrame(columns)


def log_lag_grid(
    t_max_s: float, t_min_s: float = 1.0, n: int = 60, *, resolution_s: float = 1.0
) -> np.ndarray:
    """A logarithmically spaced grid of lags, the natural one for a power law.

    Args:
        t_max_s: Largest lag.
        t_min_s: Smallest lag; the native cadence is the sensible floor.
        n: Number of points before deduplication.
        resolution_s: Grid the lags are snapped to; ``0`` leaves them unsnapped. Without
            it the short end of a log grid is finer than the data -- at a 1 s cadence,
            lags of 1.00, 1.13 and 1.27 s all resolve to the *same* fix, so the curve
            there is a staircase of repeated values whose local slope alternates between
            zero and a spurious spike. At long lags the rounding is a part in 10^4.

    Returns:
        The lags, ascending and distinct.
    """
    grid = np.geomspace(t_min_s, t_max_s, n)
    if resolution_s > 0:
        grid = np.round(grid / resolution_s) * resolution_s
    return np.unique(grid[grid > 0])


class MSDAccumulator:
    """Accumulates an ensemble MSD one flight at a time.

    One flight at a time, and never the whole archive in memory: the ``fixes`` table
    runs to ~10^9 rows, so the curve is built by streaming it past this object rather
    than by loading it. Feed it *whole* flights --
    :func:`soaring.analysis.derived.stream_flights` is what produces them -- and never
    the contents of a Parquet row group, which is a unit of storage and cuts across
    flights.
    """

    def __init__(self, lags: np.ndarray, *, keep_samples: bool = True) -> None:
        """Start an empty accumulator on the given lag grid.

        Args:
            lags: The lag grid.
            keep_samples: Also keep every flight's ``|r(t)|^2`` per lag, so the result
                can carry percentiles and not only the mean. One ``float32`` per lag per
                flight -- 90 lags over the paraglider archive is under 100 MB -- which
                buys the answer to the question the mean alone cannot settle: whether
                the average describes the ensemble or is carried by a few flights.
        """
        self.lags = np.asarray(lags, dtype=float)
        self._sum = np.zeros(self.lags.size)
        self._sum_sq = np.zeros(self.lags.size)
        self._count = np.zeros(self.lags.size, dtype=np.int64)
        self._samples: list[np.ndarray] | None = [] if keep_samples else None

    def add(self, t: np.ndarray, east: np.ndarray, north: np.ndarray) -> None:
        """Add one flight, given its fixes in the parent clock and local frame.

        Args:
            t: Elapsed times of the flight's fixes, ascending, in the parent clock --
                the times of *every* retained segment, concatenated.
            east: The ``E`` coordinate at those times.
            north: The ``N`` coordinate at those times.
        """
        t = np.asarray(t, dtype=float)
        if t.size < 2:
            return
        native_dt = float(np.median(np.diff(t)))
        tolerance = max(_MIN_TOLERANCE_S, 0.5 * native_dt)
        position = (
            np.asarray(east, dtype=float) ** 2 + np.asarray(north, dtype=float) ** 2
        )

        pos = np.searchsorted(t, self.lags)
        left = np.clip(pos - 1, 0, t.size - 1)
        right = np.clip(pos, 0, t.size - 1)
        take_left = np.abs(t[left] - self.lags) <= np.abs(t[right] - self.lags)
        nearest = np.where(take_left, left, right)
        # Within half a step of a fix -- and never below the flight's own cadence. A
        # 5 s logger has no fix at t = 1 s: without the second condition the half-step
        # tolerance would let it answer with its fix at t = 0, i.e. with a displacement
        # of exactly zero, and a slow-cadence minority would drag the short-lag MSD down
        # until the lag grid crossed their step. That is an artefact of the estimator,
        # not a property of the motion.
        covered = (np.abs(t[nearest] - self.lags) <= tolerance) & (
            self.lags >= native_dt
        )

        squared = np.where(covered, position[nearest], 0.0)
        self._sum += squared
        self._sum_sq += squared**2
        self._count += covered
        if self._samples is not None:
            self._samples.append(np.where(covered, squared, np.nan).astype(np.float32))

    def stacked_samples(self) -> np.ndarray | None:
        """The per-flight ``|r(t)|^2``, one row per flight, or ``None`` if not kept.

        What :func:`bootstrap_alpha_error` needs, and the reason ``keep_samples`` is on
        by default: an uncertainty on the exponent that resamples flights cannot be
        computed from the averaged curve alone.
        """
        if self._samples is None or not self._samples:
            return None
        return np.vstack(self._samples)

    def result(self) -> MSDResult:
        """The curve accumulated so far."""
        n = self._count
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(n > 0, self._sum / np.maximum(n, 1), np.nan)
            variance = np.where(
                n > 1, self._sum_sq / np.maximum(n, 1) - mean**2, np.nan
            )
            sem = np.sqrt(np.maximum(variance, 0.0) / np.maximum(n, 1))
        percentiles: list[np.ndarray] | list[None] = [None, None, None]
        if self._samples:
            stacked = np.vstack(self._samples)
            # Only the lags some flight answered: nanpercentile over an all-nan column
            # is a warning and a nan, and the nan is already what `n == 0` says.
            answered = n > 0
            percentiles = [np.full(n.size, np.nan) for _ in range(3)]
            if answered.any():
                for target, q in zip(percentiles, (10.0, 50.0, 90.0), strict=True):
                    target[answered] = np.nanpercentile(stacked[:, answered], q, axis=0)
        return MSDResult(
            t=self.lags,
            msd=mean,
            n_flights=n,
            sem=sem,
            p10=percentiles[0],
            p50=percentiles[1],
            p90=percentiles[2],
        )


def ensemble_msd(fixes: pd.DataFrame, lags: np.ndarray) -> MSDResult:
    """The ensemble MSD of a ``fixes`` table held in memory.

    Args:
        fixes: Rows with ``flight_id``, ``t``, ``E``, ``N`` -- every retained segment of
            every flight, since a segment keeps its parent's clock and origin.
        lags: The lag grid.

    Returns:
        The :class:`MSDResult`.
    """
    accumulator = MSDAccumulator(lags)
    for _, flight in fixes.groupby("flight_id", sort=False):
        ordered = flight.sort_values("t")
        accumulator.add(
            ordered["t"].to_numpy(), ordered["E"].to_numpy(), ordered["N"].to_numpy()
        )
    return accumulator.result()


@dataclass(frozen=True)
class PowerLawFit:
    """A straight line fitted to ``log MSD`` against ``log t``.

    Attributes:
        alpha: The exponent, the slope of the fit.
        alpha_err: Its standard error, from the least-squares covariance.
        prefactor: ``K`` in ``MSD = K t^alpha``, in m^2/s^alpha.
        t_min: Lower end of the fitted range, in seconds.
        t_max: Upper end.
        n_points: How many lags the fit used.
    """

    alpha: float
    alpha_err: float
    prefactor: float
    t_min: float
    t_max: float
    n_points: int


def fit_msd_exponent(
    result: MSDResult,
    *,
    t_min_s: float,
    t_max_s: float,
    min_flights: int = 100,
) -> PowerLawFit:
    """Fit ``MSD ~ K t^alpha`` on a lag range, in log-log space.

    Unweighted in log space, which is the right choice for a scaling exponent: it gives
    every decade the same say, whereas a fit weighted by the (much larger) absolute
    errors at long lags would be dominated by the last decade alone.

    Args:
        result: The curve to fit.
        t_min_s: Lower end of the fit range.
        t_max_s: Upper end.
        min_flights: Lags with fewer contributing flights are excluded, whatever the
            range says: at the long-lag end the ensemble thins out, and the flights left
            there are the ones that kept going rather than a random sample of it.

    Returns:
        The :class:`PowerLawFit`.

    Raises:
        ValueError: If fewer than three lags survive the range and the count cut.
    """
    usable = (
        np.isfinite(result.msd)
        & (result.msd > 0)
        & (result.t >= t_min_s)
        & (result.t <= t_max_s)
        & (result.n_flights >= min_flights)
    )
    if usable.sum() < 3:
        raise ValueError(
            f"only {int(usable.sum())} usable lags in [{t_min_s}, {t_max_s}] s with at "
            f"least {min_flights} flights: nothing to fit"
        )
    log_t = np.log10(result.t[usable])
    log_msd = np.log10(result.msd[usable])
    coefficients, covariance = np.polyfit(log_t, log_msd, 1, cov=True)
    slope, intercept = coefficients
    return PowerLawFit(
        alpha=float(slope),
        alpha_err=float(np.sqrt(covariance[0, 0])),
        prefactor=float(10.0**intercept),
        t_min=float(result.t[usable].min()),
        t_max=float(result.t[usable].max()),
        n_points=int(usable.sum()),
    )


def bootstrap_alpha_error(
    samples: np.ndarray,
    lags: np.ndarray,
    *,
    t_min_s: float,
    t_max_s: float,
    n_resamples: int = 200,
    seed: int = 20260803,
) -> float:
    """The sampling uncertainty on ``alpha``, by resampling the flights themselves.

    The error :func:`fit_msd_exponent` reports is the ordinary least-squares error
    on the slope, and it answers a question nobody asked: how well the fitted line
    describes *these* points, treating the residual at each lag as an independent
    draw. They are nothing of the kind. Every lag of an ensemble MSD is an average
    over the *same* flights, so the residuals are almost perfectly correlated -- a
    flight that happens to fly far contributes to every lag at once, tilting the
    whole curve rather than scattering one point off it. The least-squares error
    cannot see that, and it understates the real uncertainty by roughly a factor of
    four.

    What the exponent's uncertainty actually depends on is which flights the ensemble
    happens to contain, so that is what is resampled: draw ``n_resamples`` ensembles of
    the same size with replacement from the flights, refit each, and report the standard
    deviation of the exponents. This is the ordinary non-parametric bootstrap with the
    flight as the resampling unit, which is the unit the ensemble average is over.

    Args:
        samples: ``(n_flights, n_lags)`` of ``|r(t)|^2``, ``nan`` where a flight did
            not reach that lag -- what ``keep_samples=True`` makes an accumulator hold.
        lags: The lag grid, matching the columns of ``samples``.
        t_min_s: Lower end of the fit range -- the same one the reported fit used.
        t_max_s: Upper end.
        n_resamples: How many ensembles to draw. 200 is enough for a standard deviation;
            a confidence interval would want more.
        seed: Fixed, so the reported uncertainty is reproducible.

    Returns:
        The standard deviation of ``alpha`` over the resampled ensembles, or ``nan`` if
        fewer than three lags of the range can be fitted.
    """
    stacked = np.asarray(samples, dtype=float)
    if stacked.ndim != 2 or stacked.shape[0] < 2:
        return float("nan")
    window = (lags >= t_min_s) & (lags <= t_max_s)
    if window.sum() < 3:
        return float("nan")
    within = stacked[:, window]
    log_t = np.log10(lags[window])

    rng = np.random.default_rng(seed)
    n_flights = within.shape[0]
    alphas = []
    for _ in range(n_resamples):
        draw = rng.integers(0, n_flights, n_flights)
        with np.errstate(invalid="ignore"):
            curve = np.nanmean(within[draw], axis=0)
        usable = np.isfinite(curve) & (curve > 0)
        if usable.sum() < 3:
            continue
        slope, _ = np.polyfit(log_t[usable], np.log10(curve[usable]), 1)
        alphas.append(float(slope))
    return float(np.std(alphas, ddof=1)) if len(alphas) > 2 else float("nan")


def local_slope(
    result: MSDResult, half_width_dex: float = _SLOPE_HALF_WIDTH_DEX
) -> tuple[np.ndarray, np.ndarray]:
    """The local logarithmic slope ``d log MSD / d log t``, by windowed regression.

    The honest companion to a fitted exponent: a power law is a *straight line* in
    log-log, so the slope is flat where one exponent describes the data and bends where
    the regime changes. Reading a single ``alpha`` off a curve whose local slope drifts
    would hide exactly the crossover that matters.

    It is a regression over a window and not a centred difference between
    neighbours, and the difference is visible on the page. Adjacent lags of the grid
    this module builds are about 0.05 decades apart, so a centred difference divides
    by twice that and multiplies whatever the curve carries by roughly four. On the
    archive that turns a point-to-point scatter of a few tenths of a per cent in the
    MSD into a slope that jitters by 0.05 and reads as noise, on a curve whose own
    standard error is 0.3 %.

    The window is a compromise stated rather than tuned: too narrow and the
    amplification returns, too wide and a genuine bend is flattened into the
    straight line the panel exists to test for. At the adopted 0.15 decades it spans
    five to six points and resolves a crossover of half a decade. It does not remove
    the structure it is pointed at: the residual wiggle of this archive is
    correlated across some four grid points, so it survives the window, which is the
    correct outcome for something that is not noise.

    The regression is robust in the sense that matters here, which is resistance to
    a single bad lag rather than to a heavy-tailed residual: it is a Theil--Sen
    estimator, the median of the slopes of all pairs of points in the window. One
    lag knocked out by a coverage artefact moves the median by nothing, where least
    squares would tilt the whole window. On a clean stretch the two agree to a few
    thousandths, so nothing is lost by using it everywhere.

    It is reported with an uncertainty, because a slope drawn without one invites
    the eye to read structure into a wiggle. The uncertainty is the interquartile
    range of those same pairwise slopes divided by ``1.35``, a robust standard
    deviation, divided again by the square root of the number of points in the
    window -- the scatter of the window about its own line, expressed as an error on
    its slope.

    Args:
        result: The curve.
        half_width_dex: Half-width of the fitting window, in decades of lag.

    Returns:
        ``(slope, error)``, both the length of ``result.t``, and both ``nan``
        wherever the window holds fewer than three usable points.
    """
    usable = np.isfinite(result.msd) & (result.msd > 0) & (result.t > 0)
    log_t = np.log10(np.where(usable, result.t, np.nan))
    log_msd = np.log10(np.where(usable, result.msd, np.nan))
    slope = np.full(result.t.size, np.nan)
    error = np.full(result.t.size, np.nan)
    for i in np.flatnonzero(usable):
        window = np.flatnonzero(usable & (np.abs(log_t - log_t[i]) <= half_width_dex))
        if window.size < 3:
            continue
        x, y = log_t[window], log_msd[window]
        a, b = np.triu_indices(x.size, k=1)
        gaps = x[b] - x[a]
        pairs = (y[b] - y[a])[gaps > 0] / gaps[gaps > 0]
        if pairs.size < 2:
            continue
        slope[i] = float(np.median(pairs))
        spread = float(np.subtract(*np.percentile(pairs, [75, 25]))) / 1.349
        error[i] = spread / np.sqrt(x.size)
    return slope, error


def coverage_limited_range(
    result: MSDResult, *, t_min_s: float, min_coverage: float = 0.25
) -> tuple[float, float]:
    """A fit range whose upper end is set by how much of the ensemble is still there.

    The lower end is an argument, because what sets it is physics: below the thermalling
    period the MSD is dominated by circling rather than by transport, so the fit starts
    above it. The upper end is not a choice but a consequence -- the ensemble thins out
    with the lag, and the flights that remain are the ones that kept going, so the curve
    stops being an average over the population well before it stops being computable.
    The cut is where the count falls below ``min_coverage`` of the ensemble at the
    lower end.

    Args:
        result: The curve.
        t_min_s: Lower end of the range, in seconds.
        min_coverage: Fraction of the ensemble at ``t_min_s`` that must survive.

    Returns:
        ``(t_min_s, t_max_s)``.
    """
    in_range = result.t >= t_min_s
    if not in_range.any() or result.n_flights[in_range][0] == 0:
        return t_min_s, float(result.t.max())
    reference = result.n_flights[in_range][0]
    enough = in_range & (result.n_flights >= min_coverage * reference)
    return t_min_s, float(result.t[enough].max())


def time_averaged_msd(east: np.ndarray, north: np.ndarray, dt_s: float) -> np.ndarray:
    r"""The time-averaged MSD of one uniformly sampled segment (thesis, sec:obs-global).

    Slides a window of width ``tau`` along the trajectory and averages the squared
    displacement over every starting time *inside that segment*::

        delta2(tau) = < |r(t0 + tau) - r(t0)|^2 >_{t0}

    The average over ``t0`` is a **time** average internal to one flight; it has nothing
    to do with the ensemble average over flights that the MSD uses, and the two answer
    different questions. A feature at a fixed elapsed time can only be something the
    ensemble is synchronised on -- every flight starts at take-off -- whereas a feature
    at a fixed *lag*, seen here, is a property of the motion wherever it occurs.

    Computed **within a segment**, never across a split: a time-averaged window is one
    of the quantities sec:uniform requires to stay inside a segment, since the
    trajectory across the gap that ends it is unknown.

    The direct double loop is ``O(n^2)`` and hopeless at 10^4 samples per segment. The
    identity behind the implementation is standard: writing ``D_j = |r_j|^2``,

        delta2(k) = mean_j (D_j + D_{j+k}) - 2 mean_j (r_j . r_{j+k}),

    where the first term is a pair of running sums and the second an autocorrelation,
    which the FFT gives in ``O(n log n)``.

    Args:
        east: The ``E`` coordinate on a uniform grid.
        north: The ``N`` coordinate on the same grid.
        dt_s: The grid step, in seconds.

    Returns:
        ``delta2`` at lags ``0, dt, 2 dt, ...``, of the same length as the input; entry
        ``0`` is zero by construction. An array of one ``nan`` if the segment is too
        short to carry a lag.
    """
    n = int(np.asarray(east).size)
    if n < 2:
        return np.full(1, np.nan)
    squared = np.asarray(east, dtype=float) ** 2 + np.asarray(north, dtype=float) ** 2

    # First term: the mean over starting points of D_j + D_{j+k}. Both sums are
    # contiguous ranges of D, so a prefix sum gives every lag at once -- no Python loop
    # over lags, which at 10^4 samples per segment and 10^5 flights would dominate.
    prefix = np.concatenate([[0.0], np.cumsum(squared)])
    lag = np.arange(n)
    first = (prefix[n - lag] + prefix[n] - prefix[lag]) / (n - lag)

    # Second term: the autocorrelation of each component, via the FFT.
    size = 2 * n
    correlation = np.zeros(n)
    for component in (east, north):
        values = np.asarray(component, dtype=float)
        spectrum = np.fft.rfft(values, size)
        full = np.fft.irfft(spectrum * np.conjugate(spectrum), size)[:n]
        correlation += full / (n - np.arange(n))
    _ = dt_s  # the lag axis is the caller's: k * dt_s
    return first - 2.0 * correlation


class TAMSDAccumulator:
    """Accumulates the ensemble-averaged time-averaged MSD, one segment at a time.

    The companion the ensemble MSD needs, and not a refinement of it. The two average
    over different things, so a feature can appear in one and not the other, and that
    difference is itself the measurement: the ensemble is synchronised at take-off, so
    anything it shows at a fixed *elapsed time* is a property of that common origin,
    whereas a time average slides its window along each flight and sees a lag wherever
    it occurs. Where the two disagree the process is not ergodic (sec:obs-global), and
    where the ensemble alone shows a feature, the feature belongs to the launch.

    Accumulated on a **time** lag axis, so flights of different cadence pool: each
    segment contributes at the lags its own grid resolves.
    """

    def __init__(self, lags_s: np.ndarray) -> None:
        """Start an empty accumulator on the given lag grid, in seconds."""
        self.lags = np.asarray(lags_s, dtype=float)
        self._sum = np.zeros(self.lags.size)
        self._count = np.zeros(self.lags.size, dtype=np.int64)
        self._samples: list[np.ndarray] = []

    def add(self, east: np.ndarray, north: np.ndarray, dt_s: float) -> None:
        """Add one segment, given its coordinates on a uniform grid of step ``dt_s``."""
        n = int(np.asarray(east).size)
        if n < 3 or not np.isfinite(dt_s) or dt_s <= 0:
            return
        delta2 = time_averaged_msd(east, north, dt_s)
        index = np.round(self.lags / dt_s).astype(int)
        # A lag the segment cannot resolve -- shorter than its step, or longer than the
        # segment itself -- is not answered rather than answered badly. The last few
        # lags of a segment average over a handful of starting points, so they are cut
        # at half its length, where the time average still has something to average.
        # `index >= 1` alone lets a segment answer any lag from dt/2 upwards, with the
        # value belonging to a *full* step: a 10 s logger answered a lag of 6 s with its
        # value at 10 s, an overstatement of 2.8x, and every slow-cadence segment
        # inflated the short-lag end. The ensemble estimator has carried the matching
        # guard from the start (`self.lags >= native_dt`); this is the same statement,
        # and the two must agree or the comparison between the averages is between two
        # different things.
        usable = (self.lags >= dt_s) & (index >= 1) & (index <= n // 2)
        values = np.where(usable, delta2[np.clip(index, 0, n - 1)], np.nan)
        self._sum += np.where(usable, values, 0.0)
        self._count += usable
        self._samples.append(values.astype(np.float32))

    def stacked_samples(self) -> np.ndarray | None:
        """The per-segment ``delta2(tau)``, one row per segment."""
        return np.vstack(self._samples) if self._samples else None

    def result(self) -> MSDResult:
        """The curve accumulated so far, with its across-segment percentiles."""
        n = self._count
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(n > 0, self._sum / np.maximum(n, 1), np.nan)
        stacked = np.vstack(self._samples) if self._samples else np.zeros((1, n.size))
        # Only the lags some segment answered: nanpercentile over an all-nan column is
        # a warning and a nan, and the nan is already what `n == 0` says.
        answered = n > 0
        percentiles = [np.full(n.size, np.nan) for _ in range(3)]
        if answered.any():
            for target, q in zip(percentiles, (10.0, 50.0, 90.0), strict=True):
                target[answered] = np.nanpercentile(stacked[:, answered], q, axis=0)
        return MSDResult(
            t=self.lags,
            msd=mean,
            n_flights=n,
            sem=np.full(n.size, np.nan),
            p10=percentiles[0],
            p50=percentiles[1],
            p90=percentiles[2],
        )
