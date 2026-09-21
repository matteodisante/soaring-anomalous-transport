"""Measure the experimental Section 3.2 factorial analysis and redraw it offline."""

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
from conditional_plot_style import CIRCUIT_COLORS, EQUIPMENT_COLORS
from summarize_ch3_fixed import portable

from soaring.analysis.observables.bootstrap_reliability import calendar_blocks
from soaring.analysis.observables.conditional_transport import BANDS
from soaring.analysis.observables.factorial_transport import (
    COMPONENTS,
    EQUIPMENT_KEYS,
    TASKS,
    bootstrap_summary,
    cell_masks,
    contrasts,
    decompose,
    diagnostics,
)
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means, cluster_draws
from soaring.analysis.observables.fixed_transport import FIT_RANGES, LAGS, log_fit
from soaring.analysis.observables.grid_bootstrap import (
    cell_membership,
    grid_season_labels,
    project_launches,
)

PREFIX = "ch3_factorial"
SEEDS = (20260921, 20260922)
CONTRAST_NAMES = (
    [f"circuit_alt{i}_{e}" for i in range(4) for e in EQUIPMENT_KEYS]
    + [f"equipment_alt{i}_{t}" for i in range(4) for t in TASKS]
    + [
        "attenuation_beginners",
        "attenuation_experts",
        "attenuation_experts_minus_beginners",
    ]
)
COMPONENT_LABELS = (
    "Altitude",
    "Circuit",
    "Equipment",
    r"Altitude $\times$ circuit",
    r"Altitude $\times$ equipment",
    r"Circuit $\times$ equipment",
    "Three-way interaction",
)


def summarize_cube(h):
    """Use one declared family of 19 contrasts for simultaneous intervals."""
    contrast = contrasts(h)
    joined = np.concatenate(
        [
            contrast[k].reshape(len(h), -1)
            for k in ("circuit", "equipment", "endpoints")
        ],
        axis=1,
    )
    joint = bootstrap_summary(joined)
    parts = decompose(h)
    d = diagnostics(h)
    return portable(
        {
            "cells": bootstrap_summary(h),
            "residual": bootstrap_summary(parts["residual"]),
            "components": {k: bootstrap_summary(parts[k]) for k in COMPONENTS},
            "contrasts": {
                name: {
                    k: v[j]
                    for k, v in joint.items()
                    if k not in ("critical", "family_size")
                }
                for j, name in enumerate(CONTRAST_NAMES)
            },
            "contrast_family_size": joint["family_size"],
            "contrast_critical": joint["critical"],
            "r2_add": bootstrap_summary(d["r2_add"]),
            "residual_rms": bootstrap_summary(d["residual_rms"]),
            "variation": {
                key: {
                    name: bootstrap_summary(value) for name, value in component.items()
                }
                for key, component in d["components"].items()
            },
        }
    )


def measure_cube(values, masks, labels, draws):
    """Reaggregate per-flight MSDs, retaining identical draws across all cells."""
    curves = np.empty((len(draws), 16, len(LAGS)))
    support = []
    for j, (key, mask) in enumerate(masks.items()):
        if not mask.any():
            raise ValueError(f"Empty factorial cell: {key}")
        occupied, local = np.unique(labels[mask], return_inverse=True)
        curves[:, j] = bootstrap_means(values[mask], local, draws[:, occupied])
        if not np.isfinite(curves[:, j]).all() or (curves[:, j] <= 0).any():
            raise ValueError(f"Incomplete joint bootstrap support in {key}")
        np.testing.assert_allclose(curves[0, j], values[mask].mean(axis=0), rtol=1e-12)
        counts = np.bincount(local)
        support.append(
            {
                "cell": key,
                "flights": int(mask.sum()),
                "groups": len(occupied),
                "largest_group_fraction": float(counts.max() / counts.sum()),
                "size_balance_index": float(
                    counts.sum() ** 2 / np.sum(counts.astype(float) ** 2)
                ),
            }
        )
    return curves.reshape(len(draws), 4, 2, 2, len(LAGS)), support


