#!/usr/bin/env python3
r"""Reduce the propagator pass into Chapter 3's exponent from the bulk, its figure and macros.

The chapter's other exponents are second moments. This one is not, and it is not measured
from the common origin either, which is what makes it the only independent check the archive
supports: the ensemble MSD and the first-passage time both failed on the origin, and the
filtered variation and the time-averaged MSD are both moments.

Three readings come out of the same histograms.

**The exponent.** Every quantile of :math:`|x|` grows as :math:`\Delta^{H}` for a
self-similar process. The median absolute increment is an order statistic set by the middle
of the distribution, so a heavy tail moves it not at all and every flight contributes to it.

**Whether one exponent is enough.** The four quantiles must give the *same* slope. Their
spread is therefore a test of the scaling form rather than an error bar on the exponent, and
it has to be read against what an exactly self-similar process gives on the same window --
which is the calibration this script also quotes.

**The collapse.** :math:`\Delta^{H}P` against :math:`x/\Delta^{H}` falls on one curve if the
form holds, and the curve is :math:`F`.

Writes ``thesis/generated/propagator.tex`` and ``propagator.pdf``.
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
from soaring.reporting import DISCIPLINES, write_macros  # noqa: E402

OUT_TEX = ROOT / "thesis" / "generated" / "propagator.tex"
OUT_FIG = ROOT / "thesis" / "generated" / "propagator.pdf"

FIT_RANGE_S = (60.0, 2000.0)
# A cadence contributes only if it supplies this many increments; below it the upper
# quantiles are order statistics over too few and the slope is noise. Counted on one
# variable, which is one increment per placement. It was 5,000,000 while the pass held two
# components and the test summed both, i.e. the same bar in the units used here.
MIN_INCREMENTS = 2_500_000

# Quantiles below and above the median, read separately. The chapter's finding is that the
# two halves disagree, so they have to be reported apart rather than averaged.
BULK = (0, 1)      # q25, q50
FLANK = (2, 3)     # q75, q90

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def _read(path: Path):
    """Every cadence with enough increments, as ``(dt, lags_s, counts, edges, blocks)``.

    ``blocks`` is the per-block quantile array the pass kept for the resampling, or
    ``None`` for a cadence it did not track.
    """
    if not path.is_file():
        return []
    data = np.load(path)
    out = []
    for step in data["cadences"]:
        tag = f"dt{step:g}".replace(".", "p")
        counts = data[f"{tag}_counts"]
        # On the modulus alone. counts now holds three variables, so summing all of them
        # would silently lower this threshold by half against the value it was set at.
        if counts[2].sum() < MIN_INCREMENTS:
            continue
        blocks = data[f"{tag}_block_quantiles"] if f"{tag}_block_quantiles" in data else None
        out.append(
            (float(step), data[f"{tag}_lags_s"], counts, data[f"{tag}_edges"], blocks)
        )
    return out


def measure(discipline: str, cadences, macros: dict) -> dict:
    """Fit every cadence and every variable, and emit the macros for one discipline."""
    from soaring.analysis.observables.propagator import (
        VARIABLES,
        collapse_residual,
        hurst_bootstrap_error,
        quantiles_from_histogram,
        scaling_from_quantiles,
    )

    tag = DISCIPLINES[discipline].tag

    def put(name, value):
        macros[f"StatProp{tag}{name}"] = value

    fastest = min(c[0] for c in cadences)
    rows, drawn = [], {}
    for step, lags, counts, edges, blocks in cadences:
        for index, variable in enumerate(VARIABLES):
            quantiles = np.array(
                [quantiles_from_histogram(counts[index, i], edges) for i in range(lags.size)]
            )
            fitted = scaling_from_quantiles(lags, quantiles, fit_range=FIT_RANGE_S)
            if not np.isfinite(fitted["hurst"]):
                continue
            residual = collapse_residual(
                lags, counts[index], edges, fitted["hurst"], fit_range=FIT_RANGE_S
            )
            boot = (
                hurst_bootstrap_error(lags, blocks[:, index], fit_range=FIT_RANGE_S)
                if blocks is not None
                else {"hurst_err": np.nan, "per_quantile_err": np.full(4, np.nan),
                      "n_blocks": 0, "n_resamples": 0}
            )
            row = {
                "dt": step,
                "variable": variable,
                "hurst": fitted["hurst"],
                "spread": fitted["spread"],
                "per_quantile": fitted["per_quantile"],
                "hurst_err": boot["hurst_err"],
                "per_quantile_err": boot["per_quantile_err"],
                "n_blocks": boot["n_blocks"],
                "collapse": residual,
                "n": int(counts[index].sum()),
            }
            rows.append(row)
            if step == fastest:
                drawn[variable] = {
                    "lags": lags, "quantiles": quantiles, "counts": counts[index],
                    "edges": edges, "fitted": fitted, "row": row,
                }

    if not rows:
        return {}

    # The modulus is the headline. |dr| is what the ensemble MSD averages and what the
    # filtered variation sums the components to recover, so it is the only one of the
    # three that can be set beside them; a component exponent answers a different
    # question, and on an anisotropic ensemble it is a different number.
    radial = [r for r in rows if r["variable"] == "R"]
    hurst = np.array([r["hurst"] for r in radial])
    spread = np.array([r["spread"] for r in radial])
    collapse = np.array([r["collapse"] for r in radial])
    per = np.vstack([r["per_quantile"] for r in radial])

    put("Hurst", f"{np.median(hurst):.3f}")
    put("HurstMin", f"{hurst.min():.3f}")
    put("HurstMax", f"{hurst.max():.3f}")
    put("Alpha", f"{2 * np.median(hurst):.2f}")
    put("Cadences", f"{len({r['dt'] for r in rows})}")
    put("Increments", f"{sum(r['n'] for r in rows if r['variable'] == 'R')}")
    put("FitMinS", f"{FIT_RANGE_S[0]:.0f}")
    put("FitMaxS", f"{FIT_RANGE_S[1]:.0f}")

    # The two halves of the distribution, which is the finding.
    put("HurstBulk", f"{np.median(per[:, BULK]):.3f}")
    put("HurstFlank", f"{np.median(per[:, FLANK]):.3f}")
    put("QuantileSpread", f"{np.median(spread):.3f}")
    put("CollapseDex", f"{np.median(collapse):.3f}")
    # The same scatter as a factor in the density, which is what a reader of the panel
    # sees; quoting the dex alone asks them to exponentiate it themselves.
    put("CollapseFactor", f"{10 ** np.median(collapse):.2f}")

    # The anisotropy, which Sec. 2.8 sees in the amplitude and which reaches the exponent.
    for variable, name in (("E", "East"), ("N", "North")):
        picked = [r for r in rows if r["variable"] == variable]
        if not picked:
            continue
        put(f"Hurst{name}", f"{np.median([r['hurst'] for r in picked]):.3f}")
        # The quantile drift on each component, for the comparison with the modulus: a
        # small |dx| is not a small displacement -- the wing may be going due north --
        # so a component's low quantile mixes "barely moved" with "moved the other way",
        # and the modulus is the one that separates them.
        put(f"QuantileSpread{name}", f"{np.median([r['spread'] for r in picked]):.3f}")

    # Everything the figure and the quantile table quote: the fastest cadence, which is
    # the most populous by increments, on the modulus. Checked rather than assumed --
    # every cadence resolves the same 14 of the 20 nominal lags inside the fit window,
    # so it is sample size and not lag coverage that picks it.
    if "R" in drawn:
        d = drawn["R"]
        put("DrawnDtS", f"{fastest:g}")
        put("DrawnLags", f"{d['fitted']['lags_used']}")
        put("DrawnHurst", f"{d['fitted']['hurst']:.3f}")
        put("DrawnBlocks", f"{d['row']['n_blocks']}")
        if np.isfinite(d["row"]["hurst_err"]):
            put("DrawnHurstErr", f"{d['row']['hurst_err']:.4f}")
        # LaTeX control sequences are ASCII letters only, so the percentile is spelled
        # out rather than typed as a digit (StatPropParaHurstQ25 would be read as
        # StatPropParaHurstQ followed by the text "25", and \newcommand takes that 2
        # as an argument count).
        labels = ("TwentyFifth", "Median", "SeventyFifth", "Ninetieth")
        for label, column in zip(labels, range(4), strict=True):
            value = d["fitted"]["per_quantile"][column]
            error = d["row"]["per_quantile_err"][column]
            if np.isfinite(value):
                put(f"Hurst{label}", f"{value:.3f}")
            if np.isfinite(error):
                put(f"Hurst{label}Err", f"{error:.4f}")
        # The least-squares error the fit reports, kept only so the chapter can say how
        # far below the resampled one it sits rather than asserting that it does.
        ols = np.nanmedian(d["fitted"]["per_quantile_err"])
        if np.isfinite(ols):
            put("DrawnHurstErrOls", f"{ols:.4f}")
        # The largest of the four, which is what the text compares the spread down the
        # column against: if even the worst error is far below it, the quantiles
        # disagreeing is not sampling noise.
        worst = np.nanmax(d["row"]["per_quantile_err"])
        if np.isfinite(worst):
            put("HurstQuantileErrMax", f"{worst:.4f}")

    # The east/north twins of DrawnHurst, for panel (c)'s per-component collapse: each
    # column rescales by its own row's H, not the modulus's, since H differs by component
    # and a shared scale would misdraw the collapse for the two that do not own it.
    for variable, name in (("E", "East"), ("N", "North")):
        if variable in drawn:
            put(f"DrawnHurst{name}", f"{drawn[variable]['fitted']['hurst']:.3f}")

    return {"rows": rows, "drawn": drawn, "fastest": fastest}


def _from_histogram(counts, edges, probabilities):
    """Quantiles of a linearly binned histogram, interpolated across the bin.

    The cumulative count after bin ``i`` is the mass below ``edges[i+1]``, not the mass
    below the bin's centre, so the two arrays passed to ``interp`` have to be the edges and
    a cumulative that starts at zero. Pairing ``cumsum(counts)`` with the centres instead
    shifts every quantile down by half a bin, uniformly and silently: on a distribution
    whose true median is zero, the vertical grid used here returns -0.0625.
    """
    counts = np.asarray(counts, dtype=float)
    total = counts.sum()
    if total <= 0:
        return [float("nan")] * len(probabilities)
    cumulative = np.concatenate([[0.0], np.cumsum(counts)]) / total
    return [float(np.interp(p, cumulative, edges)) for p in probabilities]


def kinematics(discipline: str, path: Path, macros: dict) -> dict:
    """The three observables Sec. 3.1 catalogues and nothing measured, until now.

    They need no scaling argument: they are the marginal distributions of what the pipeline
    already computes. Each is quoted against the value an unstructured process would give,
    which is what makes it a measurement rather than a description --- an isotropic walk
    turns by 90 degrees in the median, and a flight that neither gains nor loses net altitude
    climbs half the time.
    """
    if not path.is_file():
        return {}
    data = np.load(path)
    if "angle_counts" not in data:
        return {}
    tag = DISCIPLINES[discipline].tag

    def put(name, value):
        macros[f"StatKin{tag}{name}"] = value

    angle, angle_edges = data["angle_counts"], data["angle_edges"]
    centres = 0.5 * (angle_edges[:-1] + angle_edges[1:])
    median = _from_histogram(angle, angle_edges, [0.5])[0]
    put("Angles", f"{int(angle.sum())}")
    # The stride is a sample count. It was emitted as "...S" and typeset inside \SI{}{\second},
    # which is false wherever the cadence is not 1 Hz -- 10.7 % of paraglider fixes and 38.3 %
    # of hang-glider ones. The name now says what the number is.
    put("AngleStrideSamples", f"{int(data['angle_stride'][0])}")
    put("AngleMedianDeg", f"{np.degrees(median):.0f}")
    put("AngleForwardPct", f"{100 * angle[centres < np.pi / 6].sum() / angle.sum():.0f}")
    # The same median over 1 Hz segments only, where five samples are five seconds, so the
    # two disciplines are compared at a matched stride rather than across their logger mixes.
    if "angle_counts_one_hz" in data:
        one_hz = data["angle_counts_one_hz"]
        if one_hz.sum() > 0:
            matched = _from_histogram(one_hz, angle_edges, [0.5])[0]
            put("AnglesOneHz", f"{int(one_hz.sum())}")
            put("AngleMedianOneHzDeg", f"{np.degrees(matched):.1f}")
            put("AngleOneHzSharePct", f"{100 * one_hz.sum() / angle.sum():.0f}")

    speed = _from_histogram(data["speed_counts"], data["speed_edges"], [0.5, 0.9, 0.99])
    put("SpeedMedianMs", f"{speed[0]:.1f}")
    put("SpeedNinetyMs", f"{speed[1]:.1f}")
    put("SpeedNinetyNineMs", f"{speed[2]:.1f}")

    vertical = data["vertical_counts"]
    v_edges = data["vertical_edges"]
    v_centres = 0.5 * (v_edges[:-1] + v_edges[1:])
    quantiles = _from_histogram(vertical, v_edges, [0.1, 0.5, 0.9])
    put("VerticalMedianMs", f"{quantiles[1]:+.2f}")
    put("VerticalTenMs", f"{quantiles[0]:+.2f}")
    put("VerticalNinetyMs", f"{quantiles[2]:+.2f}")
    put("ClimbingPct", f"{100 * vertical[v_centres > 0].sum() / vertical.sum():.0f}")

    return {
        "angle": (angle, angle_edges),
        "speed": (data["speed_counts"], data["speed_edges"]),
        "vertical": (vertical, v_edges),
    }


def calibration(macros: dict) -> None:
    """What an exactly self-similar process gives on the same window, measured not assumed.

    Without it the quantile spread is a number with no scale: 0.08 could be the estimator's
    own resolution or a departure from the scaling form, and only this says which.
    """
    from soaring.analysis.observables import synthetic as S
    from soaring.analysis.observables.propagator import (
        PropagatorAccumulator,
        quantiles_from_histogram,
        scaling_from_quantiles,
    )

    lags_s = np.unique(np.round(np.geomspace(30, 4000, 20)))
    accumulator = PropagatorAccumulator(lags_s.astype(int), order=1)
    for seed in range(40):
        accumulator.add(np.asarray(S.fractional_brownian(2**15, 0.90, seed=seed)))
    # Index 2 is the modulus, which is what the chapter quotes; calibrating on a component
    # would compare the archive's |dr| spread against a reference for |dx|.
    quantiles = np.array(
        [quantiles_from_histogram(accumulator.counts[2, i], accumulator.edges)
         for i in range(lags_s.size)]
    )
    fitted = scaling_from_quantiles(lags_s, quantiles, fit_range=FIT_RANGE_S)
    macros["StatPropCalibHurst"] = f"{fitted['hurst']:.3f}"
    macros["StatPropCalibSpread"] = f"{fitted['spread']:.3f}"


#: Line style per percentile in panel (a), and per variable in panel (b). Stated once so
#: the caption and the legend cannot drift apart from the plot.
_PERCENTILE_STYLE = (("25th", "-"), ("50th", "--"), ("75th", "-."), ("90th", ":"))
_VARIABLE_STYLE = (("R", "|Δr|", "o-"), ("E", "|Δx| east", "s--"), ("N", "|Δy| north", "^:"))


#: Column label for panels (a) and (c), now one sub-panel per variable rather than the
#: modulus alone. Reuses _VARIABLE_STYLE's own labels so the two cannot drift apart.
_VARIABLE_LABEL = {variable: label for variable, label, _ in _VARIABLE_STYLE}


def draw(measured: dict):
    """Panels (a) and (c), one sub-panel per variable; panel (b) unchanged, all three at
    the fastest native cadence of each discipline."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    fig, axes = plt.subplots(2, 4, figsize=(16.8, 7.6))
    quantile_axes = {"R": axes[0, 0], "E": axes[0, 1], "N": axes[0, 2]}
    drift_ax = axes[0, 3]
    collapse_axes = {"R": axes[1, 0], "E": axes[1, 1], "N": axes[1, 2]}
    legend_ax = axes[1, 3]

    for discipline, m in measured.items():
        colour = DISCIPLINES[discipline].color
        drawn = m.get("drawn") or {}
        if "R" not in drawn:
            continue

        # (a) the four percentiles, one sub-panel per variable.
        for variable, ax in quantile_axes.items():
            if variable not in drawn:
                continue
            d = drawn[variable]
            lags, quantiles = d["lags"], d["quantiles"]
            window = (lags >= FIT_RANGE_S[0]) & (lags <= FIT_RANGE_S[1])
            for column, (_, style) in enumerate(_PERCENTILE_STYLE):
                ax.loglog(
                    lags[window], quantiles[window, column], style, color=colour, lw=1.2
                )

        # (b) the same fit per percentile, for each of the three variables (unchanged).
        for variable, _, marker in _VARIABLE_STYLE:
            if variable not in drawn:
                continue
            drift_ax.plot(
                [25, 50, 75, 90], drawn[variable]["fitted"]["per_quantile"],
                marker, color=colour, ms=4, lw=1.0, alpha=0.85,
            )

        # (c) the collapse, one sub-panel per variable, each at that row's own exponent
        # -- H differs by component, so E and N do not share R's scale.
        for variable, ax in collapse_axes.items():
            if variable not in drawn:
                continue
            d = drawn[variable]
            lags, counts, edges, fitted = d["lags"], d["counts"], d["edges"], d["fitted"]
            window = (lags >= FIT_RANGE_S[0]) & (lags <= FIT_RANGE_S[1])
            centres = np.sqrt(edges[:-1] * edges[1:])
            widths = np.diff(edges)
            for i in np.flatnonzero(window)[::3]:
                if counts[i].sum() <= 0:
                    continue
                scale = lags[i] ** fitted["hurst"]
                density = counts[i] / counts[i].sum() / widths
                keep = density > 0
                ax.loglog(
                    centres[keep] / scale, density[keep] * scale,
                    color=colour, lw=0.8, alpha=0.6,
                )

    disciplines = [d for d in measured if (measured[d].get("drawn") or {}).get("R")]
    colour_keys = [
        Line2D([], [], color=DISCIPLINES[d].color, lw=1.5,
               label=f"{d} ({measured[d]['fastest']:g} s)")
        for d in disciplines
    ]
    style_keys = [
        Line2D([], [], color="0.35", lw=1.2, ls=style, label=f"{name} percentile")
        for name, style in _PERCENTILE_STYLE
    ]
    variable_keys = [
        Line2D([], [], color="0.35", lw=1.0, marker=marker[0], ls=marker[1:], ms=4,
               label=label)
        for _, label, marker in _VARIABLE_STYLE
    ]

    for variable, ax in quantile_axes.items():
        ax.set_xlabel(r"lag $\Delta$ (s)")
        title = f"(a) {_VARIABLE_LABEL[variable]}" if variable == "R" else _VARIABLE_LABEL[variable]
        ax.set_title(title, fontsize=10, loc="left")
    quantile_axes["R"].set_ylabel("percentile of the increment (m)")

    drift_ax.set_xlabel("percentile of the increment")
    drift_ax.set_ylabel("$H$ fitted at that percentile alone")
    drift_ax.set_title("(b) one exponent would be a flat line", fontsize=10, loc="left")
    drift_ax.set_xticks([25, 50, 75, 90])
    second = drift_ax.legend(handles=colour_keys, frameon=False, fontsize=7, loc="lower left")
    drift_ax.add_artist(second)
    drift_ax.legend(handles=variable_keys, frameon=False, fontsize=7, loc="upper right")

    for variable, ax in collapse_axes.items():
        # The far-left decades are a handful of counts per bin and show nothing; the
        # story is the bulk and the flank, which is where the curves part company.
        ax.set_xlim(3e-2, 1.2e2)
        ax.set_ylim(1e-4, 1.0)
        ax.set_xlabel(r"increment $/\, \Delta^{H}$")
        title = f"(c) {_VARIABLE_LABEL[variable]}" if variable == "R" else _VARIABLE_LABEL[variable]
        ax.set_title(title, fontsize=10, loc="left")
    collapse_axes["R"].set_ylabel(r"$\Delta^{H} P$")

    legend_ax.axis("off")
    legend_ax.legend(
        handles=[
            *colour_keys,
            *style_keys,
            Line2D([], [], color="0.35", lw=0.8, label="one lag inside the fit window (c)"),
        ],
        frameon=False, fontsize=8, loc="center",
    )

    fig.tight_layout()
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")

    macros: dict[str, str] = {}
    measured: dict[str, dict] = {}
    missing: list[str] = []
    for discipline, glider in DISCIPLINES.items():
        slug = glider.slug
        cadences = _read(args.audit_dir / f"propagator_{slug}.npz")
        if not cadences:
            print(f"{discipline}: propagator pass not found")
            missing.append(discipline)
            continue
        result = measure(discipline, cadences, macros)
        if result:
            result["kinematics"] = kinematics(
                discipline, args.audit_dir / f"propagator_{slug}.npz", macros
            )
            measured[discipline] = result

    if missing and not args.allow_partial:
        print(
            f"{', '.join(missing)}: pass not reachable. propagator.tex would be written for "
            "the other discipline alone and the thesis would fail to build on the macros this "
            "one owns. Re-run the pass, or pass --allow-partial."
        )
        return 1
    if not macros:
        print("no propagator pass reachable; propagator.tex not written")
        return 1

    calibration(macros)
    draw(measured).savefig(OUT_FIG, metadata=_PDF_METADATA)
    write_macros(
        OUT_TEX,
        macros,
        generator="scripts/reporting/ch3_global_transport/generate_propagator_figure.py",
        sort=True,
    )
    print(f"wrote {OUT_TEX.name}, {OUT_FIG.name} ({len(macros)} macros)")
    for k, v in sorted(macros.items()):
        print(f"  {k:34s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
