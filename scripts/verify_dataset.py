#!/usr/bin/env python3
r"""Check processed-table integrity and report filtered kinematic anomalies.

Structural requirements are finite kinematics, increasing uniform time inside segments,
matching retained flights and segment counts, and unique metadata keys. Speed, origin
and reach checks use operational tolerances on the filtered coordinates: they flag
anomalies requiring investigation, not proven sensor errors. Every stored coordinate
has been smoothed, including interior rows with no interpolation flag.

Tables are streamed by whole flight across Parquet row-group boundaries. A failing
check returns nonzero and does not replace the thesis macros.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

GENERATED_OUTPUTS = ("verify.tex",)

ROOT = Path(__file__).resolve().parents[1]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES, write_macros  # noqa: E402

# The smoothing evaluates the edge samples off-centre, so the stored position at the
# origin is the filter's estimate there rather than an exact zero: metres, not microns.
_ORIGIN_TOLERANCE_M = 50.0

# The grid step may wander by this much within a segment before the series stops being
# uniform in any useful sense (float32 storage of a time in the tens of thousands of
# seconds is itself worth a few milliseconds).
_STEP_TOLERANCE_S = 0.05

_KINEMATIC = ["t", "E", "N", "z", "v_E", "v_N", "v_z", "a_E", "a_N", "a_z"]

# An operational gross-anomaly gate on filtered interior steps. Savitzky--Golay
# overshoot is possible; passing/failing this threshold does not identify its cause.
_GROSS_EXCESS = 2.0


def verify(
    discipline: str, derived: Path, max_speed_mps: float
) -> tuple[list[str], dict[str, str]]:
    """Run every check over one discipline's tables.

    Returns:
        ``(failures, macros)``. The macros are the few numbers this script measures
        that the thesis quotes -- the re-acquisition offsets above all, which no
        other script computes because telling them from an ordinary gap crossing
        needs the written table and the speed bound together. They go through the
        same generated-macro contract as every other quoted figure, rather than
        being read off a console and typed into the text.
    """
    import pandas as pd

    from soaring.analysis.derived import stream_flights

    failures: list[str] = []
    meta = pd.read_parquet(derived / "flights_meta.parquet")
    segments = pd.read_parquet(derived / "segments.parquet")
    meta["flight_id"] = meta["flight_id"].astype(str)
    segments["flight_id"] = segments["flight_id"].astype(str)
    if meta["flight_id"].duplicated().any():
        failures.append("integrity: duplicate flight_id in flights_meta")
    if segments.duplicated(["flight_id", "segment_id"]).any():
        failures.append("integrity: duplicate (flight_id, segment_id) in segments")
    from soaring.analysis.preproc.pipeline import DROP_ERROR

    failed = meta["drop_reason"].eq(DROP_ERROR)
    if "drop_stage" in meta:
        failed |= meta["drop_stage"].eq("error")
    if failed.any():
        columns = [name for name in ("flight_id", "error_detail") if name in meta]
        examples = meta.loc[failed, columns].head(3).to_dict("records")
        failures.append(
            f"pipeline errors: {int(failed.sum())} flights; examples={examples}"
        )
    retained = set(meta.loc[meta["drop_reason"].isna(), "flight_id"])
    if (segments.loc[segments["kept"], "n_fix"] <= 0).any():
        failures.append("integrity: a retained segment declares no fixes")
    declared = (
        segments[segments["kept"]]
        .set_index(["flight_id", "segment_id"])["n_fix"]
        .to_dict()
    )

    seen: set[str] = set()
    counted: dict[tuple, int] = {}
    n_nonfinite = n_backwards = n_ragged = n_impossible = n_off_origin = 0
    n_reconstructed_over = n_marginal = n_steps = n_unreachable = n_rows = 0
    n_unreachable_recon = 0
    worst_step = 0.0
    boundary_jumps: list[float] = []
    offset_jumps: list[float] = []
    # Whole flights, not row groups. Read a row group at a time and a segment straddling
    # its boundary arrives in two pieces, and the step *between* them -- the one joining
    # the pieces -- is never differenced, so it is never checked. A check with a blind
    # spot reports success over it, which is the one failure mode a verifier must not
    # have (see soaring.analysis.derived).
    for frame in stream_flights(derived / "fixes.parquet"):
        n_rows += len(frame)
        n_nonfinite += int(
            (~np.isfinite(frame[_KINEMATIC].to_numpy(dtype=float))).sum()
        )
        frame["flight_id"] = frame["flight_id"].astype(str)
        seen |= set(frame["flight_id"].unique())
        for key, segment in frame.groupby(["flight_id", "segment_id"], sort=False):
            counted[key] = counted.get(key, 0) + len(segment)
            t = segment["t"].to_numpy(dtype=float)
            if t.size < 2:
                continue
            step = np.diff(t)
            n_backwards += int((step <= 0).sum())
            n_ragged += int((np.abs(step - np.median(step)) > _STEP_TOLERANCE_S).sum())
            distance = np.hypot(
                np.diff(segment["E"].to_numpy(dtype=float)),
                np.diff(segment["N"].to_numpy(dtype=float)),
            )
            with np.errstate(divide="ignore", invalid="ignore"):
                speed = np.where(step > 0, distance / step, 0.0)
            over = speed > max_speed_mps
            # Interior filtered estimates and edge/interpolated estimates are
            # reported separately; neither category is an untouched measurement.
            reconstructed = segment["edge"].to_numpy(dtype=bool) | segment[
                "interpolated"
            ].to_numpy(dtype=bool)
            touched = reconstructed[:-1] | reconstructed[1:]
            gross = speed > _GROSS_EXCESS * max_speed_mps
            n_impossible += int((gross & ~touched).sum())
            n_marginal += int((over & ~gross & ~touched).sum())
            n_reconstructed_over += int((over & touched).sum())
            n_steps += int(step.size)
            worst_step = max(worst_step, float(speed[~touched].max(initial=0.0)))
        for _, flight in frame.groupby("flight_id", sort=False):
            ordered = flight.sort_values("t")
            first = ordered.iloc[0]
            if first["t"] == 0.0 and (
                abs(first["E"]) > _ORIGIN_TOLERANCE_M
                or abs(first["N"]) > _ORIGIN_TOLERANCE_M
            ):
                n_off_origin += 1
            # Boundary displacement and excess against the configured reach envelope
            # are descriptive. They do not distinguish reacquisition error from every
            # physical, interpolation or reference-frame mechanism.
            edges = np.flatnonzero(np.diff(ordered["segment_id"].to_numpy()))
            if edges.size:
                east = ordered["E"].to_numpy(dtype=float)
                north = ordered["N"].to_numpy(dtype=float)
                span = np.diff(ordered["t"].to_numpy(dtype=float))[edges]
                jump = np.hypot(np.diff(east)[edges], np.diff(north)[edges])
                offset = jump > max_speed_mps * span + _ORIGIN_TOLERANCE_M
                boundary_jumps.append(jump.max())
                if offset.any():
                    offset_jumps.append(float(jump[offset].max()))
            # Apply the reach envelope with the declared origin tolerance. Filtering
            # can shift the origin and local positions, so this is an anomaly check.
            reach = np.hypot(
                ordered["E"].to_numpy(dtype=float), ordered["N"].to_numpy(dtype=float)
            )
            allowed = max_speed_mps * ordered["t"].to_numpy(dtype=float)
            beyond = reach > allowed + _ORIGIN_TOLERANCE_M
            invented = ordered["interpolated"].to_numpy(dtype=bool) | ordered[
                "edge"
            ].to_numpy(dtype=bool)
            n_unreachable += int((beyond & ~invented).sum())
            n_unreachable_recon += int((beyond & invented).sum())

    if n_nonfinite:
        failures.append(
            f"completeness (sec:uniform): {n_nonfinite} non-finite "
            "values in the kinematics"
        )
    if n_backwards:
        failures.append(f"time base (sec:uniform): {n_backwards} non-increasing steps")
    if n_ragged:
        failures.append(f"uniformity (sec:uniform): {n_ragged} steps off the grid")
    if n_impossible:
        failures.append(
            f"kinematic anomaly (sec:fixlevel): {n_impossible} filtered interior steps "
            f"exceed {_GROSS_EXCESS:.0f}x the {max_speed_mps:.0f} m/s bound "
            f"(worst {worst_step:.0f} m/s); investigate data and filtering"
        )
    if n_off_origin:
        failures.append(
            f"origin anomaly (sec:enu): {n_off_origin} flights exceed the "
            f"{_ORIGIN_TOLERANCE_M:g} m coordinate tolerance at t=0"
        )
    if n_unreachable_recon:
        print(
            f"[{discipline}] {n_unreachable_recon} reconstructed samples beyond "
            f"{max_speed_mps:.0f} m/s of the origin (interpolated or edge; reported, "
            "not a failure)"
        )
    if n_unreachable:
        failures.append(
            f"reachability (sec:enu): {n_unreachable} filtered interior positions "
            "lie further "
            f"from the origin than {max_speed_mps:.0f} m/s allows"
        )
    # Both directions. Testing only `seen - retained` asks whether the table holds
    # anything it should not, and says nothing about what it is *missing* -- so a run
    # that lost an arbitrary share of its flights (a worker that died, a batch never
    # flushed, a writer closed early) passed every check and printed success. The second
    # direction is the one that catches a truncated file, which is exactly the failure a
    # long unattended run has.
    if seen - retained:
        failures.append(
            f"integrity: {len(seen - retained)} flight_id in fixes are not retained"
        )
    if retained - seen:
        failures.append(
            f"integrity: {len(retained - seen)} flights are retained in flights_meta "
            "but have no rows in fixes"
        )
    mismatched = [
        k for k in counted.keys() | declared.keys() if counted.get(k) != declared.get(k)
    ]
    if mismatched:
        failures.append(
            f"integrity: {len(mismatched)} segments whose row count differs from "
            "segments.n_fix"
        )
    if boundary_jumps:
        jumps = np.asarray(boundary_jumps)
        print(
            f"[{discipline}] displacement across a retained segment boundary: "
            f"median {np.median(jumps):.0f} m, p90 {np.percentile(jumps, 90):.0f} m, "
            f"max {jumps.max() / 1000:.1f} km, on {jumps.size:,} of {len(seen):,} "
            "flights"
        )
    if offset_jumps:
        off = np.asarray(offset_jumps)
        print(
            f"[{discipline}] boundaries exceeding the speed-envelope diagnostic: "
            f"{off.size:,} flights, median {np.median(off):.0f} m, "
            f"p90 {np.percentile(off, 90) / 1000:.1f} km, max {off.max() / 1000:.1f} km"
        )
    else:
        print(f"[{discipline}] none of them exceeds what the speed bound allows")
    print(
        f"[{discipline}] {n_rows:,} rows, {len(seen):,} flights, "
        f"{len(counted):,} segments | worst filtered interior speed "
        f"{worst_step:.1f} m/s | "
        f"steps over the bound: {n_reconstructed_over:,} reconstructed, "
        f"{n_marginal:,} filtered interior within {_GROSS_EXCESS:.0f}x, of {n_steps:,} "
        f"({100 * (n_reconstructed_over + n_marginal) / max(n_steps, 1):.4f} %)"
    )
    tag = "Para" if discipline.startswith("para") else "Hang"
    macros = {
        f"StatVerify{tag}FlightsWithBoundary": f"{len(boundary_jumps)}",
        # The excess on reconstructed samples, quoted rather than left on the console.
        # sec:savgol asks for it to be measured, and the ensemble MSD is the consumer
        # that does *not* qualify its samples the way this file does: it reads every
        # fix, edge ones included, so the size of the excess is the size of what enters
        # the short-lag end of that curve.
        f"StatVerify{tag}EdgeStepsOver": f"{n_reconstructed_over}",
        f"StatVerify{tag}EdgeStepsPct": (
            f"{100.0 * n_reconstructed_over / max(n_steps, 1):.4f}"
        ),
        f"StatVerify{tag}MeasuredStepsOver": f"{n_marginal}",
        f"StatVerify{tag}WorstMeasuredMs": f"{worst_step:.0f}",
    }
    if offset_jumps:
        off = np.asarray(offset_jumps)
        macros |= {
            f"StatVerify{tag}OffsetFlights": f"{off.size}",
            f"StatVerify{tag}OffsetPct": f"{100.0 * off.size / max(len(seen), 1):.3f}",
            f"StatVerify{tag}OffsetMedianM": f"{np.median(off):.0f}",
            # Spelled out: a LaTeX control sequence takes letters only, so a "90"
            # in the name makes the definition itself unparseable.
            f"StatVerify{tag}OffsetPNinetyKm": f"{np.percentile(off, 90) / 1000:.1f}",
            f"StatVerify{tag}OffsetMaxKm": f"{off.max() / 1000:.1f}",
        }
    else:
        macros[f"StatVerify{tag}OffsetFlights"] = "0"
    return failures, macros


def main() -> int:
    """Verify every reachable discipline; non-zero exit if any invariant fails."""
    import argparse

    from soaring.analysis.config import load_preproc_config

    parser = argparse.ArgumentParser(description=__doc__)
    # Refuse partial macro files unless the caller explicitly requests one.
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="allow a macro file containing only the reachable disciplines",
    )
    args = parser.parse_args()

    cfg = load_preproc_config()
    total = 0
    missing: list[str] = []
    quoted: dict[str, str] = {}
    for discipline in DISCIPLINES:
        derived = DISCIPLINES[discipline].derived_dir()
        if derived is None:
            print(f"[{discipline}] no processed dataset; skipped.")
            missing.append(discipline)
            continue
        failures, macros = verify(
            discipline, derived, cfg.fix.max_horizontal_speed_mps[discipline]
        )
        quoted |= macros
        for failure in failures:
            print(f"  FAIL  {failure}")
        if not failures:
            print(
                "  structural checks passed; kinematic anomalies are within "
                "the adopted tolerances."
            )
        total += len(failures)

    if missing and not args.allow_partial:
        roots = ", ".join(DISCIPLINES[d].env for d in missing)
        print(f"Unreachable: {', '.join(missing)}. verify.tex not replaced.")
        print(f"Export {roots}, or pass --allow-partial.")
        return 1

    if total:
        print("Verification failed; verify.tex was not replaced.")
        return 1

    if quoted:
        out = (
            Path(__file__).resolve().parents[1] / "thesis" / "generated" / "verify.tex"
        )
        write_macros(out, quoted, generator="scripts/verify_dataset.py", sort=True)
        print(f"Wrote {out.name} ({len(quoted)} macros).")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
