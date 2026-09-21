"""Terrain and flight axes in Alpine boxes chosen for a reliable terrain axis.

The Alpine chain bends, so one axis cannot describe it. This producer selects
disjoint boxes inside the Alpine take-off box from terrain alone, with the rules of
soaring.analysis.observables.terrain_axis.BOX_RULES: an elongated, straight crest
footprint whose axis survives changes of elevation threshold and of the box edges.
The only non-terrain requirement is a minimum count of take-offs, which involves no
direction. Selection is complete and written to the report before a single flight
axis is measured, and the flights play no part in it.

For each selected box it then measures the 10,000-s displacement axis of the flights
that took off inside, with the regional-PCA estimator, and compares it with the
terrain axis. A single lag needs no fixed population, so every flight with a
supported increment contributes. The DEM is the verified NOAA ETOPO 2022 subset of
revisions/terrain-axis-2026-09-12.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy.io import netcdf_file

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.archive_diagnostics import DiskFrames  # noqa: E402
from soaring.analysis.observables.regional_pca import regional_pca  # noqa: E402
from soaring.analysis.observables.takeoff_frames import takeoff_frames  # noqa: E402
from soaring.analysis.observables.terrain_axis import (  # noqa: E402
    BOX_RULES,
    chain_bend,
    select_boxes,
)
from soaring.analysis.preproc.enu import geodetic_to_enu  # noqa: E402
from soaring.analysis.regions import REGIONAL_BOXES  # noqa: E402
from soaring.reporting import write_macros  # noqa: E402
from soaring.reporting.style import ILLUSTRATION_COLORS, paper_style  # noqa: E402

DATA = Path("/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917")
DEM_DIR = ROOT / "revisions/terrain-axis-2026-09-12"
OUT = ROOT / "thesis/generated"
LAG_S = 10000
MIN_TAKEOFFS = 300
COLORS = ("#202020", ILLUSTRATION_COLORS["secondary"])
LABELS = "ABCDEFGH"


def digest(path):
    """Identify a large input without loading it."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def separation(a, b):
    """Angle between two undirected axes, in [0, 90] degrees."""
    return abs((a - b + 90) % 180 - 90)


def load_dem():
    """Read the archived ETOPO subset after checking it is the verified file."""
    report = json.loads((DEM_DIR / "terrain-axis.json").read_text())
    dem = DEM_DIR / "alps-etopo2022.nc"
    if digest(dem) != report["inputs"]["alps-etopo2022.nc"]["sha256"]:
        raise ValueError("The archived DEM changed")
    with netcdf_file(dem, mmap=False) as nc:
        lat, lon = np.meshgrid(
            nc.variables["latitude"][:].copy(),
            nc.variables["longitude"][:].copy(),
            indexing="ij",
        )
        return lon, lat, nc.variables["z"][:].copy()


