#!/usr/bin/env python3
r"""Whether the anisotropy of fig:prelim-isotropy is a property of displacement alone.

fig:prelim-isotropy reads the per-component variance ratio ``<E^2>/<N^2>`` off the
*displacement* ``E(t)``, ``N(t)`` from each flight's first retained fix. Displacement is
an integral of velocity, so a ratio away from unity there is consistent with either an
anisotropic *process* (the wind, the terrain) or with an anisotropic *sampling* of an
isotropic one (more flights drifting east than north). Reading the same ratio off the
velocity and the acceleration the Savitzky-Golay stage (sec:savgol) already wrote into
the fix table separates the two: velocity and acceleration are local in time, so their
anisotropy cannot be inherited from where a flight happened to start or how long ago that
was, only from the process generating the motion at that instant.

Four exploratory figures, not wired into the thesis document:

``kinematic_isotropy_discipline.pdf``
    Same reduction as fig:prelim-isotropy -- paragliders against hang gliders -- but one
    panel per quantity: position, velocity, acceleration.
``kinematic_isotropy_terrain.pdf``
    The same three panels, paragliders only, grouped by orographic setting instead of
    discipline: Alps against Pyrenees against the Channel Coast flat control of
    ``generate_prelim_figure.py`` (its ``OROGRAPHY``/``FLAT_CONTROL`` boxes) -- whether
    relief is what the anisotropy tracks.
``kinematic_isotropy_level.pdf``
    The same three panels, paragliders only, grouped by pilot level instead of terrain:
    beginner (EN A-C) against expert (EN D, CCC, tandem/non-certified) -- whether pilot
    skill is what the anisotropy tracks.
``kinematic_isotropy_terrain_level.pdf``
    Terrain and level crossed: one row per terrain zone (Alps, Pyrenees, flat control),
    each holding the same three panels split beginner against expert -- whether the level
    effect, if any, is uniform across terrain or specific to a zone.
``kinematic_isotropy_flat_level.pdf``
    Level within relief held fixed at *flat*: one row per one of three separated French
    plains (``FLAT_REGIONS`` below), each holding the same three panels split beginner
    against expert -- whether the level effect survives once every row is low-relief, or
    whether ``kinematic_isotropy_terrain_level.pdf``'s Channel Coast row was one lucky
    site rather than a property of flying over flat ground anywhere.

Reads ``audit_positions_<discipline>.npz`` via ``generate_prelim_figure.load()``, which
needs the ``VE``/``VN``/``AE``/``AN`` arrays ``audit_msd.py`` writes alongside ``E``/``N``
(re-run it if an older npz predates them). Writes no macros: this is a diagnostic, run by
hand, not a numbered thesis figure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# generate_prelim_figure.py is a sibling script, not a package -- imported by adding its
# directory to sys.path, the same trick this repo's scripts already use for `soaring`.
import generate_prelim_figure as prelim  # noqa: E402

from soaring.reporting import DISCIPLINES  # noqa: E402

OUT_DISCIPLINE = ROOT / "thesis" / "generated" / "kinematic_isotropy_discipline.pdf"
OUT_TERRAIN = ROOT / "thesis" / "generated" / "kinematic_isotropy_terrain.pdf"
OUT_LEVEL = ROOT / "thesis" / "generated" / "kinematic_isotropy_level.pdf"
OUT_TERRAIN_LEVEL = ROOT / "thesis" / "generated" / "kinematic_isotropy_terrain_level.pdf"
OUT_FLAT_LEVEL = ROOT / "thesis" / "generated" / "kinematic_isotropy_flat_level.pdf"

# The three quantities read off the same audit npz, in the order the panels are drawn.
QUANTITIES = [
    ("position", "east", "north", r"$\langle E^2\rangle\,/\,\langle N^2\rangle$"),
    ("velocity", "veast", "vnorth", r"$\langle v_E^2\rangle\,/\,\langle v_N^2\rangle$"),
    ("acceleration", "aeast", "anorth", r"$\langle a_E^2\rangle\,/\,\langle a_N^2\rangle$"),
]

# Three terrain groups, paragliders only: the two named massifs with the deepest
# ensembles against the flat control -- the same boxes generate_prelim_figure.py's
# orographic_group() labels take-offs with. Massif Central and the two exclusion-defined
# labels (outside massifs, abroad) are left out: the question is relief-vs-relief-vs-none
# for the two ranges with enough flights to carry a curve, not every stratum at once.
TERRAIN_GROUPS = [("Alps", "#b5482a"), ("Pyrenees", "#6a3d9a"), ("Channel Coast", "#2a6db5")]
TERRAIN_LABELS = {"Alps": "Alps", "Pyrenees": "Pyrenees", "Channel Coast": "flat (Channel Coast)"}

# Pilot level, paragliders only: Table~\ref{tab:aileclass}'s six EN/FAI wing classes
# collapsed to two groups rather than read one by one, so a level comparison is legible
# on top of a terrain comparison. EN A-C are the classes flown while still learning the
# fundamentals; EN D, CCC and the pooled tandem/non-certified row (Sec.~\ref{sec:glider})
# are flown by qualified or competition pilots, or under an instructor.
BEGINNER_CLASSES = ("EN A", "EN B", "EN C")
EXPERT_CLASSES = ("EN D", "CCC", "tandem / non-certified")
LEVEL_GROUPS = [("beginner", "#2a6db5"), ("expert", "#b5482a")]

# Three plains, chosen far apart on the map rather than adjacent, so that a level effect
# common to all three is a property of flat ground in general and not of one region's
# take-off mix. Boxes, not polygons, for the same reason OROGRAPHY/FLAT_CONTROL are: a
# box is checkable against a gazetteer. Independent of generate_prelim_figure.REGIONS, so
# this diagnostic cannot perturb the thesis's own strata (Sec.~\ref{sec:strata-compat}).
# Widened from a first pass over real take-off density (audit_flights_para, median
# alt0 shown) until each box held enough flights to compare beginner against expert:
# a box drawn from a map alone, without checking who actually launches there, left two of
# the three rows empty against MIN_STRATUM.
FLAT_REGIONS = {
    # Normandy / Picardy / coastal Nord, median alt0 ~220 m -- same box as
    # generate_prelim_figure.py's FLAT_CONTROL["Channel Coast"]. By far the deepest of
    # the three (beginner 2,618 / expert 2,347), so it alone would already clear
    # MIN_STRATUM; kept as the north-west anchor the other two are compared against.
    "Channel Coast": {"lon": (-1.8, 2.0), "lat": (48.3, 51.2)},
    # Poitou / Charente inland plain (Niort-Melle-Poitiers), median alt0 ~240 m -- west,
    # ~350 km from the Channel Coast box. Fewer experts than beginners fly here
    # (947 against 2,022): unlike the other two rows this one is level-imbalanced by
    # itself, which is part of what a flat-vs-flat comparison can show.
    "Poitou-Charente": {"lon": (-2.0, 1.5), "lat": (44.5, 47.8)},
    # Champagne / southern Lorraine plain, median alt0 ~355 m -- north-centre-east,
    # ~500 km from the other two, clipped short of the Vosges take-offs just east of it
    # (median alt0 there is >1200 m, not flat at all).
    "Champagne-Lorraine": {"lon": (2.1, 6.2), "lat": (48.0, 50.6)},
}
FLAT_GROUPS = [
    ("Channel Coast", "#2a6db5"), ("Poitou-Charente", "#2a9e6d"), ("Champagne-Lorraine", "#c98a1e"),
]

# Two of the three regions above run a little under generate_prelim_figure.MIN_STRATUM
# (2,000) per level even at this width -- the archive simply has fewer flat-terrain
# flights outside the Channel Coast. Widening the boxes further stops being a "flat
# region" and starts being "most of France", so the bar is lowered for this figure only;
# the flight count in every legend still says exactly how thin each curve is.
FLAT_MIN_STRATUM = 900

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def flat_region(lat, lon) -> np.ndarray:
    """Each take-off's ``FLAT_REGIONS`` label, or ``""`` if in none of the three."""
    lat, lon = np.asarray(lat), np.asarray(lon)
    labels = np.full(lat.shape, "", dtype=object)
    for name, box in FLAT_REGIONS.items():
        hit = (
            (lon >= box["lon"][0]) & (lon <= box["lon"][1])
            & (lat >= box["lat"][0]) & (lat <= box["lat"][1])
        )
        labels[hit] = name
    return labels


