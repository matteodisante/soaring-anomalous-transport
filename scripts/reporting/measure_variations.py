#!/usr/bin/env python3
r"""One streaming pass computing the trend-robust scaling estimators, per flight.

The mean-squared displacement about take-off is not a transport observable on this archive
--- it crosses over where the population leaves its launch area --- and subtracting each
flight's own drift to repair it introduces a bias with no safe lag range
(:func:`soaring.analysis.observables.variations.centring_bias`). What is left is to filter
the trend out instead: an order-``p`` difference annihilates any polynomial of degree
``p-1`` identically, so the exponent is read without ever estimating a drift.

This pass computes ``V_p(lag)`` for ``p = 1, 2, 3`` **within each retained segment**, and
keeps the per-flight curve rather than only the average. Everything the chapter needs
afterwards --- the clustered bootstrap, the order scan, the stratified curves, the regime
fit and its null --- is then a reduction of that matrix and costs no further pass over the
43 GB of fixes.

Writes ``variations_<discipline>.npz`` (one row per flight, one column per lag, one array
per order) and ``variation_flights_<discipline>.parquet`` (the clustering keys and the
stratifiers) into ``--out``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES  # noqa: E402

# Lags in seconds. The floor is above the smoothing scale of the slowest logger kept
# (5 samples at dt = 10 s is 50 s, so nothing below it is a measurement of motion); the
# ceiling is where the median flight still supplies windows.
LAG_MIN_S, LAG_MAX_S, N_LAGS = 60.0, 20_000.0, 36
ORDERS = (1, 2, 3)


def run(discipline: str, out_dir: Path) -> int:
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.variations import filtered_variation

    glider = DISCIPLINES[discipline]
    derived, catalog_path = glider.derived_dir(), glider.catalog_path()
    if derived is None:
        print(f"{discipline}: fixes.parquet not reachable, skipping")
        return 1

    lags_s = np.unique(np.round(np.geomspace(LAG_MIN_S, LAG_MAX_S, N_LAGS)))
    rows: list[dict] = []
    per_order = {p: [] for p in ORDERS}

    for count, flight in enumerate(
        stream_flights(derived / "fixes.parquet", ["segment_id", "t", "E", "N"]), 1
    ):
        ordered = flight.sort_values(["segment_id", "t"], kind="stable")
        # Accumulate over the flight's segments, weighted by how many windows each
        # supplies: a segment is where the increments are defined, and one long segment
        # must not be outvoted by a short one that happens to sit in the same flight.
        total = {p: np.zeros(lags_s.size) for p in ORDERS}
        weight = {p: np.zeros(lags_s.size) for p in ORDERS}
        native = np.nan
        for _, segment in ordered.groupby("segment_id", sort=False):
            times = segment["t"].to_numpy(dtype=float)
            if times.size < 8:
                continue
            step = float(np.median(np.diff(times)))
            if not np.isfinite(step) or step <= 0:
                continue
            native = step if not np.isfinite(native) else native
            positions = np.column_stack(
                [segment["E"].to_numpy(dtype=float), segment["N"].to_numpy(dtype=float)]
            )
            lags_samples = np.round(lags_s / step).astype(int)
            for p in ORDERS:
                value = filtered_variation(positions, lags_samples, order=p)
                span = lags_samples * p
                n_windows = np.maximum(times.size - span, 0)
                usable = np.isfinite(value) & (n_windows > 0) & (lags_samples >= 1)
                total[p][usable] += value[usable] * n_windows[usable]
                weight[p][usable] += n_windows[usable]

        if not np.any(weight[1] > 0):
            continue
        for p in ORDERS:
            with np.errstate(invalid="ignore", divide="ignore"):
                per_order[p].append(
                    np.where(weight[p] > 0, total[p] / np.maximum(weight[p], 1), np.nan
                    ).astype(np.float32)
                )
        rows.append(
            {
                "flight_id": str(ordered["flight_id"].iloc[0]),
                "native_dt_s": native,
                "duration_s": float(ordered["t"].iloc[-1] - ordered["t"].iloc[0]),
                "n_windows_p1": float(weight[1].max()),
            }
        )
        if count % 20_000 == 0:
            print(f"  {discipline}: {count} flights", flush=True)

    slug = DISCIPLINES[discipline].slug
    frame = pd.DataFrame(rows)

    # The clustering keys. Flights are not independent records: two wings launched from
    # one site on one day saw the same air, and the bootstrap has to resample the day
    # rather than the flight or it will report an error bar that is far too small.
    if catalog_path is not None and Path(catalog_path).is_file():
        catalog = pd.read_csv(catalog_path, low_memory=False)
        catalog["flight_id"] = catalog["flight_id"].astype(str)
        keep = [
            c
            for c in ("flight_id", "date", "takeoff", "pilot", "season", "wing_class",
                      "flight_type", "distance_km", "points")
            if c in catalog
        ]
        frame = frame.merge(catalog[keep], on="flight_id", how="left")

    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / f"variations_{slug}.npz",
        lags_s=lags_s,
        **{f"order{p}": np.vstack(per_order[p]) for p in ORDERS},
    )
    frame.to_parquet(out_dir / f"variation_flights_{slug}.parquet")
    print(f"{discipline}: {len(frame)} flights, {lags_s.size} lags -> {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discipline", choices=[*DISCIPLINES, "all"], default="all")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    targets = list(DISCIPLINES) if args.discipline == "all" else [args.discipline]
    status = 0
    for discipline in targets:
        status |= run(discipline, args.out)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
