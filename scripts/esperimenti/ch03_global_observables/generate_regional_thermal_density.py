#!/usr/bin/env python3
r"""Horizontal density of climb-phase (thermal) points inside each named regional box.

The interactive viewer's "Thermal density" view
(:mod:`soaring.viewer.widgets.thermal_plane`) pools every prepared 10 m height plane
into one map, for each of its four hand-picked 5x5 km cells. This script is the same
idea -- overlay many height planes into one density map, coloured by how many
climb-phase points land in each patch -- at the scale of
:data:`soaring.analysis.regions.REGIONAL_BOXES` (Alps, Pyrenees, Channel Coast,
Champagne-Lorraine) plus the Massif Central box from
``scripts/condivisi/generate_prelim_figure.py``'s ``OROGRAPHY``, instead of a single
cell.

The two are deliberately not built the same way underneath. A region spans hundreds of
kilometres, far more than the four viewer cells combined, so re-running the viewer's
per-cell pipeline (which decodes climb geometry from scratch for every flight that ever
visits one specific 5x5 km square) at this scale would mean decoding the whole archive
per region. Instead this reads each discipline's already-decoded, archive-wide
``segmentation/phase_points.parquet`` (the HMM "own" output only -- Vilpellet's
fix-level segmentation lives in a separate directory and is not pooled here),
restricted to flights that launch inside a region's box (the same population
:func:`soaring.analysis.regions.region_box_masks` selects for every other regional
analysis), and bins the lon/lat of their climb-phase fixes, all heights pooled
together since a region has no single ground reference the way one small cell does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.analysis.preproc.enu import LocalFrame  # noqa: E402
from soaring.analysis.regions import REGIONAL_BOXES  # noqa: E402
from soaring.reporting import DISCIPLINES  # noqa: E402
from soaring.viewer.geodesy import enu_to_geodetic  # noqa: E402
from soaring.viewer.geography import draw_density, draw_land, load_basemap  # noqa: E402

OUT = ROOT / "thesis" / "generated" / "regional_thermal_density.pdf"

# Same bound as OROGRAPHY["Massif Central"] in generate_prelim_figure.py. REGIONAL_BOXES
# omits it (conditional_transport.py's stratification never uses it), but
# generate_prelim_figure.py's MAP_REGIONS always draws it alongside the other four, and
# that five-region set is what this script reproduces as density maps.
MASSIF_CENTRAL = (1.8, 4.6, 43.6, 46.2)
REGIONS = {**REGIONAL_BOXES, "Massif Central": MASSIF_CENTRAL}

# Finer than the 0.15 deg national take-off mesh (generate_prelim_figure.py): a region
# is a small fraction of France.
CELL_DEG = 0.03
# Margin drawn around each box so a thermal just outside the launch box is not clipped.
PAD_DEG = 0.3


def _region_flight_ids(meta: pd.DataFrame, box: tuple[float, float, float, float]):
    """Flights launching inside ``box`` -- the same population as region_box_masks."""
    west, east, south, north = box
    inside = meta.lon0.between(west, east) & meta.lat0.between(south, north)
    return set(meta.loc[inside.fillna(False), "flight_id"])


def _climb_points(discipline, flight_ids: set[str]) -> pd.DataFrame:
    """Lon/lat of every climb-phase fix belonging to ``flight_ids``, one discipline."""
    derived = discipline.config().derived_dir
    points_path = derived / "segmentation" / "phase_points.parquet"
    columns = ["flight_id", "lon", "lat"]
    if not flight_ids or not points_path.is_file():
        return pd.DataFrame(columns=columns)
    points = pd.read_parquet(
        points_path,
        columns=["flight_id", "E", "N", "z", "phase"],
        filters=[("flight_id", "in", list(flight_ids))],
    )
    points = points.loc[points.phase == "climb"].copy()
    if points.empty:
        return pd.DataFrame(columns=columns)
    points["flight_id"] = points.flight_id.astype(str)
    meta = pd.read_parquet(
        derived / "flights_meta.parquet", columns=["flight_id", "lat0", "lon0", "alt0"]
    )
    meta["flight_id"] = meta.flight_id.astype(str)
    meta = meta.drop_duplicates("flight_id", keep="last").set_index("flight_id")
    frames = []
    for flight_id, group in points.groupby("flight_id", sort=False):
        if flight_id not in meta.index:
            continue
        lat0, lon0, alt0 = meta.loc[flight_id, ["lat0", "lon0", "alt0"]]
        frame = LocalFrame(lat0, lon0, alt0)
        lat, lon = enu_to_geodetic(
            group.E.to_numpy(), group.N.to_numpy(), group.z.to_numpy(), frame
        )
        frames.append(pd.DataFrame({"flight_id": flight_id, "lon": lon, "lat": lat}))
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    """Write one density panel per region to :data:`OUT`."""
    disciplines = [d for d in DISCIPLINES.values() if d.derived_dir() is not None]
    if not disciplines:
        raise FileNotFoundError("Connect the archive SSD to read fixes.parquet")
    metas = []
    for disc in disciplines:
        meta = pd.read_parquet(
            disc.config().derived_dir / "flights_meta.parquet",
            columns=["flight_id", "lat0", "lon0"],
        )
        meta["flight_id"] = meta.flight_id.astype(str)
        metas.append((disc, meta))

    basemap = load_basemap()
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    axes = axes.ravel()
    for ax, (name, box) in zip(axes, REGIONS.items(), strict=False):
        west, east, south, north = box
        frames = [
            _climb_points(disc, _region_flight_ids(meta, box)) for disc, meta in metas
        ]
        points = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        extent = (west - PAD_DEG, south - PAD_DEG, east + PAD_DEG, north + PAD_DEG)
        if basemap:
            draw_land(ax, basemap["france"]["rings"], extent)
        else:
            ax.set_xlim(extent[0], extent[2])
            ax.set_ylim(extent[1], extent[3])
        mesh = None
        if not points.empty:
            mesh = draw_density(
                ax, points.lon.to_numpy(), points.lat.to_numpy(), extent, cell=CELL_DEG
            )
        if mesh is not None:
            fig.colorbar(mesh, ax=ax, shrink=0.85, label="Climb-phase fixes per cell")
        ax.add_patch(
            Rectangle(
                (west, south),
                east - west,
                north - south,
                fill=False,
                edgecolor="black",
                linewidth=1.2,
                zorder=5,
            )
        )
        ax.set_title(f"{name} · {len(points):,} points", fontsize=10)
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
    for ax in axes[len(REGIONS) :]:
        ax.axis("off")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
