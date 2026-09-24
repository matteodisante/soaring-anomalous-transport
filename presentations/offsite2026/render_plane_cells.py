"""Draw the four regional plane-crossing panels from measure_plane_cells.py.

Each panel: shaded IGN relief, the terrain standing above the plane, and every climb
crossing of the plane. No SSD or network access; reads assets/plane-cells only.

Concentration: the share of the cell's 250 m bins that holds half of the crossings,
with one crossing per flight (its first in time) and 500 flights drawn per region,
so that unequal traffic does not decide the comparison. The same statistic for as
many uniform random points is saved as the reference.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets/plane-cells"
PANEL_IN = 34 / 25.4  # printed width on the slide
RISING = "#D9480F"  # rising air on the thermal-mechanism slide
ABOVE = "#6B5B4B"  # terrain standing above the plane
POINT_SIZE = 1.7
POINT_ALPHA = .35
BIN_M = 250
CHECK_BINS_M = (100, 250, 500, 1000)  # robustness of the ranking, report only
SAMPLE_FLIGHTS = 500
DRAWS = 1000
DEM_STEP_M = 25


def hillshade(z, azimuth=315, altitude=45):
    """Lambertian shading with one fixed light and no per-image contrast stretch.

    Matplotlib's LightSource rescales each image to the full grey range, which
    would make flat lowlands look as rugged as mountains.
    """
    gy, gx = np.gradient(z, DEM_STEP_M)  # rows run north to south
    nx, ny = -gx, gy
    norm = np.sqrt(nx**2 + ny**2 + 1)
    az, alt = np.radians(90 - azimuth), np.radians(altitude)
    light = np.cos(alt) * np.cos(az), np.cos(alt) * np.sin(az), np.sin(alt)
    return np.clip((nx * light[0] + ny * light[1] + light[2]) / norm, 0, 1)


def half_share(points, bounds, rng, bin_m=BIN_M):
    """Median share of bins holding half of 500 flights' first crossings."""
    west, south, east, north = bounds
    first = points.sort_values("utc", kind="stable").drop_duplicates(["discipline", "flight_id"])
    bins = int((east - west) // bin_m)
    ix = ((first.x - west) // bin_m).astype(int).to_numpy()
    iy = ((first.y - south) // bin_m).astype(int).to_numpy()
    flat = ix * bins + iy
    n = min(SAMPLE_FLIGHTS, len(flat))

    def share(cells):
        counts = np.sort(np.bincount(cells, minlength=bins**2))[::-1]
        return (np.searchsorted(np.cumsum(counts), n / 2) + 1) / bins**2

    observed = [share(rng.choice(flat, n, replace=False))
                for _ in range(DRAWS if len(flat) > n else 1)]
    uniform = [share(rng.integers(0, bins**2, n)) for _ in range(DRAWS)]
    return float(np.median(observed)), float(np.median(uniform)), n


def panel(slug, region):
    west, south, east, north = region["bounds_epsg2154"]
    with Image.open(io.BytesIO((OUT / region["dem"]["file"]).read_bytes())) as im:
        dem = np.asarray(im, dtype=float)
    points = pd.read_csv(OUT / f"{slug}-points.csv", dtype={"flight_id": str})
    km = (east - west) / 1000
    fig, ax = plt.subplots(figsize=(PANEL_IN, PANEL_IN))
    fig.subplots_adjust(left=0, bottom=0, right=1, top=1)
    ax.set(xlim=(0, km), ylim=(0, km), aspect="equal")
    # The WMS repeats some rows and columns; a 1.5-pixel blur hides the striping
    # in the shading only. The plane mask below uses the unsmoothed elevations.
    ax.imshow(hillshade(gaussian_filter(dem, 1.5)), cmap="gray", vmin=-.35, vmax=1.05,
              extent=(0, km, 0, km), origin="upper", interpolation="bilinear")
    above = np.ma.masked_where(dem <= region["plane_altitude_m"], np.ones_like(dem))
    ax.imshow(above, cmap=ListedColormap([ABOVE]), alpha=.5, extent=(0, km, 0, km),
              origin="upper", interpolation="nearest")
    ax.scatter((points.x - west) / 1000, (points.y - south) / 1000, s=POINT_SIZE,
               color=RISING, alpha=POINT_ALPHA, edgecolors="none", linewidths=0,
               rasterized=True, zorder=3)
    bar, margin = 5 if km >= 20 else 2, .06 * km
    ax.plot([km - margin - bar, km - margin], [.05 * km] * 2, color="black", lw=1.2,
            solid_capstyle="butt", zorder=4)
    ax.text(km - margin - bar / 2, .07 * km, f"{bar} km", ha="center", va="bottom",
            fontsize=5.5, bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": .6},
            zorder=4)
    ax.set_axis_off()
    fig.savefig(OUT / f"{slug}.pdf", dpi=600, metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT / f"{slug}.png", dpi=400)
    plt.close(fig)
    return points


def main():
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Palatino", "DejaVu Serif"]})
    report = json.loads((OUT / "plane-cells-report.json").read_text())
    rng = np.random.default_rng(2026)
    concentration, macros = {}, []
    for slug, region in report["regions"].items():
        points = panel(slug, region)
        share, uniform, n = half_share(points, region["bounds_epsg2154"], rng)
        concentration[slug] = {
            "share_for_half": share, "uniform_share_for_half": uniform, "flights_drawn": n,
            "share_for_half_by_bin_m": {
                str(b): half_share(points, region["bounds_epsg2154"], rng, b)[:2] for b in CHECK_BINS_M
            },
        }
        tag = "".join(part.capitalize() for part in slug.split("-"))
        macros.append(f"\\newcommand{{\\PlaneCell{tag}HalfShare}}{{{100 * share:.1f}}}")
        print(f"{slug}: half of {n} first crossings in {100 * share:.1f}% of the cell "
              f"(uniform {100 * uniform:.1f}%)")
    uniform = np.mean([c["uniform_share_for_half"] for c in concentration.values()])
    macros.append(f"\\newcommand{{\\PlaneCellUniformHalfShare}}{{{100 * uniform:.0f}}}")
    (OUT / "plane-cells-concentration.json").write_text(json.dumps({
        "definition": (
            f"Median over {DRAWS} draws of {SAMPLE_FLIGHTS} flights (all flights if fewer) "
            f"of the smallest share of {BIN_M} m bins holding half of their first crossings. "
            "share_for_half_by_bin_m gives [observed, uniform] for other bin sizes."
        ),
        "regions": concentration,
    }, indent=2) + "\n")
    (OUT / "plane-cells-concentration.tex").write_text("\n".join(macros) + "\n")


if __name__ == "__main__":
    main()
