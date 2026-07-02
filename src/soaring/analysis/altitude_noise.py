"""Noise diagnostics for the two IGC altitude channels (barometric vs GNSS).

The thesis adopts the **barometric** altitude for the vertical dynamics; this module
produces the empirical evidence behind that choice, on raw IGC tracks from both
disciplines (paragliders and hang gliders).

The central tool is the **power spectral density (PSD)**, estimated with Welch's method
(:func:`scipy.signal.welch`): it shows *at which frequencies* a channel carries power.
The expectation, confirmed by the figure, is that the barometric channel dominates at
low frequency (slow pressure drift) while the GNSS channel carries a much higher
high-frequency noise floor -- exactly the band that contaminates vertical velocity, MSD
increments and the segmentation. A second diagnostic reports the fraction of flights
whose barometric channel is absent (no pressure sensor, so the whole channel is zero),
which sizes the population that must fall back to GNSS.

Two different precision needs drive two different sampling policies, both made explicit
here rather than left implicit:

* The **barometric-presence fraction** is a headline number quoted in the thesis, so its
  precision must be justified, not asserted. When the population is small enough that a
  full census is cheap (the hang-glider archive, ~6,700 files, a couple of minutes), it
  is censused exactly -- there is then nothing to estimate. When it is not (the
  paraglider archive, ~186,000 files, the better part of an hour to parse serially), the
  fraction is instead estimated from a **simple random sample sized to a stated
  precision target**: :func:`required_sample_size` gives the sample size ``n`` needed
  for a 95%-confidence margin of error of a chosen number of percentage points, using
  the standard proportion formula with the conservative variance bound ``p=0.5`` (so the
  achieved precision is at least as good as targeted, whatever the true proportion turns
  out to be); :func:`proportion_ci` then reports the point estimate with its actual
  confidence interval. A few thousand files at this sample size take well under a
  minute to parse, even serially -- the reason to sample at all is speed, and the reason
  the sample size is not arbitrary is that a wrong number quoted without a stated
  precision would be worse than not quoting one.
* The **PSD** is a qualitative ensemble-average spectral *shape*, not a headline
  statistic with an error bar, so it is computed on a smaller, explicitly sized and
  seeded random subsample (see ``sample_igc_paths``) -- standard practice for this kind
  of exploratory spectral diagnostic, and far cheaper than a full sweep.

``scipy`` and ``matplotlib`` are imported lazily so importing this module never requires
the optional ``analysis`` extra; only building the figure does.
"""

from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .igc import baro_present_fraction, median_sampling_period, parse_igc

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# Welch segment length (fixed so every flight yields the same frequency grid).
NPERSEG = 256
# A flight qualifies for the PSD only if its native cadence matches the sample
# mode within this tolerance (so the pooled spectra share one sampling frequency).
DT_TOLERANCE_S = 0.25
# A flight "has" a barometric channel when at least this fraction of its fixes carry a
# non-zero pressure altitude. Presence is essentially bimodal (a logger either has a
# pressure sensor, so the channel is full, or has none, so it is all zero), so the exact
# value is not critical.
BARO_PRESENT_MIN = 0.5


def required_sample_size(
    margin_of_error: float,
    *,
    confidence: float = 0.95,
    p: float = 0.5,
) -> int:
    """Sample size needed to estimate a population proportion to a given precision.

    Standard normal-approximation formula for a proportion,
    ``n = z^2 p(1-p) / e^2``. The population is treated as effectively infinite (no
    finite-population correction): the archives sampled here (paragliders,
    ~186,000 flights) are always large enough, at the sample sizes this formula
    returns, that the correction would change ``n`` by a percent or two -- not worth
    the extra parameter. The default ``p=0.5`` is the conservative
    (variance-maximising) choice: with it, the *actual* margin of error at the returned
    sample size is guaranteed to be at most ``margin_of_error``, whatever the true
    proportion turns out to be, so no prior guess about it is needed.

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
    """Point estimate and normal-approximation confidence interval for a proportion.

    Valid when ``n`` is reasonably large and the estimate is not too close to 0 or 1
    (concretely, ``n * p_hat * (1 - p_hat)`` comfortably above 5); this holds for the
    sample sizes and proportions seen here.

    Args:
        k: Number of "successes" (e.g. flights whose barometric channel is absent).
        n: Sample size (or population size, for a census -- then ``half_width`` is 0).
        confidence: Confidence level.

    Returns:
        ``(p_hat, half_width)``: the point estimate and the confidence-interval
        half-width, so the interval is ``[p_hat - half_width, p_hat + half_width]``.
    """
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
    grid = np.arange(t[0], t[-1] + 0.5 * dt, dt)
    return np.interp(grid, t, z)


def _welch(z: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Welch PSD of ``z`` with linear detrending (removes drift and the climb trend)."""
    from scipy.signal import welch

    nperseg = min(NPERSEG, len(z))
    f, pxx = welch(z, fs=fs, nperseg=nperseg, detrend="linear")
    return f, pxx


