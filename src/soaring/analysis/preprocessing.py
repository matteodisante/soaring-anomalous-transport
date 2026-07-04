"""Pre-processing thresholds and the *track-based* diagnostics that justify them.

Trajectory pre-processing uses several numeric thresholds (see the thesis chapter "Next
steps", Sec. 4.1). **None of them is hard-coded here**: their values live in
``configs/preprocessing.yaml`` -- the single documented place to change a cut -- read
into typed dataclasses by :func:`load_preproc_config`. This module also provides the
diagnostics that justify the flight-level cuts, computed **from the parsed IGC tracks
themselves** (:func:`scan_tracks`), not from the declared catalog metadata (which has
outliers and placeholder dates, so it is a coarse pre-filter at most).
:func:`make_diagnostics_figure` draws the track distributions with the adopted cuts
marked, so the choice is auditable on the real data.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .igc import median_sampling_period, parse_igc

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


@dataclass(frozen=True)
class FixLevelThresholds:
    """Physical bounds for fix-level cleaning (loaded from the config).

    The speeds are great-circle (haversine) speeds between consecutive fixes, on the raw
    geographic coordinates (no conversion yet). The vertical-speed and altitude bounds
    apply to the adopted barometric channel.
    """

    max_horizontal_speed_mps: float
    max_vertical_speed_mps: float
    min_altitude_m: float
    max_altitude_m: float
    max_time_gap_s: float


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
    fix from the first), and the native sampling interval.

    Args:
        fixes: Table returned by :func:`soaring.analysis.igc.parse_igc`.

    Returns:
        A mapping with ``duration_s``, ``n_fix``, ``path_km``, ``extent_km`` and
        ``dt_s``, or ``None`` if the track has fewer than two fixes.
    """
    n = len(fixes)
    if n < 2:
        return None
    t = fixes["t"].to_numpy()
    lat = fixes["lat"].to_numpy()
    lon = fixes["lon"].to_numpy()
    steps = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    disp = great_circle_m(lat[0], lon[0], lat, lon)
    return {
        "duration_s": float(t[-1] - t[0]),
        "n_fix": int(n),
        "path_km": float(np.nansum(steps)) / 1000.0,
        "extent_km": float(np.nanmax(disp)) / 1000.0,
        "dt_s": median_sampling_period(fixes),
    }


_SCAN_COLUMNS = ["duration_s", "n_fix", "path_km", "extent_km", "dt_s"]


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


def fraction_retained(values: np.ndarray | pd.Series, threshold: float) -> float:
    """Fraction of the finite ``values`` at/above ``threshold`` (0 if none finite)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0
    return float((v >= threshold).mean())


def retention_curve(
    values: np.ndarray | pd.Series, thresholds: np.ndarray | list[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Retained fraction vs a lower cut (marginal: one criterion at a time).

    Returns:
        ``(thresholds, fractions)``: ``fractions[i]`` is the retained fraction of
        ``values`` at or above ``thresholds[i]``.
    """
    thr = np.asarray(thresholds, dtype=float)
    frac = np.array([fraction_retained(values, float(t)) for t in thr])
    return thr, frac


def make_diagnostics_figure(
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
