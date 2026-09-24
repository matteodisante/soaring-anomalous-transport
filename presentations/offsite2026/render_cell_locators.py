"""Locate the four 20 km cells on the archived regional basemaps, offline.

The rectangle uses the exact Lambert-93 bounds from plane-cells-report.json.
Geographic coordinates are transformed from that same rectangle, not inferred
from map pixels. Town reference coordinates come from geo.api.gouv.fr.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as effects
import numpy as np
from matplotlib.patches import Rectangle
from PIL import Image
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets/plane-cells"
BASE = HERE / "assets/regional-climb"
# Equal aspect ratios, with scales appropriate to the surrounding region.
VIEWS = {
    "alps": (900_000, 6_477_000, 1_020_000, 6_555_000),
    "pyrenees": (430_000, 6_160_000, 550_000, 6_238_000),
    "channel-coast": (405_000, 6_845_000, 505_000, 6_910_000),
    "champagne": (790_000, 6_907_000, 890_000, 6_972_000),
}
COLOURS = {"alps": "#8E3B5C", "pyrenees": "#C98A1E",
           "channel-coast": "#2E7D8A", "champagne": "#4A6079"}
# Offsets in points keep names clear of each cell and of the scale bar.
LABELS = {
    "alps": [("Annecy", -4, 1, "right"), ("Chambéry", 3, -6, "left")],
    "pyrenees": [("Loudenvielle", -4, -11, "right"),
                 ("Bagnères-de-Luchon", 3, 1, "left")],
    "channel-coast": [("Caen", 3, 1, "left"), ("Clécy", -4, 1, "right"),
                      ("Flers", -4, -5, "right")],
    "champagne": [("Charleville-Mézières", -3, 3, "right"),
                  ("Sedan", -4, -5, "right"), ("Mouzon", 3, -5, "left")],
}
TO_GEO = Transformer.from_crs(2154, 4326, always_xy=True)
TO_MAP = Transformer.from_crs(4326, 2154, always_xy=True)


def render(slug, region, places):
    source = BASE / f"{slug}-basemap.png"
    meta = json.loads((BASE / f"{slug}-basemap.json").read_text())
    west, south, east, north = meta["bounds_epsg2154"]
    view = VIEWS[slug]
    assert west <= view[0] < view[2] <= east
    assert south <= view[1] < view[3] <= north
    bg = np.asarray(Image.open(source).convert("RGB")) / 255
    # Lighten the map without changing its geographic registration.
    bg = .55 * bg + .45
    fig, ax = plt.subplots(figsize=(39 / 25.4, 25.35 / 25.4))
    fig.subplots_adjust(left=0, bottom=0, right=1, top=1)
    ax.imshow(bg, extent=(west, east, south, north), origin="upper")
    x0, y0, x1, y1 = region["bounds_epsg2154"]
    assert x1 - x0 == y1 - y0 == 20_000
    assert view[0] < x0 < x1 < view[2] and view[1] < y0 < y1 < view[3]
    cell = Rectangle((x0, y0), x1 - x0, y1 - y0,
                     facecolor="none", edgecolor=COLOURS[slug], linewidth=1.6,
                     path_effects=[effects.withStroke(linewidth=2.8, foreground="white")])
    ax.add_patch(cell)
    for name, dx, dy, align in LABELS[slug]:
        x, y = TO_MAP.transform(*places[name]["centre"]["coordinates"])
        short = {"Charleville-Mézières": "Charleville", "Bagnères-de-Luchon": "Luchon"}.get(name, name)
        ax.plot(x, y, "o", ms=1.5, color="#222222")
        ax.annotate(short, (x, y), xytext=(dx, dy), textcoords="offset points",
                    ha=align, va="center", fontsize=5.3, color="#222222",
                    path_effects=[effects.withStroke(linewidth=1.5, foreground="white")])
    span = view[2] - view[0]
    barx, bary = view[0] + .71 * span, view[1] + .075 * (view[3] - view[1])
    ax.plot([barx, barx + 20_000], [bary, bary], color="black", lw=1,
            path_effects=[effects.withStroke(linewidth=2.8, foreground="white")])
    ax.text(barx + 10_000, bary + .025 * span, "20 km", ha="center", fontsize=5.2,
            path_effects=[effects.withStroke(linewidth=1.5, foreground="white")])
    ax.set(xlim=(view[0], view[2]), ylim=(view[1], view[3]), aspect="equal")
    ax.set_axis_off()
    fig.savefig(OUT / f"{slug}-locator.pdf", dpi=400,
                metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT / f"{slug}-locator.png", dpi=400)
    plt.close(fig)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    centre = TO_GEO.transform(cx, cy)
    assert np.allclose(centre, region["centre_lon_lat"], atol=1e-10, rtol=0)
    return {
        "bounds_epsg2154_m": [x0, y0, x1, y1],
        "centre_lon_lat": centre,
        "corners_lon_lat": {name: TO_GEO.transform(x, y) for name, x, y in
                            [("SW", x0, y0), ("SE", x1, y0), ("NE", x1, y1), ("NW", x0, y1)]},
        "map_bounds_epsg2154_m": view,
        "basemap_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "basemap_source": meta["tile_url_template"],
        "basemap_attribution": meta["attribution"],
    }


def main():
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Palatino", "DejaVu Serif"]})
    report = json.loads((OUT / "plane-cells-report.json").read_text())
    places = json.loads((OUT / "cell-locator-places.json").read_text())
    result, macros = {}, []
    for slug, region in report["regions"].items():
        result[slug] = render(slug, region, places)
        tag = "".join(part.capitalize() for part in slug.split("-"))
        x0, y0, x1, y1 = region["bounds_epsg2154"]
        lon, lat = result[slug]["centre_lon_lat"]
        geo = f"{lat:.5f}$^\\circ$\\,N\\\\{abs(lon):.5f}$^\\circ$\\,{'E' if lon >= 0 else 'W'}"
        bounds = f"E {x0}--{x1}\\\\N {y0}--{y1}"
        macros.extend([f"\\newcommand{{\\CellLocator{tag}Centre}}{{{geo}}}",
                       f"\\newcommand{{\\CellLocator{tag}Bounds}}{{{bounds}}}"])
    (OUT / "cell-locator-values.tex").write_text("\n".join(macros) + "\n")
    (OUT / "cell-locator-report.json").write_text(json.dumps({
        "method": "Exact 20 km Lambert-93 rectangles; WGS84 centres printed to five decimals. Map north is Lambert-93 grid north.",
        "place_reference": "Municipal centres from geo.api.gouv.fr; contextual labels, not cell definitions.",
        "regions": result,
    }, indent=2) + "\n")
    print("Rendered four cell locators and exported exact bounds and geographic coordinates.")


if __name__ == "__main__":
    main()
