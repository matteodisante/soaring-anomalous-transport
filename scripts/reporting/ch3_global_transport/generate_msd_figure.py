#!/usr/bin/env python3
r"""Reduce the MSD pass into Chapter 3's opening measurement, figure and macros.

Reads what ``measure_msd.py`` wrote --- the ensemble and time-averaged MSD, their
east-only and north-only twins (Sec. 3.5), and the fixed-duration cohorts, each with the
per-flight or per-segment samples the bootstrap needs --- and produces:

* ``thesis/generated/msd.pdf`` -- the three-panel figure of
  :func:`soaring.analysis.figures.msd.make_msd_figure`: the ensemble MSD with its fitted
  power law, the local logarithmic slope, and the number of flights contributing at each
  lag;
* ``thesis/generated/msd_curve.csv`` -- every curve, one row per lag per discipline, so a
  number in the text can be traced to the data behind it;
* ``thesis/generated/msd.tex`` -- the ``\\StatMsd*``/``\\StatMsdTa*`` macros the thesis
  quotes.

Costs seconds, not minutes: the traversal of ``fixes.parquet`` happens once, in
``measure_msd.py``, and its output is meant to be kept -- on the SSD beside the raw
archive, not under a temp directory a reboot clears -- so that a change to a fit range, a
bootstrap count, or a figure's styling costs this reduction and not that pass again.

The fit range is not free. Its lower end is physics -- above the thermalling period, so
the fit sees transport and not circling -- and its upper end follows from the ensemble
thinning out with the lag: past it the average is over the flights that kept going
rather than over the population. Both ends are reported with the exponent.

Run it after ``measure_msd.py``, with a shared ``--out`` / ``--audit-dir``::

    uv run python scripts/reporting/ch3_global_transport/measure_msd.py --out "$AUDIT_DIR"
    uv run python scripts/reporting/ch3_global_transport/generate_msd_figure.py --audit-dir "$AUDIT_DIR"
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT_FIG = ROOT / "thesis" / "generated" / "msd.pdf"
OUT_CSV = ROOT / "thesis" / "generated" / "msd_curve.csv"
OUT_TEX = ROOT / "thesis" / "generated" / "msd.tex"

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES, write_macros  # noqa: E402

# The fit starts above the thermalling period (~30 s) by a comfortable margin, so that
# what it measures is transport rather than the circling superimposed on it.
FIT_MIN_S = 120.0

# Matches measure_msd.py's own COHORTS_S -- kept apart rather than imported, the same way
# ORDERS/AXIS_ORDERS are duplicated between measure_variations.py and
# generate_transport_figure.py: the two scripts do not import from each other.
COHORTS_S = (3600.0, 7200.0, 14_400.0)

# Macro names are spelled out because a LaTeX control sequence takes letters only.
_HOURS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 6: "Six", 8: "Eight"}

# East/north twins of the two headline estimators (Sec. 3.5). Not the cohorts, which stay
# pooled -- tripling those too was not asked for and the axis question is about the
# exponent, not about the selection control.
AXIS_NAMES = ("ensemble_east", "ensemble_north", "ta_east", "ta_north")

# Deterministic PDF metadata -> committing the figure produces clean diffs.
_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def _load_result(data, prefix: str):
    """Reconstruct one ``MSDResult`` from the named arrays ``measure_msd.py`` wrote."""
    from soaring.analysis.observables.transport import MSDResult

    return MSDResult(
        t=data[f"{prefix}_t"],
        msd=data[f"{prefix}_msd"],
        n_flights=data[f"{prefix}_n"],
        sem=data[f"{prefix}_sem"],
        p10=data[f"{prefix}_p10"] if f"{prefix}_p10" in data else None,
        p50=data[f"{prefix}_p50"] if f"{prefix}_p50" in data else None,
        p90=data[f"{prefix}_p90"] if f"{prefix}_p90" in data else None,
    )


def _load_samples(data, prefix: str):
    key = f"{prefix}_samples"
    return data[key] if key in data else None


def load(slug: str, audit_dir: Path):
    """Everything one discipline's pass wrote, or ``None`` if it has not run."""
    path = audit_dir / f"msd_{slug}.npz"
    if not path.is_file():
        return None
    data = np.load(path)
    return {
        "result": _load_result(data, "ensemble"),
        "samples": _load_samples(data, "ensemble"),
        "ta_result": _load_result(data, "time_averaged"),
        "ta_samples": _load_samples(data, "time_averaged"),
        "axis_results": {
            name: (_load_result(data, name), _load_samples(data, name))
            for name in AXIS_NAMES
        },
        "cohort_results": {t: _load_result(data, f"cohort_{int(t)}") for t in COHORTS_S},
        "ta_cohort_results": {
            t: _load_result(data, f"ta_cohort_{int(t)}") for t in COHORTS_S
        },
        "n_flights": int(data["n_flights"]),
        "n_segments": int(data["n_segments"]),
    }