def draw(lon, lat, height, records):
    """One map per box, as in the regional terrain comparison, with both axes."""
    paper_style()
    plt.rcParams.update({"font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9})
    fig = plt.figure(figsize=(6.1, 6.6), layout="constrained")
    grid = fig.add_gridspec(2, 2)
    mappable = None
    for k, (label, record) in enumerate(zip(LABELS, records, strict=False)):
        ax = fig.add_subplot(grid[k // 2, k % 2])
        west, east, south, north = record["box"]
        centre = ((west + east) / 2, (south + north) / 2)
        e, n, _ = geodetic_to_enu(
            lat.ravel(), lon.ravel(), np.zeros(lon.size), centre[1], centre[0], 0
        )
        e, n = e.reshape(lon.shape) / 1000, n.reshape(lon.shape) / 1000
        inside = (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
        shown = np.where(inside, height, np.nan)
        mappable = ax.pcolormesh(
            e,
            n,
            shown,
            shading="auto",
            cmap="terrain",
            vmin=0,
            vmax=3500,
            rasterized=True,
        )
        ax.contour(
            e,
            n,
            shown,
            levels=[BOX_RULES["primary_threshold_m"]],
            colors=".15",
            linewidths=0.4,
        )
        origin = np.array(record["centre_km"])
        half = 0.4 * min(np.ptp(e[inside]), np.ptp(n[inside]))
        for angle, color, style in zip(
            (record["angle_deg"], record["flight"]["angle_deg"]),
            COLORS,
            ("-", "--"),
            strict=True,
        ):
            unit = np.array([np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))])
            line = origin[:, None] + unit[:, None] * np.array([-half, half])
            ax.plot(*line, color="white", lw=4, zorder=4)
            ax.plot(*line, color=color, ls=style, lw=2, zorder=5)
        ax.set(
            title=(
                f"{label}: terrain {record['angle_deg']:.0f}\u00b0, "
                f"flights {record['flight']['angle_deg']:.0f}\u00b0"
            ),
            aspect="equal",
            xlim=(e[inside].min() - 3, e[inside].max() + 3),
            ylim=(n[inside].min() - 3, n[inside].max() + 3),
            xlabel="East [km]",
            ylabel="North [km]",
        )
    key = fig.add_subplot(grid[1, 1])
    key.axis("off")
    fig.colorbar(
        mappable,
        ax=key,
        orientation="horizontal",
        label="Elevation [m]",
        shrink=0.9,
        location="top",
    )
    key.legend(
        [
            Line2D([], [], color=c, ls=s, lw=2)
            for c, s in zip(COLORS, ("-", "--"), strict=True)
        ],
        [
            f"Terrain above {BOX_RULES['primary_threshold_m']} m",
            f"Flight PCA at {LAG_S:,} s",
        ],
        loc="center",
        frameon=False,
        fontsize=8,
    )
    fig.savefig(
        OUT / "ch3_alps_box_axes.pdf",
        bbox_inches="tight",
        pad_inches=0.05,
        metadata={"CreationDate": None, "Creator": "soaring.analysis"},
    )
    plt.close(fig)


def main():
    """Select boxes from terrain, then measure and compare the flight axes."""
    lon, lat, height = load_dem()
    domain = REGIONAL_BOXES["Alps"]
    takeoffs = pd.read_parquet(
        DATA / "para/flights.parquet", columns=["flight_id", "lon0", "lat0"]
    )
    inside = takeoffs.lon0.between(*domain[:2]) & takeoffs.lat0.between(*domain[2:])
    launch_lon, launch_lat = (
        takeoffs.lon0[inside].to_numpy(),
        takeoffs.lat0[inside].to_numpy(),
    )

    def count(box):
        return int(
            (
                (launch_lon >= box[0])
                & (launch_lon <= box[1])
                & (launch_lat >= box[2])
                & (launch_lat <= box[3])
            ).sum()
        )

    records = select_boxes(
        lon, lat, height, domain, supported=lambda b: count(b) >= MIN_TAKEOFFS
    )
    (OUT / "ch3_alps_boxes_selection.json").write_text(
        json.dumps(
            {
                "rules": {**BOX_RULES, "min_takeoffs": MIN_TAKEOFFS},
                "domain_west_east_south_north": domain,
                "selected": records,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Selected {len(records)} boxes from terrain and take-off counts alone")

    audit = json.loads((DATA / "para/input-audit.json").read_text())
    store = Path(audit["inputs"]["coordinates"]["path"])
    if digest(store) != audit["inputs"]["coordinates"]["sha256"]:
        raise ValueError("The coordinate store differs from the audited one")
    coordinates = DiskFrames(store.parent)
    whole_bend = chain_bend(lon, lat, height, domain, BOX_RULES["primary_threshold_m"])
    macros = {
        "StatAlpsBoxCount": str(len(records)),
        "StatAlpsWholeBend": f"{whole_bend:.0f}",
    }
    for label, record in zip(LABELS, records, strict=False):
        box = record["box"]
        flights = regional_pca(
            takeoff_frames(coordinates, takeoffs, {"box": box}),
            {"box": box},
            lags_s=(LAG_S,),
        )
        if len(flights) != 1:
            raise ValueError(f"Too few flights for a displayed PCA in box {label}")
        record["flight"] = flights[0]
        record["takeoffs"] = count(box)
        gap = separation(record["angle_deg"], flights[0]["angle_deg"])
        record["difference_deg"] = gap
        angles = record["threshold_angles_deg"]
        prefix = f"StatAlpsBox{label}"
        macros.update(
            {
                prefix + "West": f"{box[0]:.1f}",
                prefix + "East": f"{box[1]:.1f}",
                prefix + "South": f"{box[2]:.1f}",
                prefix + "North": f"{box[3]:.1f}",
                prefix + "TerrainAngle": f"{record['angle_deg']:.1f}",
                prefix + "TerrainRatio": f"{record['ratio']:.1f}",
                prefix + "TerrainLowAngle": f"{angles['1500']:.1f}",
                prefix + "TerrainHighAngle": f"{angles['2500']:.1f}",
                prefix + "Bend": f"{record['bend_deg']:.1f}",
                prefix + "EdgeSpread": f"{record['edge_spread_deg']:.1f}",
                prefix + "FlightAngle": f"{flights[0]['angle_deg']:.1f}",
                prefix + "FlightRatio": f"{flights[0]['ratio']:.2f}",
                prefix + "Flights": str(flights[0]["n_flights"]),
                prefix + "Increments": str(flights[0]["n_increments"]),
                prefix + "Difference": f"{gap:.1f}",
            }
        )
    write_macros(
        OUT / "ch3_alps_boxes_values.tex",
        macros,
        generator=str(Path(__file__).relative_to(ROOT)),
    )
    report = {
        "population": "every flight with a supported 10,000-s increment",
        "lag_s": LAG_S,
        "rules": {**BOX_RULES, "min_takeoffs": MIN_TAKEOFFS},
        "boxes": records,
        "coordinate_sha256": audit["inputs"]["coordinates"]["sha256"],
        "producer_sha256": digest(__file__),
    }
    (OUT / "ch3_alps_boxes.json").write_text(json.dumps(report, indent=2) + "\n")
    draw(lon, lat, height, records)
    for label, r in zip(LABELS, records, strict=False):
        print(
            label,
            r["box"],
            f"terrain {r['angle_deg']:.1f} ratio {r['ratio']:.1f}",
            f"flights {r['flight']['n_flights']} axis {r['flight']['angle_deg']:.1f}",
            f"diff {r['difference_deg']:.1f}",
        )


if __name__ == "__main__":
    main()
