#!/usr/bin/env python3
r"""Map first-fix altitude using four descriptive elevation bands.

The labels and thresholds follow Hernandez-Aguayo, Cristelli \& Benzaquen
(arXiv:2608.00241, Eq.~1). These four bands do not reproduce the full mountain
classification of Kapos et al. (2000), which also uses terrain characteristics.

Here the altitude comes from the raw IGC file's first valid B record: GNSS if
available, otherwise barometric. It is a rough geographical proxy, with unknown
datum and possible measurement error; it is neither a terrain model nor a
verified launch altitude. The barometric fallback is specific to this exploratory
map and does not change the cleaned trajectory's altitude source.

Writes ``thesis/generated/terrain_map.pdf`` and ``thesis/generated/terrain.tex``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.acquisition.ffvl.naming import igc_filename  # noqa: E402
from soaring.analysis.igc import first_fix  # noqa: E402
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)
from soaring.viewer.geography import (  # noqa: E402
    FRANCE_EXTENT,
    draw_land,
    load_basemap,
)

OUT_MAP = ROOT / "thesis" / "generated" / "terrain_map.pdf"
OUT_TEX = ROOT / "thesis" / "generated" / "terrain.tex"

CELL_DEG = 0.15
TOP_N_PER_CLASS = 10

# Descriptive elevation bands from arXiv:2608.00241 Eq. 1. Their terrain-altitude
# source differs from the raw first-fix proxy used here (see module docstring).
TERRAIN_BANDS = [
    ("Plains", -np.inf, 300.0),
    ("Hills", 300.0, 800.0),
    ("Low mountains", 800.0, 1500.0),
    ("High mountains", 1500.0, np.inf),
]
TERRAIN_ORDER = [name for name, _, _ in TERRAIN_BANDS]
TERRAIN_COLORS = {
    "Plains": "#3a7d34",
    "Hills": "#a6c93a",
    "Low mountains": "#d99a3d",
    "High mountains": "#8c2f2f",
}

_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def classify(alt: np.ndarray) -> np.ndarray:
    """Assign finite altitude to a descriptive band; otherwise return an empty label."""
    labels = np.full(alt.shape, "", dtype=object)
    finite = np.isfinite(alt)
    for name, lo, hi in TERRAIN_BANDS:
        labels[finite & (alt >= lo) & (alt < hi)] = name
    return labels


def _flight_paths(glider) -> pd.DataFrame | None:
    """``flight_id``, season and raw ``.igc`` path for the retained ensemble."""
    derived = glider.derived_dir("flights_meta.parquet")
    catalog_path = glider.catalog_path()
    if derived is None or catalog_path is None or not Path(catalog_path).is_file():
        return None
    meta = pd.read_parquet(derived / "flights_meta.parquet")
    meta = meta[meta.drop_reason.isna()][["flight_id"]].copy()
    meta["flight_id"] = meta["flight_id"].astype(str)

    catalog = pd.read_csv(
        catalog_path, low_memory=False, usecols=["flight_id", "season", "date"]
    )
    catalog["flight_id"] = catalog["flight_id"].astype(str)
    frame = meta.merge(catalog, on="flight_id", how="left")

    igc_dir = glider.config().igc_dir
    frame["path"] = [
        None
        if pd.isna(season) or pd.isna(date)
        else igc_dir / str(season) / igc_filename(date, flight_id)
        for season, date, flight_id in zip(
            frame["season"], frame["date"], frame["flight_id"], strict=True
        )
    ]
    return frame


def load_terrain(glider) -> pd.DataFrame | None:
    """Raw first-fix position, altitude, channel and terrain class.

    One row per *retained* flight (matching Sec.~\\ref{sec:prelim}'s ensemble), whether
    or not its raw file yielded a usable first altitude: an unreadable/unusable one keeps
    its row with ``terrain == ""`` rather than being dropped, so the classified count can
    always be read as a share of the retained one.

    A first fix's altitude is accepted only inside the same receiver-plausibility band
    fix-level cleaning already uses (``configs/preprocessing.yaml``, ``min_altitude_m``/
    ``max_altitude_m``) -- this is not the pipeline's cleaning (a raw first fix can still
    be a genuine outlier the band lets through), only the same minimal "not a corrupt GPS
    read" gate, applied to a fix cleaning never otherwise sees.
    """
    frame = _flight_paths(glider)
    if frame is None:
        return None

    from soaring.analysis.config import load_preproc_config

    alt_lo = load_preproc_config().fix.min_altitude_m
    alt_hi = load_preproc_config().fix.max_altitude_m

    n = len(frame)
    lats = np.full(n, np.nan)
    lons = np.full(n, np.nan)
    alts = np.full(n, np.nan)
    channel = np.full(n, "", dtype=object)
    for i, path in enumerate(frame["path"].to_numpy()):
        if path is None or not path.is_file():
            continue
        fix = first_fix(path)
        if fix is None:
            continue
        gnss, baro = fix["gnss_alt"], fix["baro_alt"]
        if np.isfinite(gnss) and gnss != 0.0 and alt_lo <= gnss <= alt_hi:
            alts[i], channel[i] = gnss, "gnss"
        elif np.isfinite(baro) and baro != 0.0 and alt_lo <= baro <= alt_hi:
            alts[i], channel[i] = baro, "baro"
        else:
            continue  # neither channel usable: absent, zero, or outside the plausible band
        lats[i], lons[i] = fix["lat"], fix["lon"]

    frame = frame.assign(lat=lats, lon=lons, alt=alts, channel=channel)
    frame["terrain"] = classify(frame["alt"].to_numpy())
    return frame


def _cell_table(
    frame: pd.DataFrame, extent: tuple[float, float, float, float]
) -> pd.DataFrame:
    """One row per occupied grid cell: its centre, flight count and majority terrain."""
    classified = frame.terrain != ""
    inside = frame.lon.between(extent[0], extent[2]) & frame.lat.between(
        extent[1], extent[3]
    )
    sub = frame.loc[classified & inside].copy()
    sub["lon_bin"] = (
        np.floor((sub.lon - extent[0]) / CELL_DEG) * CELL_DEG + extent[0] + CELL_DEG / 2
    )
    sub["lat_bin"] = (
        np.floor((sub.lat - extent[1]) / CELL_DEG) * CELL_DEG + extent[1] + CELL_DEG / 2
    )
    grouped = sub.groupby(["lon_bin", "lat_bin"])
    cells = grouped.size().rename("n").reset_index()
    majority = grouped["terrain"].agg(lambda s: s.value_counts().idxmax())
    cells = cells.merge(majority.rename("terrain"), on=["lon_bin", "lat_bin"])
    return cells


def draw_terrain_map(loaded: dict) -> object:
    """France, one marker per occupied cell, coloured by majority terrain and sized by
    log flight count; the ten busiest cells of each class are marked with a cross."""
    import matplotlib.pyplot as plt

    frame = pd.concat([d for d in loaded.values() if d is not None], ignore_index=True)
    cells = _cell_table(frame, FRANCE_EXTENT)

    fig, ax = plt.subplots(figsize=(6.1, 6.1))
    panels = load_basemap()
    if panels:
        draw_land(ax, panels["france"]["rings"], FRANCE_EXTENT)

    size = 6.0 + 22.0 * np.log10(cells["n"] + 1.0)
    for name in TERRAIN_ORDER:
        sub = cells[cells.terrain == name]
        ax.scatter(
            sub.lon_bin,
            sub.lat_bin,
            s=size[sub.index],
            c=TERRAIN_COLORS[name],
            marker="s",
            linewidths=0,
            alpha=0.85,
            zorder=2,
            label=name,
        )

    top_cells = []
    for name in TERRAIN_ORDER:
        sub = cells[cells.terrain == name].nlargest(TOP_N_PER_CLASS, "n")
        top_cells.append(sub)
    top = pd.concat(top_cells) if top_cells else cells.iloc[0:0]
    ax.scatter(
        top.lon_bin,
        top.lat_bin,
        s=90,
        facecolors="none",
        edgecolors="0.15",
        marker="X",
        linewidths=1.4,
        zorder=3,
        label=f"Top-{TOP_N_PER_CLASS} cells",
    )

    ax.set_xlim(FRANCE_EXTENT[0], FRANCE_EXTENT[2])
    ax.set_ylim(FRANCE_EXTENT[1], FRANCE_EXTENT[3])
    ax.set_aspect(1 / np.cos(np.deg2rad(0.5 * (FRANCE_EXTENT[1] + FRANCE_EXTENT[3]))))
    ax.set_xlabel("longitude (deg)")
    ax.set_ylabel("latitude (deg)")
    ax.legend(frameon=True, fontsize=9, loc="upper left")
    fig.tight_layout()
    return fig


def macros(loaded: dict) -> dict[str, str]:
    """The ``\\StatTerrain*`` family: counts, shares and channel use of Sec.~\\ref
    {sec:prelim}'s terrain figure."""
    out: dict[str, str] = {}
    for discipline, frame in loaded.items():
        if frame is None:
            continue
        tag = DISCIPLINES[discipline].tag

        def put(name, value, tag=tag):
            out[f"StatTerrain{tag}{name}"] = value

        retained = len(frame)
        classified = frame[frame.terrain != ""]
        put("Retained", f"{retained}")
        put("Classified", f"{len(classified)}")
        put(
            "ClassifiedPct",
            f"{100 * len(classified) / retained:.1f}" if retained else "0.0",
        )
        # Shares are of the *classified* flights, so the four bands sum to 100%; a flight
        # with no usable raw altitude carries no terrain opinion to average in.
        shares = classified["terrain"].value_counts(normalize=True)
        for name in TERRAIN_ORDER:
            key = "".join(name.split())
            put(f"{key}Pct", f"{100 * shares.get(name, 0.0):.1f}")
        channel_shares = classified["channel"].value_counts(normalize=True)
        put("GnssPct", f"{100 * channel_shares.get('gnss', 0.0):.1f}")
        put("BaroPct", f"{100 * channel_shares.get('baro', 0.0):.1f}")
    out["StatTerrainTopN"] = str(TOP_N_PER_CLASS)
    out["StatTerrainCellDeg"] = f"{CELL_DEG:.2f}"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    from soaring.reporting.style import paper_style

    paper_style()

    loaded = {}
    missing = []
    for discipline in DISCIPLINES:
        frame = load_terrain(DISCIPLINES[discipline])
        if frame is None:
            missing.append(discipline)
        else:
            loaded[discipline] = frame
    if not loaded:
        print("no raw archive reachable; terrain figure not written")
        return 1
    refusal = partial_write_refusal(
        missing,
        "the terrain figure",
        allow_partial=args.allow_partial,
        reasons=[
            unreachable_reason(DISCIPLINES[d], "flights_meta.parquet") for d in missing
        ],
    )
    if refusal:
        print(refusal)
        return 1

    draw_terrain_map(loaded).savefig(
        OUT_MAP, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    values = macros(loaded)
    write_macros(
        OUT_TEX,
        values,
        generator="scripts/reporting/ch2_dataset/generate_terrain_figure.py",
    )
    print(f"wrote {OUT_MAP.name}, {OUT_TEX.name} ({len(values)} macros)")
    for k, v in values.items():
        print(f"  {k:32s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
