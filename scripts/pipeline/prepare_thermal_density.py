#!/usr/bin/env python3
"""Prepare conservative thermal residence-time maps in hours/km² on the SSD."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.viewer.thermal_time_prepare import prepare  # noqa: E402


def main():
    """Build all regions and cells, or benchmark a bounded separate output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["regions", "cells"])
    parser.add_argument("--limit-batches", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    prepare(
        regions=args.only != "cells",
        cells=args.only != "regions",
        limit_batches=args.limit_batches,
        output=args.output,
        progress=lambda message: print(message, flush=True),
    )


if __name__ == "__main__":
    main()
