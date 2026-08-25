#!/usr/bin/env python3
"""Build the committed basemap the take-off maps are drawn on.

The take-off panels of Sec.~\\ref{sec:prelim} need real coastlines and borders, and the
figure that carries them has to regenerate from a clean checkout with no network and no
heavy geospatial stack. Cartopy would supply the geometry but fetches Natural Earth at
draw time and drags in GEOS and PROJ; neither is acceptable for an artefact the thesis
build depends on.

So the geometry is fetched once, here, cropped to the panels that actually use it,
decimated, and written to ``data/basemap.json`` -- which is committed. Drawing it needs
nothing but Matplotlib. Re-run this only to change a panel's extent:

    python scripts/reporting/build_basemap.py

Source: Natural Earth admin-0 countries (public domain), via the nvkelso/natural-earth-
vector mirror. Country polygons rather than the land layer, so that one pass gives both
the coastline and the borders; the overseas departments arrive inside the France feature,
which is what puts Reunion on the map at all.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import bare_cli  # noqa: E402

OUT = ROOT / "data" / "basemap.json"

SOURCE = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_{resolution}_admin_0_countries.geojson"
)

# One entry per map panel. ``tolerance`` is the decimation step in degrees: vertices
# closer than that to the previously kept one are dropped, which is invisible at the
# panel's scale and is what keeps the committed file small.
PANELS = {
    # Metropolitan France, where 94.8 % of the retained ensemble launches.
    "france": {
        "bbox": (-5.5, 41.0, 10.0, 51.5),
        "resolution": "10m",
        "tolerance": 0.01,
    },
    # La Reunion: the only overseas department with a substantial share of the archive.
    # The island is 70 km across, so it needs the fine layer and almost no decimation.
    "reunion": {
        "bbox": (55.1, -21.5, 56.0, -20.75),
        "resolution": "10m",
        "tolerance": 0.001,
    },
    # Everything else: the CFD admits flights flown abroad, and they run from the
    # Canaries to Nepal. Drawn on a world frame, where the coarse layer is enough.
    "world": {
        "bbox": (-180.0, -60.0, 180.0, 75.0),
        "resolution": "50m",
        "tolerance": 0.25,
    },
}


def _rings(geometry):
    """Every exterior ring of a (Multi)Polygon, as a list of ``[lon, lat]`` pairs."""
    if geometry["type"] == "Polygon":
        return list(geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return [ring for polygon in geometry["coordinates"] for ring in polygon]
    return []


def _intersects(ring, bbox) -> bool:
    lon_min, lat_min, lon_max, lat_max = bbox
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    return (
        min(xs) <= lon_max
        and max(xs) >= lon_min
        and min(ys) <= lat_max
        and max(ys) >= lat_min
    )


def _decimate(ring, tolerance):
    """Drop vertices closer than ``tolerance`` to the last kept one.

    The ring is kept whole rather than clipped to the panel: Matplotlib clips to the axes
    anyway, and clipping a polygon properly needs a geometry library, which is the
    dependency this file exists to avoid. A ring that survives with fewer than four
    vertices is dropped -- it has no area left to fill.
    """
    kept = [ring[0]]
    for point in ring[1:]:
        last = kept[-1]
        if math.hypot(point[0] - last[0], point[1] - last[1]) >= tolerance:
            kept.append(point)
    if kept[0] != ring[-1]:
        kept.append(ring[0])
    if len(kept) < 4:
        return None
    return [[round(x, 4), round(y, 4)] for x, y in kept]


def main() -> int:
    cache: dict[str, dict] = {}
    panels: dict[str, list] = {}

    for name, spec in PANELS.items():
        resolution = spec["resolution"]
        if resolution not in cache:
            url = SOURCE.format(resolution=resolution)
            print(f"fetching {url}")
            with urllib.request.urlopen(url, timeout=180) as response:
                cache[resolution] = json.loads(response.read())
        collection = cache[resolution]

        rings = []
        for feature in collection["features"]:
            for ring in _rings(feature["geometry"]):
                if len(ring) < 4 or not _intersects(ring, spec["bbox"]):
                    continue
                thinned = _decimate(ring, spec["tolerance"])
                if thinned is not None:
                    rings.append(thinned)
        panels[name] = rings
        vertices = sum(len(r) for r in rings)
        print(f"  {name}: {len(rings)} rings, {vertices} vertices")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "source": "Natural Earth admin-0 countries (public domain)",
                "built_by": "scripts/reporting/build_basemap.py",
                "panels": {
                    name: {"bbox": list(PANELS[name]["bbox"]), "rings": rings}
                    for name, rings in panels.items()
                },
            },
            separators=(",", ":"),
        )
    )
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    bare_cli(__doc__)

    raise SystemExit(main())
