"""Regional PCA panels and reference values shared by full and focused reports."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

from soaring.analysis.observables.regional_pca import PCA_REFERENCE_LAG_S
from soaring.reporting.style import PCA_LAG_COLORS, paper_style


def pca_macros(summaries, disciplines):
    """Keep the PCA reference scale independent of the duration diagnostic grid."""
    macros = {}
    for name, glider in disciplines.items():
        macros[f"StatRev{glider.tag}PcaReferenceLagS"] = str(PCA_REFERENCE_LAG_S)
        for row in summaries[name]["pca"]:
            if row["lag_s"] != PCA_REFERENCE_LAG_S:
                continue
            prefix = f"StatRev{glider.tag}Pca{row['region'].replace(' ', '')}"
            macros[prefix + "Flights"] = str(row["n_flights"])
            macros[prefix + "Ratio"] = f"{row['ratio']:.2f}"
            macros[prefix + "Angle"] = f"{row['angle_deg']:.1f}"
    return macros


def pca_figure(records, regions):
    """Render every supported lag with matching ellipse, marker and annotation."""
    paper_style()
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "lines.linewidth": 1.1,
            "pdf.fonttype": 42,
            "savefig.bbox": None,
        }
    )
    fig, axes = plt.subplots(
        len(regions),
        2,
        figsize=(6.1, 2.6 * len(regions)),
        layout="constrained",
        squeeze=False,
    )
    for row, name in enumerate(regions):
        rows = sorted(
            (r for r in records if r["region"] == name), key=lambda r: r["lag_s"]
        )
        left, right = axes[row]
        right.semilogx(
            [r["lag_s"] for r in rows], [r["ratio"] for r in rows], "-", color=".45"
        )
        for record in rows:
            lag = record["lag_s"]
            color = PCA_LAG_COLORS[lag]
            values = np.linalg.eigvalsh(record["covariance"])
            scale = np.sqrt(values.sum())
            left.add_patch(
                Ellipse(
                    (0, 0),
                    2 * np.sqrt(values[-1]) / scale,
                    2 * np.sqrt(values[0]) / scale,
                    angle=record["angle_deg"],
                    fill=False,
                    color=color,
                    lw=1.6,
                    label=f"{lag} s; N={record['n_flights']}",
                )
            )
            right.plot(lag, record["ratio"], "o", color=color, ms=5)
            right.annotate(
                f"{record['angle_deg']:.0f}°",
                (lag, record["ratio"]),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )
        left.set(
            title=name,
            xlabel="East / centred RMS radius",
            ylabel="North / centred RMS radius",
            xlim=(-1.1, 1.1),
            ylim=(-1.1, 1.1),
            aspect="equal",
            xticks=(-1, 0, 1),
            yticks=(-1, 0, 1),
        )
        left.axhline(0, color=".8", lw=0.6)
        left.axvline(0, color=".8", lw=0.6)
        right.set(
            xlabel=r"Lag $\tau$ [s]", ylabel=r"$\lambda_1/\lambda_2$", xlim=(6, 17000)
        )
        right.set_ylim(1, max([r["ratio"] for r in rows], default=1) * 1.35)
        handles, labels = left.get_legend_handles_labels()
        right.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.3),
            frameon=False,
            ncol=2,
            columnspacing=0.8,
        )
        for ax in (left, right):
            ax.grid(visible=False)
    return fig
