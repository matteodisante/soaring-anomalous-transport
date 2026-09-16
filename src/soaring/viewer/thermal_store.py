"""Self-contained thermal-plane delivery file: the viewer opens it read-only."""

from __future__ import annotations

import io
import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ..reporting.disciplines import DISCIPLINES
from .thermal_geometry import ThermalCell

EDGE_COLUMNS = [f"{axis}{end}" for end in (0, 1) for axis in ("x", "y", "z", "utc")]
STORE_NAME = "thermal-planes.sqlite3"


class CancelledError(Exception):
    """A saved-data read was cancelled."""


@dataclass(frozen=True)
class PlaneData:
    """Saved edges and their coverage for the chosen UTC interval."""

    edges: pd.DataFrame
    selected: int
    decoded: int
    unclassified: int
    unavailable: int
    unknown_clock: int
    cached: int = 0
    points: pd.DataFrame | None = None


@contextmanager
def _connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    try:
        yield db
    finally:
        db.close()


class ThermalStore:
    """Only a filename crosses threads; each read owns its SQLite connection."""

    def __init__(self, path):
        """Validate the completed snapshot without probing any archive inputs."""
        self.path = Path(path)
        with _connect(self.path) as db:
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
            if metadata.get("ready") != "1" or metadata.get("version") not in (
                "1",
                "2",
            ):
                raise ValueError(
                    "The prepared thermal-plane file is incomplete or incompatible"
                )
            self.has_points = metadata.get("point_lattice") == "10m-v1"
            self.disciplines = tuple(json.loads(metadata["disciplines"]))
            self.quality_summary = json.loads(metadata.get("launch_quality", "null"))

    def cells(self):
        """Read the already ranked cells without recomputing their ranking."""
        with _connect(self.path) as db:
            return [
                ThermalCell(**json.loads(row[0]))
                for row in db.execute("SELECT payload FROM cells ORDER BY position")
            ]

    def relief(self, cell=None):
        """Read prepared relief and its exact coordinates, without networking."""
        key = "france" if cell is None else f"{cell.ix}/{cell.iy}"
        with _connect(self.path) as db:
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='relief'"
            ).fetchone():
                return None
            row = db.execute(
                "SELECT metadata,png FROM relief WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return None
        from PIL import Image

        return np.asarray(Image.open(io.BytesIO(row[1])).convert("RGB")), json.loads(
            row[0]
        )

    def background(self, cell=None, kind="relief"):
        """Read saved imagery, including the acquisition-date provenance."""
        if kind == "relief":
            return self.relief(cell)
        key = "france" if cell is None else f"{cell.ix}/{cell.iy}"
        with _connect(self.path) as db:
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='backgrounds'"
            ).fetchone():
                return None
            row = db.execute(
                "SELECT metadata,image FROM backgrounds WHERE kind=? AND key=?",
                (kind, key),
            ).fetchone()
        if row is None:
            return None
        from PIL import Image

        return np.asarray(Image.open(io.BytesIO(row[1])).convert("RGB")), json.loads(
            row[0]
        )

    def reference_audit(self, cell):
        """Return the saved unfiltered support beside the screened reference."""
        with _connect(self.path) as db:
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='ground_audit'"
            ).fetchone():
                return None
            return db.execute(
                "SELECT raw_count,raw_median FROM ground_audit WHERE ix=? AND iy=?",
                (cell.ix, cell.iy),
            ).fetchone()

    def time_extent(self):
        """Saved global coverage; no per-cell selection can narrow the user's dates."""
        with _connect(self.path) as db:
            return db.execute("SELECT MIN(start),MAX(end) FROM visitors").fetchone()

    def summer_days(self, cell):
        """Busiest summer dates, ranked by distinct crossing flights (ties: date)."""
        if not self.has_points:
            return []
        with _connect(self.path) as db:
            return db.execute(
                "SELECT day,flights FROM summer_days WHERE ix=? AND iy=? "
                "ORDER BY flights DESC,day",
                (cell.ix, cell.iy),
            ).fetchall()

    def defaults(self, cell):
        """Return a prepared day and height with climb data for immediate display."""
        with _connect(self.path) as db:
            return db.execute(
                "SELECT day,height FROM cells WHERE ix=? AND iy=?", (cell.ix, cell.iy)
            ).fetchone()

    def read_plane(
        self, cell, start, end, source, *, progress=lambda _: None, cancel=None
    ):
        """Read saved products only: no raw files, parquet, models or write handles."""
        if source not in ("own", "vilpellet"):
            raise ValueError(f"Unknown segmentation: {source}")
        if end < start:
            raise ValueError("The end time precedes the start time")
        edges = []
        point_frames = []
        selected = decoded = unclassified = unavailable = 0
        with _connect(self.path) as db:
            unknown = db.execute(
                "SELECT COUNT(*) FROM visitors WHERE ix=? AND iy=? AND start IS NULL",
                (cell.ix, cell.iy),
            ).fetchone()[0]
            product = "p.points" if self.has_points else "c.edges"
            join = (
                (
                    " LEFT JOIN plane_points p ON p.source=c.source "
                    "AND p.ix=c.ix AND p.iy=c.iy "
                    "AND p.discipline=c.discipline AND p.flight_id=c.flight_id "
                )
                if self.has_points
                else ""
            )
            rows = db.execute(
                f"""SELECT v.discipline,v.flight_id,c.status,{product}
                FROM visitors v LEFT JOIN climbs c
                ON c.discipline=v.discipline AND c.flight_id=v.flight_id
                AND c.ix=v.ix AND c.iy=v.iy AND c.source=?
                {join} WHERE v.ix=? AND v.iy=? AND v.end>=? AND v.start<=?""",
                (source, cell.ix, cell.iy, start, end),
            )
            for discipline, fid, status, blob in rows:
                if cancel is not None and cancel.is_set():
                    raise CancelledError("Cancelled")
                if status is None:
                    raise ValueError(
                        "Missing saved product; rerun the offline preparation"
                    )
                selected += 1
                decoded += status != "unavailable"
                unclassified += status == "unclassified"
                unavailable += status == "unavailable"
                if blob is None:
                    raise ValueError(
                        "Missing prepared intersections; finish offline preparation"
                    )
                if self.has_points:
                    with np.load(io.BytesIO(blob), allow_pickle=False) as saved:
                        values = saved["points"]
                    values = values[(values[:, 3] >= start) & (values[:, 3] <= end)]
                    if len(values):
                        frame = pd.DataFrame(values, columns=["level", "x", "y", "utc"])
                        frame["discipline"], frame["flight_id"] = discipline, fid
                        point_frames.append(frame)
                    continue
                with np.load(io.BytesIO(blob), allow_pickle=False) as saved:
                    values = saved["edges"]
                values = values[(values[:, 7] >= start) & (values[:, 3] <= end)]
                if len(values):
                    frame = pd.DataFrame(values, columns=EDGE_COLUMNS)
                    frame["discipline"], frame["flight_id"] = discipline, fid
                    edges.append(frame)
        progress(f"Read {selected:,} saved flights from SSD")
        return PlaneData(
            pd.concat(edges, ignore_index=True) if edges else pd.DataFrame(),
            selected,
            decoded,
            unclassified,
            unavailable,
            unknown,
            selected,
            (
                pd.concat(point_frames, ignore_index=True)
                if point_frames
                else pd.DataFrame(
                    columns=["level", "x", "y", "utc", "discipline", "flight_id"]
                )
            )
            if self.has_points
            else None,
        )