def pilot_level(wing_class) -> np.ndarray:
    """Each paraglider's canonical wing class collapsed to ``"beginner"``/``"expert"``.

    A flight with no canonical class (an unclassified or missing ``aile_class``) comes
    back as ``""``, dropped from both groups rather than guessed.
    """
    wing_class = np.asarray(wing_class, dtype=object)
    labels = np.full(wing_class.shape, "", dtype=object)
    labels[np.isin(wing_class, BEGINNER_CLASSES)] = "beginner"
    labels[np.isin(wing_class, EXPERT_CLASSES)] = "expert"
    return labels


def _clip_to_medians(ax, medians: list[np.ndarray]) -> None:
    """Scale the main panel to the median curves, not the bootstrap band's tail.

    At the longest lags a handful of flights carry a cluster, and a resample that lands
    on a near-zero denominator sends that one replicate -- and so the 90% band, though not
    the median -- to an outlier ratio. Autoscaling to the band lets that single point set
    the axis and flattens everything else to a line; the medians, which are what the
    comparison is actually about, stay well-behaved throughout.
    """
    finite = np.concatenate([m[np.isfinite(m)] for m in medians]) if medians else np.array([])
    if finite.size == 0:
        return
    low, high = min(0.0, float(finite.min())), float(finite.max())
    pad = 0.15 * (high - low if high > low else max(abs(high), 1.0))
    ax.set_ylim(low - pad, high + pad)


