"""Pre-processing thresholds and the catalog diagnostics that justify them.

Trajectory pre-processing applies two kinds of thresholds (see the thesis chapter
"Next steps"):

* **fix-level cleaning** -- *physical* bounds that reject impossible or corrupted GPS
  fixes. They do not depend on the dataset and are fixed a priori
  (:class:`FixLevelThresholds`);
* **flight-level filtering** -- *population* thresholds that drop whole flights unfit
  for the ensemble analysis (:class:`FlightLevelThresholds`). These are read off the
  empirical distributions of the flight catalog rather than guessed: the helpers here
  compute those distributions and :func:`make_diagnostics_figure` draws them with the
  chosen thresholds marked, so the choice is auditable.

The catalog analysed is ``data/catalog.csv`` (one row per flight; see
:mod:`soaring.acquisition.ffvl.catalog`). Only its metadata columns are used
(``duration_s``, ``distance_km``, ``file_size``); the true number of valid fixes and
the true spatial extent require parsing the IGC tracks and will refine the
``file_size``/``distance_km`` proxies used at this stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# A B record (one GPS fix) is ~35 characters plus a line ending; with the common
# optional extensions it is of order 40 bytes. Used only as a fix-count proxy until
# the tracks themselves are parsed.
APPROX_BYTES_PER_FIX = 40


@dataclass(frozen=True)
class FixLevelThresholds:
    """Physical bounds for fix-level cleaning (fixed a priori, not data-driven).

    The speed bounds are for paragliders (the current FFVL dataset) and scale up for
    the faster gliders of future sources.

    Attributes:
        max_horizontal_speed_mps: Ground speed above which a step is a GPS jump.
        max_vertical_speed_mps: Vertical speed beyond the soaring climb/sink range
            (also catches GNSS-altitude spikes); depends on the altitude channel.
        min_altitude_m: Lower plausible GNSS-altitude bound.
        max_altitude_m: Upper plausible GNSS-altitude bound.
        max_time_gap_s: Inter-fix interval above which the gap is flagged or split.
    """

    max_horizontal_speed_mps: float = 40.0
    max_vertical_speed_mps: float = 10.0
    min_altitude_m: float = -100.0
    max_altitude_m: float = 6000.0
    max_time_gap_s: float = 60.0


@dataclass(frozen=True)
class FlightLevelThresholds:
    """Population thresholds for flight-level filtering (set from the catalog).

    Attributes:
        min_duration_s: Minimum airborne duration; shorter logs are sled runs or
            aborted attempts. Placed on the flat part of the retention curve.
        min_valid_fixes: Minimum number of valid fixes after cleaning.
        min_extent_km: Minimum net displacement (or bounding-box diagonal).
    """

    min_duration_s: float = 1800.0
    min_valid_fixes: int = 200
    min_extent_km: float = 2.0


def approx_num_fixes(file_size_bytes: pd.Series | np.ndarray) -> np.ndarray:
    """Rough number of GPS fixes inferred from the IGC file size.

    Args:
        file_size_bytes: File sizes in bytes.

    Returns:
        Estimated fix counts (``file_size / APPROX_BYTES_PER_FIX``).
    """
    return np.asarray(file_size_bytes, dtype=float) / APPROX_BYTES_PER_FIX


def fraction_retained(values: np.ndarray | pd.Series, threshold: float) -> float:
    """Fraction of the finite ``values`` at or above ``threshold``.

    Args:
        values: Sample values (NaNs are ignored).
        threshold: Lower cut.

    Returns:
        Retained fraction in ``[0, 1]`` (``0.0`` if there are no finite values).
    """
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0
    return float((v >= threshold).mean())


def retention_curve(
    values: np.ndarray | pd.Series, thresholds: np.ndarray | list[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Retained fraction as a function of a lower cut.

    Args:
        values: Sample values (NaNs ignored).
        thresholds: Candidate lower cuts.

    Returns:
        A pair ``(thresholds, fractions)``, with ``fractions[i]`` the fraction of
        ``values`` at or above ``thresholds[i]``.
    """
    thr = np.asarray(thresholds, dtype=float)
    frac = np.array([fraction_retained(values, float(t)) for t in thr])
    return thr, frac


def load_catalog(path: Path) -> pd.DataFrame:
    """Load the flight catalog CSV.

    Args:
        path: Path to ``catalog.csv``.

    Returns:
        The catalog as a DataFrame.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Catalog not found: {path}")
    return pd.read_csv(path)


def make_diagnostics_figure(
    catalog: pd.DataFrame, flight_level: FlightLevelThresholds | None = None
) -> Figure:
    """Build the pre-processing diagnostics figure.

    Four panels show the catalog distributions that justify the flight-level filtering
    thresholds, each marked with the adopted cut: (a) flight duration and (b) the
    fraction of flights retained versus the minimum duration; (c) the declared
    cross-country distance (a spatial-extent proxy); (d) the approximate track length.

    Args:
        catalog: Flight catalog with ``duration_s``, ``distance_km`` and ``file_size``.
        flight_level: Thresholds to mark (defaults to :class:`FlightLevelThresholds`).

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt  # lazy import: matplotlib is an optional extra

    ft = flight_level or FlightLevelThresholds()
    line_kw = {"color": "crimson", "ls": "--", "lw": 1.3}

    dur_h = pd.to_numeric(catalog["duration_s"], errors="coerce")
    dur_h = dur_h[dur_h > 0] / 3600.0
    dist = pd.to_numeric(catalog["distance_km"], errors="coerce")
    dist = dist[(dist > 0) & (dist < 2000)]
    nfix = approx_num_fixes(pd.to_numeric(catalog["file_size"], errors="coerce"))
    nfix = nfix[np.isfinite(nfix) & (nfix > 0)]

    fig, axes = plt.subplots(2, 2, figsize=(9.0, 6.4))

    ax = axes[0, 0]
    ax.hist(dur_h.clip(upper=12), bins=np.linspace(0, 12, 60), color="#3477a8")
    ax.axvline(ft.min_duration_s / 3600.0, **line_kw)
    ax.set_xlabel("flight duration [h]")
    ax.set_ylabel("flights")
    ax.set_title("(a) Duration")

    ax = axes[0, 1]
    tmin_min = np.linspace(5, 120, 60)
    _, frac = retention_curve(dur_h * 60.0, tmin_min)
    ax.plot(tmin_min, 100.0 * frac, color="#b5482a")
    ax.axvline(ft.min_duration_s / 60.0, **line_kw)
    ax.set_xlabel(r"minimum duration $T_{\min}$ [min]")
    ax.set_ylabel("flights retained [%]")
    ax.set_title("(b) Retention vs cut")
    ax.grid(alpha=0.3)

    ax = axes[1, 0]
    ax.hist(dist, bins=np.logspace(0.0, np.log10(2000), 60), color="#3d8c54")
    ax.axvline(ft.min_extent_km, **line_kw)
    ax.set_xscale("log")
    ax.set_xlabel("declared XC distance [km]")
    ax.set_ylabel("flights")
    ax.set_title("(c) Distance (extent proxy)")

    ax = axes[1, 1]
    ax.hist(nfix, bins=np.logspace(np.log10(50), np.log10(50000), 60), color="#7a5aa0")
    ax.axvline(ft.min_valid_fixes, **line_kw)
    ax.set_xscale("log")
    ax.set_xlabel(rf"approx. fixes ($\approx$ size / {APPROX_BYTES_PER_FIX} B)")
    ax.set_ylabel("flights")
    ax.set_title("(d) Track length proxy")

    fig.tight_layout()
    return fig
