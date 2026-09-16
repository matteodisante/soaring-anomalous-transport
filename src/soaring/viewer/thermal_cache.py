"""Persistent, resumable climb products shared by viewer sessions on the SSD."""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..analysis.segmentation.config import DEFAULT_SEGMENTATION_CONFIG_PATH
from ..analysis.segmentation.vilpellet.config import DEFAULT_VILPELLET_CONFIG_PATH
from ..reporting.disciplines import DISCIPLINES

if TYPE_CHECKING:
    from .thermal_index import ThermalIndex

EDGE_COLUMNS = [f"{axis}{end}" for end in (0, 1) for axis in ("x", "y", "z", "utc")]


def segmentation_signature(index: ThermalIndex, source: str) -> str:
    """Invalidate only the affected decoder when its code, config or model changes."""
    root = Path(__file__).resolve().parents[1]
    paths = [
        Path(__file__).with_name("data.py"),
        Path(__file__).with_name("thermal_geometry.py"),
        Path(__file__).with_name("thermal_index.py"),
        Path(__file__).with_name("geodesy.py"),
    ]
    if source == "own":
        paths.append(DEFAULT_SEGMENTATION_CONFIG_PATH)
        paths.extend(sorted((root / "analysis/segmentation").glob("*.py")))
        for name in index.disciplines:
            model = DISCIPLINES[name].config().derived_dir / "segmentation/model"
            paths.extend([model / "metadata.json", model / "gaussian_hmm.pkl"])
    else:
        paths.append(DEFAULT_VILPELLET_CONFIG_PATH)
        paths.extend(sorted((root / "analysis/segmentation/vilpellet").glob("*.py")))
    digest = hashlib.sha256()
    # Geometry and temporal origins belong to the archive signature. A test/custom
    # index without one still has a stable identity between separate viewer loads.
    stat = index.path.stat()
    geometry = (index.signature, str(index.path), stat.st_size, stat.st_mtime_ns)
    digest.update(json.dumps([1, geometry, source]).encode())
    for path in paths:
        digest.update(str(path).encode())
        digest.update(path.read_bytes() if path.is_file() else b"missing")
    return digest.hexdigest()


class ClimbCache:
    """One compressed edge array per flight/cell/method, committed independently."""

    def __init__(self, index: ThermalIndex, source: str):
        """Open persistent products next to the archive's saved cell index."""
        self.path = index.path.with_name("thermal-climbs.sqlite3")
        self.key = segmentation_signature(index, source)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS climbs (
                cache_key TEXT, discipline TEXT, flight_id TEXT,
                ix INTEGER, iy INTEGER, status TEXT, edges BLOB,
                PRIMARY KEY (cache_key, discipline, flight_id, ix, iy)
            )
        """)
        self.db.commit()

    def get(self, discipline, flight_id, cell, *, geometry=True):
        """Read a completed result, or None; optionally skip decompressing geometry."""
        payload = "edges" if geometry else "NULL"
        record = self.db.execute(
            f"SELECT status, {payload} FROM climbs WHERE cache_key=? AND discipline=? "
            "AND flight_id=? AND ix=? AND iy=?",
            (self.key, discipline, flight_id, cell.ix, cell.iy),
        ).fetchone()
        if record is None:
            return None
        status, blob = record
        if not geometry or blob is None:
            edges = pd.DataFrame(columns=EDGE_COLUMNS)
        else:
            with np.load(io.BytesIO(blob), allow_pickle=False) as saved:
                edges = pd.DataFrame(saved["edges"], columns=EDGE_COLUMNS)
        return status, edges

    def put(self, discipline, flight_id, cell, status, edges):
        """Commit a whole-flight result; cancellation never leaves a partial flight."""
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer, edges=edges.reindex(columns=EDGE_COLUMNS).to_numpy(dtype=float)
        )
        self.db.execute(
            "INSERT OR REPLACE INTO climbs VALUES (?,?,?,?,?,?,?)",
            (
                self.key,
                discipline,
                flight_id,
                cell.ix,
                cell.iy,
                status,
                buffer.getvalue(),
            ),
        )
        self.db.commit()

    def close(self):
        """Release the SQLite handle on the worker that opened it."""
        self.db.close()

    def __enter__(self):
        """Use a bounded handle around one load or preparation request."""
        return self

    def __exit__(self, *_):
        """Close even when a decode fails or the user cancels."""
        self.close()
