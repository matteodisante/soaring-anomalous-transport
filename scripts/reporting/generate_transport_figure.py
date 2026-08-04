#!/usr/bin/env python3
r"""Reduce the filtered-variation pass into Chapter 3's measurement, figure and macros.

Reads what ``measure_variations.py`` wrote --- one curve per flight per filter order ---
and answers, in this order, the questions the chapter is built on.

**Where can transport be read at all?** Not wherever the sample allows. The CFD scores
closed tasks, so most flights fly a triangle and return towards their start; above lags
comparable to a task leg the displacement statistic measures the scoring rule rather than
the motion. The two populations are compared lag by lag and the ceiling is set where they
part company, which is a far lower ceiling than the coverage rule gives.

**What is the exponent, and how much of it was course?** The order scan. An order-``p``
filtered variation annihilates any polynomial of degree ``p-1``, so ``p = 1`` still carries
each flight's net course and ``p \ge 2`` does not; the difference between them is the part
of the apparent exponent that was drift, measured rather than assumed.

**How certain is it?** A bootstrap that resamples days and sites, not flights, with the
intraclass correlation reported at each candidate level so the choice is justified.

**How many regimes?** A breakpoint fit whose null is built from the bootstrap's sampling
covariance --- never from the residuals about a straight line, which is circular for a
curve that is genuinely bent.

Writes ``thesis/generated/transport.tex`` and ``transport.pdf``.
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

OUT_TEX = ROOT / "thesis" / "generated" / "transport.tex"
OUT_FIG = ROOT / "thesis" / "generated" / "transport.pdf"

DISCIPLINES = {"paragliders": ("para", "Para"), "hang gliders": ("hang", "Hang")}
COLORS = {"paragliders": "#3477a8", "hang gliders": "#b5482a"}
ORDERS = (1, 2, 3)

# A LaTeX control sequence takes letters only, so the filter order is spelled out in the
# macro name. The checker catches this, but only once a generator has already written the
# unusable name -- the definition itself is what fails, whether or not anything quotes it.
_ORDER_WORD = {1: "One", 2: "Two", 3: "Three"}

# Levels the bootstrap may resample at, coarsest last. The one used is chosen by the
# intraclass correlation rather than by preference.
LEVELS = ("flight", "day_site", "day", "pilot")

# A task counts as closed when the declared type names a triangle: those return towards
# their start by construction, which is what saturates a displacement statistic.
_CLOSED = "triangle"

# The fitted range, stated rather than discovered. Its lower end is above the slowest
# logger's smoothing scale (5 samples at dt = 10 s is 50 s); its upper end is where the
# flight-duration censoring begins to bite on the median flight. Every exponent is quoted
# with the range it was fitted over, and with how much it moves when the range changes.
FIT_RANGE_S = (60.0, 2000.0)

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def load(slug: str, audit_dir: Path):
    npz = audit_dir / f"variations_{slug}.npz"
    table = audit_dir / f"variation_flights_{slug}.parquet"
    if not npz.is_file() or not table.is_file():
        return None
    data = np.load(npz)
    return {
        "lags_s": data["lags_s"],
        "orders": {p: data[f"order{p}"] for p in ORDERS},
        "flights": pd.read_parquet(table),
    }


def task_systematic(lags, curves, closed, fit_range):
    """How much the declared task moves the exponent, as the closed/open difference.

    The CFD scores closed tasks, so most flights fly a triangle and return towards their
    start. That suppresses a plain displacement statistic at long lags by construction.
    There is no lag below which the effect is absent -- the two populations differ at every
    lag and the difference grows smoothly, from 0.03 in the local slope at 60 s to 1.1 at
    12000 s -- so a "ceiling" above which the measurement is clean does not exist and any
    threshold on the difference merely picks an arbitrary point on a smooth curve, at a
    place that moves with the sample size.

    What can be done instead is to fit both populations and report the gap as a systematic.
    It is also the sharpest demonstration of why the chapter uses a filtered variation: on
    the plain increment the gap reaches 0.28 over a wide range, and on the second-order
    variation it stays under 0.15, because a difference of curvature does not care that
    the course eventually comes home.

    Returns:
        ``(alpha_open, alpha_closed, slope_open, slope_closed)``.
    """
    from soaring.analysis.observables.regimes import local_slope
    from soaring.analysis.observables.variations import hurst_from_variations

    with np.errstate(invalid="ignore"):
        mean_closed = np.nanmean(curves[closed], axis=0)
        mean_open = np.nanmean(curves[~closed], axis=0)
    alpha_closed = 2.0 * hurst_from_variations(lags, mean_closed, fit_range=fit_range)[0]
    alpha_open = 2.0 * hurst_from_variations(lags, mean_open, fit_range=fit_range)[0]
    return (
        alpha_open,
        alpha_closed,
        local_slope(lags, mean_open, 0.25),
        local_slope(lags, mean_closed, 0.25),
    )



def stratified_exponents(lags, curves, frame, column, fit_range, *, minimum=2000):
    """The exponent within each level of a stratifier, largest stratum first.

    Three of these answer three different questions with the same code.

    *Cadence* is a check on the pipeline rather than on the flying. The
    Savitzky--Golay window has a floor of five **samples**, so the velocity is a
    5 s derivative at \SI{1}{\hertz} and a 50 s one at \SI{10}{\second}: the
    trajectories of slow loggers are smoothed over a scale ten times longer than
    those of fast ones. If the exponent depends on cadence, the estimator is
    reading the filter.

    *Wing class* and *orographic group* are the heterogeneity confound. A
    superposition of ordinary processes with different persistence times imitates
    a single anomalous one, and Sec. 2.8 has already measured these strata as
    incompatible at 40 and 62 per cent on the ensemble MSD.

    *Season* is the control that should come out flat, since Sec. 2.8 found it
    compatible; a stratifier that separates here and not there would indict the
    estimator rather than the archive.

    Returns:
        ``{level: (alpha, n_flights)}`` for the levels holding at least
        ``minimum`` flights.
    """
    from soaring.analysis.observables.variations import hurst_from_variations

    if column not in frame:
        return {}
    counts = frame[column].value_counts()
    out = {}
    for level in counts[counts >= minimum].index:
        member = (frame[column] == level).to_numpy()
        with np.errstate(invalid="ignore"):
            mean_curve = np.nanmean(curves[member], axis=0)
        alpha = 2.0 * hurst_from_variations(lags, mean_curve, fit_range=fit_range)[0]
        if np.isfinite(alpha):
            out[str(level)] = (alpha, int(member.sum()))
    return out


def measure(discipline: str, loaded: dict, macros: dict) -> dict:
    from soaring.analysis.observables.regimes import (
        effective_dof,
        select_breakpoints,
        spurious_breakpoints,
    )
    from soaring.analysis.observables.variations import hurst_from_variations
    from soaring.analysis.stats.bootstrap import (
        cluster_bootstrap,
        cluster_labels,
        intraclass_correlation,
        sampling_covariance,
    )

    tag = DISCIPLINES[discipline][1]
    lags = loaded["lags_s"]
    frame = loaded["flights"]

    def put(name, value):
        macros[f"StatVar{tag}{name}"] = value

    # ---- the ceiling the task geometry imposes -------------------------------------
    closed = (
        frame["flight_type"].astype(str).str.contains(_CLOSED, case=False, na=False).to_numpy()
        if "flight_type" in frame
        else np.zeros(len(frame), bool)
    )
    put("ClosedPct", f"{100 * closed.mean():.0f}")
    put("FitMinS", f"{FIT_RANGE_S[0]:.0f}")
    put("FitMaxS", f"{FIT_RANGE_S[1]:.0f}")
    put("FitDecades", f"{np.log10(FIT_RANGE_S[1] / FIT_RANGE_S[0]):.1f}")
    task = {
        p: task_systematic(lags, loaded["orders"][p], closed, FIT_RANGE_S) for p in ORDERS
    }
    for p in ORDERS:
        put(f"TaskGapOrder{_ORDER_WORD[p]}", f"{task[p][0] - task[p][1]:+.2f}")
    slope_open, slope_closed = task[1][2], task[1][3]

    # ---- how much clustering there is, at each level --------------------------------
    reference = np.log10(
        np.where(loaded["orders"][1][:, len(lags) // 3] > 0,
                 loaded["orders"][1][:, len(lags) // 3], np.nan)
    )
    icc = {}
    for level in LEVELS:
        try:
            icc[level] = intraclass_correlation(reference, cluster_labels(frame, level))
        except KeyError:
            continue
    for level, value in icc.items():
        put(f"Icc{level.title().replace('_', '')}", f"{value:.2f}")
    chosen = max(
        (lvl for lvl in ("day_site", "day") if lvl in icc),
        key=lambda lvl: icc[lvl],
        default="flight",
    )
    put("BootstrapLevel", chosen.replace("_", " and "))
    labels = cluster_labels(frame, chosen)
    put("Clusters", f"{np.unique(labels).size}")

    # ---- the order scan, with clustered intervals -----------------------------------
    window = (lags >= FIT_RANGE_S[0]) & (lags <= FIT_RANGE_S[1])
    put("FitLags", f"{int(window.sum())}")
    alphas = {}
    for p in ORDERS:
        curves = loaded["orders"][p]

        def exponent(mean_curve, mask=window):
            hurst, _ = hurst_from_variations(lags[mask], mean_curve[mask])
            return 2.0 * hurst

        point, replicates = cluster_bootstrap(
            curves, labels, exponent, n_resamples=120, seed=7
        )
        sampling = float(np.nanstd(replicates))
        # Sampling error is not the whole uncertainty, and on this archive it is not even
        # the larger part. The curve is not a straight line, so the exponent depends on
        # the range it is fitted over; that dependence is a systematic and is estimated by
        # refitting each half of the window. Quoting the bootstrap alone would put four
        # significant figures on a number whose second is not determined.
        half = np.flatnonzero(window)
        lower = np.zeros_like(window); lower[half[: len(half) // 2 + 1]] = True
        upper = np.zeros_like(window); upper[half[len(half) // 2 :]] = True
        mean_curve = np.nanmean(curves, axis=0)
        halves = [exponent(mean_curve, mask=m) for m in (lower, upper)]
        systematic = float(abs(halves[0] - halves[1]) / 2.0)
        total = float(np.hypot(sampling, systematic))
        alphas[p] = (point, total)
        put(f"AlphaOrder{_ORDER_WORD[p]}", f"{point:.2f}")
        # H = alpha/2, emitted rather than left to the reader: Sec. 3.6 compares it against
        # a published Hurst exponent, and a halved number typed into prose stops tracking
        # the data the moment the fit moves.
        put(f"HurstOrder{_ORDER_WORD[p]}", f"{0.5 * point:.3f}")
        put(f"AlphaOrder{_ORDER_WORD[p]}Err", f"{total:.2f}")
        put(f"AlphaOrder{_ORDER_WORD[p]}ErrSampling", f"{sampling:.3f}")
        put(f"AlphaOrder{_ORDER_WORD[p]}ErrRange", f"{systematic:.3f}")
        # The per-flight bootstrap, for the comparison that justifies the clustering.
        _, naive = cluster_bootstrap(
            curves, np.arange(len(frame)), exponent, n_resamples=120, seed=7
        )
        put(f"AlphaOrder{_ORDER_WORD[p]}ErrNaive", f"{float(np.nanstd(naive)):.3f}")

    put("DriftShare", f"{alphas[1][0] - alphas[2][0]:+.2f}")
    put("OrderAgreement", f"{abs(alphas[2][0] - alphas[3][0]):.2f}")

    # ---- does the answer depend on who is in the ensemble? --------------------------
    # Every one of these is a row selection on the matrix already in memory, so the
    # confound checks cost nothing beyond the pass that has already been paid for.
    curves2 = loaded["orders"][2]
    if "native_dt_s" in frame:
        frame = frame.assign(cadence=frame["native_dt_s"].round().astype("Int64"))
    spreads = {}
    for column, name in (("cadence", "Cadence"), ("wing_class", "Class"),
                         ("season", "Season")):
        levels = stratified_exponents(lags, curves2, frame, column, FIT_RANGE_S)
        if len(levels) < 2:
            continue
        values = np.array([v[0] for v in levels.values()])
        spreads[name] = float(values.max() - values.min())
        put(f"{name}Strata", f"{len(levels)}")
        put(f"{name}SpreadAlpha", f"{spreads[name]:.2f}")
        put(f"{name}AlphaMin", f"{values.min():.2f}")
        put(f"{name}AlphaMax", f"{values.max():.2f}")

    # ---- how many regimes, against a null the shape cannot leak into ----------------
    mean_curve = np.nanmean(loaded["orders"][2], axis=0)
    noise = sampling_covariance(loaded["orders"][2], labels, n_resamples=80, seed=11)
    sigma = float(np.nanmedian(noise["sigma_dex"][window]))
    chosen_fit = select_breakpoints(lags[window], mean_curve[window], max_breaks=2)
    null = spurious_breakpoints(
        lags[window], mean_curve[window], n_surrogates=200, seed=13,
        sigma=sigma, autocorrelation=noise["autocorrelation"],
    )
    put("Dof", f"{effective_dof(lags[window], mean_curve[window]):.1f}")
    put("NoiseSigmaDex", f"{sigma:.4f}")
    put("Breaks", f"{chosen_fit['n_breaks']}")
    put("FalsePositivePct", f"{100 * null['false_positive_rate']:.0f}")
    if chosen_fit["breaks_s"]:
        put("BreakOneS", f"{chosen_fit['breaks_s'][0]:.0f}")
    put("SlopeLow", f"{chosen_fit['slopes'][0]:.2f}")
    put("SlopeHigh", f"{chosen_fit['slopes'][-1]:.2f}")

    return {
        "lags": lags,
        "orders": loaded["orders"],
        "slope_closed": slope_closed,
        "slope_open": slope_open,
        "window": window,
    }


def draw(measured: dict):
    import matplotlib.pyplot as plt

    from soaring.analysis.observables.regimes import local_slope

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.6))
    (curve_ax, order_ax), (task_ax, slope_ax) = axes

    for discipline, m in measured.items():
        colour = COLORS[discipline]
        lags = m["lags"]
        with np.errstate(invalid="ignore"):
            mean2 = np.nanmean(m["orders"][2], axis=0)
        curve_ax.loglog(lags, mean2, color=colour, label=discipline)
        curve_ax.axvspan(*FIT_RANGE_S, color="0.92", zorder=0)

        for p, style in zip(ORDERS, ("-", "--", ":")):
            with np.errstate(invalid="ignore"):
                mean = np.nanmean(m["orders"][p], axis=0)
            order_ax.semilogx(lags, local_slope(lags, mean, 0.25) / 2.0, style,
                              color=colour, lw=1.2, label=f"{discipline}, $p={p}$")

        task_ax.semilogx(lags, m["slope_closed"], "-", color=colour, label=f"{discipline}, closed")
        task_ax.semilogx(lags, m["slope_open"], "--", color=colour, label=f"{discipline}, open")

        with np.errstate(invalid="ignore"):
            slope_ax.semilogx(lags, local_slope(lags, np.nanmean(m["orders"][2], 0), 0.25),
                              color=colour, label=discipline)
        slope_ax.axvspan(*FIT_RANGE_S, color="0.92", zorder=0)

    curve_ax.set_xlabel("lag (s)")
    curve_ax.set_ylabel(r"$V_2(\Delta)$ (m$^2$)")
    curve_ax.set_title("(a) second-order filtered variation", fontsize=10, loc="left")
    order_ax.set_xlabel("lag (s)")
    order_ax.set_ylabel("local $H$")
    order_ax.set_title("(b) order scan: $p=1$ carries the course, $p\\geq 2$ does not",
                       fontsize=10, loc="left")
    task_ax.set_xlabel("lag (s)")
    task_ax.set_ylabel(r"local slope of $V_1$")
    task_ax.set_title("(c) closed against open tasks: where the scoring rule takes over",
                      fontsize=10, loc="left")
    slope_ax.set_xlabel("lag (s)")
    slope_ax.set_ylabel(r"local slope of $V_2$")
    slope_ax.set_title("(d) the fitted range", fontsize=10, loc="left")
    for ax in axes.ravel():
        ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")

    macros: dict[str, str] = {}
    measured: dict[str, dict] = {}
    for discipline, (slug, _) in DISCIPLINES.items():
        loaded = load(slug, args.audit_dir)
        if loaded is None:
            print(f"{discipline}: variation pass not found, skipping")
            continue
        measured[discipline] = measure(discipline, loaded, macros)
    if not macros:
        print("no variation pass reachable; transport.tex not written")
        return 1

    draw(measured).savefig(OUT_FIG, metadata=_PDF_METADATA)
    lines = ["% Generated by scripts/reporting/generate_transport_figure.py -- do not edit."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()]
    OUT_TEX.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_TEX.name}, {OUT_FIG.name} ({len(macros)} macros)")
    for k, v in macros.items():
        print(f"  {k:38s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