def _plot_band(ax, inset_ax, lags, east, north, frame, color, label) -> np.ndarray | None:
    """Draw one group's iso-ratio band and median onto the main and inset axes.

    Returns the drawn median (for ``_clip_to_medians``), or ``None`` if nothing was
    finite to draw -- the caller then knows not to count this group as drawn.
    """
    lo, med, hi = prelim.iso_ratio_band(east, north, frame)
    drawable = np.isfinite(med) & (lags >= 1.0)
    if not drawable.any():
        return None
    ax.fill_between(lags[drawable], lo[drawable], hi[drawable], color=color, alpha=0.25, lw=0)
    ax.semilogx(lags[drawable], med[drawable], color=color, label=label)
    zoom = drawable & (lags <= 1e4)
    inset_ax.fill_between(lags[zoom], lo[zoom], hi[zoom], color=color, alpha=0.25, lw=0)
    inset_ax.semilogx(lags[zoom], med[zoom], color=color)
    return med[drawable]


def _finish_panel(ax, inset_ax, title, ylabel, letter, medians: list[np.ndarray]) -> None:
    """Axis labels, legend and inset framing shared by every panel of every figure."""
    ax.axhline(1.0, color="0.3", lw=0.8, ls="--")
    ax.set_xlabel("elapsed time $t$ (s)")
    ax.set_ylabel(ylabel)
    ax.set_title(f"({letter}) {title}", fontsize=10, loc="left")
    if medians:
        ax.legend(frameon=True, framealpha=0.85, edgecolor="none", fontsize=8, loc="upper left")
        _clip_to_medians(ax, medians)
        inset_ax.axhline(1.0, color="0.3", lw=0.8, ls="--")
        inset_ax.set_xlim(1.0, 1e4)
        inset_ax.set_xticks([1e0, 1e2, 1e4])
        inset_ax.tick_params(labelsize=6)
        ax.indicate_inset_zoom(inset_ax, edgecolor="0.4")
    else:
        ax.text(0.5, 0.5, "no kinematics in audit npz\n(re-run audit_msd.py)",
                transform=ax.transAxes, ha="center", va="center", fontsize=8, color="0.4")
        inset_ax.remove()


