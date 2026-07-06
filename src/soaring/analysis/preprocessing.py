"""Pre-processing thresholds and the *track-based* diagnostics that justify them.

Trajectory pre-processing uses several numeric thresholds (see the thesis chapter "Next
steps", Sec. 4.1). **None of them is hard-coded here**: their values live in
``configs/preprocessing.yaml`` -- the single documented place to change a cut -- read
into typed dataclasses by :func:`load_preproc_config`. This module also provides the
diagnostics that justify the flight-level cuts, computed **from the parsed IGC tracks
themselves** (:func:`scan_tracks`), not from the declared catalog metadata (which has
outliers and placeholder dates, so it is a coarse pre-filter at most).
:func:`make_flightlevel_diagnostics_figure` (and
:func:`make_fixlevel_diagnostics_figure`, for the per-fix bounds) draws the track
distributions with the adopted cuts marked, so the choice is auditable on the real data.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .igc import baro_present_fraction, median_sampling_period, parse_igc

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# Mean Earth radius (metres), the usual choice for a haversine great-circle distance.
_EARTH_RADIUS_M = 6371008.8

# The authoritative threshold file (repo ``configs/preprocessing.yaml``).
DEFAULT_PREPROC_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "preprocessing.yaml"
)

# Per-discipline colours, shared with the thesis figure palette.
_DISC_COLOR = {
    "paragliders": "#3477a8",
    "hang gliders": "#b5482a",
    "sailplanes": "#3d8c54",
}

# A flight "has" a barometric channel when at least this fraction of its fixes carry a
# non-zero pressure altitude (presence is essentially all-or-nothing). Vertical speed
# and altitude are only physical on such flights; on a GNSS-only flight the barometric
# field is a constant-zero placeholder and is excluded from the fix-level distributions.
_BARO_PRESENT_MIN = 0.5


@dataclass(frozen=True)
class FixLevelThresholds:
    """Physical bounds for fix-level cleaning (loaded from the config).

    The speeds are great-circle (haversine) speeds between consecutive fixes, on the raw
    geographic coordinates (no conversion yet). The vertical-speed and altitude bounds
    apply to the adopted barometric channel. Inter-fix gaps are not bounded here: they
    are handled once, at the flight level, by :class:`SamplingThresholds`.
    """

    max_horizontal_speed_mps: float
    max_vertical_speed_mps: float
    min_altitude_m: float
    max_altitude_m: float


@dataclass(frozen=True)
class FlightLevelThresholds:
    """Population thresholds for flight-level filtering (loaded from the config).

    A separate minimum-fix-count cut is intentionally omitted: it is redundant with the
    duration cut -- even the slowest logger (~5 s) over ``min_duration_s`` gives several
    hundred fixes, well above what the kinematics need.
    """

    min_duration_s: float
    min_path_km: float


@dataclass(frozen=True)
class TrimmingThresholds:
    """Ground-phase trimming bounds on the horizontal speed (loaded from config)."""

    takeoff_speed_mps: float
    sustained_s: float


@dataclass(frozen=True)
class SamplingThresholds:
    """Intra-flight sampling-regularity bounds (loaded from the config)."""

    max_gap_factor: float
    max_missing_fraction: float


@dataclass(frozen=True)
class SavgolParams:
    """Savitzky-Golay parameters (loaded from the config; window is set per flight)."""

    polyorder: int
    tau_c_horizontal_s: float
    tau_c_vertical_s: float


@dataclass(frozen=True)
class PreprocConfig:
    """The full set of pre-processing thresholds, grouped by pipeline level."""

    fix: FixLevelThresholds
    trimming: TrimmingThresholds
    flight: FlightLevelThresholds
    sampling: SamplingThresholds
    savgol: SavgolParams


def load_preproc_config(path: str | Path | None = None) -> PreprocConfig:
    """Load the pre-processing thresholds from the YAML config.

    Args:
        path: Config file; defaults to :data:`DEFAULT_PREPROC_CONFIG_PATH`.

    Returns:
        The populated :class:`PreprocConfig`.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    import yaml

    p = Path(path) if path is not None else DEFAULT_PREPROC_CONFIG_PATH
    if not p.is_file():
        raise FileNotFoundError(f"Pre-processing config not found: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return PreprocConfig(
        fix=FixLevelThresholds(**raw["fix_level"]),
        trimming=TrimmingThresholds(**raw["trimming"]),
        flight=FlightLevelThresholds(**raw["flight_level"]),
        sampling=SamplingThresholds(**raw["sampling"]),
        savgol=SavgolParams(**raw["savgol"]),
    )


