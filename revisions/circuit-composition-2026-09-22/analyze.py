"""Review altitude contrasts after fixing the open/closed flight proportions.

Reuses published curves and independently verified, paired bootstrap replicates.
Writes review artifacts only; does not modify the thesis or production reports.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / "thesis/generated/ch3_conditional.json"
REPLICATES = (
    ROOT / "revisions/conditional-bootstrap-audit-2026-09-21/verified_replicates.npz"
)
NAMES = ["Plains", "Hills", "Low mountains", "High mountains"]
COLORS = ["#547A3B", "#9B7A35", "#9A4C68", "#60528C"]


def signature(path):
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def summary(values):
    lo, hi = np.percentile(values[1:], [5, 95])
    return {"point": float(values[0]), "low": float(lo), "high": float(hi)}


def main():
    report = json.loads(SOURCE.read_text())
    groups = report["groups"]
    lags = np.asarray(report["lags_s"], dtype=float)
    x = np.log10(lags)
    centered_x = x - x.mean()

    def fit_h(curves):
        assert np.isfinite(curves).all() and (curves > 0).all()
        return np.log10(curves) @ centered_x / (centered_x @ centered_x) / 2

    p_ref = groups["open"]["flights"] / (
        groups["open"]["flights"] + groups["closed"]["flights"]
    )
    curves = {}
    with np.load(REPLICATES) as archive:
        np.testing.assert_array_equal(archive["lags"], lags)
        for i in range(4):
            for key in (f"alt{i}", f"open_{i}", f"closed_{i}"):
                curves[key] = archive[key].copy()
                np.testing.assert_allclose(
                    curves[key][0], groups[key]["msd"]["point"], rtol=1e-12
                )
                np.testing.assert_allclose(
                    fit_h(curves[key])[0],
                    groups[key]["fit"]["hurst"]["point"],
                    atol=2e-14,
                )

    rows, standardized, known_h, sweep = [], {}, {}, []
    common_fractions = np.linspace(0, 1, 201)
    for i, name in enumerate(NAMES):
        o, c = groups[f"open_{i}"], groups[f"closed_{i}"]
        mo, mc = curves[f"open_{i}"], curves[f"closed_{i}"]
        p = o["flights"] / (o["flights"] + c["flights"])
        observed_known = p * mo[0] + (1 - p) * mc[0]
        known_h[i] = float(fit_h(observed_known))
        standardized[i] = fit_h(p_ref * mo + (1 - p_ref) * mc)
        h_sweep = fit_h(
            common_fractions[:, None] * mo[0]
            + (1 - common_fractions[:, None]) * mc[0]
        )
        sweep.append(h_sweep)
        shares = p * mo[0] / observed_known
        rows.append(
            {
                "class": name,
                "n_open": o["flights"],
                "n_closed": c["flights"],
                "n_unknown": groups[f"alt{i}"]["circuit_counts"].get("unknown", 0),
                "p_open_known": p,
                "H_published": summary(fit_h(curves[f"alt{i}"])),
                "H_known_only": known_h[i],
                "H_common_fraction": summary(standardized[i]),
                "H_half_open": float(fit_h(0.5 * mo[0] + 0.5 * mc[0])),
                "H_open": summary(fit_h(mo)),
                "H_closed": summary(fit_h(mc)),
                "msd_common_fraction": (p_ref * mo[0] + (1 - p_ref) * mc[0]).tolist(),
                "open_share_of_msd": shares.tolist(),
                "H_fraction_sweep": h_sweep.tolist(),
            }
        )

    contrasts = []
    for i in (0, 1):
        for j in (2, 3):
            baseline = known_h[i] - known_h[j]
            standardized_delta = standardized[i] - standardized[j]
            balanced_delta = rows[i]["H_half_open"] - rows[j]["H_half_open"]
            contrasts.append(
                {
                    "comparison": f"{NAMES[i]} - {NAMES[j]}",
                    "observed_known_delta_H": baseline,
                    "common_fraction_delta_H": summary(standardized_delta),
                    "reduction_fraction": float(1 - standardized_delta[0] / baseline),
                    "half_open_delta_H": balanced_delta,
                    "half_open_reduction_fraction": 1 - balanced_delta / baseline,
                }
            )

    result = {
        "sources": [signature(SOURCE), signature(REPLICATES), signature(Path(__file__))],
        "method": {
            "mixture": "M_a(p,tau) = p M_open,a(tau) + (1-p) M_closed,a(tau)",
            "fit": "Half OLS slope of log10 mixed MSD versus log10 lag; 33 lags, 10-10000 s",
            "common_open_fraction": p_ref,
            "target": "Pooled open fraction among all classified cohort flights",
            "unknowns": "78 unclassified flights excluded from mixtures and known-only baselines",
            "intervals": "Pointwise 5-95 percentiles of 1000 paired site-day bootstrap draws; p fixed",
            "interpretation": "Descriptive standardization; reduction depends on reference p and is not causal attribution",
        },
        "lags_s": lags.tolist(),
        "common_fraction_sweep": common_fractions.tolist(),
        "classes": rows,
        "contrasts": contrasts,
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, 4.7), gridspec_kw={"width_ratios": [0.9, 1.25]})
    fractions = np.asarray([row["p_open_known"] for row in rows])
    positions = np.arange(4)
    ax.bar(positions, 100 * fractions, color="#7B3294", label="Open")
    ax.bar(positions, 100 * (1 - fractions), bottom=100 * fractions, color="#008577", label="Closed")
    for i, p in enumerate(fractions):
        ax.text(i, 100 * p / 2, f"{p:.1%}", ha="center", va="center", color="white", weight="bold")
    ax.set_xticks(positions, ["Plains", "Hills", "Low\nmountains", "High\nmountains"])
    ax.set_ylabel("Fraction of classified flights (%)")
    ax.set_ylim(0, 100)
    ax.set_title("(a) The observed circuit mix differs sharply", loc="left", fontsize=11)
    ax.legend(loc="upper right", bbox_to_anchor=(1, -0.14), ncol=2, frameon=False)

    for i, row in enumerate(rows):
        bx.plot(100 * common_fractions, sweep[i], color=COLORS[i], label=NAMES[i], lw=2)
        bx.scatter(100 * fractions[i], row["H_known_only"], color=COLORS[i], s=50, zorder=4)
        fixed = row["H_common_fraction"]
        bx.errorbar(
            100 * p_ref, fixed["point"],
            yerr=[[fixed["point"] - fixed["low"]], [fixed["high"] - fixed["point"]]],
            fmt="s", ms=5, color=COLORS[i], mfc="white", capsize=3, zorder=5,
        )
    bx.axvline(100 * p_ref, ls="--", color="0.5", lw=1)
    bx.set_xlim(0, 100)
    bx.set_ylim(0.80, 0.965)
    bx.set_xlabel("Open-flight fraction used to mix each class's MSDs (%)")
    bx.set_ylabel("H fitted after mixing the MSD curves")
    bx.set_title("(b) Matching the circuit mix leaves a residual H gap", loc="left", fontsize=11)
    bx.grid(axis="y", alpha=0.2)
    bx.legend(loc="lower right", frameon=False)
    bx.text(0.03, 0.98, f"Dots: observed mix\nSquares: common {p_ref:.1%} open", transform=bx.transAxes, va="top", fontsize=9)
    fig.subplots_adjust(left=0.065, right=0.985, top=0.91, bottom=0.23, wspace=0.30)
    fig.text(0.065, 0.03, "Fixed cohort; 10-10000 s. Curves hold circuit-specific MSDs fixed and vary only their flight fractions.\nSquares show nominal 90% paired site-day bootstrap intervals at the fixed reference fraction.", fontsize=9)
    fig.savefig(OUT / "composition_control.png", dpi=200)
    plt.close(fig)

    print(f"Common open fraction: {p_ref:.6%}")
    for row in rows:
        h = row["H_common_fraction"]
        print(f"{row['class']}: H {row['H_known_only']:.6f} -> {h['point']:.6f} [{h['low']:.6f}, {h['high']:.6f}]")
    for row in contrasts:
        h = row["common_fraction_delta_H"]
        print(f"{row['comparison']}: residual {h['point']:.6f} [{h['low']:.6f}, {h['high']:.6f}]; reduction {row['reduction_fraction']:.1%}; 50/50 reduction {row['half_open_reduction_fraction']:.1%}")


if __name__ == "__main__":
    main()