def measure(data, out):
    """Validate source provenance and evaluate baseline plus six sensitivity runs."""
    source = json.loads((data / "report.json").read_text())
    if source.get("status") != "complete":
        raise ValueError("A complete source report is required")
    frame, cohort, values, _, provenance = load_inputs(data, "para", source)
    members = frame.loc[cohort].copy()
    masks = cell_masks(members)
    membership_count = np.sum(list(masks.values()), axis=0)
    if (membership_count > 1).any():
        raise ValueError("Factorial cells must be disjoint")
    selected = membership_count == 1
    membership = members[
        ["flight_id", "wing_class", "task", "altitude_band", "cluster", "lon0", "lat0"]
    ].copy()
    membership["factorial_cell"] = "excluded"
    for key, mask in masks.items():
        membership.loc[mask, "factorial_cell"] = key
    membership.to_parquet(out / "membership.parquet", index=False)
    archived = np.load(data / "para/cluster-draws.npy", mmap_mode="r")
    configurations = [("site_day", None, frame.cluster.to_numpy(dtype=int), archived)]
    for days in (1, 3):
        labels, missing = calendar_blocks(frame.date, days)
        if missing[cohort][selected].any():
            raise ValueError("Missing dates in factorial population")
        configurations.append((f"calendar_{days}day", SEEDS, labels, None))
    cells = cell_membership(project_launches(frame), 50)
    labels, missing = grid_season_labels(frame, cells)
    if missing[cohort][selected].any():
        raise ValueError("Missing grid/season labels in factorial population")
    configurations.append(("grid50_altitude_month", SEEDS, labels, None))
    results, stored, observed = {}, {"lags": LAGS}, None
    for grouping, seeds, labels, original in configurations:
        for seed in seeds or (None,):
            key = grouping if seed is None else f"{grouping}_seed{seed}"
            draws = (
                original
                if seed is None
                else cluster_draws(labels, len(archived) - 1, seed)
            )
            curves, support = measure_cube(values, masks, labels[cohort], draws)
            if observed is None:
                observed = curves[0].copy()
                stored["site_day_msd"] = curves
            else:
                np.testing.assert_allclose(curves[0], observed, rtol=1e-12)
            windows = {}
            for interval in FIT_RANGES:
                window = f"{interval[0]}_{interval[1]}"
                fitted = log_fit(LAGS, curves, interval)
                h = fitted["slope"] / 2
                stored[f"{key}_H_{window}"] = h
                windows[window] = summarize_cube(h)
                windows[window]["fit_rms_dex"] = portable(fitted["rms_dex"][0])
            results[key] = {
                "grouping": grouping,
                "seed": seed,
                "archive_groups": int(labels.max()) + 1,
                "support": support,
                "windows": windows,
            }
            print(
                f"Completed {key}: 16 cells, {len(draws) - 1} paired replicates, "
                "four fit windows",
                flush=True,
            )
            del curves, draws
    np.savez_compressed(out / "replicates.npz", **stored)
    return portable(
        {
            "status": "complete",
            "experimental": True,
            "source_report": signature(data / "report.json"),
            "source_files": provenance,
            "measurement_script": signature(Path(__file__)),
            "factorial_source": signature(
                ROOT / "src/soaring/analysis/observables/factorial_transport.py"
            ),
            "strata_source": signature(
                ROOT / "src/soaring/analysis/observables/conditional_transport.py"
            ),
            "resampling_sources": {
                name: signature(ROOT / "src/soaring/analysis/observables" / name)
                for name in (
                    "fixed_bootstrap.py",
                    "grid_bootstrap.py",
                    "bootstrap_reliability.py",
                )
            },
            "contract": {
                "cohort": "C_10000; unchanged flights and segments in every fit window",
                "estimator": "H = half the OLS log-log slope of equal-flight cell MSD",
                "axes": [list(BANDS), list(TASKS), list(EQUIPMENT_KEYS)],
                "cell_weights": "equal; these average cell exponents, not pooled MSDs",
                "cohort_flights": len(members),
                "included_flights": int(selected.sum()),
                "excluded_flights": int((~selected).sum()),
                "resamples": len(archived) - 1,
                "coverage": 0.9,
                "contrast_family": CONTRAST_NAMES,
                "intervals": (
                    "single-step bootstrap maximum absolute centred deviation / "
                    "fixed marginal bootstrap SE; pointwise percentiles also saved"
                ),
                "sampling_frame": (
                    "whole eligible archive resampled, then fixed cohort/cell selected"
                ),
                "calendar_anchor": "2000-01-01; one boundary offset",
                "grid": "50 km UTM cell x altitude x month of year, all years pooled",
                "sensitivity_seeds": SEEDS,
                "interpretation": (
                    "exploratory associations; coverage and cluster independence "
                    "not established"
                ),
            },
            "results": results,
        }
    )


def matrix(values):
    """Display circuit/equipment rows and altitude columns."""
    return np.asarray(values).reshape(4, 2, 2).transpose(1, 2, 0).reshape(4, 4)


