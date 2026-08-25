#!/usr/bin/env python3
"""One streaming pass over ``fixes.parquet`` that materialises the MSD audit inputs.

The ensemble MSD hides its assumptions inside a single averaged curve: by the time the
curve exists, the per-flight information that would say *why* it has the shape it has is
gone. Every question the audit asks -- is the growth transport or a spread of flight
speeds, is the ensemble isotropic, does the shape survive on a fixed sub-population, is
the origin where the estimator thinks it is -- is a different reduction of the same
per-flight quantity, and re-reading a 43 GB table once per question is not affordable.

So this reads the table once and writes what every question needs:

``audit_positions_<discipline>.npz``
    ``E`` and ``N``: one row per flight, one column per lag of the shared grid, in
    metres, ``NaN`` where the flight does not cover that lag under the estimator's own
    coverage rule. ``r0_e``/``r0_n``: each flight's position at its first retained fix,
    which the current estimator assumes is the origin and which is not exactly zero.
``audit_flights_<discipline>.parquet``
    One row per flight: duration, path length, fix and segment counts, native step, the
    mean-velocity components, the largest step speed, and the coordinate extent.

Both are analysis products, not thesis products: they carry no macros and nothing in the
document depends on them. ``scripts/reporting/audit_msd_report.py`` reduces them.
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

# The lag grid of generate_msd_figure.py, so that the audit and the figure speak about
# the same lags and a discrepancy between them is a discrepancy of substance.
LAG_MIN_S, LAG_MAX_S, N_LAGS = 1.0, 43_200.0, 90

# The estimator's own floor on the coverage tolerance (transport.MSDAccumulator).
MIN_TOLERANCE_S = 0.5


def _sample_flight(times, east, north, lags):
    """The flight's ``E`` and ``N`` at each lag, ``NaN`` where it does not cover it.

    The coverage rule is :class:`~soaring.analysis.transport.MSDAccumulator`'s, copied
    rather than imported so that a change to the estimator shows up here as a
    disagreement instead of being silently tracked: nearest fix within half the flight's
    own native step, and never a lag below that step.
    """
    native_dt = float(np.median(np.diff(times)))
    tolerance = max(MIN_TOLERANCE_S, 0.5 * native_dt)

    pos = np.searchsorted(times, lags)
    left = np.clip(pos - 1, 0, times.size - 1)
    right = np.clip(pos, 0, times.size - 1)
    take_left = np.abs(times[left] - lags) <= np.abs(times[right] - lags)
    nearest = np.where(take_left, left, right)
    covered = (np.abs(times[nearest] - lags) <= tolerance) & (lags >= native_dt)

    e = np.where(covered, east[nearest], np.nan)
    n = np.where(covered, north[nearest], np.nan)
    return e.astype(np.float32), n.astype(np.float32), native_dt


def run(discipline: str, out_dir: Path) -> int:
    from soaring.analysis.derived import stream_flights

    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        print(f"{discipline}: derived/fixes.parquet not reachable, skipping")
        return 1

    lags = np.geomspace(LAG_MIN_S, LAG_MAX_S, N_LAGS)
    lags = np.unique(np.round(lags))
    lags = lags[lags > 0]

    rows: list[dict] = []
    e_rows: list[np.ndarray] = []
    n_rows: list[np.ndarray] = []
    r0: list[tuple[float, float]] = []

    for count, flight in enumerate(
        stream_flights(derived / "fixes.parquet", ["segment_id", "t", "E", "N"]), 1
    ):
        ordered = flight.sort_values(["t"], kind="stable")
        times = ordered["t"].to_numpy(dtype=float)
        east = ordered["E"].to_numpy(dtype=float)
        north = ordered["N"].to_numpy(dtype=float)
        if times.size < 2:
            continue

        e, n, native_dt = _sample_flight(times, east, north, lags)
        e_rows.append(e)
        n_rows.append(n)
        r0.append((float(east[0]), float(north[0])))

        # Path length and the largest step speed are computed *within* a segment: the
        # step across a gap is not a step the wing took at that rate.
        seg = ordered["segment_id"].to_numpy()
        boundary = np.diff(seg) != 0
        de, dn, dt = np.diff(east), np.diff(north), np.diff(times)
        step = np.hypot(de, dn)
        inside = ~boundary
        with np.errstate(divide="ignore", invalid="ignore"):
            speed = np.where(inside & (dt > 0), step / np.maximum(dt, 1e-9), np.nan)

        duration = float(times[-1] - times[0])
        rows.append(
            {
                "flight_id": str(ordered["flight_id"].iloc[0]),
                "n_fix": int(times.size),
                "n_segments": int(np.unique(seg).size),
                "duration_s": duration,
                "native_dt_s": native_dt,
                "path_m": float(np.nansum(np.where(inside, step, 0.0))),
                "r0_e": float(east[0]),
                "r0_n": float(north[0]),
                "end_e": float(east[-1]),
                "end_n": float(north[-1]),
                # The mean velocity of the whole flight: the quantity a heterogeneous
                # ballistic population would write the whole MSD out of.
                "vbar_e": float((east[-1] - east[0]) / duration) if duration else np.nan,
                "vbar_n": float((north[-1] - north[0]) / duration)
                if duration
                else np.nan,
                "max_step_speed_ms": float(np.nanmax(speed)) if speed.size else np.nan,
                "extent_e_m": float(east.max() - east.min()),
                "extent_n_m": float(north.max() - north.min()),
                "n_nonfinite": int((~np.isfinite(east)).sum() + (~np.isfinite(north)).sum()),
                "t_monotone": bool(np.all(np.diff(times) > 0)),
            }
        )
        if count % 20_000 == 0:
            print(f"  {discipline}: {count} flights", flush=True)

    slug = "para" if discipline.startswith("para") else "hang"
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / f"audit_positions_{slug}.npz",
        lags=lags,
        E=np.vstack(e_rows),
        N=np.vstack(n_rows),
        r0=np.asarray(r0, dtype=np.float32),
    )
    pd.DataFrame(rows).to_parquet(out_dir / f"audit_flights_{slug}.parquet")
    print(f"{discipline}: {len(rows)} flights -> {out_dir}")
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