def great_circle_m(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Haversine great-circle distance (metres) between two (arrays of) points.

    Scalars or equal-length arrays; ``(lat1, lon1)`` may be a single reference point
    broadcast against arrays ``(lat2, lon2)``, or two aligned arrays for consecutive
    steps. All angles in degrees.

    Returns:
        Distances in metres, broadcast to the common shape.
    """
    p1 = np.radians(np.asarray(lat1, dtype=float))
    p2 = np.radians(np.asarray(lat2, dtype=float))
    dphi = np.radians(np.asarray(lat2, dtype=float) - np.asarray(lat1, dtype=float))
    dlam = np.radians(np.asarray(lon2, dtype=float) - np.asarray(lon1, dtype=float))
    a = np.sin(dphi / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2.0) ** 2
    return 2.0 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def track_stats(fixes: pd.DataFrame) -> dict | None:
    """Per-flight diagnostic quantities computed from a parsed IGC track.

    Everything comes from the track's own ``B`` records, not declared metadata: the
    recorded duration (a tight upper bound on the trimmed airborne duration), the fix
    count, the total flown path length (sum of great-circle steps), the extent (farthest
    fix from the first), the native sampling interval, the largest single gap and the
    missing fraction (the two quantities the intra-flight sampling-regularity cut acts
    on, Sec. 4.1.6 of the thesis), the barometric-presence fraction, the largest
    horizontal/vertical speed between consecutive fixes, and the barometric-altitude
    range -- these last four are not yet used by any thesis figure, but are cheap
    byproducts of this same scan and directly support future work: validating the
    fix-level speed/altitude bounds of Table 4.1 against real data, and (for
    ``baro_present_frac``) the barometric-presence figure of Sec. 4.1.1, which today
    runs its own separate scan.

    Args:
        fixes: Table returned by :func:`soaring.analysis.igc.parse_igc`.

    Returns:
        A mapping with ``duration_s``, ``n_fix``, ``path_km``, ``extent_km``, ``dt_s``,
        ``max_gap_ratio``, ``missing_fraction``, ``baro_present_frac``, ``max_vxy_mps``,
        ``max_vz_mps``, ``baro_alt_min_m`` and ``baro_alt_max_m``, or ``None`` if the
        track has fewer than two fixes.
    """
    n = len(fixes)
    if n < 2:
        return None
    t = fixes["t"].to_numpy()
    lat = fixes["lat"].to_numpy()
    lon = fixes["lon"].to_numpy()
    baro = fixes["baro_alt"].to_numpy()
    steps = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    disp = great_circle_m(lat[0], lon[0], lat, lon)
    duration_s = float(t[-1] - t[0])
    dt = median_sampling_period(fixes)
    diffs = np.diff(t)
    max_gap_s = float(np.max(diffs)) if diffs.size else float("nan")
    if np.isfinite(dt) and dt > 0:
        max_gap_ratio = max_gap_s / dt
        n_expected = duration_s / dt + 1.0
        missing_fraction = max(0.0, 1.0 - n / n_expected)
    else:
        max_gap_ratio = float("nan")
        missing_fraction = float("nan")
    # Speeds between consecutive fixes; guard the (rare) duplicate-timestamp case.
    nonzero = diffs > 0
    max_vxy_mps = (
        float(np.max(steps[nonzero] / diffs[nonzero]))
        if nonzero.any()
        else float("nan")
    )
    max_vz_mps = (
        float(np.max(np.abs(np.diff(baro))[nonzero] / diffs[nonzero]))
        if nonzero.any()
        else float("nan")
    )
    return {
        "duration_s": duration_s,
        "n_fix": int(n),
        "path_km": float(np.nansum(steps)) / 1000.0,
        "extent_km": float(np.nanmax(disp)) / 1000.0,
        "dt_s": dt,
        "max_gap_ratio": max_gap_ratio,
        "missing_fraction": missing_fraction,
        "baro_present_frac": baro_present_fraction(fixes),
        "max_vxy_mps": max_vxy_mps,
        "max_vz_mps": max_vz_mps,
        "baro_alt_min_m": float(np.nanmin(baro)),
        "baro_alt_max_m": float(np.nanmax(baro)),
    }


_SCAN_COLUMNS = [
    "duration_s",
    "n_fix",
    "path_km",
    "extent_km",
    "dt_s",
    "max_gap_ratio",
    "missing_fraction",
    "baro_present_frac",
    "max_vxy_mps",
    "max_vz_mps",
    "baro_alt_min_m",
    "baro_alt_max_m",
]


def _scan_one(path: Path) -> tuple | None:
    """Worker: parse one file, return its :func:`track_stats` as a tuple or ``None``.

    A top-level function (not a closure) so it can be pickled for
    :class:`~concurrent.futures.ProcessPoolExecutor`.
    """
    stats = track_stats(parse_igc(path))
    if stats is None:
        return None
    return tuple(stats[c] for c in _SCAN_COLUMNS)


def scan_tracks(paths: list[Path], *, n_jobs: int = 1) -> pd.DataFrame:
    """Parse a set of IGC files and tabulate their per-flight diagnostics.

    Args:
        paths: IGC file paths (a full census, or a sample).
        n_jobs: Worker processes; ``1`` runs serially in-process.

    Returns:
        A DataFrame with one row per readable flight and columns :data:`_SCAN_COLUMNS`.
    """
    if n_jobs > 1 and len(paths) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            results = list(ex.map(_scan_one, paths, chunksize=200))
    else:
        results = [_scan_one(p) for p in paths]
    rows = [r for r in results if r is not None]
    return pd.DataFrame(rows, columns=_SCAN_COLUMNS)


def load_or_scan_tracks(
    igc_dir: Path, cache_path: Path, *, n_jobs: int = 1, force: bool = False
) -> pd.DataFrame:
    """Load a cached full-dataset scan, or run :func:`scan_tracks` and cache it.

    A full census (:func:`scan_tracks` over every ``.igc`` file under ``igc_dir``) takes
    tens of minutes for the paraglider archive; this avoids repeating it every time a
    figure changes. The cache is a single flat Parquet file, one row per flight, with no
    invalidation logic beyond its presence: delete ``cache_path`` (or pass
    ``force=True``) to force a fresh scan, e.g. after changing :func:`track_stats`.

    Args:
        igc_dir: The discipline's ``igc/`` root (scanned recursively for ``*.igc``).
        cache_path: Where to read/write the cached scan (e.g.
            ``data/paragliders/track_scan.parquet``).
        n_jobs: Worker processes for a fresh scan.
        force: Rescan even if ``cache_path`` already exists.

    Returns:
        The per-flight diagnostics table (:data:`_SCAN_COLUMNS`).
    """
    if cache_path.is_file() and not force:
        print(f"Using cached scan at {cache_path} (delete it to force a rescan).")
        return pd.read_parquet(cache_path)
    paths = sorted(igc_dir.rglob("*.igc"))
    print(
        f"No cache at {cache_path}; scanning {len(paths)} tracks, {n_jobs} workers..."
    )
    scan = scan_tracks(paths, n_jobs=n_jobs)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    scan.to_parquet(cache_path)
    print(f"Cached scan to {cache_path} ({len(scan)} rows).")
    return scan


def fraction_retained(
    values: np.ndarray | pd.Series, threshold: float, *, mode: str = "at_least"
) -> float:
    """Fraction of the finite ``values`` passing ``threshold`` (0 if none finite).

    Args:
        values: Sample values (NaNs ignored).
        threshold: Cut value.
        mode: ``"at_least"`` retains ``values >= threshold`` (a minimum, e.g. duration);
            ``"at_most"`` retains ``values <= threshold`` (a maximum, e.g. a gap size or
            missing fraction, where larger is worse).
    """
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0
    if mode == "at_most":
        return float((v <= threshold).mean())
    return float((v >= threshold).mean())


def retention_curve(
    values: np.ndarray | pd.Series,
    thresholds: np.ndarray | list[float],
    *,
    mode: str = "at_least",
) -> tuple[np.ndarray, np.ndarray]:
    """Retained fraction vs a cut (marginal: one criterion at a time).

    Returns:
        ``(thresholds, fractions)``: ``fractions[i]`` is the retained fraction of
        ``values`` under ``thresholds[i]`` with the given ``mode`` (see
        :func:`fraction_retained`).
    """
    thr = np.asarray(thresholds, dtype=float)
    frac = np.array([fraction_retained(values, float(t), mode=mode) for t in thr])
    return thr, frac


def make_flightlevel_diagnostics_figure(
    scans: dict[str, pd.DataFrame], flight_level: FlightLevelThresholds
) -> Figure:
    """Flight-level filtering diagnostics, per discipline, from full-census track data.

    Four panels, each overlaying every discipline: (a) recorded flight duration and
    (b) total flown path length, with the adopted cut marked; (c)/(d) the fraction of
    flights retained versus that cut, computed for **that cut alone** (marginal, not
    cascaded), so each curve isolates the effect of one criterion.

    Args:
        scans: Mapping ``discipline -> per-flight table`` (``duration_s``, ``path_km``),
            each a full census (:func:`scan_tracks` over every track).
        flight_level: The adopted thresholds to mark.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 6.8))

    dur_grid = np.linspace(5.0, 150.0, 80)  # minutes
    path_grid = np.logspace(np.log10(1.0), np.log10(500.0), 80)  # km

    for disc, s in scans.items():
        color = _DISC_COLOR.get(disc, "gray")
        dur_h = pd.to_numeric(s["duration_s"], errors="coerce") / 3600.0
        dur_h = dur_h[dur_h > 0]
        path = pd.to_numeric(s["path_km"], errors="coerce")
        path = path[path > 0]

        axes[0, 0].hist(
            dur_h[dur_h <= 12],
            bins=np.linspace(0, 12, 70),
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[0, 1].hist(
            path,
            bins=np.logspace(np.log10(0.5), np.log10(1000), 70),
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[1, 0].plot(
            dur_grid,
            100.0 * retention_curve(dur_h * 60.0, dur_grid)[1],
            color=color,
            lw=1.6,
            label=disc,
        )
        axes[1, 1].plot(
            path_grid,
            100.0 * retention_curve(path, path_grid)[1],
            color=color,
            lw=1.6,
            label=disc,
        )

    axes[0, 0].axvline(flight_level.min_duration_s / 3600.0, **line_kw)
    axes[0, 0].set(
        xlabel="recorded flight duration [h]",
        ylabel="density",
        title="(a) Duration",
        xlim=(0, 12),
    )
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].axvline(flight_level.min_path_km, **line_kw)
    axes[0, 1].set(
        xlabel="flown path length [km]",
        ylabel="density",
        title="(b) Path length",
        xscale="log",
    )

    axes[1, 0].axvline(flight_level.min_duration_s / 60.0, **line_kw)
    axes[1, 0].set(
        xlabel=r"minimum duration $T_{\min}$ [min]",
        ylabel="flights retained [%]",
        title="(c) Retention vs duration cut (this cut alone)",
    )
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].axvline(flight_level.min_path_km, **line_kw)
    axes[1, 1].set(
        xlabel="minimum path length [km]",
        ylabel="flights retained [%]",
        title="(d) Retention vs path cut (this cut alone)",
        xscale="log",
    )
    axes[1, 1].grid(alpha=0.3)

    fig.tight_layout()
    return fig


