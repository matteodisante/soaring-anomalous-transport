"""Measure and redraw Section 3.2 from validated fixed-cohort flight MSDs."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from check_bootstrap_reliability import load_inputs, signature
from conditional_plot_style import CONDITIONAL_COLORS
from circuit_msd_weights import publish_weights
from render_ch3_fixed import axes_style, band
from summarize_ch3_fixed import fit_summary, portable, summary

from soaring.analysis.observables.conditional_transport import (
    BANDS,
    EQUIPMENT,
    REGIONAL_TERRAIN,
    strata,
)
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means
from soaring.analysis.observables.fixed_transport import LAGS, log_fit
from soaring.analysis.regions import REGIONAL_BOXES as REGIONS
from soaring.analysis.regions import region_box_masks

PREFIX = "ch3_conditional"
PANELS = {
    "circuit": [("All initial altitudes", [("open", "Open"), ("closed", "Closed")])],
    "circuit_geometry": [
        (
            "Closed routes",
            [("triangle", "Triangle"), ("out_and_return", "Out-and-return")],
        )
    ],
    "altitude": [("All circuit types", [(f"alt{i}", b) for i, b in enumerate(BANDS)])],
    "regions": [
        ("Low + High mountains", [("alps", "Alps"), ("pyrenees", "Pyrenees")]),
        (
            "Plains + Hills",
            [
                ("channel_coast", "Channel Coast"),
                ("champagne_lorraine", "Champagne-Lorraine"),
            ],
        ),
    ],
    "equipment": [
        ("All initial altitudes", [("beginners", "Beginners"), ("experts", "Experts")])
    ],
    "equipment_altitude": [
        (
            group.capitalize(),
            [(f"{group}_alt{i}", band) for i, band in enumerate(BANDS)],
        )
        for group in ("beginners", "experts")
    ],
}


def measure(data, out):
    """Validate source identities and reuse exactly the archived paired draws."""
    reference = json.loads((data / "report.json").read_text())
    if reference.get("status") != "complete":
        raise ValueError("A complete source report is required")
    frame, cohort, values, baseline, provenance = load_inputs(data, "para", reference)
    members = frame.loc[cohort].copy()
    masks = strata(members)
    labels = members.cluster.to_numpy(dtype=int)
    archived = np.load(data / "para/cluster-draws.npy", mmap_mode="r")
    curves, exponents, results = {}, {}, {}
    membership = members[
        ["flight_id", "wing_class", "task", "altitude_band", "lon0", "lat0", "cluster"]
    ].copy()
    for key, mask in masks.items():
        membership[key] = mask
        n = int(mask.sum())
        if not n:
            raise ValueError(f"Empty requested stratum: {key}")
        # Omit zero-contribution columns without redrawing or relabelling draws.
        occupied, local = np.unique(labels[mask], return_inverse=True)
        curve = bootstrap_means(values[mask], local, archived[:, occupied])
        if not np.isfinite(curve).all() or (curve <= 0).any():
            raise ValueError(f"Incomplete bootstrap support: {key}")
        np.testing.assert_allclose(curve[0], values[mask].mean(axis=0), rtol=1e-12)
        curves[key] = curve
        exponents[key] = log_fit(LAGS, curve)["slope"] / 2
        results[key] = {
            "flights": n,
            "clusters": len(occupied),
            "valid_replicates": len(curve) - 1,
            "msd": summary(curve),
            "fit": fit_summary(LAGS, curve, (10, 10000)),
            "circuit_counts": members.loc[mask, "task"].value_counts().to_dict(),
        }
        print(f"{key}: {n} flights, H={exponents[key][0]:.4f}", flush=True)
    for name, box in region_box_masks(members).items():
        key = name.lower().replace(" ", "_").replace("-", "_")
        results[key]["box_flights"] = int(box.sum())
        results[key]["altitude_excluded"] = int((box & ~masks[key]).sum())
        results[key]["terrain"] = REGIONAL_TERRAIN[name]
    np.testing.assert_allclose(curves["all"], baseline, rtol=1e-10)
    for task in ("open", "closed"):
        for i in range(4):
            key = f"{task}_{i}"
            np.testing.assert_allclose(
                curves[key][0],
                reference["results"]["para"]["groups"][key]["curve"]["point"],
                rtol=1e-10,
            )
    comparisons = {}

    def contrast(key, terms):
        differences = sum(weight * exponents[group] for group, weight in terms)
        comparisons[key] = {"terms": terms, "hurst": summary(differences)}

    contrast("open_closed", [("open", 1), ("closed", -1)])
    contrast("triangle_out_and_return", [("triangle", 1), ("out_and_return", -1)])
    contrast("experts_beginners", [("experts", 1), ("beginners", -1)])
    for i in range(4):
        contrast(
            f"equipment_alt{i}", [(f"experts_alt{i}", 1), (f"beginners_alt{i}", -1)]
        )
        for j in range(i + 1, 4):
            contrast(f"alt{i}_alt{j}", [(f"alt{i}", 1), (f"alt{j}", -1)])
            contrast(
                f"equipment_interaction_{i}_{j}",
                [
                    (f"experts_alt{i}", 1),
                    (f"beginners_alt{i}", -1),
                    (f"experts_alt{j}", -1),
                    (f"beginners_alt{j}", 1),
                ],
            )
    contrast("mountain_regions", [("alps", 1), ("pyrenees", -1)])
    contrast("lowland_regions", [("channel_coast", 1), ("champagne_lorraine", -1)])
    membership.to_parquet(out / "membership.parquet", index=False)
    np.savez_compressed(out / "replicates.npz", lags=LAGS, **curves)
    return portable(
        {
            "status": "complete",
            "source_report": signature(data / "report.json"),
            "source_files": provenance,
            "measurement_script": signature(Path(__file__)),
            "strata_source": signature(
                ROOT / "src/soaring/analysis/observables/conditional_transport.py"
            ),
            "regions_source": signature(ROOT / "src/soaring/analysis/regions.py"),
            "contract": {
                "discipline": "paragliders",
                "cohort": "C_10000; fixed flights and segments",
                "estimator": "equal-flight TA-MSD; all within-segment origins",
                "fit_s": [10, 10000],
                "bands_m": [300, 800, 1500],
                "equipment": EQUIPMENT,
                "regions_west_east_south_north": REGIONS,
                "region_boundaries": "inclusive; initial cleaned position",
                "regional_terrain": REGIONAL_TERRAIN,
                "regional_altitude_selection": {
                    "mountains": "Low + High mountains: initial altitude >= 800 m",
                    "lowlands": "Plains + Hills: initial altitude < 800 m",
                },
                "bootstrap": (
                    "archived site-day draws, paired across every stratum and lag"
                ),
                "resamples": len(archived) - 1,
                "percentiles": [5, 95],
                "unknown_equipment_flights": int(
                    (~(masks["beginners"] | masks["experts"])).sum()
                ),
                "unclassified_circuit_flights": int(
                    (~(masks["open"] | masks["closed"])).sum()
                ),
            },
            "lags_s": LAGS,
            "groups": results,
            "contrasts": comparisons,
        }
    )


def interval(item):
    """Format a numerical estimate and its paired 90% interval for TeX."""
    return rf"${item['point']:.3f}\;[{item['low']:.3f},\,{item['high']:.3f}]$"


def macro_key(key):
    """Map group keys to TeX control sequences, spelling out numeric indices."""
    for i, word in enumerate(("Zero", "One", "Two", "Three")):
        key = key.replace(str(i), word)
    return "".join(part[:1].upper() + part[1:] for part in key.split("_"))


def render(report, out):
    """Draw consistent MSD panels and export all supports and paired contrasts."""
    if report.get("status") != "complete":
        raise ValueError("Refusing incomplete conditional report")
    if report["contract"].get("regional_terrain") != REGIONAL_TERRAIN:
        raise ValueError(
            "This renderer requires the geography-plus-terrain measurement; "
            "remeasure into a fresh output directory"
        )
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "pdf.fonttype": 42,
        }
    )
    lags = np.asarray(report["lags_s"])
    groups = report["groups"]
    for name, panels in PANELS.items():
        fig, axes = plt.subplots(
            1,
            len(panels),
            figsize=(7.1, 3.7),
            squeeze=False,
            layout="constrained",
            sharey=True,
        )
        for ax, (title, entries) in zip(axes.flat, panels, strict=True):
            for key, label in entries:
                color = CONDITIONAL_COLORS[label]
                row = groups[key]
                h = row["fit"]["hurst"]
                band(
                    ax,
                    lags,
                    row["msd"],
                    color,
                    f"{label} (n={row['flights']:,})\n"
                    f"H={h['point']:.3f} [{h['low']:.3f}, {h['high']:.3f}]",
                    scale=1e6,
                )
                fit = row["fit"]
                ax.plot(
                    lags,
                    10 ** fit["intercept"]["point"] * lags ** (2 * h["point"]) / 1e6,
                    "--",
                    color=color,
                    lw=0.9,
                )
            axes_style(ax, logy=True)
            ax.set(xlim=(10, 10000), ylim=(2e-3, 2e4), title=title)
            ax.legend(loc="upper left", fontsize=7.3)
        axes[0, 0].set_ylabel(r"$M_{2,g}(\tau)$ (km$^2$)")
        fig.savefig(
            out / f"{PREFIX}_{name}.pdf",
            bbox_inches="tight",
            metadata={"CreationDate": None, "ModDate": None},
        )
        plt.close(fig)
    rows, curve_rows = [], []
    for key, row in groups.items():
        h = row["fit"]["hurst"]
        rows.append(
            {
                "group": key,
                "flights": row["flights"],
                "clusters": row["clusters"],
                "H": h["point"],
                "H_low": h["low"],
                "H_high": h["high"],
            }
        )
        for j, lag in enumerate(lags):
            curve_rows.append(
                {
                    "group": key,
                    "lag_s": lag,
                    "flights": row["flights"],
                    **{k: row["msd"][k][j] for k in ("point", "low", "high")},
                }
            )
    pd.DataFrame(rows).to_csv(out / f"{PREFIX}_fits.csv", index=False)
    pd.DataFrame(curve_rows).to_csv(out / f"{PREFIX}_curves.csv", index=False)
    macros = []
    for key, row in groups.items():
        tag = macro_key(key)
        macros.extend(
            [
                rf"\newcommand{{\Cond{tag}H}}{{{interval(row['fit']['hurst'])}}}",
                rf"\newcommand{{\Cond{tag}N}}{{{row['flights']}}}",
            ]
        )
        if "altitude_excluded" in row:
            macros.append(
                rf"\newcommand{{\Cond{tag}Excluded}}{{{row['altitude_excluded']}}}"
            )
    for key, row in report["contrasts"].items():
        macros.append(
            rf"\newcommand{{\Cond{macro_key(key)}Delta}}{{{interval(row['hurst'])}}}"
        )
    macros.append(
        rf"\newcommand{{\CondUnknownEquipment}}{{{report['contract']['unknown_equipment_flights']}}}"
    )
    for i, name in enumerate(("Plains", "Hills", "LowMountains", "HighMountains")):
        row = groups[f"alt{i}"]
        pct = 100 * row["circuit_counts"].get("open", 0) / row["flights"]
        macros.append(rf"\newcommand{{\ChThreeConditional{name}OpenPct}}{{{pct:.1f}}}")
    (out / f"{PREFIX}_values.tex").write_text(
        "% Generated conditional transport measurements.\n" + "\n".join(macros) + "\n"
    )
    tables = {
        "regional": [
            ("Mountains", "Alps -- Pyrenees", "mountain_regions"),
            ("Lowlands", "Coast -- Champagne-Lorraine", "lowland_regions"),
        ],
        "equipment": [("All altitudes", "Experts -- beginners", "experts_beginners")]
        + [
            (b, "Experts -- beginners", f"equipment_alt{i}")
            for i, b in enumerate(BANDS)
        ],
    }
    for name, entries in tables.items():
        lines = [
            r"\begin{tabular}{@{}llc@{}}",
            r"\toprule",
            r"Setting & Contrast & $\Delta H$ [5--95\%] \\",
            r"\midrule",
        ]
        for label, contrast, key in entries:
            lines.append(
                f"{label} & {contrast} & {interval(report['contrasts'][key]['hurst'])}"
                + r" \\"
            )
        lines.extend([r"\bottomrule", r"\end{tabular}"])
        (out / f"{PREFIX}_{name}_table.tex").write_text("\n".join(lines) + "\n")
    (out / f"{PREFIX}.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    publish_weights(report, out)


def main():
    """Keep measurements separate from the archived source and allow offline redraw."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--publish", type=Path)
    parser.add_argument("--redraw", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "report.json"
    if args.redraw:
        report = json.loads(path.read_text())
    else:
        if path.exists():
            raise ValueError("Use a fresh output directory or --redraw")
        if args.data is None:
            parser.error("--data is required for measurement")
        report = measure(args.data, args.out)
        path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    render(report, args.out)
    if args.publish:
        args.publish.mkdir(parents=True, exist_ok=True)
        for source in args.out.glob(f"{PREFIX}*"):
            shutil.copy2(source, args.publish / source.name)
    print(f"Completed: {path}", flush=True)


if __name__ == "__main__":
    main()
