#!/usr/bin/env python3
"""Enrich the already prepared viewer file; no raw reads or segmentation."""

import argparse
import fcntl
from pathlib import Path

from soaring.viewer.thermal_daily import prepare_daily, prepare_reference_audit
from soaring.viewer.thermal_imagery import prepare_imagery
from soaring.viewer.thermal_store import load_store


def main():
    """Prepare the snapshot under the shared offline-writer lock."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--skip-imagery", action="store_true")
    args = parser.parse_args()
    store = args.store or load_store().path
    with store.with_name(".prepare.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepare_reference_audit(store)
        prepare_daily(store, progress=lambda s: print(s, flush=True))
        if not args.skip_imagery:
            prepare_imagery(store, progress=lambda s: print(s, flush=True))
    print(f"Ready: {store} ({store.stat().st_size / 1e9:.3f} GB)")


if __name__ == "__main__":
    main()
