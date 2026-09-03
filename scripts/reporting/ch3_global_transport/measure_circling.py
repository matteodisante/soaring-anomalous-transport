#!/usr/bin/env python3
r"""The circling period, read off the ensemble velocity autocorrelation at native cadence.

Chapter 3 said the circling leaves no trace in any statistic of the unsegmented trajectory.
It does, and the reason it was not seen is a grid: ``measure_shape.py`` evaluates
:func:`velocity_autocorrelation` --- which returns every integer lag --- and then keeps only
the lags of its geometric grid, whose floor is \SI{60}{\second}. A circle takes about twenty
seconds, so the whole feature lies below the first lag the shape pass retains.

What a circling wing produces in ``C(tau)`` is not a sign change. Radius and phase disperse
across flights, so the ensemble average of many circles does not go negative; what survives
is the *shape*, because at half a period a wing's velocity is anti-aligned with its own
velocity a half-period earlier and at a full period it is aligned again. So the signature is
a local minimum at half the period followed by a local maximum at the period, both positive.
That is what this measures.

Restricted to \SI{1}{\hertz} segments, because a lag in samples is a lag in seconds only
there, and mixing cadences would blur a feature ten samples wide. A subsample suffices and
the sample size is reported: the period is a property of the flying that every thermalling
flight has, not a tail statistic.
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
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)

OUT_TEX = ROOT / "thesis" / "generated" / "circling.tex"

MAX_LAG_S = 60
# A segment has to be long enough that the mean-removal bias is not the whole of what is
# measured, and the feature sits at 10-25 s, so a few hundred samples is the floor.
MIN_SAMPLES = 400
# The minimum is looked for away from lag 1, where the smoothing still dominates, and the
# maximum after it. Both windows are stated rather than tuned.
MIN_SEARCH_S, MAX_SEARCH_S = 5, 30


def run(discipline: str, limit: int) -> dict[str, str]:
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.persistence import velocity_autocorrelation

    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        print(f"{discipline}: fixes.parquet not reachable")
        return {}

    tag = DISCIPLINES[discipline].tag
    total = np.zeros(MAX_LAG_S + 1)
    count = np.zeros(MAX_LAG_S + 1)
    segments = 0

    for read, flight in enumerate(
        stream_flights(derived / "fixes.parquet", ["segment_id", "t", "v_E", "v_N"]), 1
    ):
        ordered = flight.sort_values(["segment_id", "t"], kind="stable")
        for _, segment in ordered.groupby("segment_id", sort=False):
            times = segment["t"].to_numpy(dtype=float)
            if times.size < MIN_SAMPLES:
                continue
            if float(np.median(np.diff(times))) != 1.0:
                continue
            velocity = np.column_stack(
                [segment["v_E"].to_numpy(dtype=float), segment["v_N"].to_numpy(dtype=float)]
            )
            # max_lag is in samples and MAX_LAG_S is in seconds; the two are the same
            # number only because the 1 Hz filter above has already excluded every other
            # cadence. Reuse this line anywhere else and it needs dividing by the step.
            _, correlation = velocity_autocorrelation(velocity, max_lag=MAX_LAG_S)
            good = np.isfinite(correlation)
            total[: correlation.size][good] += correlation[good]
            count[: correlation.size][good] += 1
            segments += 1
        if read >= limit:
            break

    if segments < 100:
        print(f"{discipline}: only {segments} segments at 1 Hz; not reported")
        return {}

    curve = total / np.maximum(count, 1)
    trough = MIN_SEARCH_S + int(np.argmin(curve[MIN_SEARCH_S : MAX_SEARCH_S + 1]))
    crest = trough + int(np.argmax(curve[trough : min(trough + 25, MAX_LAG_S + 1)]))
    macros = {
        f"StatCircling{tag}Segments": f"{segments}",
        f"StatCircling{tag}TroughS": f"{trough}",
        f"StatCircling{tag}Trough": f"{curve[trough]:+.3f}",
        f"StatCircling{tag}CrestS": f"{crest}",
        f"StatCircling{tag}Crest": f"{curve[crest]:+.3f}",
        f"StatCircling{tag}Amplitude": f"{curve[crest] - curve[trough]:+.3f}",
        f"StatCircling{tag}Min": f"{np.min(curve[1:]):+.3f}",
    }
    print(
        f"{discipline}: {segments} segments at 1 Hz | trough {curve[trough]:+.3f} at "
        f"{trough} s, crest {curve[crest]:+.3f} at {crest} s | never negative: "
        f"{'yes' if curve[1:].min() > 0 else 'NO'}"
    )
    return macros


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=25000, help="flights read per discipline")
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
        print("nothing reachable; circling.tex not written")
        return 1
    refusal = partial_write_refusal(
        missing, OUT_TEX.name, allow_partial=args.allow_partial,
        reasons=[unreachable_reason(DISCIPLINES[d]) for d in missing],
    )
    if refusal:
        print(refusal)
        return 1
    write_macros(
        OUT_TEX, macros, generator="scripts/reporting/ch3_global_transport/measure_circling.py", sort=True
    )
    print(f"wrote {OUT_TEX.name} ({len(macros)} macros)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