def _is_baro_absent(path: Path) -> bool | None:
    """Worker: parse one file and report whether its barometric channel is absent.

    A top-level function (rather than a closure) so it can be pickled for
    :class:`~concurrent.futures.ProcessPoolExecutor`.

    Returns:
        ``True``/``False`` for barometric absent/present, or ``None`` if the file has
        too few fixes to judge (excluded from both the numerator and the denominator).
    """
    fixes = parse_igc(path)
    if len(fixes) < 3:
        return None
    return baro_present_fraction(fixes) < BARO_PRESENT_MIN


def baro_presence_stats(
    samples: dict[str, list[Path]], *, n_jobs: int = 1
) -> tuple[dict, dict]:
    """Count, per discipline, how many flights lack a barometric channel.

    Intended to be run as a full-population census (see the module docstring): each
    file is parsed once and checked with :func:`baro_present_fraction`, with no PSD
    computed. ``n_jobs`` parallelises this scan across processes, which matters for the
    paraglider archive (tens of minutes serially, single-digit minutes with ``n_jobs=8``
    on a modern machine).

    Args:
        samples: Mapping ``discipline -> list of .igc paths``.
        n_jobs: Number of worker processes; ``1`` runs serially in-process.

    Returns:
        A pair ``(baro_absent, n_flights)``, each a mapping ``discipline -> count``.
    """
    baro_absent: dict[str, int] = {}
    n_flights: dict[str, int] = {}
    for disc, paths in samples.items():
        if n_jobs > 1 and len(paths) > 1:
            with ProcessPoolExecutor(max_workers=n_jobs) as ex:
                results = list(ex.map(_is_baro_absent, paths, chunksize=200))
        else:
            results = [_is_baro_absent(p) for p in paths]
        judged = [r for r in results if r is not None]
        n_flights[disc] = len(judged)
        baro_absent[disc] = sum(judged)
    return baro_absent, n_flights


class _Accumulator:
    """Running aggregates over the sampled flights, per discipline and channel."""

    def __init__(self) -> None:
        # per-discipline flight and baro-absent counts (see baro_presence_stats)
        self.baro_absent: dict[str, int] = {}
        self.n_flights: dict[str, int] = {}
        # PSD accumulation, keyed by (discipline, channel) -> [sum_pxx, count]
        self._psd: dict[tuple[str, str], list] = {}
        self._psd_f: np.ndarray | None = None
        # one representative flight (discipline, t, z_baro, z_gnss)
        self.representative: tuple[str, np.ndarray, np.ndarray, np.ndarray] | None = (
            None
        )
        self.target_dt: float = 1.0

    def add_psd(self, disc: str, channel: str, f: np.ndarray, pxx: np.ndarray) -> None:
        if self._psd_f is None:
            self._psd_f = f
        if len(f) != len(self._psd_f):
            return  # different segment length: cannot pool onto the common grid
        key = (disc, channel)
        if key not in self._psd:
            self._psd[key] = [np.zeros_like(pxx), 0]
        self._psd[key][0] += pxx
        self._psd[key][1] += 1

    def mean_psd(self, disc: str, channel: str) -> tuple[np.ndarray, np.ndarray] | None:
        key = (disc, channel)
        if self._psd_f is None or key not in self._psd or self._psd[key][1] == 0:
            return None
        total, count = self._psd[key]
        return self._psd_f, total / count


def collect(
    samples: dict[str, list[Path]],
    *,
    stat_samples: dict[str, list[Path]] | None = None,
    stat_n_jobs: int = 1,
) -> _Accumulator:
    """Parse the sampled flights and accumulate the noise diagnostics.

    Args:
        samples: Mapping ``discipline -> list of .igc paths``, used for the PSD and the
            representative-flight panel.
        stat_samples: Optional, typically much larger (up to full-population) mapping
            used only for the barometric-presence fraction (see
            :func:`baro_presence_stats`); defaults to ``samples``.
        stat_n_jobs: Worker processes for the barometric-presence census.

    Returns:
        The populated :class:`_Accumulator`.
    """
    acc = _Accumulator()
    acc.baro_absent, acc.n_flights = baro_presence_stats(
        stat_samples or samples, n_jobs=stat_n_jobs
    )

    # First pass over all disciplines: find the modal sampling period, so the pooled PSD
    # uses one sampling frequency.
    periods: list[float] = []
    parsed: dict[str, list[pd.DataFrame]] = {}
    for disc, paths in samples.items():
        parsed[disc] = []
        for p in paths:
            fixes = parse_igc(p)
            parsed[disc].append(fixes)
            dt = median_sampling_period(fixes)
            if np.isfinite(dt) and dt > 0:
                periods.append(round(dt))
    target_dt = float(max(set(periods), key=periods.count)) if periods else 1.0
    acc.target_dt = target_dt
    fs = 1.0 / target_dt

    for disc, frames in parsed.items():
        for fixes in frames:
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
            t = fixes["t"].to_numpy()
            zb = _uniform_resample(t, fixes["baro_alt"].to_numpy(), target_dt)
            zg = _uniform_resample(t, fixes["gnss_alt"].to_numpy(), target_dt)
            if len(zb) < NPERSEG:
                continue
            f, pxx_b = _welch(zb, fs)
            _, pxx_g = _welch(zg, fs)
            acc.add_psd(disc, "baro", f, pxx_b)
            acc.add_psd(disc, "gnss", f, pxx_g)
            if acc.representative is None:
                acc.representative = (
                    disc,
                    t,
                    fixes["baro_alt"].to_numpy(),
                    fixes["gnss_alt"].to_numpy(),
                )

    return acc


