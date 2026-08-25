#!/usr/bin/env python3
r"""How much the edge-flagged samples move the ensemble MSD, measured rather than asserted.

The smoothing evaluates its polynomial off-centre at the ends of a segment, and the table
flags those samples ``edge``. ``verify_dataset.py`` qualifies its invariants by that flag,
which is why its speed invariant holds; the MSD estimators do not, and read every fix. So
the edge samples enter the curve, and Chapter 3 states the size of what they do to it.

That size was typed by hand until this pass. It is measured here by computing the same
ensemble MSD twice on the same flights, once over all samples and once over interior ones
only, and reporting the largest relative difference below and above a stated lag.

A subsample suffices and is used: the effect is a property of the segment ends, which every
flight has, so it converges in thousands rather than in the whole archive -- and the number
that matters is a bound, which a subsample gives honestly as long as the sample is stated.
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

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)

OUT_TEX = ROOT / "thesis" / "generated" / "edge_effect.tex"

# The two regions Chapter 3 separates: below the short-lag artefacts, and above the lower
# end of every fit range.
SHORT_S, LONG_S = 10.0, 60.0
LAGS_S = np.unique(np.round(np.geomspace(1.0, 600.0, 40)))


def _msd_about_origin(times, positions, mask, lags_s, step):
    """Squared distance from the flight's own take-off, at each lag, using masked fixes only.

    The origin is the first fix of the *whole* record and does not move with the mask. That
    is the whole point: the first samples of a record are exactly the edge-flagged ones, so
    re-zeroing on the first retained fix would compare two curves about two different
    origins and report the shift as the effect. What is wanted is one origin and two
    populations of fixes answering the lags.
    """
    if mask.sum() < 4:
        return None
    origin_t, origin_p = times[0], positions[0]
    t = times[mask] - origin_t
    p = positions[mask] - origin_p
    out = np.full(lags_s.size, np.nan)
    for i, lag in enumerate(lags_s):
        j = int(np.searchsorted(t, lag))
        if j >= t.size or abs(t[j] - lag) > max(0.5, step / 2):
            continue
        out[i] = p[j, 0] ** 2 + p[j, 1] ** 2
    return out


def run(discipline: str, limit: int) -> dict[str, str]:
    from soaring.analysis.derived import stream_flights

    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        print(f"{discipline}: fixes.parquet not reachable")
        return {}

    tag = DISCIPLINES[discipline].tag
    total_all = np.zeros(LAGS_S.size)
    total_interior = np.zeros(LAGS_S.size)
    count_all = np.zeros(LAGS_S.size)
    count_interior = np.zeros(LAGS_S.size)
    flights = 0
    edge_share_num = 0
    edge_share_den = 0

    for count, flight in enumerate(
        stream_flights(derived / "fixes.parquet", ["segment_id", "t", "E", "N", "edge"]), 1
    ):
        ordered = flight.sort_values(["segment_id", "t"], kind="stable")
        times = ordered["t"].to_numpy(dtype=float)
        positions = np.column_stack(
            [ordered["E"].to_numpy(dtype=float), ordered["N"].to_numpy(dtype=float)]
        )
        edge = ordered["edge"].to_numpy(dtype=bool)
        edge_share_num += int(edge.sum())
        edge_share_den += edge.size
        if times.size < 8:
            continue
        step = float(np.median(np.diff(times)))
        if not np.isfinite(step) or step <= 0:
            continue
        every = _msd_about_origin(times, positions, np.ones(times.size, dtype=bool), LAGS_S, step)
        interior = _msd_about_origin(times, positions, ~edge, LAGS_S, step)
        if every is None or interior is None:
            continue
        # Each curve averages over the flights that answer the lag under its own rule, and
        # the two rules do not answer the same set. That is deliberate: excluding a class of
        # samples changes which lags a flight can answer, and that change is part of what
        # excluding them does to the curve. Restricting both to the lags they answer in
        # common was tried and throws away exactly the cases where the effect exists -- it
        # returns zero by construction.
        for curve, total, counter in (
            (every, total_all, count_all),
            (interior, total_interior, count_interior),
        ):
            good = np.isfinite(curve)
            total[good] += curve[good]
            counter[good] += 1
        flights += 1
        if count >= limit:
            break

    with np.errstate(invalid="ignore", divide="ignore"):
        msd_all = np.where(count_all > 0, total_all / np.maximum(count_all, 1), np.nan)
        msd_interior = np.where(
            count_interior > 0, total_interior / np.maximum(count_interior, 1), np.nan
        )
        relative = np.abs(msd_interior / msd_all - 1.0)

    short = LAGS_S <= SHORT_S
    long = LAGS_S >= LONG_S
    macros = {
        f"StatEdge{tag}Flights": f"{flights}",
        f"StatEdge{tag}SamplePct": f"{100.0 * edge_share_num / max(edge_share_den, 1):.2f}",
        f"StatEdge{tag}ShortLagS": f"{SHORT_S:.0f}",
        f"StatEdge{tag}LongLagS": f"{LONG_S:.0f}",
    }
    for label, window in (("Short", short), ("Long", long)):
        usable = window & np.isfinite(relative)
        if usable.any():
            macros[f"StatEdge{tag}{label}Pct"] = f"{100.0 * np.nanmax(relative[usable]):.1f}"
    print(
        f"{discipline}: {flights} flights, edge share "
        f"{macros[f'StatEdge{tag}SamplePct']} %, "
        f"below {SHORT_S:.0f} s {macros.get(f'StatEdge{tag}ShortPct', '--')} %, "
        f"above {LONG_S:.0f} s {macros.get(f'StatEdge{tag}LongPct', '--')} %"
    )
    return macros


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20000, help="flights per discipline")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    macros: dict[str, str] = {}
    missing = []
    for discipline in DISCIPLINES:
        written = run(discipline, args.limit)
        if not written:
            missing.append(discipline)
        macros |= written
    if not macros:
        print("nothing reachable; edge_effect.tex not written")
        return 1
    refusal = partial_write_refusal(
        missing, OUT_TEX.name, allow_partial=args.allow_partial,
        reasons=[unreachable_reason(DISCIPLINES[d]) for d in missing],
    )
    if refusal:
        print(refusal)
        return 1
    write_macros(
        OUT_TEX, macros, generator="scripts/reporting/measure_edge_effect.py", sort=True
    )
    print(f"wrote {OUT_TEX.name} ({len(macros)} macros)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
