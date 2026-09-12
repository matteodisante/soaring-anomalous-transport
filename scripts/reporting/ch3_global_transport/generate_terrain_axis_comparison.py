"""Publish independent terrain axes alongside the current 10,000-s flight PCA.

The indicative terrain calculation and small NOAA elevation subsets are retained
under revisions/terrain-axis-2026-09-12. This producer verifies those inputs,
reads the current flight results, and renders the comparison without refitting
terrain thresholds or remeasuring flight trajectories.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from scipy.io import netcdf_file

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.preproc.enu import geodetic_to_enu  # noqa: E402
from soaring.reporting import write_macros  # noqa: E402
from soaring.reporting.style import ILLUSTRATION_COLORS, paper_style  # noqa: E402

SOURCE = ROOT / "revisions/terrain-axis-2026-09-12"
OUT = ROOT / "thesis/generated"
GENERATED_OUTPUTS = (
    "ch3_terrain_axes.pdf",
    "ch3_terrain_axis_alps.pdf",
    "ch3_terrain_axis_pyrenees.pdf",
    "ch3_terrain_axes_values.tex",
    "ch3_terrain_axes.json",
)
COLORS = ("#202020", ILLUSTRATION_COLORS["secondary"])


def digest(path):
    """Identify an input or output without changing it."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def draw_map(ax, name, record, dataset):
    """Show elevations, the 1000-m contour and two translated orientation axes."""
    with netcdf_file(dataset, mmap=False) as nc:
        lat, lon = np.meshgrid(
            nc.variables["latitude"][:].copy(),
            nc.variables["longitude"][:].copy(),
            indexing="ij",
        )
        height = nc.variables["z"][:].copy()
    west, east, south, north = record["box_lon_lat_deg"]
    inside = (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
    e, n, _ = geodetic_to_enu(
        lat, lon, np.zeros_like(height), (north + south) / 2, (west + east) / 2, 0
    )
    e, n = e / 1000, n / 1000
    shown = np.where(inside, height, np.nan)
    im = ax.pcolormesh(
        e, n, shown, shading="auto", cmap="terrain", vmin=0, vmax=3500, rasterized=True
    )
    ax.contour(e, n, shown, levels=[1000], colors=".2", linewidths=0.35)
    centre = np.array(record["terrain"]["centre_km"])
    half_length = 0.4 * min(np.ptp(e[inside]), np.ptp(n[inside]))
    lines = []
    for angle in (record["terrain"]["angle_deg"], record["flight_angle_deg"]):
        unit = np.array([np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))])
        lines.append(
            centre[:, None] + unit[:, None] * np.array([-half_length, half_length])
        )
    for line in lines:
        ax.plot(*line, color="white", lw=4, zorder=4)
    for line, color, style in zip(lines, COLORS, ("-", "--"), strict=True):
        ax.plot(*line, color=color, ls=style, lw=2, zorder=5)
    ax.set(
        title=name,
        aspect="equal",
        xlabel="East [km]",
        ylabel="North [km]",
        xticks=(-150, 0, 150),
        yticks=(-150, 0, 150),
    )
    return im


def render(records):
    """Provide a compact thesis comparison and separate readable slide panels."""
    paper_style()
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
        }
    )
    handles = [
        Line2D([], [], color=c, ls=s, lw=2)
        for c, s in zip(COLORS, ("-", "--"), strict=True)
    ]
    labels = ["Terrain above 1000 m", "Flight PCA at 10,000 s"]
    groups = [
        ("ch3_terrain_axes.pdf", list(records)),
        ("ch3_terrain_axis_alps.pdf", ["Alps"]),
        ("ch3_terrain_axis_pyrenees.pdf", ["Pyrenees"]),
    ]
    for filename, names in groups:
        fig, axs = plt.subplots(
            1,
            len(names),
            figsize=(6.1 if len(names) == 2 else 5.2, 3.8),
            layout="constrained",
            squeeze=False,
        )
        for ax, name in zip(axs[0], names, strict=True):
            im = draw_map(
                ax, name, records[name], SOURCE / (name.lower() + "-etopo2022.nc")
            )
        fig.colorbar(im, ax=list(axs[0]), label="Elevation [m]", shrink=0.65, pad=0.025)
        fig.legend(
            handles,
            labels,
            loc="outside lower center",
            ncol=2,
            frameon=False,
            fontsize=8,
        )
        fig.savefig(
            OUT / filename,
            bbox_inches="tight",
            pad_inches=0.05,
            metadata={"CreationDate": None, "Creator": "soaring.analysis"},
        )
        plt.close(fig)


