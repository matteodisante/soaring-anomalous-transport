#!/usr/bin/env python3
"""Analytical illustrations for Chapter 3; no flight data."""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import lognorm, norm

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting.style import QUANTILE_COLORS

# Static output contract for the provenance checker; paths may be built dynamically.
GENERATED_OUTPUTS = (
    "quantile_scaling_schematic.pdf",
    "closed_loop_schematic.pdf",
    "moment_spectrum_schematic.pdf",
)

OUT = ROOT / "thesis" / "generated"
COLORS = ["#3477A8", "#B5482A", "#4E8A5B", "#CC79A7"]
META = {"Creator": "soaring.analysis", "CreationDate": None, "ModDate": None}
plt.rcParams.update(
    {
        "font.size": 9.5,
        "axes.titlesize": 10,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.bbox": None,
        "pdf.fonttype": 42,
    }
)


def quantiles():
    """A lognormal family whose relative width decreases with scale."""
    tau = np.geomspace(1, 100, 150)
    sigma = 0.9 - 0.1 * np.log(tau)
    probabilities = np.array([0.25, 0.5, 0.75, 0.9])
    z = norm.ppf(probabilities)
    h = 0.85 - 0.1 * z
    q = tau[:, None] ** 0.85 * np.exp(sigma[:, None] * z)
    fig, axs = plt.subplots(2, 2, figsize=(6.1, 5.8), layout="constrained")
    for j, (p, color) in enumerate(
        zip(probabilities, QUANTILE_COLORS.values(), strict=True)
    ):
        axs[0, 0].loglog(tau, q[:, j], color=color, label=f"P{100 * p:g}")
    axs[0, 0].set(
        xlabel=r"Lag $\tau/\tau_0$",
        ylabel="Displacement quantile (a.u.)",
        title="(a) All quantiles grow",
    )
    axs[0, 0].legend(
        ncol=2,
        frameon=False,
        fontsize=9,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.3),
    )
    x = np.linspace(0.015, 4.5, 700)
    for lag, color in [(1, COLORS[0]), (100, COLORS[1])]:
        spread = 0.9 - 0.1 * np.log(lag)
        axs[0, 1].plot(
            x, lognorm.pdf(x, s=spread), color=color, label=rf"$\tau/\tau_0={lag}$"
        )
    axs[0, 1].axvline(1, color=".6", ls=":", lw=1)
    axs[0, 1].set(
        xlabel=r"Displacement / median, $r/Q_{0.50}$",
        ylabel="Probability density",
        title="(b) Relative width decreases",
    )
    axs[0, 1].legend(frameon=False)
    axs[1, 0].plot(100 * probabilities, h, "o-", color=COLORS[0])
    for p, value in zip(probabilities, h, strict=True):
        axs[1, 0].annotate(
            f"{value:.2f}",
            (100 * p, value),
            xytext=(4, 7),
            textcoords="offset points",
            fontsize=9,
        )
    axs[1, 0].set(
        xlabel="Percentile",
        ylabel=r"Quantile exponent $H_p$",
        title="(c) Quantile exponents",
        xticks=100 * probabilities,
        ylim=(0.69, 0.96),
    )
    axs[1, 1].semilogx(tau, q[:, 3] / q[:, 0], color=COLORS[1])
    axs[1, 1].set(
        xlabel=r"Lag $\tau/\tau_0$",
        ylabel=r"$Q_{0.90}/Q_{0.25}$",
        title="(d) Quantile ratio",
    )
    for ax in axs.flat:
        ax.grid(alpha=0.18)
    fig.savefig(OUT / "quantile_scaling_schematic.pdf", metadata=META)
    plt.close(fig)


def geometry():
    """Equal-speed straight and circular motion with exact finite differences."""
    u = np.linspace(0, 1, 500)
    theta = 2 * np.pi * u
    fig = plt.figure(figsize=(6.1, 4.9), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=(0.8, 1.2))
    axs = [
        fig.add_subplot(grid[0, :]),
        fig.add_subplot(grid[1, 0]),
        fig.add_subplot(grid[1, 1]),
    ]
    axs[0].plot(
        np.cos(theta) - 1, np.sin(theta), color=COLORS[1], label="Closed circle"
    )
    axs[0].plot(2 * np.pi * u, 0 * u, color=COLORS[0], label="Straight course")
    axs[0].scatter([0], [0], c="black", s=18, zorder=3)
    axs[0].set(
        xlabel=r"East / radius $a$",
        ylabel=r"North / radius $a$",
        title="(a) Same constant speed",
    )
    axs[0].set_aspect("equal", adjustable="datalim")
    axs[0].legend(frameon=False, fontsize=9, loc="upper right")
    for ax, order in zip(axs[1:], [1, 2], strict=True):
        circle = (4 * np.sin(np.pi * u) ** 2) ** order
        straight = (2 * np.pi * u) ** 2 if order == 1 else 0 * u
        ax.plot(u, straight, color=COLORS[0], label="Straight course")
        ax.plot(u, circle, color=COLORS[1], label="Closed circle")
        ax.axvline(0.5, color=".6", ls=":", lw=1)
        ax.set(
            xlabel=r"Lag / period, $\tau/T_c$",
            ylabel=rf"$V_{order}/a^2$",
            title="(b) Displacement" if order == 1 else "(c) Second difference",
        )
        ax.grid(alpha=0.18)

    fig.savefig(OUT / "closed_loop_schematic.pdf", metadata=META)
    plt.close(fig)


def spectra():
    """The ideal Lévy-walk spectrum versus an MSD-matched monofractal model."""
    q = np.linspace(0, 4, 401)
    beta = 1.5
    h = (3 - beta) / 2
    levy = np.where(q <= beta, q / beta, q + 1 - beta)
    fig, axs = plt.subplots(1, 2, figsize=(6.1, 3.45), layout="constrained")
    axs[0].plot(q, q * h, color=COLORS[0], label=rf"Self-similar, $H={h}$")
    axs[0].plot(q, levy, color=COLORS[1], label=rf"Lévy walk, $\beta={beta}$")
    axs[0].scatter([2], [2 * h], c="black", s=22, zorder=3)
    axs[0].annotate(
        "Same MSD exponent",
        (2, 2 * h),
        xytext=(0.15, 2.2),
        arrowprops={"arrowstyle": "->", "color": ".4"},
        fontsize=9,
    )
    axs[0].set(
        xlabel=r"Moment order $q$",
        ylabel=r"$\zeta(q)$",
        title="(a) Same MSD, different spectra",
    )
    axs[0].legend(
        frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.27)
    )
    nonzero = q > 0
    axs[1].plot(q[nonzero], q[nonzero] * 0 + h, color=COLORS[0])
    axs[1].plot(q[nonzero], levy[nonzero] / q[nonzero], color=COLORS[1])
    axs[1].set(
        xlabel=r"Moment order $q$",
        ylabel=r"$\nu(q)=\zeta(q)/q$",
        title="(b) Exponent per moment order",
    )
    for ax in axs:
        ax.axvline(beta, color=".6", ls=":", lw=1)
        ax.grid(alpha=0.18)
    # Reserve a fixed left margin and space for the outside legend; automatic
    # layout otherwise underestimates the rotated math label's width in PDF.
    fig.set_layout_engine(None)
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.30, top=0.89, wspace=0.36)
    fig.savefig(OUT / "moment_spectrum_schematic.pdf", metadata=META)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    quantiles()
    geometry()
    spectra()
