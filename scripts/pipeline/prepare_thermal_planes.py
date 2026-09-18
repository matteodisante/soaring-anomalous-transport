#!/usr/bin/env python3
"""Prepare the SSD thermal-plane cache once, independently of the viewer window."""

from __future__ import annotations

import argparse
import fcntl
import sys
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.viewer.thermal_index import build_index  # noqa: E402


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
            from soaring.viewer.thermal_prepare import prepare_climbs
            from soaring.viewer.thermal_ranking import audit_launches, rank_cells
            from soaring.viewer.thermal_store import export_store

            with index.path.with_name(".prepare.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    print("Another offline preparation is already running.")
                    return 1
                quality = audit_launches(index, progress=progress)
                index = rank_cells(index, per_category=args.top, quality=quality)
                print(f"Ground quality: {index.quality_summary}", flush=True)
                for cell in index.cells():
                    print(
                        f"{cell.terrain}: {cell.ix},{cell.iy}, {cell.flights} flights, "
                        f"{cell.launches} starts, ground {cell.ground_m}",
                        flush=True,
                    )
                prepare_climbs(index, workers=args.workers, progress=progress)
                from soaring.viewer.thermal_relief import prepare_relief

                relief = prepare_relief(index)
                target = export_store(index, relief=relief)
                from soaring.viewer.thermal_daily import (
                    prepare_daily,
                    prepare_reference_audit,
                )
                from soaring.viewer.thermal_imagery import prepare_imagery

                prepare_reference_audit(target)
                prepare_daily(target, progress=progress)
                prepare_imagery(target, progress=progress)
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
