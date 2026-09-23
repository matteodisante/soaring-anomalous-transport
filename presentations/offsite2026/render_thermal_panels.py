"""Export thesis and slide 18 maps from the viewer's prepared intersections.

No screen capture, raw-flight decoding, segmentation or network requests.
Pool all available dates, with no seasonal restriction.
"""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soaring.viewer.geography import classify_region, draw_land, load_basemap
from soaring.viewer.thermal_daily import height_levels
from soaring.viewer.thermal_geometry import unproject
from soaring.viewer.thermal_ridges import DATA_DIRECTORY, draw_ridges, load_ridges
from soaring.viewer.thermal_store import load_store


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "assets/screenshots"
HEIGHTS = (100, 600)
SOURCE = "vilpellet"
BACKGROUND = "colour"
POINT_COLORS = {"paragliders": "#005CFF", "hang gliders": "#E75A00"}
POINT_SIZE = 8
POINT_ALPHA = .9
SELECTION = (("mountain", "High mountains", 2, "H2"), ("plains", "Plains", 1, "P1"))


def render_locator(cells):
    """Locate the chosen cell centres on the viewer's geographic basemap."""
    basemap = load_basemap()
    if basemap is None:
        raise ValueError("Missing committed viewer basemap")
    fig, ax = plt.subplots(figsize=(3.2, 3.0))
    fig.subplots_adjust(left=.01, bottom=.01, right=.99, top=.99)
    draw_land(ax, basemap["france"]["rings"], (-5.5, 41, 9.8, 51.5))
    for cell in cells:
        lon, lat = cell["centre_lon_lat"]
        color = "#8D3153" if cell["name"] == "mountain" else "#217A81"
        ax.scatter([lon], [lat], s=65, color=color, edgecolor="white", linewidth=.8, zorder=3)
        ax.annotate(cell["viewer_id"], (lon, lat), xytext=(8, 5), textcoords="offset points",
                    fontsize=15, weight="bold", color=color)
    ax.text(2, 46.5, "France", ha="center", fontsize=12, color="#596773")
    ax.set_axis_off()
    fig.savefig(OUT / "cell-locator.pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT / "cell-locator.png", dpi=250)
    plt.close(fig)


def all_date_points(store, cell):
    """Use the viewer's complete time extent and the two exact saved planes."""
    start, end = store.time_extent()
    levels = height_levels(cell.max_agl_m)
    wanted = [int(np.argmin(abs(levels - h))) for h in HEIGHTS]
    assert np.array_equal(levels[wanted], HEIGHTS)
    data = store.read_plane(cell, start, end, SOURCE, progress=print)
    points = data.points.loc[data.points.level.isin(wanted)].copy()
    assert points.utc.between(start, end).all()
    coverage = {key: getattr(data, key) for key in (
        "selected", "decoded", "unclassified", "unavailable", "unknown_clock")}
    assert data.selected + data.unknown_clock == cell.flights
    return points, coverage


def main():
    store = load_store()
    if store is None or not store.has_points:
        raise SystemExit("Connect the SSD with the viewer's prepared point lattice.")
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Palatino", "DejaVu Serif"]})
    with sqlite3.connect(store.path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
    report = {
        "source_store": str(store.path),
        "store_size_bytes": store.path.stat().st_size,
        "store_mtime_ns": store.path.stat().st_mtime_ns,
        "store_metadata": metadata,
        "segmentation": SOURCE,
        "selection": "User-selected viewer ranks: High mountains #2 (H2) and Plains #1 (P1). Ranks follow descending all-time distinct crossing flights within each altitude band. Pool all available dates without a seasonal restriction.",
        "date_selection": "Entire prepared archive, inclusive time extent; no month or year exclusion.",
        "archive_time_extent_utc_s": store.time_extent(),
        "height_selection": "Exact 100 and 600 m planes above each cell reference, as requested.",
        "point_display": {
            "selection": "All selected crossings, without subsampling.",
            "colors": POINT_COLORS, "size_pt2": POINT_SIZE,
            "alpha": POINT_ALPHA, "edge": "none",
        },
        "height_reference": "Fixed median screened raw starting altitude within each cell, not a terrain model.",
        "panels": [],
        "cells": [],
        "code_sha256": {},
    }
    macros = [
        f"\\newcommand{{\\ThermalLower}}{{{HEIGHTS[0]}\\,\\mathrm{{m}}}}",
        f"\\newcommand{{\\ThermalUpper}}{{{HEIGHTS[1]}\\,\\mathrm{{m}}}}",
    ]
    for name, terrain, rank, viewer_id in SELECTION:
        candidates = sorted([c for c in store.cells() if c.terrain == terrain],
                            key=lambda c: (-c.flights, c.ix, c.iy))
        cell = candidates[rank - 1]
        ridges = load_ridges(cell)
        if ridges is None:
            raise ValueError(f"Prepare the IGN derived crest extract for {viewer_id} first")
        pooled, coverage = all_date_points(store, cell)
        saved = store.background(cell, BACKGROUND)
        if saved is None:
            raise ValueError(f"Missing prepared {BACKGROUND} map for {cell}")
        pixels, info = saved
        west, south, east, north = cell.bounds
        centre = unproject((west + east) / 2, (south + north) / 2)
        region = classify_region(np.array([centre[1]]), np.array([centre[0]]))[0]
        report["cells"].append({
            "name": name, "viewer_id": viewer_id, "viewer_rank": rank,
            **asdict(cell), "bounds_epsg2154": cell.bounds,
            "centre_lon_lat": centre, "region": region,
            "ranking_candidates": [asdict(c) for c in candidates],
            "ranking_bands": [terrain], "coverage": coverage,
            "background_kind": BACKGROUND, "background": info,
            "background_pixels_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
            "ridges": {
                "count": len(ridges["features"]),
                "provenance": ridges["provenance"],
                "file_sha256": hashlib.sha256(
                    (DATA_DIRECTORY / f"ign-ridges-{cell.ix}-{cell.iy}.geojson").read_bytes()
                ).hexdigest(),
            },
        })
        for label, height in zip(("low", "high"), HEIGHTS):
            levels = height_levels(cell.max_agl_m)
            level = int(np.argmin(abs(levels - height)))
            assert levels[level] == height
            points = pooled.loc[pooled.level == level].copy()
            local_dates = pd.to_datetime(points.utc, unit="s", utc=True).dt.tz_convert("Europe/Paris")
            assert points.x.between(west, east, inclusive="left").all()
            assert points.y.between(south, north, inclusive="left").all()
            flights = len(points[["discipline", "flight_id"]].drop_duplicates())
            fig, ax = plt.subplots(figsize=(3.5, 3.5))
            fig.subplots_adjust(left=0, bottom=0, right=1, top=1)
            ax.set(xlim=(0, 5), ylim=(0, 5), aspect="equal")
            w, s, e, n = info["extent"]
            ax.imshow(pixels, extent=((w-west)/1000, (e-west)/1000,
                      (s-south)/1000, (n-south)/1000), origin="upper", alpha=.9)
            for discipline, group in points.groupby("discipline"):
                ax.scatter((group.x-west)/1000, (group.y-south)/1000,
                           s=POINT_SIZE, alpha=POINT_ALPHA, edgecolors="none", linewidths=0,
                           zorder=3, color=POINT_COLORS[discipline])
            draw_ridges(ax, cell, ridges)
            ax.plot([3.6, 4.6], [.25, .25], color="black", lw=2, zorder=4)
            ax.text(4.1, .37, "1 km", ha="center", va="bottom", fontsize=12,
                    bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": 1})
            ax.text(4.75, 4.75, "N", ha="center", va="top", fontsize=13,
                    bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": 1})
            ax.set_axis_off()
            stem = f"{name}-{label}"
            fig.savefig(OUT / f"{stem}.png", dpi=300)
            fig.savefig(OUT / f"{stem}.pdf", metadata={"CreationDate": None, "ModDate": None})
            plt.close(fig)
            csv = points[["x", "y", "utc", "discipline", "flight_id"]].to_csv(index=False)
            (OUT / f"{stem}-points.csv").write_text(csv)
            report["panels"].append({
                "name": stem, "height_m": height, "points": len(points),
                "flights": flights, "discipline_points": points.discipline.value_counts().to_dict(),
                "year_points": local_dates.dt.year.value_counts().sort_index().to_dict(),
                "month_points": local_dates.dt.month.value_counts().sort_index().to_dict(),
                "first_crossing_local": local_dates.min().isoformat(),
                "last_crossing_local": local_dates.max().isoformat(),
                "points_sha256": hashlib.sha256(csv.encode()).hexdigest(),
                "png_sha256": hashlib.sha256((OUT / f"{stem}.png").read_bytes()).hexdigest(),
            })
            macro = "Thermal" + name.capitalize() + label.capitalize()
            macros.append(f"\\newcommand{{\\{macro}Counts}}{{{len(points):,} crossings / {flights:,} flights}}")
            print(stem, height, "m:", len(points), "crossings /", flights, "flights")
        prefix = "Thermal" + name.capitalize()
        macros.extend([
            f"\\newcommand{{\\{prefix}Cell}}{{{viewer_id}}}",
            f"\\newcommand{{\\{prefix}Region}}{{{region}}}",
            f"\\newcommand{{\\{prefix}TotalFlights}}{{{cell.flights:,}}}",
        ])
    render_locator(report["cells"])
    report["locator"] = {"basemap": "data/basemap.json", "markers": "Geographic cell centres; marker sizes exaggerated for visibility."}
    for rel in (
        "presentations/offsite2026/render_thermal_panels.py",
        "src/soaring/viewer/thermal_store.py", "src/soaring/viewer/thermal_daily.py",
        "src/soaring/viewer/thermal_geometry.py", "src/soaring/viewer/widgets/thermal_plane.py",
        "src/soaring/viewer/geography.py", "data/basemap.json",
        "src/soaring/viewer/thermal_orography.py",
        "src/soaring/viewer/thermal_ridges.py",
    ):
        report["code_sha256"][rel] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    (OUT / "thermal-panels-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "thermal-panel-values.tex").write_text("\n".join(macros) + "\n")
    # Keep the thesis independently compilable with the same plotted data.
    generated = ROOT / "thesis/generated"
    for panel in report["panels"]:
        stem = panel["name"]
        shutil.copyfile(OUT / f"{stem}.pdf", generated / f"ch3_thermal_{stem}.pdf")
    shutil.copyfile(OUT / "thermal-panel-values.tex", generated / "ch3_thermal_panel_values.tex")
    shutil.copyfile(OUT / "thermal-panels-report.json", generated / "ch3_thermal_panels_report.json")
    shutil.copyfile(OUT / "cell-locator.pdf", generated / "ch3_thermal_cell_locator.pdf")


if __name__ == "__main__":
    main()
