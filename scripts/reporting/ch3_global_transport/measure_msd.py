#!/usr/bin/env python3
r"""One streaming pass computing the ensemble and time-averaged MSD, per discipline.

The traversal every downstream MSD question is built on: the two pooled estimators
(Sec. 3.1), their east-only and north-only twins (Sec. 3.5), and the fixed-duration
cohorts that control for the ensemble thinning out with the lag -- all read off the same
pass over ``fixes.parquet``, because the table is tens of gigabytes and reading it twice to
ask a second question is the one cost worth avoiding.

Writes ``msd_<discipline>.npz`` into ``--out``: the lag grid, every curve
(``MSDAccumulator``/``TAMSDAccumulator`` results), and the per-flight or per-segment
samples the bootstrap needs -- kept, not discarded, since a naive least-squares error
understates the truth here by about fivefold and the honest one has to be resampled from
the flights themselves (:func:`soaring.analysis.observables.transport.bootstrap_alpha_error`).
Kept on disk rather than recomputed is also what makes a change to a fit range, a
bootstrap count, or a figure's colours cost a reduction (``generate_msd_figure.py``,
seconds) and not this pass again.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

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

# Fixed-duration cohorts, in seconds: the control on the ensemble thinning out with the
# lag. All start above the 40 min retention floor, so each is a genuine sub-population
# and not the whole ensemble under another name, and they climb by roughly a factor of
# two so that a trend in alpha across them would be visible rather than a scatter.
COHORTS_S = (3600.0, 7200.0, 14_400.0)


def _dump(container: dict, prefix: str, result, samples: np.ndarray | None = None) -> None:
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

    lags = log_lag_grid(LAG_MAX_S, LAG_MIN_S, N_LAGS)

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
    # The fixed-duration cohorts. Only flights lasting at least t contribute to MSD(t), so
    # the ensemble behind the curve *changes with the lag*, and the flights left at the
    # long-lag end are the ones that kept going rather than a random sample of the
    # population. Within one cohort every flight is present at every lag of the range, so
    # the population is fixed by construction and any remaining growth is motion.
    cohorts = {
        threshold: MSDAccumulator(lags, keep_samples=False) for threshold in COHORTS_S
    }
    ta_cohorts = {threshold: TAMSDAccumulator(lags) for threshold in COHORTS_S}

    n_flights = n_segments = 0
    for count, flight in enumerate(
        stream_flights(derived / "fixes.parquet", ["segment_id", "t", "E", "N"]), 1
    ):
        ordered = flight.sort_values("t")
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
    # Kept for the bootstrap: an uncertainty on the exponent that resamples flights cannot
    # be had from the averaged curve, and the least-squares error the fit reports
    # understates the truth about fivefold.
    _dump(out, "ensemble", ensemble.result(), ensemble.stacked_samples())
    _dump(out, "time_averaged", time_averaged.result(), time_averaged.stacked_samples())
    _dump(out, "ensemble_east", ensemble_east.result(), ensemble_east.stacked_samples())
    _dump(out, "ensemble_north", ensemble_north.result(), ensemble_north.stacked_samples())
    _dump(out, "ta_east", ta_east.result(), ta_east.stacked_samples())
    _dump(out, "ta_north", ta_north.result(), ta_north.stacked_samples())
    # Cohorts carry no samples: keep_samples=False above, since the bootstrap is never
    # asked of them -- only fit_msd_exponent, on the same range as the reference curve.
    for threshold, accumulator in cohorts.items():
        _dump(out, f"cohort_{int(threshold)}", accumulator.result())
    for threshold, accumulator in ta_cohorts.items():
        _dump(out, f"ta_cohort_{int(threshold)}", accumulator.result())

    slug = DISCIPLINES[discipline].slug
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / f"msd_{slug}.npz", **out)
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
