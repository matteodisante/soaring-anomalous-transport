"""Bootstrap validation for cell x launch-altitude class x month-of-year groups.

All years are pooled. The requested baseline is an unshifted 50 km UTM grid;
smaller cells, boundary shifts, adjacent months and pooled terrain are diagnostic
alternatives. Original site-day results remain an explicitly labelled reference.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from check_bootstrap_reliability import NAMES, ROOT, load_inputs, signature

from soaring.analysis.observables.bootstrap_reliability import (
    STATISTICS,
    diagnostic_statistics,
    uncertainty_summary,
)
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means, cluster_draws
from soaring.analysis.observables.fixed_transport import LAGS
from soaring.analysis.observables.grid_bootstrap import (
    cell_membership,
    grid_season_labels,
    group_composition,
    project_launches,
)

PREFIX = "ch3_transport_grid_bootstrap"


def configurations():
    """Define the baseline first, then fixed spatial and seasonal sensitivity checks."""
    result = []
    for side in (50, 25, 10):
        for x, y in ((0, 0), (side / 2, 0), (0, side / 2), (side / 2, side / 2)):
            result.append(
                {
                    "side_km": side,
                    "shift_x_km": x,
                    "shift_y_km": y,
                    "months": 1,
                    "month_offset": 0,
                    "pool_terrain": False,
                }
            )
    for width in (2, 3):
        for offset in range(width):
            result.append(
                {
                    "side_km": 50,
                    "shift_x_km": 0,
                    "shift_y_km": 0,
                    "months": width,
                    "month_offset": offset,
                    "pool_terrain": False,
                }
            )
    result.append(
        {
            "side_km": 50,
            "shift_x_km": 0,
            "shift_y_km": 0,
            "months": 1,
            "month_offset": 0,
            "pool_terrain": True,
        }
    )
    return result


def measure(data, out, seeds):
    """Validate caches and recompute paired MSD/H uncertainty for each grouping."""
    source = json.loads((data / "report.json").read_text())
    if source.get("status") != "complete":
        raise ValueError("The source run must be complete")
    report = {
        "status": "complete",
        "source_report": signature(data / "report.json"),
        "scope": "Fixed-cohort MSD/H bootstrap validation; other bands not recomputed",
        "baseline": (
            "50 km cell x initial-altitude class x month of year; all years pooled"
        ),
        "position": "archived initial position lat0/lon0, one cell per flight",
        "terrain": "initial altitude: <300, [300,800), [800,1500), >=1500 metres",
        "grid": {
            "projection": "WGS84 UTM; regular six-degree longitude zones",
            "origin_m": [0, 0],
            "side_m": 50000,
            "boundaries": "half-open squares, clipped to zone and hemisphere",
            "size_convention": "projected metres, small UTM ground-scale distortion",
            "coverage": "UTM domain [-80,84] latitude; all archive origins included",
        },
        "sampling_frame": (
            "occupied archive groups, then fixed cohort; equal-flight mean"
        ),
        "seeds": seeds,
        "configurations": configurations(),
        "results": {},
    }
    cell_tables = []
    for slug in NAMES:
        frame, cohort, values, reference, provenance = load_inputs(data, slug, source)
        projected = project_launches(frame)
        result = {
            "provenance": provenance,
            "resamples": len(reference) - 1,
            "reference": {
                "support": group_composition(frame, frame.cluster.to_numpy(), cohort),
                "statistics": uncertainty_summary(
                    diagnostic_statistics(LAGS, reference)
                ),
            },
            "configurations": [],
        }
        saved = {"lags": LAGS, "site_day_reference": reference}
        for i, config in enumerate(configurations()):
            cells = cell_membership(
                projected,
                config["side_km"],
                (config["shift_x_km"], config["shift_y_km"]),
            )
            labels, missing = grid_season_labels(
                frame,
                cells,
                config["months"],
                config["month_offset"],
                config["pool_terrain"],
            )
            if missing[cohort].any():
                raise ValueError(
                    "Missing date or altitude in cohort; no silent exclusion"
                )
            support = group_composition(frame, labels, cohort)
            support["archive_groups"] = int(labels.max() + 1)
            support["unknown_archive_flights"] = int(missing.sum())
            for seed in seeds:
                actual = int(np.random.SeedSequence([seed, i]).generate_state(1)[0])
                draws = cluster_draws(labels, len(reference) - 1, actual)
                curves = bootstrap_means(values, labels[cohort], draws)
                np.testing.assert_allclose(curves[0], reference[0], rtol=1e-10)
                stats = uncertainty_summary(diagnostic_statistics(LAGS, curves))
                for name, stat in stats.items():
                    stat["se_ratio_site_day"] = (
                        stat["se"] / result["reference"]["statistics"][name]["se"]
                    )
                key = f"config_{i}_seed_{seed}"
                saved[key] = curves
                result["configurations"].append(
                    {
                        **config,
                        "config_index": i,
                        "seed": seed,
                        "rng_seed": actual,
                        "support": support,
                        "statistics": stats,
                        "replicate_key": key,
                    }
                )
                if i == 0 and seed == seeds[0]:
                    np.save(out / f"{slug}-cluster-draws.npy", draws)
            if i == 0:
                membership = frame[
                    [
                        "flight_id",
                        "date",
                        "lat0",
                        "lon0",
                        "alt0",
                        "altitude_band",
                        "cohort_10000",
                    ]
                ].copy()
                membership = pd.concat(
                    [membership, projected, cells.drop(columns="epsg")], axis=1
                )
                membership["cluster"] = labels
                membership["month"] = pd.to_datetime(
                    frame.date, format="%Y-%m-%d", errors="coerce"
                ).dt.month
                membership.to_parquet(out / f"{slug}-membership.parquet", index=False)
                counts = membership.groupby("cluster").agg(
                    archive_flights=("flight_id", "size"),
                    cohort_flights=("cohort_10000", "sum"),
                    epsg=("epsg", "first"),
                    ix=("ix", "first"),
                    iy=("iy", "first"),
                    terrain=("altitude_band", "first"),
                    month=("month", "first"),
                )
                counts.to_csv(out / f"{slug}-groups.csv")
                cell_tables.append(cells.drop_duplicates())
            print(
                f"{slug}: config {i}, {support['groups']} groups, "
                f"median {support['flights_per_group_median']:g} flights",
                flush=True,
            )
        for name in STATISTICS:
            baseline_se = float(
                np.median(
                    [
                        c["statistics"][name]["se"]
                        for c in result["configurations"]
                        if c["config_index"] == 0
                    ]
                )
            )
            for c in result["configurations"]:
                c["statistics"][name]["se_ratio_grid"] = (
                    c["statistics"][name]["se"] / baseline_se
                )
        np.savez_compressed(out / f"{slug}-replicates.npz", **saved)
        report["results"][slug] = result
    catalogue = (
        pd.concat(cell_tables).drop_duplicates().sort_values(["epsg", "ix", "iy"])
    )
    catalogue.to_csv(out / "grid-cells.csv", index=False)
    (out / "grid-definition.json").write_text(
        json.dumps(report["grid"], indent=2) + "\n"
    )
    report["occupied_archive_cells"] = len(catalogue)
    report["cells"] = catalogue.to_dict(orient="records")
    return report


def render(report, out):
    """Render sensitivity curves, a support table and values for hand-written prose."""
    if report.get("status") != "complete":
        raise ValueError("Refusing to render an incomplete grid-bootstrap report")
    pd.DataFrame(report["cells"]).to_csv(out / f"{PREFIX}_cells.csv", index=False)
    (out / f"{PREFIX}_grid.json").write_text(
        json.dumps(report["grid"], indent=2) + "\n"
    )
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "pdf.fonttype": 42})
    fig, axs = plt.subplots(
        2, 2, figsize=(7.1, 4.8), layout="constrained", sharey="row"
    )
    colors = ("#0072B2", "#009E73", "#D55E00", "#6F4C9B")
    names = ("MSD 100 s", "MSD 1000 s", "MSD 10000 s", "$H$")
    rows, macros, table = [], {}, []
    for row, slug in enumerate(NAMES):
        result = report["results"][slug]
        configs = result["configurations"]
        baseline = [c for c in configs if c["config_index"] == 0]
        support = baseline[0]["support"]
        original = result["reference"]["support"]
        stem = f"ChThree{slug.capitalize()}Grid"
        for label, value in {
            "Groups": str(support["groups"]),
            "Median": f"{support['flights_per_group_median']:g}",
            "SingletonPct": f"{100 * support['singleton_group_fraction']:.1f}",
            "OldSingletonPct": f"{100 * original['singleton_group_fraction']:.1f}",
            "SingletonFlightPct": (
                f"{100 * support['flights_in_singletons_fraction']:.1f}"
            ),
            "MaxPct": f"{100 * support['largest_group_fraction']:.1f}",
        }.items():
            macros[stem + label] = value
        hratios = [c["statistics"]["hurst"]["se_ratio_site_day"] for c in baseline]
        macros[stem + "HFactor"] = f"{min(hratios):.2f}--{max(hratios):.2f}"
        three = [
            c["statistics"]["hurst"]["se_ratio_grid"]
            for c in configs
            if c["months"] == 3
        ]
        macros[stem + "HThreeMonths"] = f"{np.median(three):.2f}"
        shifted = [
            c["statistics"]["msd_1000"]["se_ratio_grid"]
            for c in configs
            if c["config_index"] < 4
        ]
        macros[stem + "MsdShiftRange"] = f"{min(shifted):.2f}--{max(shifted):.2f}"
        table.append(
            f"{NAMES[slug]} & {original['groups']} & {support['groups']} & "
            f"{support['flights_per_group_median']:g} & "
            f"{100 * support['singleton_group_fraction']:.1f} & "
            f"{100 * support['largest_group_fraction']:.1f} \\\\"
        )
        for c in configs:
            for stat in STATISTICS:
                rows.append(
                    {
                        "discipline": slug,
                        "statistic": stat,
                        **{
                            k: v
                            for k, v in c.items()
                            if k not in ("support", "statistics")
                        },
                        **c["support"],
                        **c["statistics"][stat],
                    }
                )
        for col, levels in enumerate(((10, 25, 50), (1, 2, 3))):
            ax = axs[row, col]
            for name, color, label in zip(STATISTICS, colors, names, strict=True):
                grouped = []
                for level in levels:
                    selected = [
                        c
                        for c in configs
                        if not c["pool_terrain"]
                        and (
                            (col == 0 and c["side_km"] == level and c["months"] == 1)
                            or (
                                col == 1
                                and c["side_km"] == 50
                                and c["months"] == level
                                and c["shift_x_km"] == c["shift_y_km"] == 0
                            )
                        )
                    ]
                    grouped.append(
                        [c["statistics"][name]["se_ratio_grid"] for c in selected]
                    )
                middle = np.array([np.median(g) for g in grouped])
                lower = middle - np.array([min(g) for g in grouped])
                upper = np.array([max(g) for g in grouped]) - middle
                ax.errorbar(
                    levels,
                    middle,
                    yerr=[lower, upper],
                    color=color,
                    label=label,
                    marker="o",
                    markersize=3,
                    linewidth=1,
                    capsize=2,
                )
            ax.axhline(1, color="0.5", linestyle="--", linewidth=0.7)
            ax.set_xticks(levels)
            ax.set_title(NAMES[slug])
            ax.set_xlabel(
                "Cell side (km); one month"
                if col == 0
                else "Adjacent months; 50 km cells"
            )
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", color="0.9", linewidth=0.5)
        axs[row, 0].set_ylabel("SE / baseline grid SE")
    handles, labels = axs[0, 0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="outside lower center", ncol=4, frameon=False, fontsize=8
    )
    fig.savefig(
        out / f"{PREFIX}.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)
    pd.DataFrame(rows).to_csv(out / f"{PREFIX}.csv", index=False)
    (out / f"{PREFIX}_values.tex").write_text(
        "% Generated values only; prose is maintained in the chapter.\n"
        + "\n".join(
            f"\\newcommand{{\\{name}}}{{{value}}}"
            for name, value in sorted(macros.items())
        )
        + "\n"
    )
    (out / f"{PREFIX}_support.tex").write_text(
        "\\begin{tabular}{lrrrrr}\n\\toprule\n"
        " & Site--day & Grid & Median size"
        " & Singletons (\\%) & Max. share (\\%) \\\\\n"
        "\\midrule\n" + "\n".join(table) + "\n\\bottomrule\n\\end{tabular}\n"
    )


def main():
    """Measure from immutable caches or redraw the standalone report offline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--publish", type=Path)
    parser.add_argument("--redraw", action="store_true")
    parser.add_argument("--seeds", type=int, nargs="+", default=[20260918, 20260919])
    args = parser.parse_args()
    if not args.seeds or min(args.seeds) < 0 or len(set(args.seeds)) != len(args.seeds):
        parser.error("Seeds must be distinct nonnegative integers")
    if args.redraw:
        report = json.loads((args.out / "report.json").read_text())
    else:
        if args.data is None:
            parser.error("--data is required")
        if (
            args.out.resolve() == args.data.resolve()
            or args.data.resolve() in args.out.resolve().parents
        ):
            parser.error("Use an output directory outside the source run")
        if (args.out / "report.json").exists():
            parser.error("Report exists; use --redraw or a fresh output directory")
        args.out.mkdir(parents=True, exist_ok=True)
        report = measure(args.data, args.out, args.seeds)
        report["code"] = signature(Path(__file__))
        report["analysis_code"] = signature(
            ROOT / "src/soaring/analysis/observables/grid_bootstrap.py"
        )
        (args.out / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
    render(report, args.out)
    if args.publish:
        args.publish.mkdir(parents=True, exist_ok=True)
        for suffix in (
            ".pdf",
            ".csv",
            "_values.tex",
            "_support.tex",
            "_cells.csv",
            "_grid.json",
        ):
            shutil.copy2(args.out / f"{PREFIX}{suffix}", args.publish)
        shutil.copy2(args.out / "report.json", args.publish / f"{PREFIX}.json")


if __name__ == "__main__":
    main()
