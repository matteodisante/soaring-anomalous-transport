#!/usr/bin/env python3
"""Download SEVIRI rapid-scan imagery cropped, on the fly, to the Thermal-planes cells.

Examples (from the repository root):
    uv run --group satellite python scripts/pipeline/download_satellite.py \
        pilot --day 2020-07-18
    uv run --group satellite python scripts/pipeline/download_satellite.py \
        run --from 2008-05 --to 2022-12
"""

from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.acquisition.satellite.config import load_config  # noqa: E402
from soaring.acquisition.satellite.crop import SOURCE, crop_and_write  # noqa: E402
from soaring.acquisition.satellite.ocf import Fetcher  # noqa: E402


def _month(text):
    year, month = (int(p) for p in text.split("-"))
    return year, month


def _report(stats):
    gb = stats["downloaded_bytes"] / 1e9
    rate = stats["downloaded_bytes"] * 8 / 1e6 / max(stats["elapsed_s"], 1e-9)
    print(
        f"downloaded {gb:.2f} GB in {stats['requests']} requests, "
        f"{stats['elapsed_s']:.0f} s ({rate:.0f} Mbit/s); "
        f"kept {stats['written_bytes'] / 1e6:.1f} MB",
        flush=True,
    )


def main():
    """Crop one pilot day, or every month in a range (skipping finished months)."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--workers", type=int, default=16)
    sub = parser.add_subparsers(dest="command", required=True)
    pilot = sub.add_parser("pilot", help="crop one day into <output_root>/pilot/")
    pilot.add_argument("--day", type=date.fromisoformat, required=True)
    run = sub.add_parser("run", help="crop whole months into <output_root>/<source>/")
    run.add_argument("--from", dest="start", type=_month, required=True)
    run.add_argument("--to", dest="end", type=_month, required=True)
    args = parser.parse_args()
    cfg = load_config()
    fetcher, stores = Fetcher(args.workers), {}

    if args.command == "pilot":
        path = cfg.output_root / "pilot" / f"{SOURCE}_{args.day.isoformat()}.npz"
        _report(crop_and_write(cfg, [args.day], path, fetcher, stores, args.workers))
        print(path)
        return 0

    year, month = args.start
    while (year, month) <= args.end:
        path = cfg.output_root / SOURCE / str(year) / f"{year}-{month:02d}.npz"
        if path.exists():
            print(f"{path.name}: already done")
        else:
            first = date(year, month, 1)
            days = [
                first + timedelta(d) for d in range(calendar.monthrange(year, month)[1])
            ]
            print(f"{year}-{month:02d}: cropping {len(days)} days", flush=True)
            _report(crop_and_write(cfg, days, path, fetcher, stores, args.workers))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