def _macro_name(discipline: str) -> str:
    """``paragliders`` -> ``Para``, ``hang gliders`` -> ``Hang``."""
    return "Para" if discipline.startswith("para") else "Hang"


def _cohort_fits(curves, reference, reach, pooled):
    """Each cohort fitted where its own population is complete, or dropped.

    The upper end is the reference range's, *capped at what the cohort's own threshold
    guarantees*. A cohort of flights lasting at least T has a fixed population only up to
    T -- past that its members start dropping out again and the control stops
    controlling, which would leave most of the artefact in place while appearing to
    measure it. ``reach`` converts a threshold into the largest lag it covers: the
    threshold itself for the ensemble, half of it for the time average, which reads a
    segment only to half its length.
    """
    from soaring.analysis.observables.transport import fit_msd_exponent

    out = {}
    for threshold, curve in curves.items():
        if not np.isfinite(curve.msd).any():
            continue
        upper = min(reference.t_max, reach(threshold))
        if upper <= reference.t_min:
            print(
                f"      cohort >= {threshold / 3600:.1f} h: no lag below its own "
                f"threshold falls inside the fit range; skipped"
            )
            continue
        try:
            cohort = fit_msd_exponent(
                curve, t_min_s=reference.t_min, t_max_s=upper, min_flights=30
            )
            # The pooled curve refitted on the *cohort's* range. Without it the
            # comparison is not like for like: capping each cohort at its own threshold
            # means each is read over a different span of lags, and the local slope is
            # not exactly constant across them, so part of any difference from the
            # pooled exponent is the shape of the curve rather than the change of
            # population the control is for. Refitting the pooled curve over the same
            # lags removes that part and leaves the one being asked about.
            same_range = fit_msd_exponent(
                pooled, t_min_s=reference.t_min, t_max_s=upper, min_flights=30
            )
            out[threshold] = (cohort, same_range)
        except ValueError:
            continue
    return out


