"""Offline IGN colour maps and aerial photographs, embedded in the SSD snapshot."""

import hashlib
import io
import json
import sqlite3
import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from PIL import Image

from .geography import FRANCE_EXTENT
from .thermal_store import ThermalStore

SERVICE = "https://data.geopf.fr/wms-r"
LAYERS = {
    "aerial": "ORTHOIMAGERY.ORTHOPHOTOS",
    "colour": "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2",
}


def _download(url):
    """Retry transient service errors; never publish a partial response."""
    for attempt in range(4):
        try:
            with urlopen(url, timeout=120) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)


def fetch_image(folder, bounds, crs, size, kind):
    """Request exactly one georeferenced image; retain attribution and provenance."""
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": LAYERS[kind],
        "STYLES": "normal",
        "CRS": crs,
        "BBOX": ",".join(map(str, bounds)),
        "WIDTH": size[0],
        "HEIGHT": size[1],
        "FORMAT": "image/jpeg",
    }
    query = urlencode(params)
    digest = hashlib.sha256(query.encode()).hexdigest()
    folder.mkdir(exist_ok=True)
    target = folder / f"{digest}.jpg"
    meta = folder / f"{digest}.json"
    if target.exists() and meta.exists():
        return json.loads(meta.read_text()), target.read_bytes()
    payload = _download(SERVICE + "?" + query)
    with Image.open(io.BytesIO(payload)) as img:
        img.verify()
    info = {
        "extent": bounds,
        "crs": crs,
        "size": size,
        "attribution": "© IGN / Géoplateforme · "
        + ("BD ORTHO" if kind == "aerial" else "Plan IGN"),
        "source_url": SERVICE,
        "layer": LAYERS[kind],
        "retrieved": datetime.now(UTC).isoformat(),
        "note": "Mosaic acquisition dates vary spatially and differ from flight dates.",
    }
    target.write_bytes(payload)
    meta.write_text(json.dumps(info))
    return info, payload


def acquisition_dates(bounds, crs):
    """Read acquisition dates from the official mosaic graph for this extent."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": "ORTHOIMAGERY.ORTHOPHOTOS.GRAPHE-MOSAIQUAGE:graphe_bdortho",
        "SRSNAME": crs,
        "BBOX": ",".join(map(str, bounds)) + "," + crs,
        "OUTPUTFORMAT": "application/json",
        "COUNT": 10000,
        "PROPERTYNAME": "date_vol",
    }
    url = "https://data.geopf.fr/wfs/ows?" + urlencode(params)
    result = json.loads(_download(url))
    if "features" not in result:
        raise ValueError(f"IGN mosaic dates unavailable: {result}")
    if int(result.get("numberMatched", 0)) > len(result["features"]):
        raise ValueError("IGN date query truncated; cannot publish incomplete dates")
    return sorted(
        {
            f["properties"]["date_vol"][:10]
            for f in result["features"]
            if f["properties"].get("date_vol")
        }
    ), url


def prepare_imagery(path, progress=print):
    """Save 1.25 m/px aerial imagery for each square plus colour maps of France."""
    store = ThermalStore(path)
    requests = [("france", FRANCE_EXTENT, "CRS:84", (1550, 1050))]
    requests += [
        (f"{c.ix}/{c.iy}", c.bounds, "EPSG:2154", (4000, 4000)) for c in store.cells()
    ]
    with sqlite3.connect(path, timeout=120) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS backgrounds(
            kind TEXT,key TEXT,metadata TEXT,image BLOB,PRIMARY KEY(kind,key))""")
        for key, bounds, crs, size in requests:
            for kind in LAYERS:
                if db.execute(
                    "SELECT 1 FROM backgrounds WHERE kind=? AND key=?", (kind, key)
                ).fetchone():
                    continue
                # A detailed orthophoto remains zoomable; maps need fewer pixels.
                dimensions = (
                    size if kind == "aerial" or key == "france" else (1500, 1500)
                )
                progress(f"Downloading IGN {kind}: {key}")
                info, payload = fetch_image(
                    store.path.parent / "imagery", bounds, crs, dimensions, kind
                )
                if kind == "aerial":
                    if key == "france":
                        info["acquisition_note"] = (
                            "France is a multi-date mosaic; "
                            "exact dates shown for the selected cell."
                        )
                    else:
                        dates, provenance = acquisition_dates(bounds, crs)
                        info["acquisition_dates"] = dates
                        info["acquisition_source"] = provenance
                db.execute(
                    "INSERT INTO backgrounds VALUES (?,?,?,?)",
                    (kind, key, json.dumps(info), payload),
                )
                db.commit()
