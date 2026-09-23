#!/usr/bin/env python3
"""Bin climb points of the five regional boxes into the viewer's SSD file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.viewer.thermal_imagery import prepare_region_backgrounds  # noqa: E402
from soaring.viewer.thermal_regions import prepare_regions  # noqa: E402
from soaring.viewer.thermal_store import load_store  # noqa: E402


def main() -> int:
    """Write thermal-regions.npz and the regions' terrain images beside the store."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backgrounds-only",
        action="store_true",
        help="Only download the IGN and hillshade images (needs network)",
    )
    args = parser.parse_args()
    log = lambda m: print(m, flush=True)  # noqa: E731
    if not args.backgrounds_only:
        print(f"Wrote {prepare_regions(progress=log)}")
    store = load_store()
    if store is None:
        print("thermal-planes.sqlite3 not found: skipping terrain images")
        return 1
    prepare_region_backgrounds(store.path, progress=log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