def main():
    """Combine unchanged independent terrain measurements with current flight axes."""
    source_path = SOURCE / "terrain-axis.json"
    original = json.loads(source_path.read_text())
    for name, record in original["inputs"].items():
        if digest(SOURCE / name) != record["sha256"]:
            raise ValueError(f"The archived DEM changed: {name}")
    if digest(SOURCE / "estimate_axes.py") != original["script_sha256"]:
        raise ValueError("The archived terrain estimator changed")
    coordinate_path = ROOT / "src/soaring/analysis/preproc/enu.py"
    if digest(coordinate_path) != original["coordinate_source_sha256"]:
        raise ValueError("Review the terrain frame after a coordinate transform change")
    reporter = (
        ROOT / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
    )
    regions = next(
        ast.literal_eval(node.value)
        for node in ast.parse(reporter.read_text()).body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "REGIONS" for t in node.targets)
    )
    flight_path = OUT / "ch3_revision.json"
    flights = json.loads(flight_path.read_text())["results"]["paragliders"]["pca"]
    results, macros = {}, {}
    for name, saved in original["results"].items():
        if list(regions[name]) != saved["box_lon_lat_deg"]:
            raise ValueError(
                "Recalculate terrain orientation after changing the launch boxes"
            )
        row = next(r for r in flights if r["region"] == name and r["lag_s"] == 10000)
        record = results[name] = copy.deepcopy(saved)
        record.update(
            flight_angle_deg=row["angle_deg"],
            flight_n=row["n_flights"],
            flight_ratio=row["ratio"],
        )
        for geom in [record["terrain"], *record["threshold_sensitivity"].values()]:
            geom["difference_from_flight_axis_deg"] = abs(
                (geom["angle_deg"] - row["angle_deg"] + 90) % 180 - 90
            )
        prefix = "StatTerrain" + name
        values = {
            "Angle": f"{record['terrain']['angle_deg']:.1f}",
            "FlightAngle": f"{row['angle_deg']:.1f}",
            "Flights": str(row["n_flights"]),
            "Difference": "<1"
            if record["terrain"]["difference_from_flight_axis_deg"] < 1
            else f"{record['terrain']['difference_from_flight_axis_deg']:.1f}",
        }
        angles = [v["angle_deg"] for v in record["threshold_sensitivity"].values()]
        values.update(MinAngle=f"{min(angles):.1f}", MaxAngle=f"{max(angles):.1f}")
        macros.update({prefix + key: value for key, value in values.items()})
    report = {
        "operation": (
            "Publish independent terrain measurements against current flight PCA; "
            "no trajectory measurement or threshold fitting"
        ),
        "terrain_report": str(source_path.relative_to(ROOT)),
        "terrain_report_sha256": digest(source_path),
        "flight_report_sha256": digest(flight_path),
        "producer_sha256": digest(__file__),
        "source_url": original["source_url"],
        "doi": original["doi"],
        "method": original["method"],
        "limits": original["limits"],
        "results": results,
    }
    (OUT / "ch3_terrain_axes.json").write_text(json.dumps(report, indent=2) + "\n")
    write_macros(
        OUT / "ch3_terrain_axes_values.tex",
        macros,
        generator=str(Path(__file__).relative_to(ROOT)),
    )
    render(results)
    print(
        "Published five comparison inputs from the verified independent DEM analysis"
    )


if __name__ == "__main__":
    main()
