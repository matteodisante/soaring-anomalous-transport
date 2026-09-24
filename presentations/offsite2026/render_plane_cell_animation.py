"""Render four altitude-sweep GIFs and the PNG frames embedded in Beamer.

No SSD or network is needed after measure_plane_cell_animation.py has saved the
crossing arrays. Terrain, bounds and colours match render_plane_cells.py.
"""

from __future__ import annotations

import io
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from PIL import Image
from scipy.ndimage import gaussian_filter

from render_plane_cells import ABOVE, RISING, hillshade

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets/plane-cells"
FRAMES = OUT / "animation-frames"
WIDTH_IN = 34 / 25.4
HEIGHT_IN = 41 / 25.4


def render_frame(slug, region, xy, height, dem, index):
    west, south, east, north = region["bounds_epsg2154"]
    km = (east - west) / 1000
    fig = plt.figure(figsize=(WIDTH_IN, HEIGHT_IN), dpi=320, facecolor="white")
    ax = fig.add_axes((0, 7 / 41, 1, 34 / 41))
    ax.set(xlim=(0, km), ylim=(0, km), aspect="equal")
    ax.imshow(hillshade(gaussian_filter(dem, 1.5)), cmap="gray", vmin=-.35, vmax=1.05,
              extent=(0, km, 0, km), origin="upper", interpolation="bilinear")
    plane_altitude = region["mean_terrain_m"] + height
    above = np.ma.masked_where(dem <= plane_altitude, np.ones_like(dem))
    ax.imshow(above, cmap=ListedColormap([ABOVE]), alpha=.5,
              extent=(0, km, 0, km), origin="upper", interpolation="nearest")
    ax.scatter((xy[:, 0] - west) / 1000, (xy[:, 1] - south) / 1000,
               s=1.7, color=RISING, alpha=.35, edgecolors="none", linewidths=0,
               rasterized=True, zorder=3)
    bar, margin = 5 if km >= 20 else 2, .06 * km
    ax.plot([km - margin - bar, km - margin], [.05 * km] * 2,
            color="black", lw=1.2, solid_capstyle="butt", zorder=4)
    ax.text(km - margin - bar / 2, .07 * km, f"{bar} km", ha="center", va="bottom",
            fontsize=5.5, bbox={"facecolor": "white", "alpha": .8,
                                 "edgecolor": "none", "pad": .6}, zorder=4)
    ax.set_axis_off()
    fig.text(.5, .106, f"H = {height:,} m", ha="center", va="center",
             fontsize=8.5, color="#4A6079", fontweight="bold")
    fig.text(.5, .044, f"{len(xy):,} climb crossings", ha="center", va="center",
             fontsize=6.8, color="#666666")
    path = FRAMES / f"{slug}-{index:02d}.png"
    fig.savefig(path, dpi=320)
    plt.close(fig)
    return path


def main():
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Palatino", "DejaVu Serif"]})
    report_path = OUT / "plane-cells-report.json"
    report = json.loads(report_path.read_text())
    animation = json.loads((OUT / "plane-cell-animation-report.json").read_text())
    if hashlib.sha256(report_path.read_bytes()).hexdigest() != animation["source_report_sha256"]:
        raise ValueError("The plane-cell report changed; remeasure the altitude sweep.")
    heights = animation["height_above_mean_terrain_m"]
    FRAMES.mkdir(exist_ok=True)
    for slug, region in report["regions"].items():
        with Image.open(io.BytesIO((OUT / region["dem"]["file"]).read_bytes())) as im:
            dem = np.asarray(im, dtype=float)
        sequence = []
        with np.load(OUT / animation["regions"][slug]["array_file"]) as arrays:
            for index, height in enumerate(heights):
                path = render_frame(slug, animation["regions"][slug],
                                    arrays[f"h{height}"], height, dem, index)
                with Image.open(path) as im:
                    sequence.append(im.convert("RGB"))
        sequence[0].save(OUT / f"{slug}-height.gif", save_all=True,
                         append_images=sequence[1:], duration=[500] * (len(sequence) - 1) + [1000],
                         loop=0, optimize=True, disposal=2)
        print(f"{slug}: {len(sequence)} frames, {OUT / f'{slug}-height.gif'}", flush=True)


if __name__ == "__main__":
    main()
