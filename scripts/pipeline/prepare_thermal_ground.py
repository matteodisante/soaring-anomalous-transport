#!/usr/bin/env python3
"""Rebase saved climb intersections on each cell's mean IGN terrain elevation."""

import argparse
import fcntl
from pathlib import Path

from soaring.viewer.thermal_ground import upgrade_terrain_store
from soaring.viewer.thermal_store import find_store_path


def main():
    """Upgrade atomically using saved edges and DEMs, without decoding flights."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--terrain-directory", type=Path)
    args = parser.parse_args()
    path = args.store or find_store_path()
    if path is None:
        parser.error("Connect the SSD or pass --store thermal-planes.sqlite3")
    with path.with_name(".prepare.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        upgrade_terrain_store(
            path,
            folder=args.terrain_directory,
            progress=lambda message: print(message, flush=True),
        )


if __name__ == "__main__":
    main()