def draw_by_discipline(loaded: dict) -> object:
    """Position, velocity, acceleration isotropy, paragliders against hang gliders."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))

    for index, (ax, (title, ekey, nkey, ylabel)) in enumerate(zip(axes, QUANTITIES)):
        inset_ax = ax.inset_axes([0.42, 0.55, 0.53, 0.4])
        medians = []
        for discipline, data in loaded.items():
            if ekey not in data:
                continue
            med = _plot_band(ax, inset_ax, data["lags"], data[ekey], data[nkey], data["flights"],
                              DISCIPLINES[discipline].color, discipline)
            if med is not None:
                medians.append(med)
        _finish_panel(ax, inset_ax, title, ylabel, chr(97 + index), medians)

    fig.tight_layout()
    return fig


def draw_by_terrain(loaded: dict) -> object:
    """Position, velocity, acceleration isotropy, Alps against Pyrenees against flat."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))

    data = loaded.get("paragliders")
    for index, (ax, (title, ekey, nkey, ylabel)) in enumerate(zip(axes, QUANTITIES)):
        inset_ax = ax.inset_axes([0.42, 0.55, 0.53, 0.4])
        medians = []
        if data is not None and ekey in data:
            lags, frame = data["lags"], data["flights"]
            for name, color in TERRAIN_GROUPS:
                mask = (frame["group"] == name).to_numpy()
                if mask.sum() < prelim.MIN_STRATUM:
                    continue
                med = _plot_band(ax, inset_ax, lags, data[ekey][mask], data[nkey][mask],
                                  frame[mask], color, f"{TERRAIN_LABELS[name]} ({mask.sum():,})")
                if med is not None:
                    medians.append(med)
        _finish_panel(ax, inset_ax, title, ylabel, chr(97 + index), medians)

    fig.suptitle("Paragliders only, grouped by take-off terrain", fontsize=9, y=1.02)
    fig.tight_layout()
    return fig


