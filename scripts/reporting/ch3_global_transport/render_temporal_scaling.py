#!/usr/bin/env python3
"""Draw the completed temporal scaling measurement, without refitting."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    """Identify complete numerical and figure bytes."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    """Create complete vector figures and tables from saved small arrays."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "thesis/generated")
    args = parser.parse_args()
    report = json.loads((args.measurement / "report.json").read_text())
    assert report["status"] == "complete"
    args.out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )
    colours = ["#147d92", "#7b4173", "#b97729"]
    regimes = list(report["protocol"]["regimes"])
    groups = ["east", "north", "spatial", "temporal"]
    labels = ["Signed E", "Signed N", "Spatial", "Temporal"]
    outputs, inputs = {}, {"report.json": digest(args.measurement / "report.json")}
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), sharey=True, layout="constrained")
    for ax, (discipline, records) in zip(axes, report["results"].items(), strict=True):
        for k, regime in enumerate(regimes):
            rec = records[regime]
            points = np.array([rec["diagnostics"][g]["distance"] for g in groups])
            lo = np.array([rec["diagnostics"][g]["lower_95"] for g in groups])
            hi = np.array([rec["diagnostics"][g]["upper_95"] for g in groups])
            x = np.arange(4) + (k - 1) * 0.23
            lags = rec["lags_s"]
            ax.errorbar(
                x,
                points,
                yerr=[points - lo, hi - points],
                fmt="o",
                markersize=4,
                capsize=2,
                color=colours[k],
                label=f"{lags[0]:,}\N{EN DASH}{lags[-1]:,} s",
            )
        for tol in report["protocol"]["tolerances"]:
            ax.axhline(tol, color=".65", lw=0.6, ls="--", zorder=0)
        ax.set(
            xticks=np.arange(4),
            xticklabels=labels,
            title=discipline.capitalize(),
            ylim=(0, 0.7),
        )
        ax.legend(fontsize=8, loc="upper left")
    axes[0].set_ylabel("Maximum projected CDF discrepancy")
    path = args.out / "ch3_temporal_scaling_distances.pdf"
    fig.savefig(path)
    plt.close(fig)
    outputs[path.name] = digest(path)
    thresholds = report["protocol"]["cdf_thresholds"]
    for discipline, slug in (("paragliders", "para"), ("hang gliders", "hang")):
        path = args.measurement / slug / "intermediate.npz"
        expected = report["results"][discipline]["intermediate"]["arrays_sha256"]
        assert digest(path) == expected
        inputs[f"{slug}/intermediate.npz"] = expected
        with np.load(path) as arrays:
            curves = arrays["mean_cdfs"]
        fig, axes = plt.subplots(
            1, 3, figsize=(10, 3), sharey=True, layout="constrained"
        )
        # E1-E2 is fixed direction 7, selected here for its direct physical meaning.
        for ax, index, title in zip(
            axes,
            [0, 1, 7],
            [r"Signed $E_1$", r"Signed $N_1$", r"Temporal $(E_1-E_2)/\sqrt{2}$"],
            strict=True,
        ):
            for lag, curve, colour in zip(
                report["protocol"]["regimes"]["intermediate"],
                curves,
                plt.cm.viridis(np.linspace(0.05, 0.9, len(curves))),
                strict=True,
            ):
                ax.plot(
                    thresholds, curve[index], marker=".", color=colour, label=f"{lag} s"
                )
            ax.set(
                title=title,
                xlim=(-2.2, 2.2),
                ylim=(-0.02, 1.02),
                xlabel="Rescaled signed projection",
            )
        axes[0].set_ylabel("Held-out flight-weighted CDF")
        axes[-1].legend(fontsize=7)
        path = args.out / f"ch3_temporal_scaling_{slug}.pdf"
        fig.savefig(path)
        plt.close(fig)
        outputs[path.name] = digest(path)
    population = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r" & Lag range (s) & Train & Validate & Days & $H$ & $n_{\rm orig,val}$\\",
        r"\midrule",
    ]
    distances = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r" & Lag range (s) & Signed E & Signed N & Spatial & Temporal\\",
        r"\midrule",
    ]
    for discipline, records in report["results"].items():
        for rec in records.values():
            lags = rec["lags_s"]
            label = "Para" if discipline == "paragliders" else "Hang"
            start = f"{label} & {lags[0]}--{lags[-1]}"
            population.append(
                start
                + f" & {rec['n_training_flights']} & {rec['n_validation_flights']}"
                + f" & {rec['n_validation_days']} & {rec['fit']['common_h']:.3f}"
                + f" & {rec['n_validation_origins']}"
                + r"\\"
            )
            entries = [
                f"{rec['diagnostics'][g]['distance']:.3f} "
                f"({rec['diagnostics'][g]['upper_95']:.3f})"
                for g in groups
            ]
            distances.append(start + " & " + " & ".join(entries) + r"\\")
    for name, rows in (("population", population), ("bounds", distances)):
        path = args.out / f"ch3_temporal_scaling_{name}.tex"
        path.write_text("\n".join([*rows, r"\bottomrule", r"\end{tabular}"]) + "\n")
        outputs[path.name] = digest(path)
    (args.measurement.parent / "figure-manifest.json").write_text(
        json.dumps(
            {
                "inputs": inputs,
                "script_sha256": digest(__file__),
                "outputs": outputs,
                "operation": "Render recorded training fits and held-out CDFs; "
                "no fit or bootstrap rerun.",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
