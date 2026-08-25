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
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES  # noqa: E402

# The window Chapter 3 reads every exponent on, plus a margin either side so the fit has
# somewhere to be checked against.
LAG_MIN_S, LAG_MAX_S, N_LAGS = 30.0, 4000.0, 20

# Resampling blocks, for the uncertainty on H. The unit that matters is the cluster the
# chapter measured -- one site on one day, whose ICC is 0.57 and 0.63 -- so whole
# clusters are hashed into blocks and the reduction resamples blocks. Sixty is enough
# for a stable spread and few enough to fit the per-block histograms in memory.
N_BLOCKS = 60

# Blocks are kept only for these cadences. Every cadence that clears the reduction's
# five-million-increment floor is an integer at or below ten seconds -- the archive's
# loggers -- while the long tail of odd cadences carries too little to fit anyway, and
# allocating blocks for all seventy-odd of them would cost gigabytes to no purpose.
def _wants_blocks(step: float) -> bool:
    """Whether this native cadence gets per-block histograms."""
    return step <= 10.0 and float(step).is_integer()


def _flight_blocks(discipline: str, n_blocks: int) -> dict[str, int]:
    """Map each flight to a resampling block, keeping one day-and-site together.

    A flight the catalogue does not cover, or covers without a date or a take-off, is
    hashed on its own id instead. That makes it a cluster of one, which is the same
    convention ``bootstrap.cluster_labels`` uses and which *understates* the clustering,
    so the error it leads to is a lower bound rather than an inflated one.
    """
    import zlib

    import pandas as pd

    catalog_path = DISCIPLINES[discipline].catalog_path()
    if catalog_path is None or not Path(catalog_path).is_file():
        print(f"  {discipline}: no catalogue; blocks fall back to one flight each")
        return {}
    catalog = pd.read_csv(catalog_path, low_memory=False)
    if not {"flight_id", "date", "takeoff"} <= set(catalog.columns):
        print(f"  {discipline}: catalogue lacks date/takeoff; blocks by flight")
        return {}
    ids = catalog["flight_id"].astype(str)
    key = catalog["date"].astype(str) + "|" + catalog["takeoff"].astype(str)
    unknown = catalog[["date", "takeoff"]].isna().any(axis=1).to_numpy()
    key = key.where(~unknown, ids)
    out = {
        str(f): zlib.crc32(str(k).encode()) % n_blocks
        for f, k in zip(ids, key, strict=True)
    }
    print(
        f"  {discipline}: {len(out)} flights over {key.nunique()} day-and-site "
        f"clusters in {n_blocks} blocks ({int(unknown.sum())} without a key)"
    )
    return out


def run(discipline: str, out_dir: Path, limit: int | None = None) -> int:
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.propagator import (
        KinematicAccumulator,
        PropagatorAccumulator,
    )

    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        print(f"{discipline}: fixes.parquet not reachable")
        return 1

    lags_s = np.unique(np.round(np.geomspace(LAG_MIN_S, LAG_MAX_S, N_LAGS)))
    blocks_of = _flight_blocks(discipline, N_BLOCKS)
    accumulators: dict[float, PropagatorAccumulator] = {}
    seconds_of: dict[float, np.ndarray] = {}
    # The three observables Sec. 3.1 catalogues and nothing measured. They need no lag grid,
    # so they cost one histogram each on a pass that is reading the fix table anyway.
    kinematics = KinematicAccumulator()
    flights = 0

    for count, flight in enumerate(
        stream_flights(
            derived / "fixes.parquet",
            ["flight_id", "segment_id", "t", "E", "N", "v_E", "v_N", "v_z"],
        ),
        1,
    ):
        ordered = flight.sort_values(["segment_id", "t"], kind="stable")
        flight_id = str(ordered["flight_id"].iloc[0])
        # A flight absent from the catalogue is hashed on its own id: a cluster of one.
        block = blocks_of.get(flight_id)
        if block is None:
            block = zlib.crc32(flight_id.encode()) % N_BLOCKS
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
                accumulators[step] = PropagatorAccumulator(
                    keep, order=1, n_blocks=N_BLOCKS if _wants_blocks(step) else 1
                )
                seconds_of[step] = keep * step
            positions = np.column_stack(
                [segment["E"].to_numpy(dtype=float), segment["N"].to_numpy(dtype=float)]
            )
            accumulators[step].add(positions, block=block)
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

    slug = DISCIPLINES[discipline].slug
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, np.ndarray] = {"cadences": np.array(sorted(accumulators))}
    payload.update(kinematics.to_dict())
    for step, acc in accumulators.items():
        tag = f"dt{step:g}".replace(".", "p")
        payload[f"{tag}_counts"] = acc.counts
        payload[f"{tag}_edges"] = acc.edges
        payload[f"{tag}_lags_s"] = seconds_of[step]
        payload[f"{tag}_totals"] = acc.totals
        block_quantiles = acc.block_quantiles()
        if block_quantiles.size:
            payload[f"{tag}_block_quantiles"] = block_quantiles.astype(np.float32)
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
