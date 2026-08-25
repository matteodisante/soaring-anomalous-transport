#!/usr/bin/env python3
r"""Check the processed dataset against the invariants the thesis claims for it.

``scripts/preprocess.py`` writes four tables; this reads back the three that carry the
invariants -- fixes, segments and flight metadata -- and tests, on the data itself, the
properties Chapter 2 states. Each check names the section it comes
from, so a failure says which claim is false rather than only that something is wrong:

* **completeness** (sec:uniform) -- within a retained segment every grid point carries a
  defined ``(E, N, z)``; no ``nan`` reaches the analysis;
* **uniform, monotone time base** (sec:uniform) -- inside a segment the clock is
  strictly increasing and the step is constant to a tolerance;
* **no impossible step between two measured samples** (sec:fixlevel, the postcondition)
  -- a step past the discipline's ``v_xy`` bound is a transition of unknown course and
  must be a segment boundary, never flown path. Three separate archive defects turned
  out to violate it, which is why the check exists as a check. It is read between
  samples that are both *measured* and *centred*, because the other two cases are
  reconstruction and the table flags them as such: at a segment edge the filter is
  evaluated off-centre (sec:savgol), and across a bridged gap the monotone cubic can
  exceed the secant it spans. Their excess is counted and reported instead -- that
  number is one of the acceptance criteria sec:savgol asks for, and it is a measurement,
  not a broken invariant;
* **the origin** (sec:enu, sec:notation) -- the first fix of the first retained segment
  sits at the frame origin, to within the metre-scale offset the smoothing leaves at a
  segment edge;
* **no measured position out of reach of its own origin** -- ``|r(t)| <= v_max t``,
  since the flight started at the origin and cannot have left it faster than the bound
  allows. It is stated in terms of nothing but the frame and the bound, so it holds
  whatever the pipeline did, and it catches the failure a per-step check cannot see: a
  flight whose *origin fix* was corrupt keeps every step plausible while sitting
  thousands of kilometres from where it began. Like the step bound it is a claim about
  *measured* motion, so a reconstructed sample is reported rather than failed;
* **referential integrity** -- every ``flight_id`` in ``fixes`` is a retained flight in
  ``flights_meta``, and every segment's row count matches ``segments.n_fix``.

It streams the Parquet row groups, so it runs on the full archive without loading it.
Exit code is non-zero if any check fails, which makes it usable as a gate.

    SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... \
    uv run python scripts/verify_dataset.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

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

# The cleaning guarantees its bound on the *raw* fixes; every position in this table has
# since been through a Savitzky-Golay filter, which shifts an interior sample by a metre
# or two. A raw step just under the bound can read a few per cent over it here.
# The check exists to catch data defects, and what separates a defect from filter noise
# is orders of magnitude -- the ones it found were 40 km and 400 km in one second -- so
# it fails on a gross excess and reports the small ones with their size.
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
    retained = set(meta.loc[meta["drop_reason"].isna(), "flight_id"])
    declared = (
        segments[segments["kept"]]
        .set_index(["flight_id", "segment_id"])["n_fix"]
        .to_dict()
    )

    seen: set[str] = set()
    counted: dict[tuple, int] = {}
    n_nan = n_backwards = n_ragged = n_impossible = n_off_origin = 0
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
        n_nan += int(frame[_KINEMATIC].isna().to_numpy().sum())
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
            # A step is a claim about measured motion only when both its ends are
            # measured and centred. An edge sample is an off-centre evaluation of the
            # filter and an interpolated one is a reconstruction; the table flags both,
            # and sec:savgol asks for the excess on them to be *measured*, not assumed
            # away. So they are counted and reported, and only the rest can fail.
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
            # The displacement across a *retained* segment boundary. A boundary at a
            # gap leaves the position on either side genuine; one at a re-acquisition
            # offset does not, and everything after it carries an unknown constant that
            # enters the ensemble MSD (absolute position) and cancels out of the
            # time-averaged one (increments). Reported, never asserted: the point is to
            # bound the effect on the ensemble the analysis actually uses, which the
            # per-flight `split_jump_max_m` cannot do because it is measured before
            # trimming and so counts jumps inside a ground phase.
            #
            # The two kinds are told apart by the bound itself, with no extra column.
            # A boundary at a *gap* is a stretch the recorder missed and the wing flew:
            # the displacement across it is genuine and satisfies |dr| <= v_max dt like
            # any other motion. A boundary at a re-acquisition *offset* exists precisely
            # because that inequality failed. So the same speed bound separates them,
            # and only the second kind puts an unknown constant into the absolute
            # position. Reporting one number for both would have been useless: over the
            # archive the median boundary displacement is 381 m and the maximum 237 km,
            # and almost all of it is a wing flying across a hole in its own log.
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
            # Reachability, with the same qualification the step check carries and for
            # the same reason: a reconstructed sample is not a measurement. This is the
            # third invariant in this file to have been stated without it and the third
            # to have been wrong -- every one of the 188 samples that failed the
            # unqualified form was an interpolated grid point at t = 5 to 15 s, where
            # v_max t is still only a couple of hundred metres and the monotone cubic
            # bridging the flight's first gap lands 50 to 190 m beyond it. The wing was
            # somewhere in between; the interpolant guessed, and a guess is not a claim
            # about measured motion. Any check added here should start from the same
            # question: is this sample a measurement?
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

    if n_nan:
        failures.append(f"completeness (sec:uniform): {n_nan} nan in the kinematics")
    if n_backwards:
        failures.append(f"time base (sec:uniform): {n_backwards} non-increasing steps")
    if n_ragged:
        failures.append(f"uniformity (sec:uniform): {n_ragged} steps off the grid")
    if n_impossible:
        failures.append(
            f"postcondition (sec:fixlevel): {n_impossible} measured in-segment steps "
            f"exceed {_GROSS_EXCESS:.0f}x the {max_speed_mps:.0f} m/s bound "
            f"(worst {worst_step:.0f} m/s) -- that is a data defect, not filter noise"
        )
    if n_off_origin:
        failures.append(f"origin (sec:enu): {n_off_origin} flights not at r(0) = 0")
    if n_unreachable_recon:
        print(
            f"[{discipline}] {n_unreachable_recon} reconstructed samples beyond "
            f"{max_speed_mps:.0f} m/s of the origin (interpolated or edge; reported, "
            "not a failure)"
        )
    if n_unreachable:
        failures.append(
            f"reachability (sec:enu): {n_unreachable} measured positions lie further "
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
    mismatched = [k for k, n in counted.items() if declared.get(k) != n]
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
            "flights -- almost all of it a wing flying across a hole in its own log"
        )
    if offset_jumps:
        off = np.asarray(offset_jumps)
        print(
            f"[{discipline}] of those, the ones the speed bound cannot explain (a "
            f"re-acquisition offset, which does put an unknown constant into the "
            f"absolute position): {off.size:,} flights, median {np.median(off):.0f} m, "
            f"p90 {np.percentile(off, 90) / 1000:.1f} km, max {off.max() / 1000:.1f} km"
        )
    else:
        print(f"[{discipline}] none of them exceeds what the speed bound allows")
    print(
        f"[{discipline}] {n_rows:,} rows, {len(seen):,} flights, "
        f"{len(counted):,} segments | worst measured speed {worst_step:.1f} m/s | "
        f"steps over the bound: {n_reconstructed_over:,} reconstructed, "
        f"{n_marginal:,} measured but within {_GROSS_EXCESS:.0f}x, of {n_steps:,} "
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
    # The reductions already refuse this, and for the reason that applies here twice over:
    # ``verify.tex`` is rewritten wholesale, so one unreachable data root does not leave the
    # other discipline's macros alone -- it deletes them. The build then dies hundreds of
    # lines later on an undefined control sequence inside \SI{}, naming the sentence rather
    # than the root that was never exported. Fatal by default; the escape hatch is asked for.
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="write the macros for whichever disciplines are reachable, instead of failing",
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
            print("  every invariant holds.")
        total += len(failures)

    if missing and not args.allow_partial:
        roots = ", ".join(DISCIPLINES[d].env for d in missing)
        print(
            f"\nUnreachable: {', '.join(missing)}. verify.tex NOT rewritten -- it would have "
            f"lost the macros of the missing discipline and broken the build with an error "
            f"naming the wrong line. Export {roots}, or pass --allow-partial."
        )
        return 1

    if quoted:
        out = (
            Path(__file__).resolve().parents[1] / "thesis" / "generated" / "verify.tex"
        )
        write_macros(
            out, quoted, generator="scripts/verify_dataset.py", sort=True
        )
        print(f"Wrote {out.name} ({len(quoted)} macros).")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