def make_gap_diagnostics_figure(
    scans: dict[str, pd.DataFrame], sampling: SamplingThresholds
) -> Figure:
    """Sampling-regularity diagnostics: how the gap-based exclusion would act.

    Mirrors :func:`make_flightlevel_diagnostics_figure`. Two panels overlay every
    discipline's distribution -- (a) the largest single gap, in units of its own native
    sampling interval, and (b) the fraction of a uniform grid at that interval left
    uncovered (see :func:`track_stats`) -- and two show the marginal retention curve for
    each cut alone, with the adopted threshold marked.

    Args:
        scans: Mapping ``discipline -> per-flight table`` with ``max_gap_ratio`` and
            ``missing_fraction`` columns (:func:`scan_tracks` over every track).
        sampling: The adopted thresholds to mark.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 6.8))

    # Clean per-discipline series once.
    gaps: dict[str, np.ndarray] = {}
    misses: dict[str, np.ndarray] = {}
    for disc, s in scans.items():
        g = pd.to_numeric(s["max_gap_ratio"], errors="coerce")
        gaps[disc] = g[np.isfinite(g) & (g > 0)].to_numpy()
        m = pd.to_numeric(s["missing_fraction"], errors="coerce")
        misses[disc] = m[np.isfinite(m)].to_numpy()

    # Distribution panels (a)/(b): fit the x-range to where the mass and the cut are,
    # not a fixed constant, so it adapts to any dataset. These quantities have a very
    # heavy tail (a few flights with a huge relative gap), so a high percentile would
    # stretch the axis far past the bulk. We take the bulk (90th percentile) but keep a
    # margin past the adopted cut so it stays in view; the heavy tail is not lost, the
    # retention panels (c)/(d) sweep the whole range.
    pooled_gap = np.concatenate(
        [g for g in gaps.values() if g.size] or [np.array([1.0])]
    )
    pooled_miss = np.concatenate(
        [m for m in misses.values() if m.size] or [np.array([0.0])]
    )
    gap_hi = float(max(np.quantile(pooled_gap, 0.90), sampling.max_gap_factor * 2.0))
    miss_hi = float(
        max(np.quantile(pooled_miss, 0.90), sampling.max_missing_fraction * 2.0)
    )
    gap_bins = np.logspace(0.0, np.log10(gap_hi), 50)
    miss_bins = np.linspace(0.0, miss_hi, 50)

    # Retention curves (c)/(d) sweep a wide range to show the full saturating shape.
    gap_grid = np.logspace(0.0, np.log10(max(200.0, gap_hi)), 80)  # dimensionless ratio
    miss_grid = np.linspace(0.0, max(0.6, miss_hi), 80)  # fraction

    for disc in scans:
        color = _DISC_COLOR.get(disc, "gray")
        axes[0, 0].hist(
            gaps[disc],
            bins=gap_bins,
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[0, 1].hist(
            misses[disc],
            bins=miss_bins,
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[1, 0].plot(
            gap_grid,
            100.0 * retention_curve(gaps[disc], gap_grid, mode="at_most")[1],
            color=color,
            lw=1.6,
            label=disc,
        )
        axes[1, 1].plot(
            miss_grid,
            100.0 * retention_curve(misses[disc], miss_grid, mode="at_most")[1],
            color=color,
            lw=1.6,
            label=disc,
        )

    axes[0, 0].axvline(sampling.max_gap_factor, **line_kw)
    axes[0, 0].set(
        xlabel=r"largest gap / native $\Delta t$",
        ylabel="density",
        title="(a) Largest gap (relative)",
        xscale="log",
        xlim=(1.0, gap_hi),
    )
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].axvline(sampling.max_missing_fraction, **line_kw)
    axes[0, 1].set(
        xlabel="missing fraction of the uniform grid",
        ylabel="density",
        title="(b) Missing fraction",
        xlim=(0.0, miss_hi),
    )

    axes[1, 0].axvline(sampling.max_gap_factor, **line_kw)
    axes[1, 0].set(
        xlabel=r"cut on largest gap / native $\Delta t$",
        ylabel="flights retained [%]",
        title="(c) Retention vs gap cut (this cut alone)",
        xscale="log",
    )
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].axvline(sampling.max_missing_fraction, **line_kw)
    axes[1, 1].set(
        xlabel="cut on missing fraction",
        ylabel="flights retained [%]",
        title="(d) Retention vs missing-fraction cut (this cut alone)",
    )
    axes[1, 1].grid(alpha=0.3)

    fig.tight_layout()
    return fig


def make_sampling_figure(scans: dict[str, pd.DataFrame]) -> Figure:
    """Native sampling-interval distribution per discipline (full-census track data).

    Args:
        scans: Mapping ``discipline -> per-flight table`` with a ``dt_s`` column.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    for disc, s in scans.items():
        dt = pd.to_numeric(s["dt_s"], errors="coerce")
        dt = dt[(dt > 0) & np.isfinite(dt)]
        ax.hist(
            dt.clip(upper=8),
            bins=np.arange(0.25, 8.75, 0.5),
            density=True,
            histtype="step",
            lw=1.5,
            color=_DISC_COLOR.get(disc, "gray"),
            label=disc,
        )
    ax.set_xlabel(r"native sampling interval $\Delta t$ [s]")
    ax.set_ylabel("density")
    ax.set_title("Native sampling interval, per flight")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


