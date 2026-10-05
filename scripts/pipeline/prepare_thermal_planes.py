#!/usr/bin/env python3
"""Prepare the SSD thermal-plane cache once, independently of the viewer window."""

from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.viewer.thermal_index import build_index  # noqa: E402


def _matches_prepared_selection(path, index):
    """Resume enrichment only for the exact same census, methods and DEM selection."""
    from soaring.viewer.thermal_cache import segmentation_signature
    from soaring.viewer.thermal_store import ThermalStore

    if not path.exists():
        return False
    try:
        store = ThermalStore(path)
        with sqlite3.connect(path) as db:
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
        return (
            store.has_terrain_ranking
            and store.cells() == index.cells()
            and store.quality_summary == index.quality_summary
            and store.activity_counts == getattr(index, "activity_counts", {})
            and metadata["archive_signature"] == index.signature
            and json.loads(metadata["segmentation_signatures"])
            == {
                source: segmentation_signature(index, source)
                for source in ("own", "vilpellet")
            }
            and all(
                store.terrain_reference(cell) == json.loads(json.dumps(reference))
                for cell in index.cells()
                for reference in [index.terrain_references[cell.ix, cell.iy]]
            )
        )
    except (sqlite3.DatabaseError, ValueError, KeyError):
        return False


def main() -> int:
    """Resume saved work and print the location of the completed persistent cache."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Prepare the cells without warming both climb products",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Re-read raw starts and geometry even if unchanged",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--with-neighbours",
        action="store_true",
        help="Prepare zoom/pan neighbours and their maps before publishing",
    )
    parser.add_argument(
        "--top", type=int, default=3, help="Cells per altitude category"
    )
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be at least 1")
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    last = 0.0

    def progress(message: str) -> None:
        """Report progress without producing one log line per cached flight."""
        nonlocal last
        now = monotonic()
        if now - last >= 2:
            print(message, flush=True)
            last = now

    try:
        index = build_index(force=args.rebuild_index, progress=progress)
        if not args.index_only:
            from soaring.viewer.thermal_activity import prepare_activity
            from soaring.viewer.thermal_prepare import prepare_climbs
            from soaring.viewer.thermal_ranking import audit_launches, rank_cells
            from soaring.viewer.thermal_store import (
                STORE_NAME,
                export_store,
                neighbour_frames,
            )

            with index.path.with_name(".prepare.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    print("Another offline preparation is already running.")
                    return 1
                activity = prepare_activity(
                    index, workers=args.workers, progress=progress
                )
                quality = audit_launches(index, progress=progress)
                index = rank_cells(
                    index,
                    per_category=args.top,
                    quality=quality,
                    activity=activity,
                    progress=progress,
                )
                print(f"Ranking and launch audit: {index.quality_summary}", flush=True)
                for cell in index.cells():
                    runs = index.activity_counts[cell.ix, cell.iy]["climb_runs"]
                    print(
                        f"{cell.terrain}: {cell.ix},{cell.iy}, {cell.flights} flights, "
                        f"{runs} Vilpellet climbs, "
                        f"{cell.launches} starts, ground {cell.ground_m}",
                        flush=True,
                    )
                cells = index.cells()
                if args.with_neighbours:
                    cells = list(
                        {
                            (frame.ix, frame.iy): frame
                            for cell in cells
                            for frame in [cell, *neighbour_frames(cell)]
                        }.values()
                    )
                prepare_climbs(
                    index, workers=args.workers, progress=progress, cells=cells
                )
                target = index.path.with_name(STORE_NAME)
                staged = target.with_suffix(".preparing.sqlite3")
                if not _matches_prepared_selection(staged, index):
                    if _matches_prepared_selection(target, index):
                        # Retain completed point/map products on an unchanged rerun.
                        transfer = staged.with_suffix(".copying.sqlite3")
                        shutil.copyfile(target, transfer)
                        transfer.replace(staged)
                    else:
                        export_store(index, destination=staged)
                from soaring.viewer.thermal_daily import (
                    prepare_daily,
                    prepare_reference_audit,
                    reuse_prepared_points,
                )
                from soaring.viewer.thermal_imagery import (
                    prepare_imagery,
                    reuse_backgrounds,
                )

                reuse_backgrounds(staged, target, with_neighbours=args.with_neighbours)
                reuse_prepared_points(staged, target)
                prepare_reference_audit(staged)
                prepare_daily(staged, progress=progress)
                prepare_imagery(staged, progress=progress)
                if args.with_neighbours:
                    from soaring.viewer.thermal_neighbours import (
                        prepare_neighbour_imagery,
                        prepare_neighbour_points,
                        prepare_neighbour_terrain,
                    )

                    prepare_neighbour_points(
                        staged, workers=args.workers, progress=progress
                    )
                    prepare_neighbour_imagery(staged, progress=progress)
                    prepare_neighbour_terrain(staged, progress=progress)
                with sqlite3.connect(staged) as db:
                    if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                        raise RuntimeError(
                            "Prepared file failed SQLite integrity check"
                        )
                staged.replace(target)
                print(f"Ready for viewer: {target}", flush=True)
    except KeyboardInterrupt:
        print("Stopped. Completed work remains on the SSD; run again to resume.")
        return 130
    print(f"Saved: {index.path.parent}")
    for cell in index.cells():
        print(
            f"{cell.terrain}: {cell.flights:,} crossing flights, "
            f"ground {cell.ground_m:.1f} m, maximum {cell.max_agl_m:.1f} m AGL"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
