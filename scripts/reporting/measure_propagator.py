#!/usr/bin/env python3
r"""One streaming pass for the increment propagator: the exponent from the bulk.

Every exponent this thesis reports comes from a second moment. Two of them have already
turned out to measure something other than the motion --- the ensemble MSD measures the
launch geometry, and the first-passage time, tried as an escape, inherits the same origin.
This pass measures the exponent from neither a moment nor an origin.

For a self-similar process the distribution of the increments obeys
:math:`P(x,\Delta)=\Delta^{-H}F(x/\Delta^{H})`, so every quantile of :math:`|x|` grows as
:math:`\Delta^{H}` and the rescaled histograms coincide. The median absolute increment is an
order statistic set by the middle of the distribution, where every flight contributes; the
agreement of four separate quantiles is a test of the scaling form rather than an error bar
on it; and the collapse of the rescaled histograms is the direct test of the same thing.

Accumulated as a histogram per lag per component, which is what makes it one pass: the
archive holds :math:`1.4\times10^{9}` fixes and no quantile of that can be taken by sorting.
The two components are kept apart because Sec. 2.8 measures the archive as anisotropic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

DISCIPLINES = {
    "paragliders": ("para", "SOARING_PARA_DATA_ROOT", "PARA_CONFIG_PATH"),
    "hang gliders": ("hang", "SOARING_DELTA_DATA_ROOT", "DELTA_CONFIG_PATH"),
}

# The window Chapter 3 reads every exponent on, plus a margin either side so the fit has
# somewhere to be checked against.
LAG_MIN_S, LAG_MAX_S, N_LAGS = 30.0, 4000.0, 20


def _derived(discipline: str):
    from soaring.acquisition.ffvl import config as cfgmod

    _, env, attr = DISCIPLINES[discipline]
    try:
        cfg = cfgmod.load_config(str(getattr(cfgmod, attr)), data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None
    return cfg.derived_dir if (cfg.derived_dir / "fixes.parquet").is_file() else None


def run(discipline: str, out_dir: Path, limit: int | None = None) -> int:
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.propagator import (
        KinematicAccumulator,
        PropagatorAccumulator,
    )

    derived = _derived(discipline)
    if derived is None:
        print(f"{discipline}: fixes.parquet not reachable")
        return 1

    lags_s = np.unique(np.round(np.geomspace(LAG_MIN_S, LAG_MAX_S, N_LAGS)))
    accumulators: dict[float, PropagatorAccumulator] = {}
    seconds_of: dict[float, np.ndarray] = {}
    # The three observables Sec. 3.1 catalogues and nothing measured. They need no lag grid,
    # so they cost one histogram each on a pass that is reading the fix table anyway.
    kinematics = KinematicAccumulator()
    flights = 0

    for count, flight in enumerate(
        stream_flights(
            derived / "fixes.parquet",
            ["segment_id", "t", "E", "N", "v_E", "v_N", "v_z"],
        ),
        1,
    ):
        ordered = flight.sort_values(["segment_id", "t"], kind="stable")
        for _, segment in ordered.groupby("segment_id", sort=False):
            times = segment["t"].to_numpy(dtype=float)
            if times.size < 16:
                continue
            step = float(np.median(np.diff(times)))
            if not np.isfinite(step) or step <= 0:
                continue
            # One accumulator per native cadence: a lag in samples means a different lag in
            # seconds on each, and mixing them would blur the very scaling being measured.
            if step not in accumulators:
                in_samples = np.maximum(1, np.round(lags_s / step).astype(int))
                keep = np.unique(in_samples)
                accumulators[step] = PropagatorAccumulator(keep, order=1)
                seconds_of[step] = keep * step
            positions = np.column_stack(
                [segment["E"].to_numpy(dtype=float), segment["N"].to_numpy(dtype=float)]
            )
            accumulators[step].add(positions)
            velocity = np.column_stack(
                [segment["v_E"].to_numpy(dtype=float), segment["v_N"].to_numpy(dtype=float)]
            )
            kinematics.add(
                positions, velocity, segment["v_z"].to_numpy(dtype=float), dt=step
            )
        flights += 1
        if count % 20_000 == 0:
            print(f"  {discipline}: {count} flights", flush=True)
        if limit and count >= limit:
            break

    if not accumulators:
        print(f"{discipline}: nothing accumulated")
        return 1

    slug = DISCIPLINES[discipline][0]
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, np.ndarray] = {"cadences": np.array(sorted(accumulators))}
    payload.update(kinematics.to_dict())
    for step, acc in accumulators.items():
        tag = f"dt{step:g}".replace(".", "p")
        payload[f"{tag}_counts"] = acc.counts
        payload[f"{tag}_edges"] = acc.edges
        payload[f"{tag}_lags_s"] = seconds_of[step]
        payload[f"{tag}_totals"] = acc.totals
    np.savez_compressed(out_dir / f"propagator_{slug}.npz", **payload)
    print(f"{discipline}: {flights} flights, {len(accumulators)} cadences -> {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discipline", choices=[*DISCIPLINES, "all"], default="all")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--limit", type=int, default=None,
        help="stop after this many flights per discipline, for a first reading",
    )
    args = parser.parse_args()
    status = 0
    for discipline in list(DISCIPLINES) if args.discipline == "all" else [args.discipline]:
        status |= run(discipline, args.out, args.limit)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
