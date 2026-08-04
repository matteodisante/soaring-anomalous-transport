"""The raw-archive census: what the tracks look like before anything is done to them.

A scan over the `.igc` files that reads each track once and reduces it to a row of summary
statistics -- duration, path length, fix count, native sampling period, barometric
presence. The pre-processing thresholds are set against these distributions, and the
retention curves below are what turns a candidate threshold into "how many flights would
this keep".

It is deliberately separate from the pipeline: the pipeline transforms trajectories, this
only measures them, and it runs on the raw archive rather than on the processed tables.
The result is cached (:func:`load_or_scan_tracks`), since a full scan is tens of minutes
and nothing in it changes unless the archive does.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

# Mean Earth radius (IUGG), the sphere the great-circle distance is measured on.
_EARTH_RADIUS_M = 6371008.8

# The per-fix quantities the fix-level bounds act on, in the order the panels use.
_FIXLEVEL_QUANTITIES = ("v_xy", "v_z", "altitude")

from .altitude_noise import BARO_PRESENT_MIN

_BARO_PRESENT_MIN = BARO_PRESENT_MIN
from .igc import baro_present_fraction, median_sampling_period, parse_igc
from .preproc.resample import split_bound_s


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
    on, thesis sec:uniform), the barometric-presence fraction, the largest
    horizontal/vertical speed between consecutive fixes, and the barometric-altitude
    range -- these last four are not yet used by any thesis figure, but are cheap
    byproducts of this same scan and directly support future work: validating the
    fix-level speed/altitude bounds of tab:cleaning against real data, and (for
    ``baro_present_frac``) the barometric-presence figure of sec:altchannel, which today
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
