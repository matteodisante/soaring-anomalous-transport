#!/usr/bin/env python3
r"""Compute the ensemble MSD from the processed dataset and render the thesis figure.

Reads the ``fixes.parquet`` that ``scripts/preprocess.py`` wrote under each discipline's
``<data_root>/derived/`` and produces:

* ``thesis/generated/msd.pdf`` -- the three-panel figure of
  :func:`soaring.analysis.transport.make_msd_figure`: the ensemble MSD with its fitted
  power law, the local logarithmic slope, and the number of flights contributing at each
  lag;
* ``thesis/generated/msd_curve.csv`` -- the curve itself, one row per lag per
  discipline, so a number in the text can be traced to the data behind it;
* ``thesis/generated/msd.tex`` -- the ``\\StatMsd*`` macros the thesis quotes.

The table is far too large to load (~10^9 rows over the full archive), so the curve is
accumulated by streaming, through :func:`soaring.analysis.derived.stream_flights`, which
reassembles the flights that straddle a Parquet row-group boundary. Iterating the row
groups directly is what this script used to do, on the assumption that the writer put
whole flights in each -- it does not, and the cost was a flight count too high by 0.7 %
and a time-averaged MSD missing its longest lags.

The fit range is not free. Its lower end is physics -- above the thermalling period, so
the fit sees transport and not circling -- and its upper end follows from the ensemble
thinning out with the lag: past it the average is over the flights that kept going
rather than over the population. Both ends are reported with the exponent.

Run it after ``scripts/preprocess.py``, with the same data roots::

    SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... \\
    uv run python scripts/reporting/generate_msd_figure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_FIG = ROOT / "thesis" / "generated" / "msd.pdf"
OUT_CSV = ROOT / "thesis" / "generated" / "msd_curve.csv"
OUT_TEX = ROOT / "thesis" / "generated" / "msd.tex"

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    bare_cli,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)

# Lag grid: from one native step of the fastest logger to twelve hours, the duration
# bound of the flight-level filter, geometrically spaced.
LAG_MIN_S, LAG_MAX_S, N_LAGS = 1.0, 43_200.0, 90

# The fit starts above the thermalling period (~30 s) by a comfortable margin, so that
# what it measures is transport rather than the circling superimposed on it.
FIT_MIN_S = 120.0

# Fixed-duration cohorts, in seconds: the control on the ensemble thinning out with the
# lag. All start above the 40 min retention floor, so each is a genuine sub-population
# and not the whole ensemble under another name, and they climb by roughly a factor of
# two so that a trend in alpha across them would be visible rather than a scatter.
COHORTS_S = (3600.0, 7200.0, 14_400.0)

# Macro names are spelled out because a LaTeX control sequence takes letters only.
_HOURS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 6: "Six", 8: "Eight"}

# Deterministic PDF metadata -> committing the figure produces clean diffs.
_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def _accumulate(path: Path, lags):
    """Stream one ``fixes.parquet`` past every accumulator, one whole flight at a time.

    Every estimator in one pass: the table is tens of gigabytes, and reading it twice to
    ask two questions of the same rows would double the only expensive step here.
    """
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.transport import (
        MSDAccumulator,
        TAMSDAccumulator,
    )

    ensemble = MSDAccumulator(lags)
    time_averaged = TAMSDAccumulator(lags)
    # The fixed-duration cohorts. Only flights lasting at least t contribute to MSD(t),
    # so the ensemble behind the curve *changes with the lag* and its long-lag end is an
    # average over the flights that kept going -- which are not a random sample of the
    # population. Reading an exponent off a curve whose population drifts underneath it
    # is the one methodological weakness of an ensemble MSD over records of unequal
    # length, and the count-per-lag panel shows the drift without controlling for it.
    # A cohort does control for it: within one, every flight is present at every lag of
    # the range, so the population is fixed by construction and any remaining growth is
    # motion. If alpha is the same across cohorts, selection is not what produces it.
    cohorts = {
        threshold: MSDAccumulator(lags, keep_samples=False) for threshold in COHORTS_S
    }
    # The same control for the time average, and for the same reason. A segment answers
    # a lag only while the lag is under half its length, so the long-lag end of the
    # time-averaged curve is an average over the long segments -- which belong to the
    # long flights, which are not a random sample either. Without this the comparison
    # between the two averages, on which the aging reading rests, would be a comparison
    # between two differently selected populations.
    ta_cohorts = {threshold: TAMSDAccumulator(lags) for threshold in COHORTS_S}
    n_flights = n_segments = 0
    for flight in stream_flights(path, ["segment_id", "t", "E", "N"]):
        ordered = flight.sort_values("t")
        times = ordered["t"].to_numpy()
        east, north = ordered["E"].to_numpy(), ordered["N"].to_numpy()
        ensemble.add(times, east, north)
        duration = float(times[-1]) if times.size else 0.0
        for threshold, accumulator in cohorts.items():
            if duration >= threshold:
                accumulator.add(times, east, north)
        n_flights += 1
        # The time average is taken inside a segment, never across the gap that
        # ends it (sec:uniform): the trajectory there is unknown.
        for _, segment in ordered.groupby("segment_id", sort=False):
            times = segment["t"].to_numpy()
            if times.size < 8:
                continue
            step = float(np.median(np.diff(times)))
            east_s, north_s = segment["E"].to_numpy(), segment["N"].to_numpy()
            time_averaged.add(east_s, north_s, step)
            span = float(times[-1] - times[0])
            for threshold, ta_cohort in ta_cohorts.items():
                if span >= threshold:
                    ta_cohort.add(east_s, north_s, step)
            n_segments += 1
    return (
        ensemble.result(),
        time_averaged.result(),
        {k: v.result() for k, v in cohorts.items()},
        {k: v.result() for k, v in ta_cohorts.items()},
        n_flights,
        n_segments,
        # Kept for the bootstrap: an uncertainty on the exponent that resamples flights
        # cannot be had from the averaged curve, and the least-squares error the fit
        # reports understates the truth about fivefold.
        ensemble.stacked_samples(),
        time_averaged.stacked_samples(),
    )


def _macro_name(discipline: str) -> str:
    """``paragliders`` -> ``Para``, ``hang gliders`` -> ``Hang``."""
    return "Para" if discipline.startswith("para") else "Hang"


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
    """Accumulate the curve per discipline, fit it, and write the three artefacts."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' group); keeping the committed figure.")
        return 0
    matplotlib.use("Agg")

    import pandas as pd

    from soaring.analysis.observables.transport import (
        bootstrap_alpha_error,
        coverage_limited_range,
        fit_msd_exponent,
        log_lag_grid,
    )

    # Before the traversal, not after it: reaching one discipline of two means nothing
    # will be written, and each pass over the fix table costs minutes to hours.
    unreachable = [d for d in DISCIPLINES if DISCIPLINES[d].derived_dir() is None]
    refusal = partial_write_refusal(
        unreachable, OUT_TEX.name,
        allow_partial="--allow-partial" in sys.argv[1:],
        reasons=[unreachable_reason(DISCIPLINES[d]) for d in unreachable],
    )
    if refusal:
        print(refusal)
        return 1

    lags = log_lag_grid(LAG_MAX_S, LAG_MIN_S, N_LAGS)
    results, fits, frames, macros = {}, {}, [], []
    ta_results, ta_fits = {}, {}
    for discipline in DISCIPLINES:
        derived = DISCIPLINES[discipline].derived_dir()
        if derived is None:
            print(f"[{discipline}] no processed dataset; skipped.")
            continue
        print(f"[{discipline}] streaming {derived / 'fixes.parquet'}...")
        (
            result,
            ta_result,
            cohort_results,
            ta_cohort_results,
            n_flights,
            n_segments,
            samples,
            ta_samples,
        ) = _accumulate(derived / "fixes.parquet", lags)
        t_min, t_max = coverage_limited_range(result, t_min_s=FIT_MIN_S)
        fit = fit_msd_exponent(result, t_min_s=t_min, t_max_s=t_max)
        results[discipline], fits[discipline] = result, fit
        ta_min, ta_max = coverage_limited_range(ta_result, t_min_s=FIT_MIN_S)
        ta_fit = fit_msd_exponent(ta_result, t_min_s=ta_min, t_max_s=ta_max)
        ta_results[discipline], ta_fits[discipline] = ta_result, ta_fit
        # The uncertainty that is reported is the bootstrap one. The OLS error stays
        # in the CSV as a diagnostic, never as the quoted +/-.
        boot = bootstrap_alpha_error(
            samples, lags, t_min_s=fit.t_min, t_max_s=fit.t_max
        )
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

        # Each cohort read on its OWN range, then again on the pooled ensemble's range,
        # so the comparison is like for like: an exponent measured over a different span
        # of lags is not evidence about the same thing.
        def _cohort_fits(curves, reference, reach, pooled):
            """Each cohort fitted where its own population is complete, or dropped.

            The upper end is the reference range's, *capped at what the cohort's own
            threshold guarantees*. A cohort of flights lasting at least T has a fixed
            population only up to T -- past that its members start dropping out again
            and the control stops controlling, which would leave most of the artefact
            in place while appearing to measure it. `reach` converts a threshold into
            the largest lag it covers: the threshold itself for the ensemble, half of
            it for the time average, which reads a segment only to half its length.
            """
            out = {}
            for threshold, curve in curves.items():
                if not np.isfinite(curve.msd).any():
                    continue
                upper = min(reference.t_max, reach(threshold))
                if upper <= reference.t_min:
                    print(
                        f"      cohort >= {threshold / 3600:.1f} h: no lag below its "
                        f"own threshold falls inside the fit range; skipped"
                    )
                    continue
                try:
                    cohort = fit_msd_exponent(
                        curve, t_min_s=reference.t_min, t_max_s=upper, min_flights=30
                    )
                    # The pooled curve refitted on the *cohort's* range. Without it
                    # the comparison is not like for like: capping each cohort at its
                    # own threshold means each is read over a different span of lags,
                    # and the local slope is not exactly constant across them (panel
                    # c), so part of any difference from the pooled exponent is the
                    # shape of the curve rather than the change of population the
                    # control is for. Refitting the pooled curve over the same lags
                    # removes that part and leaves the one being asked about.
                    same_range = fit_msd_exponent(
                        pooled, t_min_s=reference.t_min, t_max_s=upper, min_flights=30
                    )
                    out[threshold] = (cohort, same_range)
                except ValueError:
                    continue
            return out

        cohort_fits = _cohort_fits(
            cohort_results, fit, lambda threshold: threshold, result
        )
        # A segment answers a lag only while the lag stays under half its
        # length (TAMSDAccumulator.add), so a cohort of segments spanning at
        # least T holds its population only to T/2, not to T.
        ta_cohort_fits = _cohort_fits(
            ta_cohort_results, ta_fit, lambda threshold: threshold / 2.0, ta_result
        )
        for name, fitted, curves_by_threshold, unit in (
            ("ensemble", cohort_fits, cohort_results, "voli"),
            ("time-averaged", ta_cohort_fits, ta_cohort_results, "segmenti"),
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

        curves = [("ensemble", result), ("time_averaged", ta_result)]
        curves += [
            (f"cohort_{int(threshold)}s", curve)
            for threshold, curve in sorted(cohort_results.items())
        ]
        curves += [
            (f"ta_cohort_{int(threshold)}s", curve)
            for threshold, curve in sorted(ta_cohort_results.items())
        ]
        for estimator, curve in curves:
            frame = curve.to_frame()
            frame.insert(0, "estimator", estimator)
            frame.insert(0, "discipline", discipline)
            frames.append(frame)
        tag = _macro_name(discipline)
        macros += [
            (f"StatMsd{tag}Alpha", f"{fit.alpha:.3f}"),
            (f"StatMsd{tag}AlphaErr", f"{boot:.3f}"),
            (f"StatMsd{tag}AlphaErrOls", f"{fit.alpha_err:.3f}"),
            (f"StatMsd{tag}Hurst", f"{fit.alpha / 2:.3f}"),
            (f"StatMsd{tag}FitMinS", f"{fit.t_min:.0f}"),
            (f"StatMsd{tag}FitMaxS", f"{fit.t_max:.0f}"),
            (f"StatMsd{tag}Flights", f"{n_flights}"),
            (f"StatMsd{tag}Segments", f"{n_segments}"),
            (f"StatMsdTa{tag}Alpha", f"{ta_fit.alpha:.3f}"),
            (f"StatMsdTa{tag}AlphaErr", f"{ta_boot:.3f}"),
            (f"StatMsdTa{tag}AlphaErrOls", f"{ta_fit.alpha_err:.3f}"),
            (f"StatMsdTa{tag}Hurst", f"{ta_fit.alpha / 2:.3f}"),
            (f"StatMsdTa{tag}FitMinS", f"{ta_fit.t_min:.0f}"),
            (f"StatMsdTa{tag}FitMaxS", f"{ta_fit.t_max:.0f}"),
            # The gap between the two averages, evaluated here rather than typeset as a
            # subtraction of two macros: LaTeX would print "1.918-1.732" where the
            # sentence promises a number.
            (f"StatMsd{tag}AlphaGap", f"{fit.alpha - ta_fit.alpha:.3f}"),
        ]
        # The cohort spread is the number the thesis needs: the largest departure of any
        # cohort's exponent from the pooled one. Small means the pooled exponent is not
        # an artefact of the ensemble thinning out.
        for prefix, fitted, reference in (
            ("StatMsd", cohort_fits, fit),
            ("StatMsdTa", ta_cohort_fits, ta_fit),
        ):
            if not fitted:
                continue
            # The spread is measured against the pooled curve *on the same lags*, so it
            # is a statement about the population and not about the range.
            spread = max(abs(c.alpha - r.alpha) for c, r in fitted.values())
            # The same figure read the naive way, against the pooled exponent over the
            # pooled range. Reported so the correction can be seen rather than asserted:
            # on the ensemble estimator most of that departure is the curve's shape.
            naive = max(abs(c.alpha - reference.alpha) for c, _ in fitted.values())
            macros += [
                (f"{prefix}{tag}CohortSpread", f"{spread:.3f}"),
                (f"{prefix}{tag}CohortSpreadNaive", f"{naive:.3f}"),
                (f"{prefix}{tag}CohortCount", f"{len(fitted)}"),
                (f"{prefix}{tag}CohortMaxH", f"{max(fitted) / 3600:.0f}"),
            ]
            macros += [
                (
                    # Spelled, not printed: a LaTeX control sequence may contain only
                    # letters, so `...CohortAlpha1H` parses as `...CohortAlpha` followed
                    # by `1H`, and \newcommand then reads the 1 as an argument count and
                    # dies. The macro-contract check cannot see this -- the macro *is*
                    # written, it is merely unusable -- so only a build catches it, and
                    # only if something is quoting it.
                    f"{prefix}{tag}CohortAlpha{_HOURS[int(threshold / 3600)]}H",
                    f"{cohort_fit.alpha:.3f}",
                )
                for threshold, (cohort_fit, _) in sorted(fitted.items())
            ]

    if not results:
        print("No processed dataset reachable; nothing to do.")
        return 0

    # The curve and the macros go out before the figure is drawn. Everything above this
    # line is a traversal of the whole fix table, and it is not cached anywhere; a
    # failure inside the drawing code would otherwise take it down with it, which is
    # exactly what happened while `local_slope` was missing from the figure module. Saved
    # first, a drawing bug costs a figure rather than the pass, and `--redraw` can finish
    # the job from the CSV -- which is what that mode is for.
    pd.concat(frames, ignore_index=True).to_csv(OUT_CSV, index=False)
    write_macros(
        OUT_TEX, dict(macros), generator="scripts/reporting/generate_msd_figure.py"
    )
    print(f"Wrote {OUT_CSV.name} and {OUT_TEX.name}.")
    _draw(results, fits, ta_results, ta_fits)
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=["--redraw", "--allow-partial"])

    import sys

    raise SystemExit(redraw() if "--redraw" in sys.argv[1:] else main())