_FIXLEVEL_QUANTITIES = ("v_xy", "v_z", "altitude")


def _fix_level_arrays(fixes: pd.DataFrame) -> dict[str, np.ndarray]:
    """The per-fix quantities the fix-level bounds act on, from one parsed track.

    Returns per-*fix* arrays (not per-flight summaries): the great-circle horizontal
    speed between consecutive fixes, the barometric vertical speed between consecutive
    fixes, and the barometric altitude at each fix. Vertical speed and altitude are only
    physical when the flight carries a barometric channel, so they are empty for a
    GNSS-only flight. Consecutive pairs with a non-positive time step (duplicate
    timestamps) are dropped.
    """
    empty = {q: np.empty(0) for q in _FIXLEVEL_QUANTITIES}
    n = len(fixes)
    if n < 2:
        return empty
    t = fixes["t"].to_numpy()
    dt = np.diff(t)
    ok = dt > 0
    if not ok.any():
        return empty
    lat = fixes["lat"].to_numpy()
    lon = fixes["lon"].to_numpy()
    step = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    out = {"v_xy": step[ok] / dt[ok], "v_z": np.empty(0), "altitude": np.empty(0)}
    if baro_present_fraction(fixes) >= _BARO_PRESENT_MIN:
        baro = fixes["baro_alt"].to_numpy()
        out["v_z"] = np.abs(np.diff(baro))[ok] / dt[ok]
        out["altitude"] = baro
    return out


