"""Map the twelve Thermal-planes windows on France, coloured by terrain band.

Cells come from configs/satellite.yaml (frozen from the viewer store); coastlines
and borders from the committed data/basemap.json, so this runs offline.

Run from the repository root:
    uv run python presentations/satellite-clouds/render_cells_map.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402
from pyproj import Transformer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from soaring.acquisition.satellite.config import load_config  # noqa: E402

OUT = Path(__file__).resolve().parent / "assets" / "cells-map.pdf"
LAND, SEA, COAST, INK = "#efece6", "#dce7ef", "#9aa5ae", "#13233A"
# Ordered bands, light green to dark brown: lightness alone tells them apart.
BANDS = {
    "Plains": ("#6BA34A", "2.1-2.3 km"),
    "Hills": ("#D4A72C", "2.4 km"),
    "Low mountains": ("#B5652B", "3.1-3.7 km"),
    "High mountains": ("#5E3A2E", "3.7-3.9 km"),
}
FRANCE = (-5.2, 41.3, 9.8, 51.2)
ALPS = (5.45, 45.0, 6.5, 46.05)
# Reference towns for the inset (approximate centres).
TOWNS = {"Grenoble": (5.72, 45.19), "Chambéry": (5.92, 45.57), "Annecy": (6.13, 45.90)}
TO_LONLAT = Transformer.from_crs(2154, 4326, always_xy=True)


def draw_land(ax, extent):
    """Country polygons, sea background and a shape-preserving aspect."""
    rings = json.loads((ROOT / "data" / "basemap.json").read_text())["panels"]["france"]["rings"]
    ax.add_collection(PolyCollection([np.asarray(r) for r in rings], facecolors=LAND,
                                     edgecolors=COAST, linewidths=0.5, zorder=0))
    ax.set_facecolor(SEA)
    ax.set_xlim(extent[0], extent[2])
    ax.set_ylim(extent[1], extent[3])
    ax.set_aspect(1 / np.cos(np.deg2rad(0.5 * (extent[1] + extent[3]))))
    ax.set_xticks([])
    ax.set_yticks([])


def window(cfg, cell):
    """Lon/lat corners of the 10 x 10 km window centred on the cell."""
    cx, cy = cfg.centre(cell)
    h = cfg.window.half_size_m
    xs = [cx - h, cx + h, cx + h, cx - h]
    ys = [cy - h, cy - h, cy + h, cy + h]
    return np.column_stack(TO_LONLAT.transform(xs, ys))


def main() -> None:
    """Draw France with one marker per cell and an Alps inset with true-size windows."""
    cfg = load_config()
    fig = plt.figure(figsize=(8.6, 4.0))
    ax = fig.add_axes((0.0, 0.02, 0.42, 0.9))
    zoom = fig.add_axes((0.42, 0.02, 0.28, 0.86))
    draw_land(ax, FRANCE)
    draw_land(zoom, ALPS)
    for cell in cfg.cells:
        colour = BANDS[cell.terrain][0]
        corners = window(cfg, cell)
        lon, lat = corners.mean(axis=0)
        ax.plot(lon, lat, "s", ms=7, color=colour, mec="white", mew=0.8, zorder=3)
        zoom.add_patch(Polygon(corners, closed=True, fc=colour, ec="white", lw=1.0,
                               alpha=0.9, zorder=3))
    ax.add_patch(Rectangle(ALPS[:2], ALPS[2] - ALPS[0], ALPS[3] - ALPS[1], fill=False,
                           ec=INK, lw=0.9, zorder=4))
    for text, lon, lat, ha in (("Normandy, 4 cells", -0.45, 49.5, "center"),
                               ("North-east, 1 cell", 5.0, 50.1, "center"),
                               ("South-west, 1 cell", 1.4, 45.0, "center"),
                               ("Pyrenees, 1 cell", 0.9, 42.45, "center"),
                               ("Alps, 5 cells", 6.0, 46.75, "center")):
        ax.text(lon, lat, text, ha=ha, va="center", fontsize=12, color=INK)
    for name, (lon, lat) in TOWNS.items():
        zoom.plot(lon, lat, "o", ms=3, color="#5B6572", zorder=2)
        left = name in ("Annecy", "Grenoble")  # their cells sit just east of the town
        zoom.text(lon + (-0.05 if left else 0.04), lat - 0.06, name, fontsize=10,
                  color="#5B6572", ha="right" if left else "left", zorder=2)
    zoom.set_title("Alps: windows at true size", fontsize=12, color=INK)
    handles = [plt.Line2D([], [], marker="s", ls="", ms=11, color=c) for c, _ in BANDS.values()]
    labels = [f"{band}\nclimbs to {top}" for band, (_, top) in BANDS.items()]
    fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.72, 0.5), frameon=False,
               fontsize=12, labelspacing=1.3, title="Terrain band", title_fontsize=13,
               alignment="left")
    fig.savefig(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
