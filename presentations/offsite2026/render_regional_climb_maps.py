"""Render matched-scale regional climb-use maps over independent IGN terrain."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as effects
import mercantile
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets/regional-climb"
EXTENT = {
    "Alps": (800_000, 6_335_000, 1_250_000, 6_555_000),
    "Pyrenees": (300_000, 6_070_000, 750_000, 6_290_000),
    "Channel Coast": (405_000, 6_845_000, 505_000, 6_910_000),
    "Champagne-Lorraine": (790_000, 6_907_000, 890_000, 6_972_000),
}
STEMS = {
    "Alps": "alps", "Pyrenees": "pyrenees",
    "Channel Coast": "channel-coast", "Champagne-Lorraine": "champagne",
}
PIXELS = {"Alps": (2250, 1100), "Pyrenees": (2250, 1100),
          "Channel Coast": (1320, 858), "Champagne-Lorraine": (1320, 858)}
ZOOM = 9
DISPLAY_MIN = .03
DISPLAY_MAX = 5.0
SMOOTHING_KM = 2.0
TILE_TEMPLATE = "https://a.tile.opentopomap.org/{z}/{x}/{y}.png"
TILE_ATTRIBUTION = "Map data: © OpenStreetMap contributors; elevation: SRTM; map style: © OpenTopoMap (CC-BY-SA)"
HEAT = LinearSegmentedColormap.from_list("thermal", ["#111952", "#1437bc", "#0758ff", "#00c9fa", "#95f86b", "#fff02e"])
NORM = LogNorm(vmin=DISPLAY_MIN, vmax=DISPLAY_MAX)


def basemap(name: str, bounds: tuple[int, int, int, int]):
    """Fetch a modest OpenTopoMap tile set and warp it into Lambert-93."""
    stem = STEMS[name]
    dest = OUT / f"{stem}-basemap.png"
    meta_file = OUT / f"{stem}-basemap.json"
    size = PIXELS[name]
    if dest.exists() and meta_file.exists():
        meta = json.loads(meta_file.read_text())
        if (meta.get("bounds_epsg2154") == list(bounds)
                and meta.get("size") == list(size) and meta.get("zoom") == ZOOM):
            return np.asarray(Image.open(dest).convert("RGB")), meta
    lonlat = transform_bounds("EPSG:2154", "EPSG:4326", *bounds, densify_pts=21)
    tiles = list(mercantile.tiles(*lonlat, ZOOM))
    xs, ys = [t.x for t in tiles], [t.y for t in tiles]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mosaic = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    tile_hashes = {}
    for tile in tiles:
        url = TILE_TEMPLATE.format(z=ZOOM, x=tile.x, y=tile.y)
        reply = subprocess.run(
            ["curl", "-L", "--fail", "--silent", "--show-error", "--retry", "3",
             "--max-time", "30", "-A", "soaring-anomalous-transport research map", url],
            capture_output=True, check=True,
        )
        raw = reply.stdout
        with Image.open(io.BytesIO(raw)) as im:
            if im.size != (256, 256):
                raise ValueError(f"Unexpected tile size at {url}: {im.size}")
            mosaic.paste(im.convert("RGB"), ((tile.x - x0) * 256, (tile.y - y0) * 256))
        tile_hashes[f"{tile.x}/{tile.y}"] = hashlib.sha256(raw).hexdigest()
    ul, lr = mercantile.xy_bounds(x0, y0, ZOOM), mercantile.xy_bounds(x1, y1, ZOOM)
    src = np.asarray(mosaic)
    width, height = size
    dst = np.zeros((height, width, 3), dtype=np.uint8)
    source_transform = rasterio.transform.from_bounds(
        ul.left, lr.bottom, lr.right, ul.top, src.shape[1], src.shape[0]
    )
    target_transform = rasterio.transform.from_bounds(*bounds, width, height)
    for band in range(3):
        reproject(src[:, :, band], dst[:, :, band],
                  src_transform=source_transform, src_crs="EPSG:3857",
                  dst_transform=target_transform, dst_crs="EPSG:2154",
                  resampling=Resampling.bilinear)
    Image.fromarray(dst).save(dest)
    meta = {"bounds_epsg2154": bounds, "size": size, "zoom": ZOOM,
            "tile_url_template": TILE_TEMPLATE, "tile_hashes": tile_hashes,
            "attribution": TILE_ATTRIBUTION,
            "retrieved_utc": datetime.now(UTC).isoformat(),
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}
    meta_file.write_text(json.dumps(meta, indent=2) + "\n")
    return dst, meta


def map_array(name: str, bounds: tuple[int, int, int, int], n: int):
    frame = pd.read_csv(OUT / f"{STEMS[name]}-cells.csv")
    west, south, east, north = bounds
    if any(v % 1000 for v in bounds):
        raise ValueError(f"1 km density grid requires aligned map bounds: {name}")
    nx, ny = (east - west) // 1000, (north - south) // 1000
    value = np.zeros((ny, nx), dtype=float)
    x = frame.ix.to_numpy(dtype=int) - west // 1000
    y = frame.iy.to_numpy(dtype=int) - south // 1000
    good = (x >= 0) & (x < nx) & (y >= 0) & (y < ny)
    value[y[good], x[good]] = frame.flights.to_numpy()[good] / n * 100
    return gaussian_filter(value, sigma=SMOOTHING_KM), int(good.sum()), int(frame.flights.to_numpy()[good].sum())


def heat_rgba(density: np.ndarray) -> np.ndarray:
    rgba = HEAT(NORM(np.clip(density, DISPLAY_MIN, DISPLAY_MAX)))
    rgba[:, :, 3] = np.clip((np.log10(np.maximum(density, DISPLAY_MIN))
                            - np.log10(DISPLAY_MIN))
                           / (np.log10(DISPLAY_MAX) - np.log10(DISPLAY_MIN)), 0, 1) ** .7 * .83
    rgba[density < DISPLAY_MIN, 3] = 0
    return rgba


def render(name: str, info: dict):
    bounds = EXTENT[name]
    bg, provenance = basemap(name, bounds)
    climb, occupied, visits = map_array(name, bounds, info["cohort_flights"])
    mountain = name in ("Alps", "Pyrenees")
    # Keep relief and labels while making the thermal layer the visual focus.
    grey = np.dot(bg[..., :3], [0.299, 0.587, 0.114])[..., None]
    bg = np.uint8(np.clip((.15 * bg + .85 * grey) * .72 + 255 * .28, 0, 255))
    fig, ax = plt.subplots(figsize=(9, 4.4) if mountain else (7, 4.55))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.imshow(bg, extent=(bounds[0], bounds[2], bounds[1], bounds[3]),
              origin="upper", interpolation="bilinear", zorder=0)
    ax.imshow(heat_rgba(climb), extent=(bounds[0], bounds[2], bounds[1], bounds[3]),
              origin="lower", interpolation="bilinear", zorder=1)
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_aspect("equal")
    scale_km = 50 if mountain else 10
    sx = bounds[0] + (bounds[2] - bounds[0]) * .035
    sy = bounds[1] + (bounds[3] - bounds[1]) * .065
    ax.plot((sx, sx + scale_km * 1000), (sy, sy), color="#17202B", lw=2.2,
            path_effects=[effects.Stroke(linewidth=4, foreground="white"), effects.Normal()], zorder=3)
    ax.text(sx + scale_km * 500, sy + (bounds[3] - bounds[1]) * .012,
            f"{scale_km} km", ha="center", va="bottom", fontsize=11 if mountain else 9,
            weight="bold", color="#17202B", zorder=3,
            bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": 1})
    ax.set_axis_off()
    fig.savefig(OUT / f"{STEMS[name]}-map.png", dpi=230)
    fig.savefig(OUT / f"{STEMS[name]}-map.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)
    return {"extent_epsg2154": bounds, "map_occupied_cells": occupied,
            "map_flight_cell_visits": visits, "basemap": provenance,
            "png_sha256": hashlib.sha256((OUT / f"{STEMS[name]}-map.png").read_bytes()).hexdigest()}


def legend():
    fig, ax = plt.subplots(figsize=(8, .6))
    fig.subplots_adjust(left=.07, right=.93, top=.7, bottom=.38)
    gradient = np.geomspace(DISPLAY_MIN, DISPLAY_MAX, 500)[None, :]
    ax.imshow(HEAT(NORM(gradient)), aspect="auto",
              extent=(0, 100, 0, 1))
    ax.set_xlim(-4, 104)
    ax.set_yticks([])
    ax.set_xticks([0, 24, 45, 69, 100], ["0.03%", "0.1%", "0.3%", "1%", "5%"], fontsize=9)
    for spine in ax.spines.values(): spine.set_visible(False)
    fig.savefig(OUT / "legend.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "counts-report.json"
    report = json.loads(report_path.read_text())
    report["display"] = {
        "mountain_extent_m": [450_000, 220_000], "lowland_extent_m": [100_000, 65_000],
        "shared_colormap": "navy-blue-cyan-lime-yellow",
        "density_unit": "percent of regional C10000 flights with a climb fix in a 1 km cell",
        "smoothing_sigma_m": 2000, "display_min_percent": DISPLAY_MIN,
        "display_max_percent": DISPLAY_MAX,
        "terrain": "OpenTopoMap topographic tiles (OSM + SRTM relief and contours)",
        "basemap_style": "85% desaturated, 28% white blend for legible heat overlay",
        "basemap_attribution": TILE_ATTRIBUTION,
    }
    for name in EXTENT:
        report["regions"][name]["map"] = render(name, report["regions"][name])
        print(name, report["regions"][name]["map"]["map_occupied_cells"], flush=True)
    legend()
    report_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