def load_store():
    """Find the ready file, without checking or opening its original archives."""
    override = os.environ.get("SOARING_VIEWER_CACHE_DIR")
    paths = (
        [Path(override).expanduser() / STORE_NAME]
        if override
        else [
            d.config().derived_dir / "viewer/thermal-planes" / STORE_NAME
            for d in DISCIPLINES.values()
        ]
    )
    for path in paths:
        if path.is_file():
            return ThermalStore(path)
    return None


def export_store(index, *, relief=None):
    """Atomically publish a complete, standalone snapshot after offline preparation."""
    from .thermal_cache import segmentation_signature

    if relief is None and hasattr(index, "quality_summary"):
        from .thermal_relief import prepare_relief

        relief = prepare_relief(index)
    target = index.path.with_name(STORE_NAME)
    temporary = target.with_suffix(".building.sqlite3")
    temporary.unlink(missing_ok=True)
    with (
        sqlite3.connect(temporary) as out,
        _connect(index.path.with_name("thermal-climbs.sqlite3")) as products,
    ):
        out.executescript("""
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE relief(key TEXT PRIMARY KEY,metadata TEXT,png BLOB);
            CREATE TABLE cells(position INTEGER PRIMARY KEY,ix INTEGER,iy INTEGER,
                payload TEXT,day REAL,height REAL);
            CREATE TABLE visitors(ix INTEGER,iy INTEGER,discipline TEXT,flight_id TEXT,
                start REAL,end REAL,
                PRIMARY KEY(ix,iy,discipline,flight_id));
            CREATE TABLE climbs(source TEXT,discipline TEXT,flight_id TEXT,
                ix INTEGER,iy INTEGER,
                status TEXT,edges BLOB,
                PRIMARY KEY(source,ix,iy,discipline,flight_id));
        """)
        keys = {s: segmentation_signature(index, s) for s in ("own", "vilpellet")}
        out.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [
                ("version", "2"),
                ("disciplines", json.dumps(index.disciplines)),
                ("archive_signature", index.signature),
                ("segmentation_signatures", json.dumps(keys)),
            ],
        )
        if relief:
            out.executemany("INSERT INTO relief VALUES (?,?,?)", relief)
        if hasattr(index, "quality_summary"):
            out.execute(
                "INSERT INTO metadata VALUES (?,?)",
                ("launch_quality", json.dumps(index.quality_summary)),
            )
        for position, cell in enumerate(index.cells()):
            visitors = index.flights(cell)
            utc = visitors.start_utc + visitors.trim_start
            out.executemany(
                "INSERT INTO visitors VALUES (?,?,?,?,?,?)",
                [
                    (
                        cell.ix,
                        cell.iy,
                        r.discipline,
                        r.flight_id,
                        float(o + r.t_min) if np.isfinite(o) else None,
                        float(o + r.t_max) if np.isfinite(o) else None,
                    )
                    for r, o in zip(visitors.itertuples(index=False), utc, strict=True)
                ],
            )
            expected = set(
                zip(
                    visitors.loc[utc.notna(), "discipline"],
                    visitors.loc[utc.notna(), "flight_id"],
                    strict=True,
                )
            )
            days = {}
            for source, key in keys.items():
                found = set()
                for discipline, fid, status, blob in products.execute(
                    "SELECT discipline,flight_id,status,edges FROM climbs "
                    "WHERE cache_key=? AND ix=? AND iy=?",
                    (key, cell.ix, cell.iy),
                ):
                    if (discipline, fid) not in expected:
                        continue
                    found.add((discipline, fid))
                    out.execute(
                        "INSERT INTO climbs VALUES (?,?,?,?,?,?,?)",
                        (source, discipline, fid, cell.ix, cell.iy, status, blob),
                    )
                    if source == "own":
                        with np.load(io.BytesIO(blob), allow_pickle=False) as saved:
                            a = saved["edges"]
                        if len(a):
                            for day in np.unique(np.floor(a[:, 3] / 86400) * 86400):
                                subset = a[np.floor(a[:, 3] / 86400) * 86400 == day]
                                n, z = days.get(float(day), (0, 0.0))
                                days[float(day)] = (
                                    n + len(subset),
                                    z
                                    + float(((subset[:, 2] + subset[:, 6]) / 2).sum()),
                                )
                if found != expected:
                    raise RuntimeError(
                        f"{cell.terrain}/{source}: {len(expected - found)} "
                        "flights still need preparation"
                    )
            if days:
                day, (n, z) = max(days.items(), key=lambda item: item[1][0])
                height = float(np.clip(z / n - cell.ground_m, 0, cell.max_agl_m))
            else:
                day, height = 0.0, 0.0
            out.execute(
                "INSERT INTO cells VALUES (?,?,?,?,?,?)",
                (position, cell.ix, cell.iy, json.dumps(asdict(cell)), day, height),
            )
        out.execute("INSERT INTO metadata VALUES ('ready','1')")
        out.commit()
        if out.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError("Prepared file failed SQLite integrity check")
    temporary.replace(target)
    return target