def draw_by_level(loaded: dict) -> object:
    """Position, velocity, acceleration isotropy, beginner against expert paragliders."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))

    data = loaded.get("paragliders")
    for index, (ax, (title, ekey, nkey, ylabel)) in enumerate(zip(axes, QUANTITIES)):
        inset_ax = ax.inset_axes([0.42, 0.55, 0.53, 0.4])
        medians = []
        if data is not None and ekey in data:
            lags, frame = data["lags"], data["flights"]
            for name, color in LEVEL_GROUPS:
                mask = (frame["level"] == name).to_numpy()
                if mask.sum() < prelim.MIN_STRATUM:
                    continue
                med = _plot_band(ax, inset_ax, lags, data[ekey][mask], data[nkey][mask],
                                  frame[mask], color, f"{name} ({mask.sum():,})")
                if med is not None:
                    medians.append(med)
        _finish_panel(ax, inset_ax, title, ylabel, chr(97 + index), medians)

    fig.suptitle("Paragliders only, grouped by pilot level", fontsize=9, y=1.02)
    fig.tight_layout()
    return fig


def draw_by_terrain_level(loaded: dict) -> object:
    """Position, velocity, acceleration isotropy, beginner against expert, one row per
    terrain zone -- whether a level effect is uniform across terrain or zone-specific."""
    import matplotlib.pyplot as plt

    zones = [name for name, _ in TERRAIN_GROUPS]
    fig, grid = plt.subplots(len(zones), 3, figsize=(13.5, 4.0 * len(zones)))

    data = loaded.get("paragliders")
    for row, zone in enumerate(zones):
        for index, (ax, (title, ekey, nkey, ylabel)) in enumerate(zip(grid[row], QUANTITIES)):
            inset_ax = ax.inset_axes([0.42, 0.55, 0.53, 0.4])
            medians = []
            if data is not None and ekey in data:
                lags, frame = data["lags"], data["flights"]
                in_zone = (frame["group"] == zone).to_numpy()
                for name, color in LEVEL_GROUPS:
                    mask = in_zone & (frame["level"] == name).to_numpy()
                    if mask.sum() < prelim.MIN_STRATUM:
                        continue
                    med = _plot_band(ax, inset_ax, lags, data[ekey][mask], data[nkey][mask],
                                      frame[mask], color, f"{name} ({mask.sum():,})")
                    if med is not None:
                        medians.append(med)
            _finish_panel(ax, inset_ax, f"{TERRAIN_LABELS[zone]}: {title}", ylabel,
                          chr(97 + index), medians)

    fig.suptitle("Paragliders only, expert vs. beginner within each terrain zone",
                 fontsize=9, y=1.0)
    fig.tight_layout()
    return fig


def draw_by_flat_level(loaded: dict) -> object:
    """Position, velocity, acceleration isotropy, beginner against expert, one row per
    flat region -- whether a level effect seen on flat ground is common to three separated
    plains or an artefact of a single site's take-off mix."""
    import matplotlib.pyplot as plt

    zones = [name for name, _ in FLAT_GROUPS]
    fig, grid = plt.subplots(len(zones), 3, figsize=(13.5, 4.0 * len(zones)))

    data = loaded.get("paragliders")
    for row, zone in enumerate(zones):
        for index, (ax, (title, ekey, nkey, ylabel)) in enumerate(zip(grid[row], QUANTITIES)):
            inset_ax = ax.inset_axes([0.42, 0.55, 0.53, 0.4])
            medians = []
            if data is not None and ekey in data:
                lags, frame = data["lags"], data["flights"]
                in_zone = (frame["flat_group"] == zone).to_numpy()
                for name, color in LEVEL_GROUPS:
                    mask = in_zone & (frame["level"] == name).to_numpy()
                    if mask.sum() < FLAT_MIN_STRATUM:
                        continue
                    med = _plot_band(ax, inset_ax, lags, data[ekey][mask], data[nkey][mask],
                                      frame[mask], color, f"{name} ({mask.sum():,})")
                    if med is not None:
                        medians.append(med)
            _finish_panel(ax, inset_ax, f"{zone}: {title}", ylabel, chr(97 + index), medians)

    fig.suptitle("Paragliders only, expert vs. beginner within each of three flat regions",
                 fontsize=9, y=1.0)
    fig.tight_layout()
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()

    import matplotlib
    matplotlib.use("Agg")

    loaded = {}
    for discipline in DISCIPLINES:
        data = prelim.load(discipline, args.audit_dir)
        if data is None:
            continue
        if discipline == "paragliders":
            data["flights"] = data["flights"].assign(
                level=pilot_level(data["flights"]["wing_class"].to_numpy()),
                flat_group=flat_region(
                    data["flights"]["lat0"].to_numpy(), data["flights"]["lon0"].to_numpy()
                ),
            )
        loaded[discipline] = data
    if not loaded:
        print("no audit inputs reachable; kinematic isotropy figures not written")
        return 1

    OUT_DISCIPLINE.parent.mkdir(parents=True, exist_ok=True)
    draw_by_discipline(loaded).savefig(OUT_DISCIPLINE, metadata=_PDF_METADATA)
    draw_by_terrain(loaded).savefig(OUT_TERRAIN, metadata=_PDF_METADATA, bbox_inches="tight")
    draw_by_level(loaded).savefig(OUT_LEVEL, metadata=_PDF_METADATA, bbox_inches="tight")
    draw_by_terrain_level(loaded).savefig(OUT_TERRAIN_LEVEL, metadata=_PDF_METADATA, bbox_inches="tight")
    draw_by_flat_level(loaded).savefig(OUT_FLAT_LEVEL, metadata=_PDF_METADATA, bbox_inches="tight")
    print(f"wrote {OUT_DISCIPLINE.name}, {OUT_TERRAIN.name}, {OUT_LEVEL.name}, "
          f"{OUT_TERRAIN_LEVEL.name}, {OUT_FLAT_LEVEL.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
