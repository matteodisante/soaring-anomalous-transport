"""Raw, paired barometric/GNSS spectral diagnostics and channel availability.

Spectra describe logged signals, not identified sensor errors. At each frequency
we report medians and between-flight bands; a high-frequency band statistic measures
heterogeneity without attributing it to quantization, multipath or receiver tracking.
Each spectral pair uses the same longest uninterrupted interval of usable readings.
Presence statistics use a separate census or explicitly sampled population.
"""

from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .igc import (
    baro_present_fraction,
    gnss_present_fraction,
    median_sampling_period,
    parse_igc,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# High-frequency diagnostic band at the dominant 1 Hz recording cadence.
FLOOR_BAND_HZ = (0.35, 0.5)

# Welch segment length (fixed so every flight yields the same frequency grid).
NPERSEG = 256
PSD_CACHE_VERSION = 2
# A flight qualifies for the PSD only if its native cadence matches the sample
# mode within this tolerance (so the pooled spectra share one sampling frequency).
DT_TOLERANCE_S = 0.25
# Raw diagnostic presence cut: fraction of finite, non-zero pressure-altitude fields.
# This is not a sensor-health test. The cleaner adopts GNSS altitude; eligibility of
# a barometric witness additionally requires the configured flight and local support.
BARO_PRESENT_MIN = 0.95
# Width of the diagnostic band immediately below BARO_PRESENT_MIN. Its records have
# incomplete field availability; the cause and the reliability of available values
# are not determined by the fraction alone.
BARO_BORDERLINE_MARGIN = 0.05


def required_sample_size(
    margin_of_error: float,
    *,
    confidence: float = 0.95,
    p: float = 0.5,
) -> int:
    """Sample size needed to estimate a population proportion to a given precision.

    Standard normal-approximation formula for a proportion,
    ``n = z^2 p(1-p) / e^2``. The population is treated as effectively infinite (no
    finite-population correction). The default ``p=0.5`` maximises the Bernoulli
    variance, giving a conservative planning size under this normal approximation.
    It does not guarantee realised error or exact finite-sample coverage.

    Args:
        margin_of_error: Desired confidence-interval half-width (e.g. ``0.02`` for a
            target precision of +/-2 percentage points).
        confidence: Confidence level (``0.95`` -> a 95% interval).
        p: Assumed proportion used for the (conservative) variance bound.

    Returns:
        The required sample size, rounded up to the nearest integer.
    """
    from scipy.stats import norm

    z = norm.ppf(0.5 + confidence / 2.0)
    n = (z**2) * p * (1.0 - p) / (margin_of_error**2)
    return int(np.ceil(n))


def proportion_ci(k: int, n: int, *, confidence: float = 0.95) -> tuple[float, float]:
    """Point estimate and Wald normal-approximation interval for a proportion.

    The formula assumes a Bernoulli sample with independent observations and has poor
    coverage near zero or one. It is not an exact finite-sample interval and is not
    automatically suppressed for a census; a caller reporting a complete population
    must state that scope separately. No finite-population correction is applied.

    Args:
        k: Number of observations satisfying the condition.
        n: Number of observations in the denominator.
        confidence: Nominal confidence level.

    Returns:
        Estimate and z*sqrt(p_hat*(1-p_hat)/n) half-width. For n=0, returns
        (0, NaN); endpoint estimates give zero width under this approximation."""
    if n == 0:
        return 0.0, float("nan")
    p_hat = k / n
    from scipy.stats import norm

    z = norm.ppf(0.5 + confidence / 2.0)
    half_width = z * (p_hat * (1.0 - p_hat) / n) ** 0.5
    return p_hat, half_width


def sample_igc_paths(igc_dir: Path, n: int, *, seed: int = 0) -> list[Path]:
    """Deterministically sample ``n`` ``.igc`` paths under an ``igc/`` directory.

    Args:
        igc_dir: The ``igc/`` root (one sub-directory per season).
        n: Number of files to sample (all of them if fewer are available).
        seed: RNG seed for a reproducible sample.

    Returns:
        A sorted-then-sampled list of file paths.
    """
    all_paths = sorted(Path(igc_dir).rglob("*.igc"))
    if len(all_paths) <= n:
        return all_paths
    return sorted(random.Random(seed).sample(all_paths, n))


def _uniform_resample(t: np.ndarray, z: np.ndarray, dt: float) -> np.ndarray:
    """Linearly resample ``z(t)`` onto a uniform grid of step ``dt`` over its span."""
    grid = t[0] + np.arange(int(np.floor((t[-1] - t[0]) / dt)) + 1) * dt
    return np.interp(grid, t, z)


def longest_regular_block(
    t: np.ndarray, values: np.ndarray, dt: float
) -> tuple[np.ndarray, np.ndarray]:
    """Longest finite, forward-time run without a gap larger than 1.5 native steps.

    ``values`` can hold multiple paired channels. Missing rows, backward/duplicate
    timestamps and long gaps split the diagnostic; they are never interpolated across.
    The earliest run wins a tie. This is diagnostic selection, not archive cleaning.
    """
    t = np.asarray(t, dtype=float)
    values = np.asarray(values, dtype=float)
    if not len(t):
        return t, values
    finite = np.isfinite(t) & np.all(np.isfinite(values.reshape(len(t), -1)), axis=1)
    links = np.zeros(len(t), dtype=bool)
    links[1:] = finite[:-1] & finite[1:] & (np.diff(t) > 0) & (np.diff(t) <= 1.5 * dt)
    starts = np.flatnonzero(finite & ~links)
    best = (0, 0)
    for start in starts:
        stop = start + 1
        while stop < len(t) and links[stop]:
            stop += 1
        if stop - start > best[1] - best[0]:
            best = (int(start), int(stop))
    return t[slice(*best)], values[slice(*best)]


def _welch(z: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Welch PSD after subtracting each window's fitted linear trend.

    Detrending suppresses slow variation but does not remove every climb shape or
    separate physical dynamics from sensor noise."""
    from scipy.signal import welch

    nperseg = min(NPERSEG, len(z))
    f, pxx = welch(z, fs=fs, nperseg=nperseg, detrend="linear")
    return f, pxx


def _gnss_present_frac(path: Path) -> float | None:
    """Worker: parse one file and report its GNSS-presence fraction.

    A top-level function (rather than a closure) so it can be pickled for
    :class:`~concurrent.futures.ProcessPoolExecutor`.

    Returns:
        The fraction of fixes carrying a non-zero GNSS altitude, or ``None`` if the
        file has too few fixes to judge (excluded from the distribution).
    """
    fixes = parse_igc(path)
    if len(fixes) < 3:
        return None
    return gnss_present_fraction(fixes)


def gnss_presence_stats(
    samples: dict[str, list[Path]], *, n_jobs: int = 1
) -> dict[str, np.ndarray]:
    """Per-flight GNSS-presence fraction, per discipline, from the raw IGC archive.

    Intended to be run as a full-population census (see the module docstring): each
    file is parsed once and reduced with :func:`gnss_present_fraction`, with no PSD
    computed. ``n_jobs`` parallelises this scan across processes, which matters for a
    large archive (tens of minutes serially, a few minutes across several workers).

    Args:
        samples: Mapping ``discipline -> list of .igc paths``.
        n_jobs: Number of worker processes; ``1`` runs serially in-process.

    Returns:
        Mapping ``discipline -> array`` of per-flight GNSS-presence fractions, one
        entry per flight with at least 3 fixes.
    """
    out: dict[str, np.ndarray] = {}
    for disc, paths in samples.items():
        if n_jobs > 1 and len(paths) > 1:
            with ProcessPoolExecutor(max_workers=n_jobs) as ex:
                results = list(ex.map(_gnss_present_frac, paths, chunksize=200))
        else:
            results = [_gnss_present_frac(p) for p in paths]
        out[disc] = np.array([r for r in results if r is not None])
    return out


def gnss_presence_from_scan(scan: pd.DataFrame) -> np.ndarray:
    """Per-flight GNSS-presence fraction from an already-parsed track scan.

    Uses the ``gnss_present_frac`` column that
    :func:`soaring.analysis.census.track_stats` computes as a byproduct of its
    own full-dataset scan
    (:func:`soaring.analysis.census.load_or_scan_tracks`). When that scan is a
    full census -- as it is for the flight-level filtering diagnostics -- this gives
    the *exact* population distribution, with no sampling needed.

    Args:
        scan: Per-flight table with a ``gnss_present_frac`` column.

    Returns:
        The array of per-flight GNSS-presence fractions, matching
        :func:`gnss_presence_stats`'s per-discipline values.
    """
    return scan["gnss_present_frac"].to_numpy()


class _Accumulator:
    """Running aggregates over the sampled flights, per discipline and channel."""

    def __init__(self) -> None:
        # per-discipline, per-flight GNSS-presence fractions (see gnss_presence_stats)
        self.gnss_present_frac: dict[str, np.ndarray] = {}
        self.n_flights: dict[str, int] = {}
        # Per-flight PSD curves, keyed by (discipline, channel) -> list of spectra.
        # Kept individually (not pre-summed) so the ensemble can be reduced with a
        # ROBUST estimator: these per-flight PSDs are variance-like and heavy-tailed
        # across flights, so an arithmetic mean is dominated by the few flights whose
        # RAW barometric channel carries an uncleaned spike (this diagnostic runs before
        # fix-level cleaning). The per-frequency median is the typical-flight spectrum
        # and is what the figure plots; see :meth:`median_psd`.
        self._psd: dict[tuple[str, str], list[np.ndarray]] = {}
        self._psd_f: np.ndarray | None = None
        # one representative flight (discipline, t, z_baro, z_gnss)
        self.representative: tuple[str, np.ndarray, np.ndarray, np.ndarray] | None = (
            None
        )
        self.target_dt: float = 1.0

    def add_psd(self, disc: str, channel: str, f: np.ndarray, pxx: np.ndarray) -> None:
        if self._psd_f is None:
            self._psd_f = f
        if len(f) != len(self._psd_f) or not np.allclose(f, self._psd_f):
            return  # different segment length: cannot pool onto the common grid
        self._psd.setdefault((disc, channel), []).append(pxx)

    def n_psd(self, disc: str, channel: str) -> int:
        """Number of flights contributing to a (discipline, channel) spectrum."""
        return len(self._psd.get((disc, channel), []))

    def _stack(self, disc: str, channel: str) -> np.ndarray | None:
        curves = self._psd.get((disc, channel))
        if self._psd_f is None or not curves:
            return None
        return np.vstack(curves)

    def median_psd(
        self, disc: str, channel: str
    ) -> tuple[np.ndarray, np.ndarray] | None:
        """Per-frequency **median** spectrum across flights (the robust estimator).

        Robust to the handful of flights whose raw barometric channel carries an
        uncleaned high-frequency artefact, which would otherwise dominate an arithmetic
        mean of these variance-like per-flight PSDs and inflate the noise floor by
        one--two orders of magnitude between samples.
        """
        s = self._stack(disc, channel)
        if s is None or self._psd_f is None:
            return None
        return self._psd_f, np.median(s, axis=0)

    def mean_psd(self, disc: str, channel: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Per-frequency arithmetic-mean spectrum, kept only for comparison.

        Not plotted: it is the outlier-sensitive estimator that :meth:`median_psd`
        replaces.
        """
        s = self._stack(disc, channel)
        if s is None or self._psd_f is None:
            return None
        return self._psd_f, np.mean(s, axis=0)

    def band_psd(
        self, disc: str, channel: str, lo: float = 10.0, hi: float = 90.0
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
        """Per-frequency ``(lo, median, hi)`` percentiles across flights.

        The band describes variability among raw flight spectra, not uncertainty in
        the median and not a decomposition into physical noise sources.
        """
        s = self._stack(disc, channel)
        if s is None or self._psd_f is None:
            return None
        plo, pmed, phi = np.percentile(s, [lo, 50.0, hi], axis=0)
        return self._psd_f, plo, pmed, phi

    def pooled_band_psd(
        self, channel: str, lo: float = 10.0, hi: float = 90.0
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
        """:meth:`band_psd` pooled over all disciplines for one channel.

        Every contributing flight has equal weight. Pooling can conceal discipline
        differences and is used only as a descriptive channel comparison.
        """
        curves = [c for (_, ch), lst in self._psd.items() if ch == channel for c in lst]
        if self._psd_f is None or not curves:
            return None
        plo, pmed, phi = np.percentile(np.vstack(curves), [lo, 50.0, hi], axis=0)
        return self._psd_f, plo, pmed, phi

    def hf_floor(
        self, channel: str, band_hz: tuple[float, float] = FLOOR_BAND_HZ
    ) -> np.ndarray:
        """The per-flight high-frequency PSD floor, pooled over every discipline.

        One number per flight: its own median PSD over ``band_hz``, for the named
        channel. This is what turns "the GNSS band fans out at high frequency" from a
        picture into a measured fraction. :meth:`band_psd` and :meth:`pooled_band_psd`
        describe the *ensemble* -- a 10th-90th percentile band across flights, at each
        frequency -- which is the right thing to plot but the wrong thing to quote a
        minority size from: two ensembles can share a median while one has a heavy tail
        and the other does not, and nothing about the band alone bounds how many flights
        sit in that tail. A per-flight scalar can be thresholded and counted directly.

        Args:
            channel: ``"baro"`` or ``"gnss"``.
            band_hz: The frequency band to average PSD over; defaults to the
                high-frequency diagnostic band shared with the Savitzky-Golay timescale
                estimator (fig:altnoise panel (c)).

        Returns:
            One value per flight that contributed a spectrum on this channel, in the
            same PSD units (altitude squared per hertz) as :meth:`median_psd`.
            Empty if no flight qualified.
        """
        curves = [c for (_, ch), lst in self._psd.items() if ch == channel for c in lst]
        if self._psd_f is None or not curves:
            return np.empty(0)
        in_band = (self._psd_f >= band_hz[0]) & (self._psd_f <= band_hz[1])
        if not in_band.any():
            return np.empty(0)
        return np.median(np.vstack(curves)[:, in_band], axis=1)


def hf_floor_excess_fraction(
    gnss_floor: np.ndarray, baro_floor: np.ndarray, factor: float
) -> float:
    """Share of flights whose GNSS floor exceeds a multiple of the barometric one.

    Each flight counts against ``factor`` times the *typical* (median) barometric
    floor, not the ensemble's -- the measured version of "the noisy minority is small":
    a fraction the thesis can quote with a number attached, in place of an inference
    from where two medians happen to sit (see :meth:`_Accumulator.hf_floor`).

    Args:
        gnss_floor: Per-flight GNSS high-frequency floors, from ``hf_floor("gnss")``.
        baro_floor: Per-flight barometric high-frequency floors, from
            ``hf_floor("baro")``, on the *same* flights -- both channels are only
            measured together where a flight carries a barometer (:func:`collect`).
        factor: The multiple of the barometric median to test against (e.g. ``3`` or
            ``10``).

    Returns:
        The fraction in ``[0, 1]``, or ``nan`` if either array is empty.
    """
    if gnss_floor.size == 0 or baro_floor.size == 0:
        return float("nan")
    reference = float(np.median(baro_floor))
    if not np.isfinite(reference) or reference <= 0:
        return float("nan")
    return float(np.mean(gnss_floor > factor * reference))


def _collect_psd(samples: dict[str, list[Path]]) -> _Accumulator:
    """Collect the PSD ensemble and representative flight from raw files.

    Kept separate from the barometric-presence half (which :func:`collect` computes on
    its own, and which already has its own reuse path -- the full-census cache from
    ``soaring.analysis.census``) so that *this* half, the one that always has to open
    and parse every sampled file, can be cached independently by
    :func:`load_or_collect_psd`.

    Args:
        samples: Mapping ``discipline -> list of .igc paths``.

    Returns:
        An :class:`_Accumulator` with ``target_dt``, the PSD stacks and
        ``representative`` populated; ``gnss_present_frac``/``n_flights`` left empty
        (that is :func:`collect`'s job).
    """
    acc = _Accumulator()

    # First pass over all disciplines: find the modal sampling period, so the pooled
    # PSD uses one sampling frequency. A single unreadable file (e.g. a transient
    # external-disk hiccup) is skipped rather than aborting the whole batch.
    periods: list[float] = []
    readable: dict[str, list[Path]] = {}
    for disc, paths in samples.items():
        readable[disc] = []
        for p in paths:
            try:
                fixes = parse_igc(p)
            except OSError as exc:
                print(f"[{disc}] skipping unreadable file {p}: {exc}")
                continue
            readable[disc].append(p)
            dt = median_sampling_period(fixes)
            if np.isfinite(dt) and dt > 0:
                periods.append(round(dt))
    target_dt = float(max(set(periods), key=periods.count)) if periods else 1.0
    acc.target_dt = target_dt
    fs = 1.0 / target_dt

    # Reparse one flight at a time after finding the joint mode. Keeping all 6000
    # raw trajectories resident can exhaust laptop RAM; the extra sequential parse
    # bounds memory by one flight plus the small spectrum matrices.
    for disc, paths in readable.items():
        for path in paths:
            try:
                fixes = parse_igc(path)
            except OSError:
                continue
            if len(fixes) < 3:
                continue
            has_baro = baro_present_fraction(fixes) >= BARO_PRESENT_MIN
            if not has_baro:
                continue  # PSD/representative use the barometric channel

            # PSD: baro flights at the modal cadence, long enough for one segment.
            dt = median_sampling_period(fixes)
            regular = np.isfinite(dt) and abs(dt - target_dt) <= DT_TOLERANCE_S
            if not (regular and len(fixes) >= NPERSEG):
                continue
            raw = fixes[["baro_alt", "gnss_alt"]].to_numpy(dtype=float, copy=True)
            raw[raw == 0] = np.nan
            if "valid" in fixes:
                raw[~fixes["valid"].to_numpy(dtype=bool), 1] = np.nan
            t, pair = longest_regular_block(fixes["t"].to_numpy(), raw, target_dt)
            if len(t) < NPERSEG:
                continue
            zb = _uniform_resample(t, pair[:, 0], target_dt)
            zg = _uniform_resample(t, pair[:, 1], target_dt)
            if len(zb) < NPERSEG:
                continue
            f, pxx_b = _welch(zb, fs)
            _, pxx_g = _welch(zg, fs)
            acc.add_psd(disc, "baro", f, pxx_b)
            acc.add_psd(disc, "gnss", f, pxx_g)
            # Keep the qualifying flight with the MOST fixes seen so far (not just the
            # first): panels (a)/(b) show a window of it, and more fixes means a longer,
            # more densely covered window. Fix count, not elapsed time (t[-1]-t[0]), is
            # the robust criterion: a corrupted or genuinely huge inter-fix gap can make
            # elapsed time enormous without the flight having much continuous data.
            if acc.representative is None or len(t) > len(acc.representative[1]):
                acc.representative = (
                    disc,
                    t,
                    pair[:, 0],
                    pair[:, 1],
                )

    return acc


def save_psd_cache(acc: _Accumulator, disc: str, cache_path: Path) -> None:
    """Cache one discipline's slice of a :func:`_collect_psd` result.

    A single ``.npz`` per discipline, on the same footing as the Chapter 3 position
    stacks in ``derived-audit/audit_positions_*.npz`` (:mod:`scripts.reporting
    .ch3_global_transport.audit_msd`): the PSD ensemble is fixed-width (every flight's
    Welch spectrum shares the same frequency grid), so a 2-D array is the natural
    format, unlike the ragged fix-level sample (:func:`soaring.analysis.census
    .load_or_scan_fixlevel`), which cannot use one. Holds ``freqs`` (shared grid),
    ``baro``/``gnss`` (one row per qualifying flight), ``target_dt``, and -- kept in the
    same file since a discipline has at most one -- the representative flight's raw
    ``t``/``baro_alt``/``gnss_alt`` (ragged, empty if this discipline is not the one
    holding the representative flight of the pair).
    """
    if acc._psd_f is None:
        return  # nothing this discipline contributed (e.g. unreachable archive)
    n_freq = len(acc._psd_f)
    baro = acc._psd.get((disc, "baro"), [])
    gnss = acc._psd.get((disc, "gnss"), [])
    rep = acc.representative
    is_rep = rep is not None and rep[0] == disc
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        cache_version=np.int64(PSD_CACHE_VERSION),
        freqs=acc._psd_f,
        baro=np.vstack(baro) if baro else np.empty((0, n_freq)),
        gnss=np.vstack(gnss) if gnss else np.empty((0, n_freq)),
        target_dt=np.float64(acc.target_dt),
        repr_t=rep[1] if is_rep else np.empty(0),
        repr_baro_alt=rep[2] if is_rep else np.empty(0),
        repr_gnss_alt=rep[3] if is_rep else np.empty(0),
    )


def load_psd_cache(disc: str, cache_path: Path) -> _Accumulator | None:
    """Read one discipline's cached PSDs and representative interval.

    Returns ``None`` if ``cache_path`` does not exist -- the caller's cue to fall back
    to a fresh pass, exactly like :func:`soaring.analysis.census.load_or_scan_tracks`.
    """
    if not cache_path.is_file():
        return None
    data = np.load(cache_path)
    if int(data.get("cache_version", 0)) != PSD_CACHE_VERSION:
        return None
    acc = _Accumulator()
    acc.target_dt = float(data["target_dt"])
    freqs = data["freqs"]
    for channel in ("baro", "gnss"):
        for row in data[channel]:
            acc.add_psd(disc, channel, freqs, row)
    if data["repr_t"].size:
        acc.representative = (
            disc,
            data["repr_t"],
            data["repr_baro_alt"],
            data["repr_gnss_alt"],
        )
    return acc


def load_or_collect_psd(
    samples: dict[str, list[Path]],
    cache_paths: dict[str, Path],
    *,
    force: bool = False,
) -> _Accumulator:
    """Load a cached PSD ensemble, or run :func:`_collect_psd` and cache the result.

    The cache stores one file per discipline. If any file is absent, incompatible,
    or explicitly invalidated, all disciplines are recomputed together because
    their samples jointly determine the modal period and common frequency grid.

    Args:
        samples: Mapping ``discipline -> list of .igc paths``.
        cache_paths: Mapping ``discipline -> cache file`` (e.g.
            ``data_root/derived/psd_sample.npz``).
        force: Recompute even if every discipline's cache already exists.

    Returns:
        An :class:`_Accumulator` with ``target_dt``, the PSD stacks and
        ``representative`` populated (``gnss_present_frac``/``n_flights`` still empty,
        as in :func:`_collect_psd`).
    """
    have_all = not force and all(
        disc in cache_paths and cache_paths[disc].is_file() for disc in samples
    )
    if have_all:
        have_all = all(
            load_psd_cache(disc, cache_paths[disc]) is not None for disc in samples
        )
    if have_all:
        merged = _Accumulator()
        target_dts: set[float] = set()
        for disc in samples:
            partial = load_psd_cache(disc, cache_paths[disc])
            if partial is None:
                continue
            target_dts.add(round(partial.target_dt, 6))
            merged._psd.update(partial._psd)
            if merged._psd_f is None:
                merged._psd_f = partial._psd_f
            if partial.representative is not None and (
                merged.representative is None
                or len(partial.representative[1]) > len(merged.representative[1])
            ):
                merged.representative = partial.representative
        if len(target_dts) <= 1:
            merged.target_dt = target_dts.pop() if target_dts else 1.0
            print(
                f"Using cached PSD sample for {list(samples)} (delete "
                "derived/psd_sample.npz per discipline to resample)."
            )
            return merged
        print(f"Cached PSD samples disagree on target_dt ({target_dts}); recomputing.")

    acc = _collect_psd(samples)
    for disc in samples:
        if disc in cache_paths:
            save_psd_cache(acc, disc, cache_paths[disc])
    return acc


def collect(
    samples: dict[str, list[Path]],
    *,
    stat_samples: dict[str, list[Path]] | None = None,
    stat_n_jobs: int = 1,
    precomputed_gnss_stats: dict[str, np.ndarray] | None = None,
    psd_cache_paths: dict[str, Path] | None = None,
    force_psd_rescan: bool = False,
) -> _Accumulator:
    """Parse the sampled flights and accumulate the noise diagnostics.

    Args:
        samples: Mapping ``discipline -> list of .igc paths``, used for the PSD and the
            representative-flight panel.
        stat_samples: Optional, typically much larger (up to full-population) mapping
            used only for the GNSS-presence distribution (see
            :func:`gnss_presence_stats`); defaults to ``samples``.
        stat_n_jobs: Worker processes for the GNSS-presence census.
        precomputed_gnss_stats: Optional mapping ``discipline -> array`` of per-flight
            GNSS-presence fractions to use instead of scanning -- e.g. from
            :func:`gnss_presence_from_scan` on an already-cached full census
            (:mod:`soaring.analysis.census`). Disciplines not present here still
            fall back to :func:`gnss_presence_stats`.
        psd_cache_paths: Optional mapping ``discipline -> cache file`` to read/write
            the PSD ensemble through (see :func:`load_or_collect_psd`). Omitted
            (``None``) runs :func:`_collect_psd` uncached, as this function always did
            before the cache existed.
        force_psd_rescan: Forces a fresh PSD pass even if ``psd_cache_paths`` are all
            present; ignored when ``psd_cache_paths`` is ``None``.

    Returns:
        The populated :class:`_Accumulator`.
    """
    if psd_cache_paths is not None:
        acc = load_or_collect_psd(samples, psd_cache_paths, force=force_psd_rescan)
    else:
        acc = _collect_psd(samples)

    precomputed_gnss_stats = precomputed_gnss_stats or {}
    base = stat_samples or samples
    to_scan = {d: paths for d, paths in base.items() if d not in precomputed_gnss_stats}
    scanned = gnss_presence_stats(to_scan, n_jobs=stat_n_jobs) if to_scan else {}
    for disc in base:
        frac = precomputed_gnss_stats.get(disc, scanned.get(disc))
        acc.gnss_present_frac[disc] = frac
        acc.n_flights[disc] = len(frac)

    return acc


def render_altitude_noise_figure(acc: _Accumulator, disciplines: list[str]) -> Figure:
    """Render the barometric-vs-GNSS altitude noise figure from collected diagnostics.

    Paired raw traces, their centred difference, median spectra with between-flight
    bands, and the GNSS-presence distribution. The difference is measured between
    logged channels; its components (datum, atmosphere, sensor error) are not resolved.

    Args:
        acc: Diagnostics already accumulated by :func:`collect`.
        disciplines: Disciplines to plot, in display order.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    ch_color = {"baro": "#3477a8", "gnss": "#b5482a"}
    diff_color = "#4e8a5b"  # distinct from both baro (blue) and gnss (red)
    # Use the same 30-minute interval for the raw channels and their difference.
    # Spectra are a separate diagnostic of their frequency content.
    window_s = 1800.0

    fig, axd = plt.subplot_mosaic(
        [["a", "b"], ["c", "d"]], figsize=(6.1, 5.8), layout="constrained"
    )

    rep = acc.representative
    if rep is not None:
        _, t, zb, zg = rep
        window = t <= t[0] + window_s
        tw = (t[window] - t[0]) / 60.0
        zb_w, zg_w = zb[window], zg[window]

        # Shared height axis makes the logged channel separation visible. It can
        # combine datum differences, atmospheric variation and sensor errors.
        ax_a = axd["a"]
        ax_a.plot(tw, zg_w, color=ch_color["gnss"], lw=0.9, label="GNSS")
        ax_a.plot(tw, zb_w, color=ch_color["baro"], lw=1.0, label="barometric")
        ax_a.legend(fontsize=8, loc="best")
        ax_a.set_ylabel("altitude [m]")

        # Remove only the mean difference. Remaining changes are observed channel
        # disagreement; this plot does not identify their physical source.
        diff = zg_w - zb_w
        axd["b"].axhline(0.0, color="0.6", lw=0.8)
        axd["b"].plot(tw, diff - diff.mean(), color=diff_color, lw=1.0)
        axd["b"].text(
            0.02,
            0.03,
            f"mean offset removed: {diff.mean():.0f} m",
            transform=axd["b"].transAxes,
            fontsize=8,
            color="0.3",
            ha="left",
            va="bottom",
        )
    axd["a"].set_xlabel("time [min]")
    axd["a"].set_title("(a) Two altitude channels")
    axd["b"].set_xlabel("time [min]")
    axd["b"].set_ylabel(r"GNSS $-$ barometric [m]")
    axd["b"].set_title("(b) Centred channel difference")

    # (c) median PSD ---------------------------------------------------------------
    ax = axd["c"]
    ch_label = {"baro": "barometric", "gnss": "GNSS"}
    for channel in ("baro", "gnss"):
        res = acc.pooled_band_psd(channel, 10.0, 90.0)
        if res is None:
            continue
        f, plo, pmed, phi = res
        color = ch_color[channel]
        # shaded 10th-90th percentile band across flights, then the median line on top:
        # the band is the point (tight for barometric, fanning out for GNSS); the two
        # channels are pooled over disciplines for clarity.
        ax.fill_between(f[1:], plo[1:], phi[1:], color=color, alpha=0.18, lw=0)
        ax.loglog(f[1:], pmed[1:], color=color, lw=1.7, label=ch_label[channel])
    f_nyquist = 1.0 / (2.0 * acc.target_dt)
    ax.axvline(f_nyquist, color="0.3", ls=":", lw=1.2)
    ax.text(
        f_nyquist,
        ax.get_ylim()[0],
        r"$f_{\mathrm{Nyq}}$",
        fontsize=8,
        color="0.3",
        ha="right",
        va="bottom",
    )
    ax.set_xlabel("frequency [Hz]")
    ax.set_ylabel(r"PSD [m$^2$/Hz]")
    ax.set_title("(c) Paired altitude spectra")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")

    # (d) GNSS-presence distribution near the admission cutoff -------------------
    # Discipline colours matching figures/preproc.py's _DISC_COLOR, kept in sync by
    # comment rather than import: that module imports soaring.analysis.census, which
    # imports this one, so the reverse import would cycle.
    disc_color = {"paragliders": "#3477a8", "hang gliders": "#b5482a"}
    ax = axd["d"]
    # Zoomed to [0.80, 1.0], not the full [0, 1] population: presence is bimodal (see
    # module docstring), so the flights with essentially no GNSS at all -- already
    # quantified in prose (thesis, sec:altchannel) -- would otherwise be a second,
    # unrelated spike competing for the same axis. A LOG y-axis is what makes the
    # near-cutoff population visible at all next to the dominant fully-present bin: on
    # a linear count, the ~99.5-100% bin (the large majority of flights) swamps the
    # tens to ~100 flights per bin that actually sit near the cutoff, which is the
    # population this panel exists to show.
    lo, hi = 0.80, 1.0
    bins = np.linspace(lo, hi, 41)
    for disc in disciplines:
        frac = acc.gnss_present_frac.get(disc)
        if frac is None or frac.size == 0:
            continue
        ax.hist(
            frac,
            bins=bins,
            histtype="step",
            lw=1.6,
            color=disc_color.get(disc, "gray"),
            label=disc,
        )
        below = 100.0 * float(np.mean(frac < BARO_PRESENT_MIN))
        ax.text(
            0.02,
            0.95 - 0.10 * disciplines.index(disc),
            f"{disc}: {below:.1f}% below cutoff",
            transform=ax.transAxes,
            fontsize=8,
            color=disc_color.get(disc, "gray"),
            ha="left",
            va="top",
        )
    ax.axvline(BARO_PRESENT_MIN, color="0.3", ls=":", lw=1.2)
    ax.set_xlim(lo, hi)
    ax.set_yscale("log")
    ax.set_xlabel("GNSS-present fraction of fixes")
    ax.set_ylabel("flights (log)")
    ax.set_title("(d) GNSS completeness")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(0.0, 0.65))

    for axis in axd.values():
        axis.tick_params(labelsize=9)
        axis.xaxis.label.set_size(9)
        axis.yaxis.label.set_size(9)
        axis.title.set_fontsize(10)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    return fig
