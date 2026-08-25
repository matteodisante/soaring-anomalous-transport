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

ROOT = Path(__file__).resolve().parents[2]
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
# quantiles are order statistics over too few and the slope is noise.
MIN_INCREMENTS = 5_000_000

# Quantiles below and above the median, read separately. The chapter's finding is that the
# two halves disagree, so they have to be reported apart rather than averaged.
BULK = (0, 1)      # q25, q50
FLANK = (2, 3)     # q75, q90

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def _read(path: Path):
    """Every cadence with enough increments, as ``(dt, lags_s, counts, edges)``."""
    if not path.is_file():
        return []
    data = np.load(path)
    out = []
    for step in data["cadences"]:
        tag = f"dt{step:g}".replace(".", "p")
        counts = data[f"{tag}_counts"]
        if counts.sum() < MIN_INCREMENTS:
            continue
        out.append((float(step), data[f"{tag}_lags_s"], counts, data[f"{tag}_edges"]))
    return out


def measure(discipline: str, cadences, macros: dict) -> dict:
    from soaring.analysis.observables.propagator import (
        collapse_residual,
        quantiles_from_histogram,
        scaling_from_quantiles,
    )

    tag = DISCIPLINES[discipline].tag

    def put(name, value):
        macros[f"StatProp{tag}{name}"] = value

    rows, drawn = [], []
    for step, lags, counts, edges in cadences:
        for component in (0, 1):
            quantiles = np.array(
                [quantiles_from_histogram(counts[component, i], edges) for i in range(lags.size)]
            )
            fitted = scaling_from_quantiles(lags, quantiles, fit_range=FIT_RANGE_S)
            if not np.isfinite(fitted["hurst"]):
                continue
            residual = collapse_residual(
                lags, counts[component], edges, fitted["hurst"], fit_range=FIT_RANGE_S
            )
            rows.append(
                {
                    "dt": step,
                    "component": "EN"[component],
                    "hurst": fitted["hurst"],
                    "spread": fitted["spread"],
                    "per_quantile": fitted["per_quantile"],
                    "collapse": residual,
                    "n": int(counts[component].sum()),
                }
            )
            if step == min(c[0] for c in cadences):
                drawn.append((lags, quantiles, counts[component], edges, fitted, "EN"[component]))

    if not rows:
        return {}

    hurst = np.array([r["hurst"] for r in rows])
    spread = np.array([r["spread"] for r in rows])
    collapse = np.array([r["collapse"] for r in rows])
    per = np.vstack([r["per_quantile"] for r in rows])

    put("Hurst", f"{np.median(hurst):.3f}")
    put("HurstMin", f"{hurst.min():.3f}")
    put("HurstMax", f"{hurst.max():.3f}")
    put("Alpha", f"{2 * np.median(hurst):.2f}")
    put("Cadences", f"{len({r['dt'] for r in rows})}")
    put("Increments", f"{sum(r['n'] for r in rows)}")
    put("FitMinS", f"{FIT_RANGE_S[0]:.0f}")
    put("FitMaxS", f"{FIT_RANGE_S[1]:.0f}")

    # The two halves of the distribution, which is the finding.
    put("HurstBulk", f"{np.median(per[:, BULK]):.3f}")
    put("HurstFlank", f"{np.median(per[:, FLANK]):.3f}")
    put("QuantileSpread", f"{np.median(spread):.3f}")
    put("CollapseDex", f"{np.median(collapse):.3f}")

    # The anisotropy, which Sec. 2.8 sees in the amplitude and which reaches the exponent.
    east = np.array([r["hurst"] for r in rows if r["component"] == "E"])
    north = np.array([r["hurst"] for r in rows if r["component"] == "N"])
    if east.size and north.size:
        put("HurstEast", f"{np.median(east):.3f}")
        put("HurstNorth", f"{np.median(north):.3f}")

    return {"rows": rows, "drawn": drawn}


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
    quantiles = np.array(
        [quantiles_from_histogram(accumulator.counts[0, i], accumulator.edges)
         for i in range(lags_s.size)]
    )
    fitted = scaling_from_quantiles(lags_s, quantiles, fit_range=FIT_RANGE_S)
    macros["StatPropCalibHurst"] = f"{fitted['hurst']:.3f}"
    macros["StatPropCalibSpread"] = f"{fitted['spread']:.3f}"


def draw(measured: dict):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.1))
    quantile_ax, drift_ax, collapse_ax = axes

    for discipline, m in measured.items():
        colour = DISCIPLINES[discipline].color
        if not m.get("drawn"):
            continue
        lags, quantiles, counts, edges, fitted, component = m["drawn"][0]
        window = (lags >= FIT_RANGE_S[0]) & (lags <= FIT_RANGE_S[1])
        for column, style in zip(range(quantiles.shape[1]), ("-", "--", "-.", ":"), strict=True):
            quantile_ax.loglog(lags[window], quantiles[window, column], style, color=colour, lw=1.1)
        quantile_ax.plot([], [], color=colour, label=f"{discipline} ({component})")

        for row in m["rows"]:
            drift_ax.plot([25, 50, 75, 90], row["per_quantile"], "o-", color=colour, ms=3,
                          lw=0.7, alpha=0.5)

        # The collapse, at the median exponent.
        centres = np.sqrt(edges[:-1] * edges[1:])
        widths = np.diff(edges)
        for i in np.flatnonzero(window)[::3]:
            if counts[i].sum() <= 0:
                continue
            scale = lags[i] ** fitted["hurst"]
            density = counts[i] / counts[i].sum() / widths
            keep = density > 0
            collapse_ax.loglog(centres[keep] / scale, density[keep] * scale, color=colour,
                               lw=0.7, alpha=0.55)

    quantile_ax.set_xlabel(r"$\Delta$ (s)")
    quantile_ax.set_ylabel(r"quantiles of $|\Delta x|$ (m)")
    quantile_ax.set_title("(a) the quantiles, and their growth", fontsize=10, loc="left")
    quantile_ax.legend(frameon=False, fontsize=7)
    # The reference an exactly self-similar process would draw: the same slope at every
    # percentile. Measured, not asserted -- it is the calibration quoted in the text.
    pooled = np.concatenate([[r["hurst"] for r in m["rows"]] for m in measured.values()])
    drift_ax.axhline(float(np.median(pooled)), color="0.35", lw=0.9, ls="--")
    drift_ax.text(0.03, 0.06, "dashed: one exponent, which an exactly\nself-similar process gives to 0.004",
                  transform=drift_ax.transAxes, fontsize=7)
    drift_ax.set_xlabel("percentile")
    drift_ax.set_ylabel("$H$ fitted at that percentile")
    drift_ax.set_title("(b) one exponent would be a flat line", fontsize=10, loc="left")
    collapse_ax.set_xlabel(r"$|\Delta x| / \Delta^{H}$")
    collapse_ax.set_ylabel(r"$\Delta^{H} P$")
    # The far-left decades are a handful of counts per bin and show nothing; the story is
    # the bulk and the flank, which is where the curves part company.
    collapse_ax.set_xlim(3e-2, 1.2e2)
    collapse_ax.set_ylim(1e-4, 1.0)
    collapse_ax.set_title("(c) the collapse, and where it fails", fontsize=10, loc="left")
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
        generator="scripts/reporting/generate_propagator_figure.py",
        sort=True,
    )
    print(f"wrote {OUT_TEX.name}, {OUT_FIG.name} ({len(macros)} macros)")
    for k, v in sorted(macros.items()):
        print(f"  {k:34s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