def _fix_level_one(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Worker: the three per-fix arrays for one file (picklable for the pool)."""
    a = _fix_level_arrays(parse_igc(path))
    return a["v_xy"], a["v_z"], a["altitude"]


def fix_level_distributions(
    paths: list[Path], *, n_jobs: int = 1
) -> dict[str, np.ndarray]:
    """Pool the per-fix fix-level quantities over a sample of flights.

    Returns concatenated arrays keyed ``v_xy``, ``v_z`` and ``altitude`` -- one value
    per fix, across every sampled flight -- the material for
    :func:`make_fixlevel_diagnostics_figure`. A sample (rather than the full census) is
    the right tool here, exactly as for the altitude PSD: even a few hundred flights is
    millions of fixes, enough for a sharp distribution and a precise cut fraction, at a
    fraction of the cost.

    Args:
        paths: IGC file paths (typically a seeded sample; see ``sample_igc_paths``).
        n_jobs: Worker processes; ``1`` runs serially in-process.
    """
    if n_jobs > 1 and len(paths) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            results = list(ex.map(_fix_level_one, paths, chunksize=50))
    else:
        results = [_fix_level_one(p) for p in paths]
    return {
        key: (np.concatenate([r[i] for r in results]) if results else np.empty(0))
        for i, key in enumerate(_FIXLEVEL_QUANTITIES)
    }


def make_fixlevel_diagnostics_figure(
    distributions: dict[str, dict[str, np.ndarray]], fix_level: FixLevelThresholds
) -> Figure:
    """Fix-level cleaning diagnostics: the per-fix distributions the bounds act on.

    Three panels, each overlaying every discipline, for the quantities the fix-level
    cuts test between/at consecutive fixes: (a) horizontal speed ``v_xy``, (b)
    barometric vertical speed ``|v_z|``, (c) barometric altitude. Unlike the
    flight-level figure these are distributions over individual *fixes*, not per-flight
    summaries: a bound removes only the few offending fixes of an otherwise good
    flight, so what justifies it is that it sits in the physically-implausible tail
    (a GPS error, not signal) and removes a negligible fraction of fixes, annotated on
    each panel. The y-axis is logarithmic so that tail, where the cuts act, is visible.

    Args:
        distributions: Mapping ``discipline -> {quantity -> per-fix values}`` from
            :func:`fix_level_distributions`.
        fix_level: The adopted bounds to mark.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.7))

    def _panel(ax, key, cuts, xlabel, title):
        # x-range fitted to the data (a high percentile of the pooled sample) and
        # extended to keep every cut in view; no fixed constant, dataset-agnostic.
        pooled = np.concatenate(
            [d[key] for d in distributions.values() if d.get(key, np.empty(0)).size]
            or [np.array([0.0])]
        )
        lo = min(float(np.quantile(pooled, 0.001)), *cuts)
        hi = max(float(np.quantile(pooled, 0.999)), *(c * 1.05 for c in cuts))
        span = (hi - lo) or 1.0
        lo, hi = lo - 0.02 * span, hi + 0.02 * span
        bins = np.linspace(lo, hi, 60)
        for disc, d in distributions.items():
            v = d.get(key, np.empty(0))
            if v.size:
                ax.hist(
                    v,
                    bins=bins,
                    density=True,
                    histtype="step",
                    lw=1.5,
                    color=_DISC_COLOR.get(disc, "gray"),
                    label=disc,
                )
        for c in cuts:
            ax.axvline(c, **line_kw)
        # Fraction of fixes each cut removes (pooled): the number that justifies it.
        if len(cuts) == 1:
            frac = float(np.mean(pooled > cuts[0])) * 100.0
            note = f"cut removes {frac:.2g}% of fixes"
        else:
            frac = float(np.mean((pooled < cuts[0]) | (pooled > cuts[1]))) * 100.0
            note = f"band removes {frac:.2g}% of fixes"
        ax.set(
            xlabel=xlabel, ylabel="density", title=title, yscale="log", xlim=(lo, hi)
        )
        ax.text(
            0.97,
            0.95,
            note,
            transform=ax.transAxes,
            fontsize=7.5,
            ha="right",
            va="top",
            color="0.25",
        )

    _panel(
        axes[0],
        "v_xy",
        (fix_level.max_horizontal_speed_mps,),
        r"horizontal speed $v_{xy}$ [m/s]",
        "(a) Horizontal speed",
    )
    axes[0].legend(fontsize=8)
    _panel(
        axes[1],
        "v_z",
        (fix_level.max_vertical_speed_mps,),
        r"barometric $|v_z|$ [m/s]",
        "(b) Vertical speed",
    )
    _panel(
        axes[2],
        "altitude",
        (fix_level.min_altitude_m, fix_level.max_altitude_m),
        "barometric altitude [m]",
        "(c) Altitude",
    )
    fig.tight_layout()
    return fig
