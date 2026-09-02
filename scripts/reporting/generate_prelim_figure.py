#!/usr/bin/env python3
r"""The preliminary characterization of Sec.~\ref{sec:prelim}: four figures and its macros.

Everything here is a statement about the ensemble the pipeline *retains*, which is what
separates it from the diagnostics of Chapter 2: ``fig:gaps`` and ``fig:sampling`` were
computed on every parsed flight, as a filtering diagnostic, and the analysis needs the
same quantities on the flights actually used.

Four figures:

``prelim_map.pdf``
    Where it launches, on real coastlines and borders: metropolitan France, La Reunion,
    and a world frame for everything else. The geometry is ``data/basemap.json``, built
    once by ``build_basemap.py`` and committed, so this needs no network and no
    geospatial stack.
``prelim_ensemble.pdf``
    What its records look like. Airborne duration, flown path and native sampling
    interval, per discipline.
``prelim_isotropy.pdf``
    Whether the 1-D marginal may replace the 2-D propagator: the per-component variance
    ratio, paragliders against hang gliders. Stays in Chapter 2 -- it is a property of the
    process, not of who is in the ensemble.
``strata_compat.pdf``
    Whether the ensemble may be pooled across wing class, orographic group and season, on
    the raw MSD. Read by Chapter 3 (Sec.~\ref{sec:strata-compat}), which is the chapter
    that needs the answer: the ensemble MSD here is what motivates the per-stratum
    $\alpha_2$ check of Table~\ref{tab:strata-alpha}.

All four read the per-flight positions ``audit_msd.py`` wrote -- one row per flight, one
column per lag -- so a stratified MSD is a row selection rather than another pass over
the 43 GB fix table. Writes ``thesis/generated/prelim.tex``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.analysis.stats.bootstrap import cluster_bootstrap, cluster_labels  # noqa: E402
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    canonical_wing_class,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)

OUT_MAP = ROOT / "thesis" / "generated" / "prelim_map.pdf"
OUT_ENSEMBLE = ROOT / "thesis" / "generated" / "prelim_ensemble.pdf"
OUT_ISOTROPY = ROOT / "thesis" / "generated" / "prelim_isotropy.pdf"
OUT_STRATA = ROOT / "thesis" / "generated" / "strata_compat.pdf"
OUT_TEX = ROOT / "thesis" / "generated" / "prelim.tex"
# Coastlines and borders, cropped and committed by build_basemap.py so that the
# figure regenerates offline and without a geospatial stack.
BASEMAP = ROOT / "data" / "basemap.json"

# Map cell, in degrees. Fine enough that a single busy site is one cell and coarse
# enough that the sparse lowlands do not dissolve into single-flight speckle.
CELL_DEG = 0.15

# La Reunion is 70 km across, so its panel needs a far finer cell than France.
CELL_ISLAND_DEG = 0.01

# Map colours: land, sea and coastline. Muted, so that the take-off density on top
# is what the eye reads.
LAND, SEA, COAST = "#efece6", "#dce7ef", "#9aa5ae"

# The three map frames, (lon_min, lat_min, lon_max, lat_max). They must match the
# panels build_basemap.py cropped the geometry to.
FRAMES = {
    "france": (-5.5, 41.0, 10.0, 51.5),
    "reunion": (55.15, -21.42, 55.92, -20.82),
    "world": (-180.0, -60.0, 180.0, 75.0),
}

# The lag range the transport analysis reads, so a stratum comparison is made where the
# exponent is read and not over lags nothing is quoted from.
FIT_MIN_S, FIT_MAX_S = 120.0, 13_021.0

# The isotropy band: resampling whole (take-off site, day) clusters rather than flights,
# the same unit measure_propagator.py resamples H at -- flights sharing a site and a day
# shared the same convective conditions and are not independent draws. Checked against
# flight-only and site-only alternatives: ICC(E(t)^2, day_site) runs 0.37-0.83 over the
# decade grid, comparable to or above the propagator's 0.57-0.63, and above the
# site-only level throughout.
ISO_BOOT_LEVEL = "day_site"
ISO_BOOT_RESAMPLES = 200
ISO_BOOT_SEED = 0

# A stratum below this contributes a curve too noisy to compare and is pooled into the
# residual group instead of being drawn as if it were a measurement.
MIN_STRATUM = 2_000

# Orographic groups, as longitude/latitude boxes rather than polygons traced from the
# basemap: a box that is written down can be checked against a gazetteer, and the test
# these strata support is whether the MSD curves separate, not where exactly the Alps end.
# FRANCE is the wider box used to label a take-off as domestic or abroad; it is deliberately
# looser than FRAMES["france"], which is what the map panel is drawn on.
FRANCE = {"lat": (41.0, 52.0), "lon": (-6.0, 10.0)}
OROGRAPHY = {
    "Alps": {"lon": (5.4, 10.0), "lat": (43.8, 46.6)},
    "Pyrenees": {"lon": (-1.9, 3.3), "lat": (42.0, 43.5)},
    "Massif Central": {"lon": (1.8, 4.6), "lat": (43.6, 46.2)},
}
# Where each box's label sits, and how it is anchored. The boxes overlap along their
# edges, so a label placed at a fixed corner of each collides with its neighbour.
_LABEL_ANCHOR = {
    "Alps": (9.85, 46.35, "right"),
    "Pyrenees": (-1.75, 42.15, "left"),
    "Massif Central": (1.95, 45.9, "left"),
}

_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def _within(lat, lon, extent):
    """Boolean mask of the points inside a ``(lon_min, lat_min, lon_max, lat_max)``."""
    return (
        (lon >= extent[0]) & (lon <= extent[2])
        & (lat >= extent[1]) & (lat <= extent[3])
    )


def orographic_group(lat: pd.Series, lon: pd.Series) -> np.ndarray:
    """Label each take-off by the orographic box it falls in."""
    inside = lat.between(*FRANCE["lat"]) & lon.between(*FRANCE["lon"])
    labels = np.full(len(lat), "lowland", dtype=object)
    for name, box in OROGRAPHY.items():
        hit = lon.between(*box["lon"]) & lat.between(*box["lat"])
        labels[hit.to_numpy()] = name
    labels[~inside.to_numpy()] = "abroad"
    return labels


def load(discipline: str, audit_dir: Path):
    """The retained ensemble, its per-lag positions and its stratum labels."""
    glider = DISCIPLINES[discipline]
    slug = glider.slug
    derived = glider.derived_dir("flights_meta.parquet")
    catalog_path = glider.catalog_path()
    positions = audit_dir / f"audit_positions_{slug}.npz"
    if derived is None or not positions.is_file():
        return None

    data = np.load(positions)
    flights = pd.read_parquet(audit_dir / f"audit_flights_{slug}.parquet")
    meta = pd.read_parquet(derived / "flights_meta.parquet")
    meta = meta[meta.drop_reason.isna()][["flight_id", "lat0", "lon0", "alt0"]]
    frame = flights.merge(meta, on="flight_id", how="left")

    if catalog_path is not None and Path(catalog_path).is_file():
        catalog = pd.read_csv(catalog_path, low_memory=False)
        catalog["flight_id"] = catalog["flight_id"].astype(str)
        frame = frame.merge(
            catalog[["flight_id", "wing_class", "season", "date", "takeoff"]],
            on="flight_id",
            how="left",
        )
        frame["wing_class"] = canonical_wing_class(discipline, frame["wing_class"])
    else:
        frame["wing_class"] = np.nan
        frame["season"] = np.nan
        frame["date"] = np.nan
        frame["takeoff"] = np.nan

    frame["group"] = orographic_group(frame.lat0, frame.lon0)
    assert len(frame) == data["E"].shape[0], "audit rows and flight rows disagree"
    return {
        "lags": data["lags"],
        "east": data["E"],
        "north": data["N"],
        "flights": frame,
    }


def stratified_msd(east, north, lags, mask):
    """``<|r(t)|^2>`` over the flights ``mask`` selects."""
    squared = east[mask] ** 2 + north[mask] ** 2
    with np.errstate(invalid="ignore"):
        return np.nanmean(squared, axis=0)


def iso_ratio_band(east, north, frame):
    """Median and 10-90% band of ``<E^2>/<N^2>`` over a (site, day) cluster bootstrap."""
    labels = cluster_labels(frame, ISO_BOOT_LEVEL)
    curves = np.stack([east**2, north**2], axis=-1)

    def ratio(mean_curve):
        with np.errstate(invalid="ignore"):
            return mean_curve[:, 0] / mean_curve[:, 1]

    with np.errstate(invalid="ignore"):
        _, replicates = cluster_bootstrap(
            curves, labels, ratio, n_resamples=ISO_BOOT_RESAMPLES, seed=ISO_BOOT_SEED
        )
        lo, med, hi = np.nanpercentile(replicates, [10, 50, 90], axis=0)
    return lo, med, hi


def _strata(frame: pd.DataFrame, column: str) -> list[tuple[str, np.ndarray]]:
    """The values of ``column`` with enough flights to carry a curve, largest first."""
    counts = frame[column].value_counts()
    keep = counts[counts >= MIN_STRATUM]
    return [(str(name), (frame[column] == name).to_numpy()) for name in keep.index]


def _basemap():
    """The committed coastline and border geometry, or ``None`` if it is missing."""
    if not BASEMAP.is_file():
        print(f"warning: {BASEMAP} is absent; run scripts/reporting/build_basemap.py")
        return None
    return json.loads(BASEMAP.read_text())["panels"]


def _draw_land(ax, rings, extent):
    """Fill the country polygons and stroke their outlines, then frame the panel.

    Rings are drawn whole and clipped by the axes limits, so a country that straddles the
    frame is cut by Matplotlib rather than by the geometry -- which is what lets the
    basemap be built without a geometry library (see build_basemap.py).
    """
    from matplotlib.collections import PolyCollection

    ax.add_collection(
        PolyCollection(
            [np.asarray(ring) for ring in rings],
            facecolors=LAND, edgecolors=COAST, linewidths=0.35, zorder=0,
        )
    )
    ax.set_facecolor(SEA)
    ax.set_xlim(extent[0], extent[2])
    ax.set_ylim(extent[1], extent[3])
    # A degree of longitude is cos(phi) of a degree of latitude, so this is what makes
    # the coastline the right shape rather than a stretched one.
    ax.set_aspect(1 / np.cos(np.deg2rad(0.5 * (extent[1] + extent[3]))))


def _density(ax, lon, lat, extent, cell, cmap="magma_r"):
    """Take-offs as a binned mesh on a log colour scale.

    A mesh and not one marker per flight: at 1.5e5 flights markers saturate over the Alps
    and the panel stops answering whether the ensemble samples the country or concentrates
    on a handful of sites. A mesh and not hexbin: hexbin's PolyCollection is rendered
    clipped to a corner of the axes by the PDF backend on Matplotlib 3.11, so the panel
    comes out of a PNG correct and out of the PDF nearly empty.
    """
    lon_edges = np.arange(extent[0], extent[2] + cell, cell)
    lat_edges = np.arange(extent[1], extent[3] + cell, cell)
    counts, _, _ = np.histogram2d(lon, lat, bins=(lon_edges, lat_edges))
    if counts.max() < 1:
        return None
    return ax.pcolormesh(
        lon_edges, lat_edges, np.ma.masked_less(counts.T, 1),
        cmap=cmap, norm=LogNorm(vmin=1, vmax=max(counts.max(), 2)), zorder=2,
    )


def draw_maps(loaded: dict) -> object:
    """Where the retained ensemble launches, on three geographic frames."""
    import matplotlib.pyplot as plt

    panels = _basemap()
    lat = pd.concat([d["flights"].lat0 for d in loaded.values()]).to_numpy()
    lon = pd.concat([d["flights"].lon0 for d in loaded.values()]).to_numpy()

    fig = plt.figure(figsize=(11.4, 7.6))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.35, 1.0], height_ratios=[1.0, 1.0],
                            hspace=0.28, wspace=0.22)
    france_ax = fig.add_subplot(grid[:, 0])
    reunion_ax = fig.add_subplot(grid[0, 1])
    world_ax = fig.add_subplot(grid[1, 1])

    # (a) Metropolitan France, where all but a twentieth of the ensemble launches.
    extent = FRAMES["france"]
    if panels:
        _draw_land(france_ax, panels["france"]["rings"], extent)
    inside = _within(lat, lon, extent)
    mesh = _density(france_ax, lon[inside], lat[inside], extent, CELL_DEG)
    if mesh is not None:
        fig.colorbar(mesh, ax=france_ax, label="flights per cell", shrink=0.75)
    for name, box in OROGRAPHY.items():
        france_ax.add_patch(
            plt.Rectangle(
                (box["lon"][0], box["lat"][0]),
                box["lon"][1] - box["lon"][0], box["lat"][1] - box["lat"][0],
                fill=False, edgecolor="#1b6b4f", lw=1.1, ls="--", zorder=3,
            )
        )
        x, y, align = _LABEL_ANCHOR[name]
        france_ax.text(x, y, name, color="#12513b", fontsize=8, ha=align, zorder=4)
    france_ax.set_title(
        f"(a) metropolitan France \u2014 {100 * inside.mean():.1f}% of the ensemble",
        fontsize=10, loc="left",
    )

    # (b) La Reunion, the one overseas department with a substantial share. The island is
    # 70 km across, so the cell is fifteen times finer than the French one.
    extent = FRAMES["reunion"]
    if panels:
        _draw_land(reunion_ax, panels["reunion"]["rings"], extent)
    on_island = _within(lat, lon, extent)
    _density(reunion_ax, lon[on_island], lat[on_island], extent, CELL_ISLAND_DEG)
    reunion_ax.set_title(
        f"(b) La R\u00e9union \u2014 {on_island.sum():,} flights",
        fontsize=10, loc="left",
    )

    # (c) Everything else. Individual sites rather than a density: the counts per site are
    # small and the point of the panel is where they are, not how many.
    extent = FRAMES["world"]
    if panels:
        _draw_land(world_ax, panels["world"]["rings"], extent)
    elsewhere = ~(_within(lat, lon, FRAMES["france"]) | _within(lat, lon, FRAMES["reunion"]))
    cells = pd.DataFrame(
        {"lon": np.round(lon[elsewhere] / 0.5) * 0.5, "lat": np.round(lat[elsewhere] / 0.5) * 0.5}
    ).value_counts().reset_index(name="n")
    world_ax.scatter(
        cells.lon, cells.lat, s=3 + 14 * np.log10(cells.n + 1), c="#b5482a",
        alpha=0.75, linewidths=0, zorder=2,
    )
    world_ax.set_title(
        f"(c) elsewhere \u2014 {int(elsewhere.sum()):,} flights",
        fontsize=10, loc="left",
    )

    for ax in (france_ax, reunion_ax, world_ax):
        ax.set_xlabel("longitude (deg)")
        ax.set_ylabel("latitude (deg)")
        ax.tick_params(labelsize=8)
    return fig


def draw_ensemble(loaded: dict) -> object:
    """What the retained records look like: duration, path and cadence."""
    import matplotlib.pyplot as plt

    fig, (dur_ax, path_ax, dt_ax) = plt.subplots(1, 3, figsize=(11.4, 3.5))

    for discipline, data in loaded.items():
        frame, color = data["flights"], DISCIPLINES[discipline].color
        dur_ax.hist(frame.duration_s / 3600, bins=np.linspace(0, 10, 80),
                    histtype="step", density=True, color=color, label=discipline)
        path_ax.hist(frame.path_m / 1000, bins=np.linspace(0, 300, 80),
                     histtype="step", density=True, color=color, label=discipline)
        steps = frame.native_dt_s.value_counts(normalize=True).sort_index()
        steps = steps[steps.index <= 12]
        dt_ax.bar(steps.index + (0.18 if discipline.startswith("hang") else -0.18),
                  steps.to_numpy(), width=0.36, color=color, label=discipline)

    dur_ax.set_xlabel("airborne duration (h)")
    dur_ax.set_title("(a) airborne duration", fontsize=10, loc="left")
    path_ax.set_xlabel("flown path (km)")
    path_ax.set_title("(b) flown path", fontsize=10, loc="left")
    dt_ax.set_xlabel(r"native sampling interval $\Delta t$ (s)")
    dt_ax.set_title("(c) native sampling interval", fontsize=10, loc="left")
    for ax in (dur_ax, path_ax, dt_ax):
        ax.set_ylabel("density" if ax is not dt_ax else "share of flights")
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def draw_isotropy(loaded: dict) -> object:
    """Whether the 1-D marginal may replace the 2-D propagator: the variance ratio alone."""
    import matplotlib.pyplot as plt

    fig, iso_ax = plt.subplots(1, 1, figsize=(5.5, 4.2))

    # Inset: the same bands zoomed to 1e0-1e4 s. Past 1e4 s coverage falls off (few
    # flights last that long) and the bootstrap band widens enough to swamp the y-scale,
    # hiding whether the band ever holds unity over a zone rather than at a point in the
    # decades that are actually well covered.
    # Placement may need adjusting once run against the real (unversioned) dataset.
    inset_ax = iso_ax.inset_axes([0.42, 0.55, 0.53, 0.4])

    for discipline, data in loaded.items():
        lags, east, north = data["lags"], data["east"], data["north"]
        lo, med, hi = iso_ratio_band(east, north, data["flights"])
        drawable = np.isfinite(med) & (lags >= 1.0)
        color = DISCIPLINES[discipline].color
        iso_ax.fill_between(lags[drawable], lo[drawable], hi[drawable],
                             color=color, alpha=0.25, lw=0)
        iso_ax.semilogx(lags[drawable], med[drawable], color=color, label=discipline)

        zoom = drawable & (lags <= 1e4)
        inset_ax.fill_between(lags[zoom], lo[zoom], hi[zoom], color=color, alpha=0.25, lw=0)
        inset_ax.semilogx(lags[zoom], med[zoom], color=color)

    iso_ax.axhline(1.0, color="0.3", lw=0.8, ls="--")
    iso_ax.set_xlabel("elapsed time $t$ (s)")
    iso_ax.set_ylabel(r"$\langle E^2\rangle\,/\,\langle N^2\rangle$")
    iso_ax.legend(frameon=False, fontsize=9)

    inset_ax.axhline(1.0, color="0.3", lw=0.8, ls="--")
    inset_ax.set_xlim(1.0, 1e4)
    inset_ax.set_xticks([1e0, 1e2, 1e4])
    inset_ax.tick_params(labelsize=7)
    iso_ax.indicate_inset_zoom(inset_ax, edgecolor="0.4")

    fig.tight_layout()
    return fig


def draw_strata(loaded: dict) -> object:
    """Whether the retained ensemble may be pooled: the ensemble MSD, stratified three ways."""
    import matplotlib.pyplot as plt

    fig, (class_ax, group_ax, season_ax) = plt.subplots(1, 3, figsize=(11.4, 4.0))

    # Paragliders only: the hang-glider archive is 4% of the size and a stratum of it
    # would be a curve about a few hundred flights.
    data = loaded.get("paragliders")
    panels = [
        (class_ax, "wing_class", "(a) MSD by wing class"),
        (group_ax, "group", "(b) MSD by orographic group"),
        (season_ax, "season", "(c) MSD by season"),
    ]
    if data is not None:
        lags, east, north = data["lags"], data["east"], data["north"]
        pooled = stratified_msd(east, north, lags, np.ones(len(data["flights"]), bool))
        for ax, column, title in panels:
            strata = _strata(data["flights"], column)
            colormap = plt.get_cmap("viridis", max(len(strata), 2))
            for index, (name, mask) in enumerate(strata):
                curve = stratified_msd(east, north, lags, mask)
                with np.errstate(invalid="ignore", divide="ignore"):
                    ax.semilogx(lags, curve / pooled, color=colormap(index), lw=1.2,
                                label=f"{name} ({mask.sum():,})")
            ax.axhline(1.0, color="0.3", lw=0.8, ls="--")
            ax.set_xlabel("elapsed time $t$ (s)")
            ax.set_ylabel("MSD / pooled MSD")
            ax.set_ylim(0.0, 2.5)
            ax.set_title(title, fontsize=10, loc="left")
            ax.legend(frameon=False, fontsize=7, ncol=2)
    fig.tight_layout()
    return fig


def macros(loaded: dict) -> dict[str, str]:
    """The ``\\StatPrelim*`` family: every number Sec.~\\ref{sec:prelim} quotes."""
    from soaring.analysis.config import load_preproc_config

    # The duration and path below are the *retained record*: they are measured over the
    # segments that survived sec:uniform, not over the trimmed flight that sec:flightfilter
    # tested. A flight reduced to one short segment therefore lands under the flight-level
    # cuts even though it passed them, which is the left tail of fig:prelim-ensemble a/b.
    flight_cut = load_preproc_config().flight

    out: dict[str, str] = {}
    for discipline, data in loaded.items():
        tag = DISCIPLINES[discipline].tag
        frame, lags = data["flights"], data["lags"]
        east, north = data["east"], data["north"]

        def put(name, value, tag=tag):
            out[f"StatPrelim{tag}{name}"] = value

        below = (frame.duration_s < flight_cut.min_duration_s) | (
            frame.path_m / 1000 < flight_cut.min_path_km
        )
        put("BelowCutFlights", f"{int(below.sum())}")
        put("BelowCutPct", f"{100 * below.mean():.2f}")

        put("Flights", f"{len(frame)}")
        put("MedianDurH", f"{frame.duration_s.median() / 3600:.2f}")
        put("MedianPathKm", f"{frame.path_m.median() / 1000:.0f}")
        put("MedianFixes", f"{frame.n_fix.median():.0f}")
        put("MedianDtS", f"{frame.native_dt_s.median():.0f}")
        put("OneHertzPct", f"{100 * (frame.native_dt_s == 1).mean():.1f}")
        put("DurationIqrLowH", f"{frame.duration_s.quantile(0.25) / 3600:.2f}")
        put("DurationIqrHighH", f"{frame.duration_s.quantile(0.75) / 3600:.2f}")
        put("PathIqrLowKm", f"{frame.path_m.quantile(0.25) / 1000:.0f}")
        put("PathIqrHighKm", f"{frame.path_m.quantile(0.75) / 1000:.0f}")

        inside = frame.lat0.between(*FRANCE["lat"]) & frame.lon0.between(*FRANCE["lon"])
        put("AbroadPct", f"{100 * (~inside).mean():.1f}")
        # The three map frames of fig:prelim-map, counted the same way the panels are.
        latitudes, longitudes = frame.lat0.to_numpy(), frame.lon0.to_numpy()
        metropolitan = _within(latitudes, longitudes, FRAMES["france"])
        island = _within(latitudes, longitudes, FRAMES["reunion"])
        put("MetroFlights", f"{int(metropolitan.sum())}")
        put("MetroPct", f"{100 * metropolitan.mean():.1f}")
        put("ReunionFlights", f"{int(island.sum())}")
        put("ReunionPct", f"{100 * island.mean():.1f}")
        put("ElsewhereFlights", f"{int((~metropolitan & ~island).sum())}")
        put("ElsewherePct", f"{100 * (~metropolitan & ~island).mean():.1f}")
        groups = frame.group.value_counts(normalize=True)
        for name, key in (("Alps", "Alps"), ("Pyrenees", "Pyrenees"),
                          ("MassifCentral", "Massif Central"), ("Lowland", "lowland")):
            put(f"Group{name}Pct", f"{100 * groups.get(key, 0.0):.1f}")
        put("Sites", f"{frame.groupby([frame.lat0.round(2), frame.lon0.round(2)]).ngroups}")

        # Isotropy, over the lags the transport analysis reads.
        with np.errstate(invalid="ignore"):
            ratio = np.nanmean(east**2, 0) / np.nanmean(north**2, 0)
        window = (lags >= FIT_MIN_S) & (lags <= FIT_MAX_S) & np.isfinite(ratio)
        put("IsoRatioMin", f"{ratio[window].min():.2f}")
        put("IsoRatioMax", f"{ratio[window].max():.2f}")
        put("IsoRatioMedian", f"{np.median(ratio[window]):.2f}")

        # Stratum compatibility: the largest departure from the pooled curve, over the
        # same lags, as a ratio. Quoted rather than a p-value: at 1.5e5 flights every
        # difference is significant and only the size of it is informative.
        pooled = stratified_msd(east, north, lags, np.ones(len(frame), bool))
        for column, name in (("wing_class", "Class"), ("group", "Group"),
                             ("season", "Season")):
            strata = _strata(frame, column)
            if not strata:
                continue
            spread = []
            for _, mask in strata:
                curve = stratified_msd(east, north, lags, mask)
                with np.errstate(invalid="ignore", divide="ignore"):
                    relative = curve[window] / pooled[window]
                spread.append(np.nanmax(np.abs(relative - 1.0)))
            put(f"{name}Strata", f"{len(strata)}")
            put(f"{name}MaxDeparturePct", f"{100 * max(spread):.0f}")
            # The worst stratum is often the smallest one, so the maximum alone reads as
            # a statement about the noisiest curve. The median across strata is what
            # separates an axis along which the ensemble genuinely splits from one along
            # which a single small group wanders.
            put(f"{name}TypicalDeparturePct", f"{100 * float(np.median(spread)):.0f}")
    # Discipline-independent, so it carries no tag: the floor below which a stratum is
    # counted but not drawn. Quoted by the text and by two captions, which had it typed.
    out["StatPrelimMinStratum"] = str(MIN_STRATUM)
    out["StatPrelimIsoBootResamples"] = str(ISO_BOOT_RESAMPLES)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    import matplotlib
    matplotlib.use("Agg")

    loaded = {}
    missing = []
    for discipline in DISCIPLINES:
        data = load(discipline, args.audit_dir)
        if data is None:
            missing.append(discipline)
        else:
            loaded[discipline] = data
    if not loaded:
        print("no audit inputs reachable; prelim figures not written")
        return 1
    refusal = partial_write_refusal(
        missing, "the prelim figures", allow_partial=args.allow_partial,
        reasons=[
            unreachable_reason(DISCIPLINES[d], "flights_meta.parquet")
            for d in missing
        ],
    )
    if refusal:
        print(refusal)
        return 1

    draw_maps(loaded).savefig(OUT_MAP, metadata=_PDF_METADATA, bbox_inches="tight")
    draw_ensemble(loaded).savefig(OUT_ENSEMBLE, metadata=_PDF_METADATA)
    draw_isotropy(loaded).savefig(OUT_ISOTROPY, metadata=_PDF_METADATA)
    draw_strata(loaded).savefig(OUT_STRATA, metadata=_PDF_METADATA)
    values = macros(loaded)
    write_macros(
        OUT_TEX, values, generator="scripts/reporting/generate_prelim_figure.py"
    )
    print(f"wrote {OUT_MAP.name}, {OUT_ENSEMBLE.name}, {OUT_ISOTROPY.name}, "
          f"{OUT_STRATA.name}, {OUT_TEX.name} ({len(values)} macros)")
    for k, v in values.items():
        print(f"  {k:44s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