def make_altitude_noise_figure(
    samples: dict[str, list[Path]],
    *,
    stat_samples: dict[str, list[Path]] | None = None,
    stat_n_jobs: int = 1,
) -> Figure:
    """Collect the diagnostics and build the altitude noise figure in one call.

    A thin convenience wrapper around :func:`collect` +
    :func:`render_altitude_noise_figure` for callers that only need the figure.
    Callers that also need the underlying counts
    (e.g. to report a confidence interval for panel (d), as
    ``scripts/reporting/generate_altitude_noise_figure.py`` does) should call
    :func:`collect` and :func:`render_altitude_noise_figure` separately instead, so the
    data is not parsed twice.

    Args:
        samples: Mapping ``discipline -> list of .igc paths``, used for panels (a)/(b).
        stat_samples: Optional, typically much larger mapping used only for panel (d).
        stat_n_jobs: Worker processes for the panel-(d) census/sample.

    Returns:
        The Matplotlib figure (not saved).
    """
    acc = collect(samples, stat_samples=stat_samples, stat_n_jobs=stat_n_jobs)
    return render_altitude_noise_figure(acc, list(samples))


def render_altitude_noise_figure(acc: _Accumulator, disciplines: list[str]) -> Figure:
    """Render the barometric-vs-GNSS altitude noise figure from collected diagnostics.

    Panels: (a) for one representative flight, the channel difference GNSS minus
    barometric (mean removed), isolating the GNSS noise from the shared climb signal;
    (b) the mean Welch PSD of the two channels (log-log), per discipline; (d) the
    fraction of flights whose barometric channel is absent, per discipline (a census or
    a sized-sample estimate, depending on how ``acc`` was built -- see :func:`collect`).

    Args:
        acc: Diagnostics already accumulated by :func:`collect`.
        disciplines: Disciplines to plot, in display order.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    ch_color = {"baro": "#3477a8", "gnss": "#b5482a"}
    disc_style = {disc: ["-", "--", ":"][i % 3] for i, disc in enumerate(disciplines)}

    fig, axd = plt.subplot_mosaic([["a", "b"], ["d", "d"]], figsize=(9.4, 6.6))

    # (a) channel difference for one representative flight ------------------------
    ax = axd["a"]
    if acc.representative is not None:
        _, t, zb, zg = acc.representative
        window = t <= t[0] + 600.0  # first 10 minutes
        diff = (zg - zb)[window]
        ax.axhline(0.0, color="0.6", lw=0.8)
        ax.plot(t[window] - t[0], diff - diff.mean(), color=ch_color["gnss"], lw=1.0)
    ax.set_xlabel("time [s]")
    ax.set_ylabel(r"GNSS $-$ barometric altitude [m]")
    ax.set_title("(a) Channel difference (one flight, mean removed)")

    # (b) mean PSD ---------------------------------------------------------------
    ax = axd["b"]
    for disc in disciplines:
        for channel in ("baro", "gnss"):
            res = acc.mean_psd(disc, channel)
            if res is None:
                continue
            f, pxx = res
            ax.loglog(
                f[1:],
                pxx[1:],
                color=ch_color[channel],
                ls=disc_style[disc],
                lw=1.2,
                label=f"{channel}, {disc}",
            )
    ax.set_xlabel("frequency [Hz]")
    ax.set_ylabel(r"PSD [m$^2$/Hz]")
    ax.set_title(f"(b) Altitude PSD (Welch, $\\Delta t={acc.target_dt:.0f}$ s)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3, which="both")

    # (d) baro-absent fraction per discipline ------------------------------------
    ax = axd["d"]
    discs = list(disciplines)
    frac = [
        (acc.baro_absent[d] / acc.n_flights[d] * 100.0) if acc.n_flights[d] else 0.0
        for d in discs
    ]
    y = range(len(discs))
    ax.barh(list(y), frac, color="#7a5aa0", height=0.5)
    ax.set_yticks(list(y))
    ax.set_yticklabels(discs)
    ax.invert_yaxis()
    ax.set_xlabel("flights without a barometric channel [%]")
    ax.set_title("(d) Barometric channel absent (falls back to GNSS)")
    ax.set_xlim(0, (max(frac) * 1.25) if any(frac) else 1.0)
    for i, v in enumerate(frac):
        ax.text(v, i, f" {v:.1f}%", va="center", fontsize=9)

    fig.tight_layout()
    return fig
