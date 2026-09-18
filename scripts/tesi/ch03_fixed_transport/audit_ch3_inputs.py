"""Verify every reused coordinate and segment against the current cleaned archive."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.derived import stream_flights
from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.reporting import DISCIPLINES


def signature(path, *, digest=False):
    """Record immutable-run input identity, hashing compact files or coordinates."""
    path = Path(path)
    stat = path.stat()
    result = {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if digest:
        with path.open("rb") as stream:
            result["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def audit(g, coordinates, out):
    """Require pointwise agreement for every eligible flight and segment."""
    started = time.monotonic()
    frames = DiskFrames(coordinates / f"ch3-full-{g.slug}")
    source = g.config().derived_dir / "fixes.parquet"
    before = signature(source)
    native = json.loads((out / "native-provenance.json").read_text())
    assert native["size"] == before["size"] and native["mtime_ns"] == before["mtime_ns"]
    assert native["limit"] is None
    count, nsegments, points, worst = 0, 0, 0, 0.0
    for flight in stream_flights(source, ["segment_id", "t", "E", "N"]):
        pieces, spans, ids, starts = [], [], [], []
        length = 0
        for sid, segment in flight.groupby("segment_id", sort=False):
            t = segment.t.to_numpy(dtype=float)
            if len(t) < 2 or np.median(np.diff(t)) > 10:
                continue
            grid = np.arange(t[0], t[-1] + 1e-7, 10.0)
            if len(grid) < 2:
                continue
            pieces.append(
                np.column_stack([np.interp(grid, t, segment[c]) for c in ("E", "N")])
            )
            ids.append(int(sid))
            starts.append(float(grid[0]))
            spans.append([length, length + len(grid)])
            length += len(grid)
        if not pieces:
            continue
        row, stored = frames[count]
        assert row["flight_id"] == str(flight.flight_id.iloc[0])
        assert row["segment_ids"] == ids and row["segments"] == spans
        np.testing.assert_array_equal(row["segment_start_s"], starts)
        xy = np.concatenate(pieces)
        xy -= xy[0]
        error = float(np.max(np.abs(stored - xy)))
        worst = max(worst, error)
        np.testing.assert_allclose(stored, xy, rtol=0, atol=1e-8)
        count += 1
        nsegments += len(pieces)
        points += len(xy)
        if count % 25000 == 0:
            print(f"{g.slug}: {count} coordinate identities verified", flush=True)
    assert count == len(frames)
    assert signature(source) == before
    result = {
        "status": "passed",
        "flights": count,
        "segments": nsegments,
        "grid_points": points,
        "maximum_coordinate_error_m": worst,
        "elapsed_s": time.monotonic() - started,
        "inputs": {
            "cleaned_fixes": before,
            "metadata": signature(
                g.config().derived_dir / "flights_meta.parquet", digest=True
            ),
            "catalog": signature(g.catalog_path(), digest=True),
            "coordinates": signature(frames.directory / "positions.bin", digest=True),
            "coordinate_index": signature(
                frames.directory / "flights.json", digest=True
            ),
        },
    }
    target = out / "input-audit.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(result, indent=2) + "\n")
    temp.replace(target)
    print(g.slug, "all inputs verified", flush=True)


def main():
    """Audit a discipline independently of its numerical measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--coordinates", type=Path, required=True)
    parser.add_argument("--discipline", choices=["para", "hang"], required=True)
    args = parser.parse_args()
    g = next(g for g in DISCIPLINES.values() if g.slug == args.discipline)
    audit(g, args.coordinates, args.data / g.slug)


if __name__ == "__main__":
    main()