def save_figure(fig, out, suffix):
    """Write a deterministic vector figure without modifying the thesis PDF."""
    fig.savefig(
        out / f"{PREFIX}_{suffix}.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def figures(report, out):
    """Draw a contrast plot and an annotated absolute/residual matrix."""
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "pdf.fonttype": 42})
    base = report["results"]["site_day"]
    main = base["windows"]["10_10000"]
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.4), layout="constrained")
    for ax, family, groups, palette, title in (
        (axes[0], "circuit", EQUIPMENT_KEYS, EQUIPMENT_COLORS, "Open - closed"),
        (axes[1], "equipment", TASKS, CIRCUIT_COLORS, "Experts - beginners"),
    ):
        for j, group in enumerate(groups):
            items = [main["contrasts"][f"{family}_alt{i}_{group}"] for i in range(4)]
            y = np.array([v["point"] for v in items])
            errors = np.array(
                [
                    [v["point"] - v["sim_low"] for v in items],
                    [v["sim_high"] - v["point"] for v in items],
                ]
            )
            ax.errorbar(
                np.arange(4) + (j - 0.5) * 0.08,
                y,
                yerr=errors,
                color=palette[group.capitalize()],
                marker="o" if j == 0 else "s",
                markersize=4,
                capsize=3,
                linewidth=1.1,
                label=group.capitalize(),
            )
        ax.axhline(0, color="0.4", linewidth=0.7, linestyle="--")
        ax.set_xticks(
            range(4), ["Plains", "Hills", "Low\nmountains", "High\nmountains"]
        )
        ax.set(title=title, ylabel=r"$\Delta H$", xlabel="Initial-altitude class")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.2)
        ax.legend(fontsize=8, frameon=False)
    fig.suptitle("Experimental factorial analysis", fontsize=10)
    save_figure(fig, out, "contrasts")
    fig, axes = plt.subplots(2, 1, figsize=(7.1, 6.0), layout="constrained")
    h = matrix(main["cells"]["point"])
    residual = matrix(main["residual"]["point"])
    counts = matrix([s["flights"] for s in base["support"]])
    groups = matrix([s["groups"] for s in base["support"]])
    for ax, values, name, cmap in (
        (axes[0], h, r"Cell exponent $H$", "viridis"),
        (
            axes[1],
            residual,
            r"Departure from additivity $r = H - H_{\rm add}$",
            "RdBu_r",
        ),
    ):
        limit = np.abs(residual).max()
        options = {"vmin": -limit, "vmax": limit} if ax is axes[1] else {}
        im = ax.imshow(values, aspect="auto", cmap=cmap, **options)
        fig.colorbar(im, ax=ax, pad=0.025, fraction=0.04)
        ax.set_xticks(range(4), BANDS)
        ax.set_yticks(
            range(4),
            [
                "Open / beginners",
                "Open / experts",
                "Closed / beginners",
                "Closed / experts",
            ],
        )
        ax.set_title(name, fontsize=10)
        for row in range(4):
            for col in range(4):
                value = values[row, col]
                color = (
                    "white"
                    if (
                        im.norm(value) < 0.35
                        if ax is axes[0]
                        else abs(value) > 0.65 * limit
                    )
                    else "black"
                )
                label = (
                    f"{value:.3f}\nn={counts[row, col]:,}; G={groups[row, col]:,}"
                    if ax is axes[0]
                    else f"{value:+.3f}"
                )
                ax.text(
                    col, row, label, ha="center", va="center", color=color, fontsize=8
                )
    fig.suptitle("Experimental factorial analysis", fontsize=10)
    save_figure(fig, out, "cells")


def interval(item, simultaneous=True):
    """Format one contrast interval in H units for the manuscript."""
    low, high = ("sim_low", "sim_high") if simultaneous else ("low", "high")
    return rf"${item['point']:.3f}\;[{item[low]:.3f},\,{item[high]:.3f}]$"


def table(out, suffix, columns, header, rows):
    """Write a booktabs fragment from numeric report content."""
    lines = [
        rf"\begin{{tabular}}{{@{{}}{columns}@{{}}}}",
        r"\toprule",
        header + r" \\",
        r"\midrule",
    ]
    lines.extend(row + r" \\" for row in rows)
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (out / f"{PREFIX}_{suffix}.tex").write_text("\n".join(lines) + "\n")


