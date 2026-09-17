"""Stream native cleaned fixes once for short lags, launch curves and grid audit."""

from __future__ import annotations

# ruff: noqa: E402 -- direct checkout execution after adding src/ to sys.path
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.derived import stream_flights
from soaring.analysis.observables.fixed_transport import (
    GENERAL_LAGS,
    launch_curve,
    native_short_msd,
)
from soaring.reporting import DISCIPLINES


def main():
    """Save per-flight descriptive curves and actual interpolation counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--discipline", choices=["para", "hang"], required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    g = next(g for g in DISCIPLINES.values() if g.slug == args.discipline)
    out = args.out / g.slug
    out.mkdir(parents=True, exist_ok=True)
    target = out / "native.npz"
    if target.exists():
        raise FileExistsError(target)
    source = g.config().derived_dir / "fixes.parquet"
    start = time.monotonic()
    ids = []
    launch = []
    short = []
    audits = []
    for number, flight in enumerate(
        stream_flights(source, ["segment_id", "t", "E", "N", "interpolated"]), 1
    ):
        fid = str(flight.flight_id.iloc[0])
        segments = []
        for sid, part in flight.groupby("segment_id", sort=False):
            t = part.t.to_numpy(dtype=float)
            xy = part[["E", "N"]].to_numpy(dtype=float)
            segments.append((t, xy))
            if len(t) < 2:
                continue
            dt = float(np.median(np.diff(t)))
            if dt > 10:
                continue
            grid = np.arange(t[0], t[-1] + 1e-7, 10.0)
            right = np.clip(np.searchsorted(t, grid), 0, len(t) - 1)
            left = np.maximum(right - 1, 0)
            nearest = np.where(
                np.abs(t[left] - grid) < np.abs(t[right] - grid), left, right
            )
            exact = np.abs(t[nearest] - grid) <= 1e-5
            previous = part.interpolated.to_numpy(dtype=bool)
            audits.append(
                {
                    "flight_id": fid,
                    "segment_id": int(sid),
                    "grid_span_s": float(grid[-1] - grid[0]),
                    "native_dt_s": dt,
                    "native_fixes": len(t),
                    "grid_points": len(grid),
                    "grid_exact": int(exact.sum()),
                    "grid_interpolated": int((~exact).sum()),
                    "grid_exact_previously_interpolated": int(
                        (exact & previous[nearest]).sum()
                    ),
                    "native_interpolated": int(previous.sum()),
                }
            )
        ids.append(fid)
        launch.append(launch_curve(segments))
        short.append(native_short_msd(segments))
        if number % 5000 == 0:
            print(
                f"{g.slug}: {number} flights; {time.monotonic() - start:.1f}s",
                flush=True,
            )
        if args.limit and number >= args.limit:
            break
    pd.DataFrame(audits).to_parquet(out / "interpolation.parquet", index=False)
    np.savez_compressed(
        target,
        flight_ids=np.asarray(ids),
        lags=GENERAL_LAGS,
        launch=np.asarray(launch),
        short_tamsd=np.asarray(short),
    )
    st = source.stat()
    (out / "native-provenance.json").write_text(
        json.dumps(
            {
                "source": str(source),
                "size": st.st_size,
                "mtime_ns": st.st_mtime_ns,
                "flights": len(ids),
                "limit": args.limit,
                "elapsed_s": time.monotonic() - start,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"{g.slug}: complete, {len(ids)} flights", flush=True)


if __name__ == "__main__":
    main()
