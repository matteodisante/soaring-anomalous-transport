"""Export the viewer's thermal-hour density over the roadmap's Chartreuse frame.

Run from the repository root with PYTHONPATH=src .venv/bin/python.
Reads prepared SSD products only; no recalculation of flight phases or network.
"""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LogNorm
import numpy as np

from soaring.viewer.density_view import AdaptiveDensity
from soaring.viewer.thermal_store import load_store
from soaring.viewer.thermal_time import TimeGrid, cache_path, load_grids


def crop_grid(source, bounds):
    """Select the map frame on the native lattice, preserving pixel durations."""
    bounds = np.asarray(bounds, float)
    offset = (bounds - np.tile(source.bounds[:2], 2)) / source.step
    if (not np.array_equal(offset, np.round(offset))
            or np.any(bounds[:2] < source.bounds[:2])
            or np.any(bounds[2:] > source.bounds[2:])):
        raise ValueError("Map bounds must align with and lie inside the source grid")
    source.flush()
    grid = TimeGrid(bounds, step=source.step)
    rows, cols = np.divmod(source.flat, source.nx)
    rows, cols = rows - int(offset[1]), cols - int(offset[0])
    inside = (cols >= 0) & (cols < grid.nx) & (rows >= 0) & (rows < grid.ny)
    grid.flat = rows[inside] * grid.nx + cols[inside]
    grid.seconds = source.seconds[inside]
    return grid


def main():
    out = Path(__file__).resolve().parent / "assets"
    grids, metadata = load_grids()
    key = "region/Alps/vilpellet"
    bounds = (925000, 6475000, 930000, 6480000)
    grid = crop_grid(grids[key], bounds)
    maximum = max(
        (float(g.seconds.max()) / 3600 / (g.step / 1000) ** 2
         for g in grids.values() if len(g.seconds)),
        default=1,
    )
    norm = LogNorm(0.01, max(1, maximum), clip=True)
    store = load_store()
    pixels, info = store.background(kind="colour", key="185/1295")
    assert np.array_equal(info["extent"], bounds)
    values, xe, ye, resolution = grid.window(925, 930, 6475, 6480)
    assert values.shape == (100, 100) and resolution == "50 m"
    assert np.isclose(values.sum() * 0.05**2, grid.hours)

    plt.rcParams.update({"font.family": "serif", "font.serif": ["Palatino", "DejaVu Serif"]})
    fig = plt.figure(figsize=(3.5, 3.5 / .84), facecolor="white")
    ax = fig.add_axes((0, .16, 1, .84))
    ax.set(xlim=(925, 930), ylim=(6475, 6480), aspect="equal", facecolor="#eef0eb")
    ax.set_autoscale_on(False)
    ax.imshow(pixels, extent=(925, 930, 6475, 6480), origin="upper",
              interpolation="bilinear", alpha=.85, zorder=.5)
    density = AdaptiveDensity(ax, grid.window, norm=norm, alpha=.8,
                              label="Thermal hours/km²")
    density.refresh()
    ax.plot([928.6, 929.6], [6475.25, 6475.25], color="black", lw=2, zorder=4)
    box = {"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": 1}
    ax.text(929.1, 6475.37, "1 km", ha="center", va="bottom", fontsize=12, bbox=box)
    ax.text(929.75, 6479.75, "N", ha="center", va="top", fontsize=13, bbox=box)
    ax.set_axis_off()
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap="magma_r"),
                      cax=fig.add_axes((.055, .105, .89, .024)), orientation="horizontal")
    cb.set_ticks([.01, 1, 100, 10000])
    cb.ax.tick_params(labelsize=10, pad=2, length=2)
    cb.ax.minorticks_off()
    cb.set_label("Thermal hours/km² (log)", fontsize=11, labelpad=2)
    cb.outline.set_linewidth(.5)
    fig.savefig(out / "thermal-density-chartreuse.pdf", dpi=350,
                metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)

    np.savez_compressed(out / "thermal-density-chartreuse-data.npz",
                        hours_per_km2=values, x_edges_km=xe, y_edges_km=ye)
    report = {
        "source": str(cache_path()), "product_created": metadata.get("created"),
        "grid": key, "bounds_epsg2154": bounds, "pixel_m": grid.step,
        "climb_hours": grid.hours, "maximum_hours_per_km2": float(values.max()),
        "colour_scale": {"cmap": "magma_r", "log_min": norm.vmin, "log_max": norm.vmax,
                         "density_alpha": .8, "background_alpha": .85},
        "scope": "All archived dates and heights; paragliders and hang gliders; Vilpellet climbs.",
        "quantity": "Cumulative recorded climb time divided by horizontal pixel area.",
        "background": info,
        "background_pixels_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
    }
    (out / "thermal-density-chartreuse.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Chartreuse: {grid.hours:.3f} climb hours; 50 m pixels; viewer scale 0.01--{norm.vmax:.3f} h/km²")


if __name__ == "__main__":
    main()
