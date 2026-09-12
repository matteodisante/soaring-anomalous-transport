#!/usr/bin/env python3
"""Draw projection-sized figures from frozen reports; no fitting or trajectory reads."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
COLORS = {"paragliders": "#3477A8", "hang gliders": "#B5482A"}
EQUIPMENT = {"EN A/B": "#6A3D9A", "EN C/D/CCC": "#C98A1E"}


def axes(size=(6.0, 2.7), ncols=1):
    """Create legible panels without decorative grids."""
    fig, ax = plt.subplots(1, ncols, figsize=size, layout="constrained", squeeze=False)
    for a in ax.flat:
        a.spines[["top", "right"]].set_visible(False)
        a.tick_params(direction="out", length=3)
    return fig, ax[0]


def save(fig, name):
    """Preserve vectors and omit volatile PDF dates."""
    fig.savefig(ROOT / "assets" / (name + ".pdf"), metadata={"CreationDate": None})
    plt.close(fig)


def main():
    """Redraw recorded arrays; explicitly preserve their original weighting."""
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral"],
            "mathtext.fontset": "stix",
            "font.size": 11,
            "axes.labelsize": 12,
            "axes.titlesize": 12,
            "legend.fontsize": 10,
            "axes.linewidth": 0.7,
            "lines.linewidth": 1.6,
            "pdf.fonttype": 42,
        }
    )
    rev = json.loads(gzip.decompress((ROOT / "data/ch3_revision.json.gz").read_bytes()))
    if rev["measurement_contract"]["scope"] != "full eligible archive":
        raise ValueError("The complete eligible archive is required")
    duration = json.loads((ROOT / "data/duration_equipment.json").read_text())
    results = rev["results"]
    probs = np.array(rev["measurement_contract"]["probabilities"]) * 100
    fig, axs = axes((6.1, 2.5), 2)
    for ax, (name, r) in zip(axs, results.items(), strict=True):
        exp = np.array(r["quantile_control"]["exponents"])[:, 2, :]
        ax.plot(probs, exp[0], "o--", color=".65", label="Changing pool", ms=4)
        ax.plot(
            probs,
            exp[3],
            "o-",
            color=COLORS[name],
            label="Fixed flights, weights, origins",
            ms=4,
        )
        ax.set(
            title=f"{name.capitalize()} ($N_*={r['n_fixed']}$)",
            xlabel="Percentile",
            xticks=probs,
        )
    axs[0].set_ylabel(r"Fitted quantile slope $H_p$")
    axs[0].legend(loc="upper right", fontsize=8.5)
    save(fig, "talk-quantile-slopes")

    fig, (ax,) = axes((5.7, 2.8))
    for name, r in results.items():
        q = np.array(r["quantile_control"]["quantiles"])[3, :, 2, :]
        ax.semilogx(
            r["lags_s"], q[:, 3] / q[:, 0], color=COLORS[name], label=name.capitalize()
        )
    ax.set(
        xlabel=r"Lag $\tau$ [s]",
        ylabel=r"$Q_{0.90}(\tau)/Q_{0.25}(\tau)$",
        xlim=(10, 10000),
    )
    ax.legend(frameon=False)
    save(fig, "talk-quantile-ratio")

    fig, (ax,) = axes((4.6, 3.0))
    q = np.array(rev["q"])
    ax.plot(q, q / 2, ":", color=".6", label="Brownian")
    theory_q = np.sort(np.r_[q, 1.5])
    ax.plot(
        theory_q,
        np.where(theory_q < 1.5, theory_q / 1.5, theory_q + 1 - 1.5),
        "--",
        color=".3",
        label=r"Lévy walk, $\beta=1.5$ (reference)",
    )
    for name, r in results.items():
        ax.plot(q, r["zeta"], "o-", color=COLORS[name], ms=3.5, label=name.capitalize())
    ax.set(
        xlabel=r"Moment order $q$", ylabel=r"Fitted exponent $\zeta(q)$", xlim=(0, 4.05)
    )
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    save(fig, "talk-moments")

    fig, (ax,) = axes((4.6, 2.9))
    for name, r in results.items():
        ax.semilogx(
            r["lags_s"],
            r["mardia"],
            "o-",
            color=COLORS[name],
            ms=3,
            label=name.capitalize(),
        )
    ax.axhline(0, color=".5", lw=0.8, ls="--")
    ax.set(
        xlabel=r"Lag $\tau$ [s]",
        ylabel=r"Centred kurtosis excess $K_M$",
        xlim=(10, 10000),
    )
    ax.legend(frameon=False)
    save(fig, "talk-kurtosis")

    fig, axs = axes((6.2, 2.5), 3)
    theta = np.linspace(0, 2 * np.pi, 241)
    circle = np.array([np.cos(theta), np.sin(theta)])
    for ax, region, color in zip(
        axs,
        ["Alps", "Pyrenees", "Channel Coast"],
        ["#8E3B5C", "#8A6240", "#2E7D8A"],
        strict=True,
    ):
        row = next(
            r
            for r in results["paragliders"]["pca"]
            if r["region"] == region and r["lag_s"] == 1000
        )
        covariance = np.array(row["covariance"])
        eigenvalues, eigenvectors = np.linalg.eigh(covariance / np.trace(covariance))
        ellipse = eigenvectors @ np.diag(np.sqrt(eigenvalues)) @ circle
        ax.plot(*ellipse, color=color)
        major = eigenvectors[:, -1] * np.sqrt(eigenvalues[-1])
        ax.plot([-major[0], major[0]], [-major[1], major[1]], "--", color=".4", lw=1)
        ax.axhline(0, color=".85", lw=0.6)
        ax.axvline(0, color=".85", lw=0.6)
        ax.set(
            xlim=(-1.05, 1.05),
            ylim=(-1.05, 1.05),
            aspect="equal",
            title=(
                f"{region}\n$N={row['n_flights']}$; "
                f"$\\lambda_1/\\lambda_2={row['ratio']:.2f}$"
            ),
            xlabel=r"$\delta E/\sqrt{\mathrm{tr}\,\Sigma}$",
            xticks=[-1, 0, 1],
            yticks=[-1, 0, 1],
        )
        ax.tick_params(labelsize=10)
    axs[0].set_ylabel(r"$\delta N/\sqrt{\mathrm{tr}\,\Sigma}$")
    save(fig, "talk-pca")

    fig, axs = axes((6.2, 2.75), 2)
    ec = duration["equipment_control"]
    lag = np.array(duration["paragliders"]["lags_s"])
    styles = ["-", "--", "-.", ":"]
    for ci, (ax, (_name, color)) in enumerate(zip(axs, EQUIPMENT.items(), strict=True)):
        for cohort, style in zip(ec["cohorts"], styles, strict=True):
            c = cohort["classes"][ci]
            y = np.array(c["curve"], dtype=float)
            support = np.array(c["support"])
            y[support < 30] = np.nan
            h = cohort["threshold_s"] / 3600
            if h > 0:
                y[lag > cohort["threshold_s"] / 2] = np.nan
            label = "All durations" if h == 0 else rf"$T\geq {h:g}$ h"
            ax.loglog(lag, y, style, color=color, label=label)
        ax.set(
            title=("EN A/B" if ci == 0 else "EN C/D/CCC"),
            xlabel=r"Lag $\tau$ [s]",
            xlim=(10, 10000),
            ylim=(3e3, 4e9),
        )
        ax.legend(frameon=False, fontsize=9, loc="upper left")
    axs[0].set_ylabel(r"Equal-flight $M_2(\tau)$ [m$^2$]")
    save(fig, "talk-duration")

    fig, (ax,) = axes((4.6, 2.8))
    shown = np.isin(lag, ec["ratio_display_lags_s"])
    for key, label, style in [
        ("raw_four_hour_ratio", "Observed class mixture", "-"),
        ("fixed_mix_four_hour_ratio", "Fixed class proportions", "--"),
    ]:
        y = np.array(ec[key], dtype=float)
        y[~shown] = np.nan
        ax.semilogx(lag, y, style, color=".2", label=label)
    ax.axhline(1, color=".7", lw=0.7)
    ax.set(
        xlabel=r"Lag $\tau$ [s]",
        ylabel=r"$M_2(T\geq4\,\mathrm{h})/M_2(\mathrm{all})$",
        xlim=(10, 10000),
    )
    ax.legend(frameon=False, fontsize=9)
    save(fig, "talk-composition")

    outputs = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "assets").glob("talk-*.pdf"))
    }
    provenance = {
        "operation": "Plot frozen arrays; no fitted or simulated values added.",
        "inputs": {
            n: hashlib.sha256((ROOT / "data" / n).read_bytes()).hexdigest()
            for n in ["ch3_revision.json.gz", "duration_equipment.json"]
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "outputs": outputs,
    }
    (ROOT / "figure-manifest.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"Drew {len(outputs)} presentation figures from frozen reports.")


if __name__ == "__main__":
    main()
