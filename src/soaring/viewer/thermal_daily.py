"""Offline intersection lattice and civil-day summaries from saved climb edges."""

from __future__ import annotations

import io
import json
import sqlite3
from collections import Counter
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from .thermal_geometry import ThermalCell

PARIS = ZoneInfo("Europe/Paris")
POINT_COLUMNS = ["level", "x", "y", "utc"]


def height_levels(maximum, step=10):
    """Regular AGL levels plus the exact supported ceiling, even off the grid."""
    values = np.arange(0, maximum, step, dtype=float)
    return np.r_[values, maximum]


def local_bounds(day, hours=(0, 24)):
    """Paris wall-clock bounds, including 23/25-hour civil days at DST changes."""
    if isinstance(day, str):
        day = date.fromisoformat(day)
    return tuple(
        (datetime.combine(day, time(), PARIS) + timedelta(hours=h)).timestamp()
        for h in hours
    )


def lattice_points(values, cell):
    """Vectorized equivalent of plane_intersections at every prepared height.

    Input is one flight's continuous saved edges. Preserve the existing half-open
    edge convention and terminal vertices. Never create new trajectory edges.
    """
    levels = height_levels(cell.max_agl_m)
    if not len(values):
        return np.empty((0, 4))
    a, b = values[:, :4], values[:, 4:]
    low = np.minimum(a[:, 2], b[:, 2]) - cell.ground_m
    high = np.maximum(a[:, 2], b[:, 2]) - cell.ground_m
    first = np.searchsorted(levels, low, side="left")
    last = np.searchsorted(levels, high, side="right")
    counts = np.maximum(last - first, 0)
    counts[a[:, 2] == b[:, 2]] = 0
    rows = np.repeat(np.arange(len(a)), counts)
    if not len(rows):
        return np.empty((0, 4))
    offsets = np.repeat(np.cumsum(counts) - counts, counts)
    level = np.repeat(first, counts) + np.arange(len(rows)) - offsets
    f = (cell.ground_m + levels[level] - a[rows, 2]) / (b[rows, 2] - a[rows, 2])
    connected = np.zeros(len(a), dtype=bool)
    connected[:-1] = (b[:-1, 3] == a[1:, 3]) & (b[:-1, 2] == a[1:, 2])
    use = ((f >= 0) & (f < 1)) | ((f == 1) & ~connected[rows])
    rows, level, f = rows[use], level[use], f[use]
    points = a[rows] + f[:, None] * (b[rows] - a[rows])
    w, s, e, n = cell.bounds
    inside = (
        (points[:, 0] >= w)
        & (points[:, 0] < e)
        & (points[:, 1] >= s)
        & (points[:, 1] < n)
    )
    return np.column_stack((level[inside], points[inside][:, [0, 1, 3]]))


def prepare_daily(path, progress=print):
    """Add resumable products to the ready SSD file without opening raw archives.

    Each flight is committed in batches. Readers use the old format until the
    final capability flag is published, so an interrupted build stays usable.
    """
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS plane_points(
                source TEXT, ix INTEGER, iy INTEGER, discipline TEXT,
                flight_id TEXT, points BLOB, count INTEGER,
                PRIMARY KEY(source,ix,iy,discipline,flight_id));
            CREATE TABLE IF NOT EXISTS summer_days(
                ix INTEGER,iy INTEGER,day TEXT,flights INTEGER,
                PRIMARY KEY(ix,iy,day));
        """)
        ready = db.execute(
            "SELECT value FROM metadata WHERE key='point_lattice'"
        ).fetchone()
        if ready and ready[0] == "10m-v1":
            expected = db.execute("SELECT COUNT(*) FROM climbs").fetchone()[0]
            actual = db.execute("SELECT COUNT(*) FROM plane_points").fetchone()[0]
            if expected == actual:
                progress(f"All {actual:,} point products already prepared")
                return
        cells = [
            ThermalCell(**json.loads(r[0]))
            for r in db.execute("SELECT payload FROM cells ORDER BY position")
        ]
        for cell in cells:
            days = Counter()
            for start, end in db.execute(
                "SELECT start,end FROM visitors "
                "WHERE ix=? AND iy=? AND start IS NOT NULL",
                (cell.ix, cell.iy),
            ):
                day = datetime.fromtimestamp(start, PARIS).date()
                last = datetime.fromtimestamp(end, PARIS).date()
                while day <= last:
                    if day.month in (6, 7, 8):
                        days[day.isoformat()] += 1
                    day += timedelta(days=1)
            db.executemany(
                "INSERT OR REPLACE INTO summer_days VALUES (?,?,?,?)",
                [(cell.ix, cell.iy, d, n) for d, n in days.items()],
            )
            db.commit()
            rows = db.execute(
                """SELECT c.source,c.discipline,c.flight_id,c.edges
                FROM climbs c LEFT JOIN plane_points p
                ON p.source=c.source AND p.ix=c.ix AND p.iy=c.iy
                AND p.discipline=c.discipline AND p.flight_id=c.flight_id
                WHERE c.ix=? AND c.iy=? AND p.source IS NULL""",
                (cell.ix, cell.iy),
            ).fetchall()
            progress(
                f"{cell.terrain} {cell.ix}/{cell.iy}: {len(rows):,} products to prepare"
            )
            for i, (source, discipline, fid, blob) in enumerate(rows):
                with np.load(io.BytesIO(blob), allow_pickle=False) as saved:
                    points = lattice_points(saved["edges"], cell)
                output = io.BytesIO()
                np.savez_compressed(output, points=points)
                db.execute(
                    "INSERT INTO plane_points VALUES (?,?,?,?,?,?,?)",
                    (
                        source,
                        cell.ix,
                        cell.iy,
                        discipline,
                        fid,
                        output.getvalue(),
                        len(points),
                    ),
                )
                if (i + 1) % 1000 == 0:
                    db.commit()
                    progress(f"  {i + 1:,}/{len(rows):,} saved")
            db.commit()
        missing = db.execute("""SELECT COUNT(*) FROM climbs c LEFT JOIN plane_points p
            ON p.source=c.source AND p.ix=c.ix AND p.iy=c.iy
            AND p.discipline=c.discipline AND p.flight_id=c.flight_id
            WHERE p.source IS NULL""").fetchone()[0]
        if missing:
            raise ValueError(f"Missing {missing} prepared point products")
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('point_lattice','10m-v1')")
        db.commit()
        count = db.execute("SELECT SUM(count) FROM plane_points").fetchone()[0]
        progress(f"Prepared points: {count:,}")


def prepare_reference_audit(path):
    """Expose raw versus screened launch support without changing any reference."""
    import statistics
    from pathlib import Path

    census = Path(path).with_name("thermal-cells.sqlite3")
    if not census.exists():
        return
    with (
        sqlite3.connect(census.as_uri() + "?mode=ro", uri=True) as source,
        sqlite3.connect(path) as db,
    ):
        db.execute("""CREATE TABLE IF NOT EXISTS ground_audit(
            ix INTEGER,iy INTEGER,raw_count INTEGER,raw_median REAL,
            PRIMARY KEY(ix,iy))""")
        for ix, iy in db.execute("SELECT ix,iy FROM cells").fetchall():
            values = [
                r[0]
                for r in source.execute(
                    "SELECT launch_alt FROM flights WHERE launch_x=? AND launch_y=? "
                    "AND launch_alt IS NOT NULL",
                    (ix, iy),
                )
            ]
            db.execute(
                "INSERT OR REPLACE INTO ground_audit VALUES (?,?,?,?)",
                (ix, iy, len(values), statistics.median(values) if values else None),
            )