def render(report, out):
    """Publish figures, tables, macros and full numerical exports from one report."""
    if report.get("status") != "complete" or not report.get("experimental"):
        raise ValueError("A complete experimental report is required")
    figures(report, out)
    base = report["results"]["site_day"]["windows"]["10_10000"]
    rows = []
    for name, label, df in zip(
        COMPONENTS, COMPONENT_LABELS, (3, 1, 1, 3, 3, 1, 3), strict=True
    ):
        v = base["variation"][name]
        share = 100 * v["share"]["point"]
        share_label = f"{share:.2f}" if share >= 0.01 else "$<0.01$"
        rows.append(f"{label} & {df} & {share_label} & {v['rms']['point']:.4f}")
    table(
        out, "decomposition", "lrrr", r"Component & df & Share (\%) & RMS in $H$", rows
    )
    rows = []
    for a, b in FIT_RANGES:
        w = report["results"]["site_day"]["windows"][f"{a}_{b}"]
        c = w["contrasts"]
        rows.append(
            f"{a}--{b} & {w['r2_add']['point']:.3f} & "
            f"{w['residual_rms']['point']:.3f} & "
            f"{c['attenuation_beginners']['point']:.3f} & "
            f"{c['attenuation_experts']['point']:.3f}"
        )
    table(
        out,
        "windows",
        "lrrrr",
        r"Fit range (s) & $R^2_{\rm add}$ & RMS & $D_{\rm B}$ & $D_{\rm E}$",
        rows,
    )
    rows = []
    for grouping, label in (
        ("site_day", "Site--day"),
        ("calendar_1day", "Calendar day"),
        ("calendar_3day", "Three days"),
        ("grid50_altitude_month", "50 km / altitude / month"),
    ):
        runs = [v for v in report["results"].values() if v["grouping"] == grouping]
        intervals = []
        for key in CONTRAST_NAMES[-3:]:
            entries = [v["windows"]["10_10000"]["contrasts"][key] for v in runs]
            low = min(v["sim_low"] for v in entries)
            high = max(v["sim_high"] for v in entries)
            intervals.append(rf"$[{low:.3f},\,{high:.3f}]$")
        rows.append(label + " & " + " & ".join(intervals))
    table(
        out,
        "sensitivity",
        "lccc",
        r"Resampling groups & $D_{\rm B}$ & $D_{\rm E}$ & $D_{\rm E}-D_{\rm B}$",
        rows,
    )
    macros = {
        "N": str(report["contract"]["included_flights"]),
        "ExcludedN": str(report["contract"]["excluded_flights"]),
        "AddPct": f"{100 * base['r2_add']['point']:.1f}",
        "AcPct": f"{100 * base['variation']['altitude_circuit']['share']['point']:.1f}",
        "AltPct": f"{100 * base['variation']['altitude']['share']['point']:.1f}",
        "ResidualRms": f"{base['residual_rms']['point']:.3f}",
        "DB": interval(base["contrasts"]["attenuation_beginners"]),
        "DE": interval(base["contrasts"]["attenuation_experts"]),
        "Triple": interval(base["contrasts"]["attenuation_experts_minus_beginners"]),
    }
    (out / f"{PREFIX}_values.tex").write_text(
        "% Experimental factorial analysis; generated.\n"
        + "\n".join(rf"\newcommand{{\Factorial{k}}}{{{v}}}" for k, v in macros.items())
        + "\n"
    )
    cell_rows, contrast_rows, component_rows = [], [], []
    for config, run in report["results"].items():
        for window, w in run["windows"].items():
            for j, support in enumerate(run["support"]):
                row = {"configuration": config, "window_s": window, **support}
                for family in ("cells", "residual"):
                    for field in ("point", "low", "high", "se", "sim_low", "sim_high"):
                        row[f"{family}_{field}"] = np.asarray(w[family][field]).ravel()[
                            j
                        ]
                row["fit_rms_dex"] = np.asarray(w["fit_rms_dex"]).ravel()[j]
                cell_rows.append(row)
                for component in COMPONENTS:
                    component_rows.append(
                        {
                            "configuration": config,
                            "window_s": window,
                            "cell": support["cell"],
                            "component": component,
                            **{
                                field: np.asarray(
                                    w["components"][component][field]
                                ).ravel()[j]
                                for field in ("point", "low", "high", "se")
                            },
                        }
                    )
            for key, values in w["contrasts"].items():
                contrast_rows.append(
                    {
                        "configuration": config,
                        "window_s": window,
                        "contrast": key,
                        **values,
                    }
                )
    for suffix, rows in (
        ("cells", cell_rows),
        ("contrasts", contrast_rows),
        ("components", component_rows),
    ):
        pd.DataFrame(rows).to_csv(out / f"{PREFIX}_{suffix}.csv", index=False)
    (out / f"{PREFIX}.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )


def main():
    """Measure into a fresh revision directory, or redraw without source SSD access."""
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
            raise ValueError("Use a fresh measurement directory or --redraw")
        if args.data is None:
            parser.error("--data is required for measurement")
        report = measure(args.data, args.out)
        path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    render(report, args.out)
    if args.publish:
        args.publish.mkdir(parents=True, exist_ok=True)
        for source in args.out.glob(f"{PREFIX}*"):
            shutil.copy2(source, args.publish / source.name)
    print(f"Completed experimental factorial analysis: {path}", flush=True)


if __name__ == "__main__":
    main()