def measure(discipline: str, loaded: dict, macros: dict) -> dict:
    """Fit every curve, run the bootstraps, and emit the macros for one discipline."""
    from soaring.analysis.observables.transport import (
        bootstrap_alpha_error,
        coverage_limited_range,
        fit_msd_exponent,
    )

    lags = loaded["result"].t
    n_flights, n_segments = loaded["n_flights"], loaded["n_segments"]

    result, samples = loaded["result"], loaded["samples"]
    t_min, t_max = coverage_limited_range(result, t_min_s=FIT_MIN_S)
    fit = fit_msd_exponent(result, t_min_s=t_min, t_max_s=t_max)
    boot = bootstrap_alpha_error(samples, lags, t_min_s=fit.t_min, t_max_s=fit.t_max)

    ta_result, ta_samples = loaded["ta_result"], loaded["ta_samples"]
    ta_min, ta_max = coverage_limited_range(ta_result, t_min_s=FIT_MIN_S)
    ta_fit = fit_msd_exponent(ta_result, t_min_s=ta_min, t_max_s=ta_max)
    ta_boot = bootstrap_alpha_error(
        ta_samples, lags, t_min_s=ta_fit.t_min, t_max_s=ta_fit.t_max
    )

    print(
        f"[{discipline}] {n_flights} flights, {n_segments} segments\n"
        f"    ensemble      alpha = {fit.alpha:.3f} +/- {boot:.3f} (bootstrap; "
        f"OLS would say {fit.alpha_err:.3f}) "
        f"on [{fit.t_min:.0f}, {fit.t_max:.0f}] s ({fit.n_points} lags)\n"
        f"    time-averaged alpha = {ta_fit.alpha:.3f} +/- {ta_boot:.3f} "
        f"(bootstrap; OLS {ta_fit.alpha_err:.3f}) "
        f"on [{ta_fit.t_min:.0f}, {ta_fit.t_max:.0f}] s ({ta_fit.n_points} lags)"
    )

    # East/north, fitted exactly like the pooled curve above -- same coverage-limited
    # range logic, same bootstrap. Coverage depends only on t/dt_s/length, never on the
    # position values, so this is not assumed to land on the pooled fit range; it is
    # verified to (sec:transport-axisroutes quotes the pooled StatMsd*FitMinS/FitMaxS
    # for the axis rows on the strength of that).
    axis_fits = {}
    for name, (axis_result, axis_samples) in loaded["axis_results"].items():
        a_min, a_max = coverage_limited_range(axis_result, t_min_s=FIT_MIN_S)
        axis_fit = fit_msd_exponent(axis_result, t_min_s=a_min, t_max_s=a_max)
        axis_boot = bootstrap_alpha_error(
            axis_samples, lags, t_min_s=axis_fit.t_min, t_max_s=axis_fit.t_max
        )
        axis_fits[name] = (axis_fit, axis_boot)

    # Each cohort read on its OWN range, then again on the pooled ensemble's range, so the
    # comparison is like for like: an exponent measured over a different span of lags is
    # not evidence about the same thing.
    cohort_fits = _cohort_fits(
        loaded["cohort_results"], fit, lambda threshold: threshold, result
    )
    # A segment answers a lag only while the lag stays under half its length
    # (TAMSDAccumulator.add), so a cohort of segments spanning at least T holds its
    # population only to T/2, not to T.
    ta_cohort_fits = _cohort_fits(
        loaded["ta_cohort_results"], ta_fit, lambda threshold: threshold / 2.0, ta_result
    )
    for name, fitted, curves_by_threshold, unit in (
        ("ensemble", cohort_fits, loaded["cohort_results"], "voli"),
        ("time-averaged", ta_cohort_fits, loaded["ta_cohort_results"], "segmenti"),
    ):
        if not fitted:
            continue
        print(f"    coorti ({name}), sullo stesso intervallo del fit:")
        for threshold, (cohort_fit, same_range) in sorted(fitted.items()):
            n_in = int(np.nanmax(curves_by_threshold[threshold].n_flights))
            print(
                f"      >= {threshold / 3600:.1f} h ({n_in:6d} {unit}): "
                f"alpha = {cohort_fit.alpha:.3f} against {same_range.alpha:.3f} "
                f"pooled on the same lags [{cohort_fit.t_min:.0f}, "
                f"{cohort_fit.t_max:.0f}] s -> "
                f"{cohort_fit.alpha - same_range.alpha:+.3f}"
            )

    tag = _macro_name(discipline)
    macros[f"StatMsd{tag}Alpha"] = f"{fit.alpha:.3f}"
    macros[f"StatMsd{tag}AlphaErr"] = f"{boot:.3f}"
    macros[f"StatMsd{tag}AlphaErrOls"] = f"{fit.alpha_err:.3f}"
    macros[f"StatMsd{tag}Hurst"] = f"{fit.alpha / 2:.3f}"
    macros[f"StatMsd{tag}FitMinS"] = f"{fit.t_min:.0f}"
    macros[f"StatMsd{tag}FitMaxS"] = f"{fit.t_max:.0f}"
    macros[f"StatMsd{tag}Flights"] = f"{n_flights}"
    macros[f"StatMsd{tag}Segments"] = f"{n_segments}"
    macros[f"StatMsdTa{tag}Alpha"] = f"{ta_fit.alpha:.3f}"
    macros[f"StatMsdTa{tag}AlphaErr"] = f"{ta_boot:.3f}"
    macros[f"StatMsdTa{tag}AlphaErrOls"] = f"{ta_fit.alpha_err:.3f}"
    macros[f"StatMsdTa{tag}Hurst"] = f"{ta_fit.alpha / 2:.3f}"
    macros[f"StatMsdTa{tag}FitMinS"] = f"{ta_fit.t_min:.0f}"
    macros[f"StatMsdTa{tag}FitMaxS"] = f"{ta_fit.t_max:.0f}"
    # The gap between the two averages, evaluated here rather than typeset as a
    # subtraction of two macros: LaTeX would print "1.918-1.732" where the sentence
    # promises a number.
    macros[f"StatMsd{tag}AlphaGap"] = f"{fit.alpha - ta_fit.alpha:.3f}"

    # East/north: sec:transport-axisroutes reads these against the pooled FitMinS/
    # FitMaxS/Flights/Segments macros above rather than duplicating them, since coverage
    # does not depend on the component.
    fit_ee, boot_ee = axis_fits["ensemble_east"]
    fit_en, boot_en = axis_fits["ensemble_north"]
    fit_te, boot_te = axis_fits["ta_east"]
    fit_tn, boot_tn = axis_fits["ta_north"]
    for prefix, axis_fit, axis_boot, name in (
        ("StatMsd", fit_ee, boot_ee, "East"),
        ("StatMsd", fit_en, boot_en, "North"),
        ("StatMsdTa", fit_te, boot_te, "East"),
        ("StatMsdTa", fit_tn, boot_tn, "North"),
    ):
        macros[f"{prefix}{tag}Alpha{name}"] = f"{axis_fit.alpha:.3f}"
        macros[f"{prefix}{tag}Alpha{name}Err"] = f"{axis_boot:.3f}"
        macros[f"{prefix}{tag}Alpha{name}ErrOls"] = f"{axis_fit.alpha_err:.3f}"
        macros[f"{prefix}{tag}Hurst{name}"] = f"{axis_fit.alpha / 2:.3f}"
        macros[f"{prefix}{tag}Hurst{name}Err"] = f"{axis_boot / 2:.3f}"
    # Read against the trustworthy time average, not against each other: the gap is the
    # diagnostic sec:transport-axisroutes uses to ask whether the withdrawn route's
    # contamination is itself isotropic.
    macros[f"StatMsd{tag}AlphaGapEast"] = f"{fit_ee.alpha - fit_te.alpha:.3f}"
    macros[f"StatMsd{tag}AlphaGapNorth"] = f"{fit_en.alpha - fit_tn.alpha:.3f}"

    # The cohort spread is the number the thesis needs: the largest departure of any
    # cohort's exponent from the pooled one. Small means the pooled exponent is not an
    # artefact of the ensemble thinning out.
    for prefix, fitted, reference in (
        ("StatMsd", cohort_fits, fit),
        ("StatMsdTa", ta_cohort_fits, ta_fit),
    ):
        if not fitted:
            continue
        # The spread is measured against the pooled curve *on the same lags*, so it is a
        # statement about the population and not about the range.
        spread = max(abs(c.alpha - r.alpha) for c, r in fitted.values())
        # The same figure read the naive way, against the pooled exponent over the
        # pooled range. Reported so the correction can be seen rather than asserted: on
        # the ensemble estimator most of that departure is the curve's shape.
        naive = max(abs(c.alpha - reference.alpha) for c, _ in fitted.values())
        macros[f"{prefix}{tag}CohortSpread"] = f"{spread:.3f}"
        macros[f"{prefix}{tag}CohortSpreadNaive"] = f"{naive:.3f}"
        macros[f"{prefix}{tag}CohortCount"] = f"{len(fitted)}"
        macros[f"{prefix}{tag}CohortMaxH"] = f"{max(fitted) / 3600:.0f}"
        for threshold, (cohort_fit, _) in sorted(fitted.items()):
            # Spelled, not printed: a LaTeX control sequence may contain only letters, so
            # `...CohortAlpha1H` parses as `...CohortAlpha` followed by `1H`, and
            # \newcommand then reads the 1 as an argument count and dies. The
            # macro-contract check cannot see this -- the macro *is* written, it is
            # merely unusable -- so only a build catches it, and only if something
            # quotes it.
            hours = _HOURS[int(threshold / 3600)]
            macros[f"{prefix}{tag}CohortAlpha{hours}H"] = f"{cohort_fit.alpha:.3f}"

    curves = [("ensemble", result), ("time_averaged", ta_result)]
    curves += [(name, axis_result) for name, (axis_result, _) in loaded["axis_results"].items()]
    curves += [
        (f"cohort_{int(threshold)}s", curve)
        for threshold, curve in sorted(loaded["cohort_results"].items())
    ]
    curves += [
        (f"ta_cohort_{int(threshold)}s", curve)
        for threshold, curve in sorted(loaded["ta_cohort_results"].items())
    ]

    return {"result": result, "fit": fit, "ta_result": ta_result, "ta_fit": ta_fit, "curves": curves}


