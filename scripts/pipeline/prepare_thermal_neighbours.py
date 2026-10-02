#!/usr/bin/env python3
"""Save the 3 x 3 neighbourhood of every published cell into the viewer file.

Zoom - in the thermal-plane viewer reads only these products. The first run
labels every flight crossing the neighbouring squares from the processed
archives (both segmentations) and downloads their IGN backgrounds; later runs
resume where the previous one stopped.
"""

import argparse
import fcntl
import sys
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.viewer.thermal_neighbours import (  # noqa: E402
    prepare_neighbour_imagery,
    prepare_neighbour_points,
)
from soaring.viewer.thermal_store import load_store  # noqa: E402


def main() -> int:
    """Prepare the neighbourhoods under the shared offline-writer lock."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--image-px",
        type=int,
        default=4000,
        help="Width of a neighbour background in pixels (published cells: 4000)",
    )
    parser.add_argument("--skip-imagery", action="store_true")
    args = parser.parse_args()
    store = args.store or load_store().path
    last = 0.0

    def progress(message: str) -> None:
        """Report progress without one line per flight."""
        nonlocal last
        now = monotonic()
        if now - last >= 2:
            print(message, flush=True)
            last = now

    with store.with_name(".prepare.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another offline preparation is already running.")
            return 1
        try:
            prepare_neighbour_points(store, workers=args.workers, progress=progress)
            if not args.skip_imagery:
                prepare_neighbour_imagery(
                    store, size=args.image_px, progress=lambda s: print(s, flush=True)
                )
        except KeyboardInterrupt:
            print("Stopped. Completed work remains on the SSD; run again to resume.")
            return 130
    print(f"Ready: {store} ({store.stat().st_size / 1e9:.3f} GB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
