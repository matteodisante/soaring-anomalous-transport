#!/usr/bin/env python3
r"""Stream the cleaned archive into displacement curves and reusable segment samples.

Writes ``msd_<slug>.npz`` and ``msd_segments_<slug>.parquet`` into ``--out``.
The segment table identifies each stored TAMSD row and records its cadence, fix count
and parent flight's total retained duration, allowing duration and equipment controls
without another traversal of the fix table.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES  # noqa: E402

# Lag grid: from one native step of the fastest logger to twelve hours, the duration
# bound of the flight-level filter, geometrically spaced.
LAG_MIN_S, LAG_MAX_S, N_LAGS = 1.0, 43_200.0, 90

# Historical elapsed-span thresholds retained in the measurement file. The current
# duration report instead uses retained flight duration and identified segment curves;
# threshold selection does not hold the contributing population fixed at every lag.
COHORTS_S = (3600.0, 7200.0, 14_400.0)


def _dump(
    container: dict, prefix: str, result, samples: np.ndarray | None = None
) -> None:
    """Flatten one ``MSDResult``, and optionally its stacked samples, into named arrays."""
    container[f"{prefix}_t"] = result.t
    container[f"{prefix}_msd"] = result.msd
    container[f"{prefix}_n"] = result.n_flights
    container[f"{prefix}_sem"] = result.sem
    if result.p10 is not None:
        container[f"{prefix}_p10"] = result.p10
        container[f"{prefix}_p50"] = result.p50
        container[f"{prefix}_p90"] = result.p90
    if samples is not None:
        container[f"{prefix}_samples"] = samples


def run(discipline: str, out_dir: Path) -> int:
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.transport import (
        MSDAccumulator,
        TAMSDAccumulator,
        log_lag_grid,
    )

    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        print(f"{discipline}: fixes.parquet not reachable, skipping")
        return 1

    lags = np.unique(np.r_[log_lag_grid(LAG_MAX_S, LAG_MIN_S, N_LAGS), 10.0, 10000.0])

    ensemble = MSDAccumulator(lags)
    time_averaged = TAMSDAccumulator(lags)
    # East-only and north-only twins, fed a zeroed column for the other component. Both
    # accumulators reduce to `east**2 + north**2` with no other dependence on either array
    # (transport.py), so a zeroed column leaves the other's own square untouched --
    # tests/analysis/test_transport.py pins this on two independent fBm axes of known,
    # different H.
    ensemble_east = MSDAccumulator(lags)
    ensemble_north = MSDAccumulator(lags)
    ta_east = TAMSDAccumulator(lags)
    ta_north = TAMSDAccumulator(lags)
    # These legacy cohort arrays describe elapsed-span selection. They are retained
    # as diagnostics; the duration/equipment report uses observed retained duration
    # and computes its own paired support from the identified segment samples.
    cohorts = {
        threshold: MSDAccumulator(lags, keep_samples=False) for threshold in COHORTS_S
    }
    ta_cohorts = {threshold: TAMSDAccumulator(lags) for threshold in COHORTS_S}

    segment_rows = []
    n_flights = n_segments = 0
    for count, flight in enumerate(
        stream_flights(derived / "fixes.parquet", ["segment_id", "t", "E", "N"]), 1
    ):
        ordered = flight.sort_values("t")
        segment_bounds = ordered.groupby("segment_id").t.agg(["min", "max"])
        retained_duration = float((segment_bounds["max"] - segment_bounds["min"]).sum())
        times = ordered["t"].to_numpy()
        east, north = ordered["E"].to_numpy(), ordered["N"].to_numpy()
        ensemble.add(times, east, north)
        zeros = np.zeros_like(east)
        ensemble_east.add(times, east, zeros)
        ensemble_north.add(times, zeros, north)
        duration = float(times[-1]) if times.size else 0.0
        for threshold, accumulator in cohorts.items():
            if duration >= threshold:
                accumulator.add(times, east, north)
        n_flights += 1
        # The time average is taken inside a segment, never across the gap that
        # ends it (sec:uniform): the trajectory across the gap is unknown.
        for _, segment in ordered.groupby("segment_id", sort=False):
            seg_times = segment["t"].to_numpy()
            if seg_times.size < 8:
                continue
            step = float(np.median(np.diff(seg_times)))
            east_s, north_s = segment["E"].to_numpy(), segment["N"].to_numpy()
            time_averaged.add(east_s, north_s, step)
            segment_rows.append(
                {
                    "flight_id": str(flight.flight_id.iloc[0]),
                    "segment_id": int(segment.segment_id.iloc[0]),
                    "n_fixes": len(segment),
                    "dt_s": step,
                    "total_retained_duration_s": retained_duration,
                }
            )
            zeros_s = np.zeros_like(east_s)
            ta_east.add(east_s, zeros_s, step)
            ta_north.add(zeros_s, north_s, step)
            span = float(seg_times[-1] - seg_times[0])
            for threshold, ta_cohort in ta_cohorts.items():
                if span >= threshold:
                    ta_cohort.add(east_s, north_s, step)
            n_segments += 1
        if count % 20_000 == 0:
            print(f"  {discipline}: {count} flights", flush=True)

    out: dict = {
        "lags": lags,
        "n_flights": np.array(n_flights),
        "n_segments": np.array(n_segments),
    }
    # Preserve individual curves so later comparisons can retain the correct weights.
    _dump(out, "ensemble", ensemble.result(), ensemble.stacked_samples())
    _dump(out, "time_averaged", time_averaged.result(), time_averaged.stacked_samples())
    _dump(out, "ensemble_east", ensemble_east.result(), ensemble_east.stacked_samples())
    _dump(
        out, "ensemble_north", ensemble_north.result(), ensemble_north.stacked_samples()
    )
    _dump(out, "ta_east", ta_east.result(), ta_east.stacked_samples())
    _dump(out, "ta_north", ta_north.result(), ta_north.stacked_samples())
    # Export aggregate curves for the historical cohorts, without per-flight or
    # per-segment cohort samples. Current duration contrasts use the identified rows.
    for threshold, accumulator in cohorts.items():
        _dump(out, f"cohort_{int(threshold)}", accumulator.result())
    for threshold, accumulator in ta_cohorts.items():
        _dump(out, f"ta_cohort_{int(threshold)}", accumulator.result())

    slug = DISCIPLINES[discipline].slug
    out_dir.mkdir(parents=True, exist_ok=True)
    if len(segment_rows) != out["time_averaged_samples"].shape[0]:
        raise ValueError("Segment identities do not match stored TAMSD samples")
    np.savez_compressed(out_dir / f"msd_{slug}.npz", **out)
    pd.DataFrame(segment_rows).to_parquet(
        out_dir / f"msd_segments_{slug}.parquet", index=False
    )
    print(f"{discipline}: {n_flights} flights, {n_segments} segments -> {out_dir}")
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