def _draw(results, fits, ta_results, ta_fits) -> None:
    """Render and save the figure from curves already in hand."""
    from soaring.analysis.figures.msd import make_msd_figure

    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    make_msd_figure(results, fits, ta_results, ta_fits).savefig(
        OUT_FIG, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    print(f"Wrote {OUT_FIG.name}.")


def redraw() -> int:
    """Re-render the figure from ``msd_curve.csv``, without touching the archive.

    Streaming 10^9 rows to change a line style is a poor trade, and the curves are
    already written beside the figure so that a number in the text can be traced to the
    data behind it. The same file lets the drawing be redone. Nothing here recomputes an
    estimator, so a redraw gives the figure the full run would have given with the
    current plotting code, and the macros -- which *are* the estimators' output -- are
    left exactly as the run wrote them.
    """
    import pandas as pd

    from soaring.analysis.observables.transport import (
        MSDResult,
        coverage_limited_range,
        fit_msd_exponent,
    )

    if not OUT_CSV.is_file():
        print(f"{OUT_CSV} not found: run the full generator first.")
        return 1
    table = pd.read_csv(OUT_CSV)
    results: dict = {}
    fits: dict = {}
    ta_results: dict = {}
    ta_fits: dict = {}
    for discipline, block in table.groupby("discipline", sort=False):
        for estimator, into, fit_into in (
            ("ensemble", results, fits),
            ("time_averaged", ta_results, ta_fits),
        ):
            rows = block[block["estimator"] == estimator].sort_values("t_s")
            if rows.empty:
                continue
            curve = MSDResult(
                t=rows["t_s"].to_numpy(),
                msd=rows["msd_m2"].to_numpy(),
                n_flights=rows["n_flights"].to_numpy(),
                sem=rows["sem_m2"].to_numpy(),
                p10=rows["p10_m2"].to_numpy(),
                p50=rows["p50_m2"].to_numpy(),
                p90=rows["p90_m2"].to_numpy(),
            )
            into[discipline] = curve
            lo, hi = coverage_limited_range(curve, t_min_s=FIT_MIN_S)
            fit_into[discipline] = fit_msd_exponent(curve, t_min_s=lo, t_max_s=hi)
    if not results:
        print("no curves in the CSV.")
        return 1
    _draw(results, fits, ta_results, ta_fits)
    return 0


def main() -> int:
    """Reduce every discipline's pass output, fit it, and write the three artefacts."""
    import argparse

    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' group); keeping the committed figure.")
        return 0
    matplotlib.use("Agg")

    import pandas as pd

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    # Writing a file for one discipline when the thesis quotes both is the worst
    # available failure: the build dies hundreds of lines later on an undefined control
    # sequence, and the error names the sentence rather than the missing pass. So a
    # missing discipline is fatal by default, and the escape hatch has to be asked for.
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="write the macros for whichever disciplines are reachable, instead of failing",
    )
    args = parser.parse_args()

    macros: dict[str, str] = {}
    frames = []
    missing: list[str] = []
    results, fits, ta_results, ta_fits = {}, {}, {}, {}
    for discipline, glider in DISCIPLINES.items():
        slug = glider.slug
        loaded = load(slug, args.audit_dir)
        if loaded is None:
            print(f"{discipline}: MSD pass not found")
            missing.append(discipline)
            continue
        measured = measure(discipline, loaded, macros)
        results[discipline] = measured["result"]
        fits[discipline] = measured["fit"]
        ta_results[discipline] = measured["ta_result"]
        ta_fits[discipline] = measured["ta_fit"]
        for estimator, curve in measured["curves"]:
            frame = curve.to_frame()
            frame.insert(0, "estimator", estimator)
            frame.insert(0, "discipline", discipline)
            frames.append(frame)

    if missing and not args.allow_partial:
        print(
            f"{', '.join(missing)}: pass not reachable. msd.tex would be written for the "
            "other discipline alone and the thesis would fail to build on the macros this "
            "one owns. Re-run measure_msd.py, or pass --allow-partial if that is what you "
            "want."
        )
        return 1
    if not macros:
        print("no MSD pass reachable; msd.tex not written")
        return 0

    # The curve and the macros go out before the figure is drawn. A failure inside the
    # drawing code would otherwise take them down with it, which is exactly what happened
    # while `local_slope` was missing from the figure module. Saved first, a drawing bug
    # costs a figure rather than the reduction, and `--redraw` can finish the job from the
    # CSV -- which is what that mode is for.
    pd.concat(frames, ignore_index=True).to_csv(OUT_CSV, index=False)
    write_macros(
        OUT_TEX, dict(macros), generator="scripts/reporting/ch3_global_transport/generate_msd_figure.py"
    )
    print(f"Wrote {OUT_CSV.name} and {OUT_TEX.name}.")
    _draw(results, fits, ta_results, ta_fits)
    return 0


if __name__ == "__main__":
    # `--redraw` takes no further arguments and skips `main()`'s own parser entirely,
    # since it works from the already-written CSV rather than `--audit-dir`; checked on
    # the raw argv rather than through argparse, the same way the pass/reduction split
    # elsewhere in this repo keeps two entry points apart without one parser knowing
    # about the other's flags.
    raise SystemExit(redraw() if "--redraw" in sys.argv[1:] else main())
