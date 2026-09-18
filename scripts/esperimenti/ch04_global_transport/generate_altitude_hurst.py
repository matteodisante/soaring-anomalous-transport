"""Fit paraglider altitude-band exponents by declared open and closed circuit.

Reuse identified segment TA-MSDs and the completed grouped report's flight
membership, joined to the verified paraglider catalogue's declared task labels.
No raw trajectory pass or historical report edit is needed. These are
range-dependent second-moment exponents, not an identification
of a self-similar stochastic process or an intrinsic Hurst parameter.
"""

from __future__ import annotations

# ruff: noqa: E402 -- allow direct execution from the checkout
import argparse
import gzip
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from generate_duration_equipment import flight_curves, portable
from generate_grouped_tamsd import COLORS, digest, write

from soaring.analysis.observables.global_diagnostics import declared_task_class
from soaring.analysis.observables.grouped_tamsd import mean_and_support
from soaring.analysis.observables.tamsd_scaling import clustered_scaling_summary
from soaring.reporting import DISCIPLINES, PARAGLIDERS
from soaring.reporting.style import PDF_METADATA, paper_style

CONTROL_NAMES = ("available segments", "fixed long segments")
# Only the fixed cohort is reported: the thesis compares exponents across lags,
# which requires flight membership and weights that do not change with lag.
FIXED = 1
GENERATED_OUTPUTS = (
    "ch3_altitude_hurst.pdf",
    "ch3_altitude_hurst_table.tex",
    "ch3_altitude_hurst_values.tex",
    "ch3_altitude_hurst.json",
)
DECADE_RANGES = ((10, 100), (100, 1000), (1000, 10000))
TASK_LABELS = {"open": "Open circuits", "closed": "Closed circuits"}
DEFAULT_PARENT = ROOT / "revisions/grouped-tamsd-2026-09-12/report.json.gz"
DEFAULT_ARRAYS = ROOT / (
    "revisions/vertical-gap-split-2026-09-11/recovery-runs/"
    "20260912T104500Z-5cfc4e8c/arrays"
)


def read_report(path):
    """Read the immutable parent or a finite portable result report."""
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt") as stream:
        report = json.load(stream)
    if report["status"] != "complete":
        raise ValueError("A complete parent report is required")
    return report


def reconstruct(parent, discipline, audit_dir, inputs):
    """Rebuild both flight controls, checking identities and every stored mean."""
    entry = parent["results"][discipline]
    slug = DISCIPLINES[discipline].slug
    paths = [audit_dir / f"msd_{slug}.npz", audit_dir / f"msd_segments_{slug}.parquet"]
    for path in paths:
        expected = [
            value["sha256"]
            for key, value in parent["inputs"].items()
            if Path(key).name == path.name
        ]
        actual = digest(path)
        if expected != [actual]:
            raise ValueError(f"Input differs from the completed grouped run: {path}")
        inputs[str(path.resolve())] = {"sha256": actual, "bytes": path.stat().st_size}
    with np.load(paths[0]) as archive:
        full_lags = archive["lags"]
        keep = (full_lags >= 10) & (full_lags <= 10000)
        lags = full_lags[keep]
        samples = archive["time_averaged_samples"][:, keep]
    np.testing.assert_array_equal(lags, entry["lags_s"])
    segments = pd.read_parquet(paths[1])
    if len(segments) != len(samples):
        raise ValueError("Segment rows and TA-MSD rows differ")
    dt = segments.dt_s.to_numpy()
    k = np.rint(lags[None, :] / dt[:, None])
    expected_support = (
        (lags[None, :] >= dt[:, None])
        & (k >= 1)
        & (k <= segments.n_fixes.to_numpy()[:, None] // 2)
    )
    np.testing.assert_array_equal(np.isfinite(samples), expected_support)
    frame, available = flight_curves(samples, segments, lags)
    long_segment = np.isfinite(samples[:, -1]) & (dt <= 10) & (dt > 0)
    fixed_frame, fixed_values = flight_curves(
        samples[long_segment], segments.loc[long_segment], lags
    )
    fixed = np.full_like(available, np.nan)
    indices = pd.Index(frame.flight_id).get_indexer(fixed_frame.flight_id)
    if np.any(indices < 0) or not np.isfinite(fixed_values).all():
        raise ValueError("Fixed control is not an aligned complete subset")
    fixed[indices] = fixed_values
    members = pd.DataFrame(entry["flights"])
    members["flight_id"] = members.flight_id.astype(str)
    if members.flight_id.duplicated().any():
        raise ValueError("Parent report has duplicate flight membership")
    if set(frame.flight_id) != set(members.flight_id):
        raise ValueError("Reconstructed flight identities differ from parent")
    members = members.set_index("flight_id").loc[frame.flight_id].reset_index()
    np.testing.assert_allclose(
        frame.total_retained_duration_s,
        members.total_retained_duration_s,
        rtol=0,
        atol=0,
    )
    values = np.stack([available, fixed], axis=1)
    for name, row in entry["altitude_band"].items():
        mask = members.altitude_band.eq(name).to_numpy()
        mean, support = mean_and_support(values[mask])
        np.testing.assert_array_equal(support, row["n_flights"])
        np.testing.assert_allclose(mean, row["mean_m2"], rtol=1e-12, equal_nan=True)
        observed_fixed = set(members.loc[mask & np.isfinite(fixed[:, -1]), "flight_id"])
        if observed_fixed != set(row["fixed_flight_ids"]):
            raise ValueError(f"Fixed flight identities differ for {name}")
    return lags, members, values


def attach_declared_tasks(members, catalog):
    """Align explicit FFVL task classes by flight identity, preserving row order."""
    catalog = catalog[["flight_id", "flight_type"]].copy()
    catalog["flight_id"] = catalog.flight_id.astype(str)
    if catalog.flight_id.duplicated().any() or members.flight_id.duplicated().any():
        raise ValueError("Task join requires unique flight identifiers")
    result = members.copy()
    aligned = catalog.set_index("flight_id").reindex(members.flight_id.astype(str))
    result["flight_type"] = aligned.flight_type.to_numpy()
    result["task"] = result.flight_type.map(declared_task_class)
    result["missing_catalog_task"] = result.flight_type.isna()
    return result


def membership_digest(flight_ids):
    """Identify ordered group membership without repeating the full flight table."""
    return hashlib.sha256("\n".join(map(str, flight_ids)).encode()).hexdigest()


def measure(args):
    """Fit only paragliders, crossing declared circuit type with altitude band."""
    parent = read_report(args.parent)
    main_range = tuple(args.fit_range)
    intervals = tuple(dict.fromkeys((*DECADE_RANGES, main_range)))
    inputs = {str(args.parent.resolve()): {"sha256": digest(args.parent)}}
    lags, members, values = reconstruct(parent, "paragliders", args.audit_dir, inputs)
    catalog_path = args.catalog or PARAGLIDERS.catalog_path()
    catalog_digest = digest(catalog_path)
    expected = parent["inputs"][str(PARAGLIDERS.catalog_path().resolve())]["sha256"]
    if catalog_digest != expected:
        raise ValueError("Paraglider catalogue differs from the grouped measurement")
    inputs[str(catalog_path.resolve())] = {
        "sha256": catalog_digest,
        "bytes": catalog_path.stat().st_size,
    }
    catalog = pd.read_csv(
        catalog_path, usecols=["flight_id", "flight_type"], dtype={"flight_id": str}
    )
    members = attach_declared_tasks(members, catalog)
    results = {}
    for task_index, (task, label) in enumerate(TASK_LABELS.items()):
        groups = {}
        for number, name in enumerate(
            parent["results"]["paragliders"]["altitude_band"]
        ):
            mask = (members.altitude_band.eq(name) & members.task.eq(task)).to_numpy()
            summary = clustered_scaling_summary(
                values[mask],
                members.cluster.to_numpy()[mask],
                lags,
                intervals=intervals,
                control_names=CONTROL_NAMES,
                resamples=args.resamples,
                seed=args.seed + 100 * task_index + number,
            )
            # Reconstruct the stratum mean directly before checking each log-log fit.
            direct_mean, direct_support = mean_and_support(values[mask])
            np.testing.assert_allclose(summary["mean_m2"], direct_mean, rtol=1e-13)
            np.testing.assert_array_equal(summary["n_flights"], direct_support)
            for fit in summary["fits"]:
                if fit["n_lags"] >= 3:
                    curve = direct_mean[fit["control_index"]]
                    selected = np.isin(lags, fit["actual_lags_s"])
                    expected_slope = np.polyfit(
                        np.log(lags[selected]), np.log(curve[selected]), 1
                    )[0]
                    np.testing.assert_allclose(fit["slope"], expected_slope, atol=1e-12)
            summary["n_flights_total"] = int(mask.sum())
            summary["flight_ids_sha256"] = membership_digest(
                members.loc[mask, "flight_id"]
            )
            summary["fixed_flight_ids_sha256"] = membership_digest(
                members.loc[mask & np.isfinite(values[:, 1, -1]), "flight_id"]
            )
            groups[name] = summary
            print(
                f"Paragliders, {label}: {name}: {mask.sum():,} flights; fits complete",
                flush=True,
            )
        results[task] = {
            "discipline": "paragliders",
            "task": task,
            "label": label,
            "lags_s": lags,
            "altitude_band": groups,
            "n_flights_total": int(members.task.eq(task).sum()),
        }
    sources = [
        Path(__file__),
        ROOT / "src/soaring/analysis/observables/tamsd_scaling.py",
        ROOT / "src/soaring/analysis/observables/grouped_tamsd.py",
        ROOT / "src/soaring/analysis/observables/global_diagnostics.py",
        Path(__file__).with_name("generate_duration_equipment.py"),
        Path(__file__).with_name("generate_grouped_tamsd.py"),
        ROOT / "src/soaring/reporting/style.py",
    ]
    return portable(
        {
            "status": "complete",
            "measured_utc": datetime.now(UTC).isoformat(),
            "inputs": inputs,
            "sources": {str(path.relative_to(ROOT)): digest(path) for path in sources},
            "validation": (
                "Unstratified paraglider altitude means and support match parent; "
                "task joins preserve row identity; split fits match direct means"
            ),
            "population": {
                "eligible_paragliders": len(members),
                "task_counts": members.task.value_counts().to_dict(),
                "missing_catalog_task": int(members.missing_catalog_task.sum()),
                "excluded_unknown_by_band": members.loc[
                    members.task.eq("unknown"), "altitude_band"
                ]
                .value_counts()
                .to_dict(),
                "raw_task_counts": members.groupby(
                    ["task", "flight_type"], dropna=False
                )
                .size()
                .reset_index(name="n_flights")
                .to_dict("records"),
            },
            "contract": {
                "discipline": "paragliders",
                "comparison": "declared open and closed circuits within altitude bands",
                "task_source": "FFVL catalogue flight_type; declared_task_class",
                "task_classes": {
                    "open": ["Dist libre", "Dist 1 pt", "Dist 2 pts", "Dist 3 pts"],
                    "closed": ["triangle*", "Quadrilatère", "Aller-Retour"],
                    "unknown": "Other or missing declarations excluded from the split",
                },
                "observable": parent["contract"]["observable"],
                "altitude_bands": parent["contract"]["altitude_bands"],
                "altitude_source": parent["contract"]["altitude_source"],
                "controls": CONTROL_NAMES,
                "fit": (
                    "Unweighted OLS of log(mean TA-MSD) against log(requested lag); "
                    "H_eff=slope/2"
                ),
                "main_requested_range_s": main_range,
                "requested_fit_ranges_s": intervals,
                "fit_windows": (
                    "Three pre-existing decades and the chosen main range; "
                    "fixed observed lag mask in every draw"
                ),
                "uncertainty": (
                    "Marginal 95% percentile intervals, complete site-day bootstrap"
                ),
                "resamples": args.resamples,
                "base_seed": args.seed,
                "pairing": (
                    "Same draws across lags and controls within each task-band stratum"
                ),
                "interval_support": (
                    "20 clusters at every fitted lag; 90% complete finite draws"
                ),
                "limitations": [
                    "Effective moment scaling does not establish self-similarity "
                    "or intrinsic Hurst H",
                    "Curves bend; the result depends on the stated fit window",
                    "Available flight membership changes with lag",
                    "Fixed segments condition on long continuous recordings",
                    "Site-day resampling assumes independent clusters; "
                    "repeat pilots and weather may span clusters",
                    "Intervals do not include fit-window, cleaning, "
                    "altitude-label or model uncertainty",
                    "Altitude groups mix regions; "
                    "no causal altitude effect is identified",
                    "Per-band marginal intervals do not test between-band differences",
                    "Declared task geometry does not prove a retained segment closes",
                    "Task strata are resampled separately; "
                    "intervals do not test task contrasts",
                ],
            },
            "results": results,
        }
    )


def render(report, out):
    """Show four curves and fitted exponents, plus lag and population sensitivity."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paper_style()
    out.mkdir(parents=True, exist_ok=True)
    main_range = report["contract"]["main_requested_range_s"]
    low, high = main_range
    main_fits = [
        fit
        for entry in report["results"].values()
        for row in entry["altitude_band"].values()
        for fit in row["fits"]
        if fit["requested_range_s"] == main_range
    ]
    actual_ranges = {
        (fit["actual_lags_s"][0], fit["actual_lags_s"][-1]) for fit in main_fits
    }
    actual_note = ", ".join(f"{a:g}-{b:g} s" for a, b in sorted(actual_ranges))
    fig, axes = plt.subplots(1, 2, figsize=(6.1, 4.4))
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.27, top=0.82, wspace=0.30)
    title = (
        "Paragliders: TA-MSD by initial GNSS altitude"
        if report["contract"].get("discipline") == "paragliders"
        else "Horizontal TA-MSD by initial GNSS altitude"
    )
    fig.suptitle(title, fontsize=11, y=0.985)
    fig.text(
        0.5,
        0.915,
        r"$M(\tau)\propto\tau^{2H_{\rm eff}}$: " f"fit over {low:g}-{high:g} s",
        ha="center",
        fontsize=9,
    )
    for column, (discipline, entry) in enumerate(report["results"].items()):
        heading = entry.get("label", discipline.capitalize())
        lags = np.asarray(entry["lags_s"])
        for control in (FIXED,):
            ax = axes[column]
            if main_range != [10, 10000]:
                ax.axvspan(low, high, color="0.94", zorder=0)
            for name, row in entry["altitude_band"].items():
                curve = np.asarray(row["mean_m2"], dtype=float)[control]
                counts = np.asarray(row["n_flights"])[control]
                curve = np.where(counts >= 8, curve, np.nan)
                bounds = np.asarray(row["pointwise_95_m2"], dtype=float)[:, control]
                fit = next(
                    f
                    for f in row["fits"]
                    if f["control_index"] == control
                    and f["requested_range_s"] == main_range
                )
                lo, hi = fit["h_eff_percentile_95"]
                label = f"{name}: {fit['h_eff']:.3f} [{lo:.3f}, {hi:.3f}]"
                ax.loglog(lags, curve, color=COLORS[name], label=label)
                ax.fill_between(lags, *bounds, color=COLORS[name], alpha=0.13)
                fit_lags = np.asarray(fit["actual_lags_s"])
                ax.plot(
                    fit_lags,
                    np.exp(fit["intercept_log_m2"]) * fit_lags ** fit["slope"],
                    linestyle="--",
                    linewidth=1.5,
                    color=COLORS[name],
                )
            population = CONTROL_NAMES[control]
            ax.set(
                title=f"{heading}: {population}",
                xlim=(10, 10000),
                ylim=(2e3, 4e10),
                xlabel=r"Requested lag $\tau$ [s]",
                ylabel=r"Flight TA-MSD [m$^2$]",
            )
            ax.set_title(ax.get_title(loc="left"), fontsize=8, loc="left")
            ax.legend(
                loc="upper left",
                fontsize=6.5,
                title=r"$H_{\rm eff}$ [95% CI]",
                title_fontsize=7,
                labelspacing=0.30,
                handlelength=1.8,
            )
            ax.grid(True, which="major")
    fig.text(
        0.10,
        0.045,
        f"Solid: measured TA-MSD. Dashed: fit at the available lags, {actual_note}.\n"
        "Ribbons: pointwise 95% intervals. Exponent CIs: "
        f"{report['contract']['resamples']:,} site-day draws.\n"
        "Fixed: same segments supporting lag 10000 s throughout.\n"
        "Initial GNSS altitude groups pool all regions; they are not terrain classes.",
        fontsize=7,
        va="center",
    )
    fig.savefig(out / "altitude_msd_hurst.pdf", metadata=PDF_METADATA)
    plt.close(fig)

    fig, axes = plt.subplots(3, 2, figsize=(6.1, 8.0))
    fig.subplots_adjust(
        left=0.10, right=0.98, bottom=0.15, top=0.90, wspace=0.30, hspace=0.43
    )
    fig.suptitle(
        "Effective scaling: lag range and flight selection", fontsize=11, y=0.98
    )
    fig.text(
        0.5,
        0.949,
        r"$H_{\rm eff}=\alpha/2$ with marginal 95% site-day intervals",
        ha="center",
        fontsize=9,
    )
    all_bounds = np.array(
        [
            fit["h_eff_percentile_95"]
            for entry in report["results"].values()
            for row in entry["altitude_band"].values()
            for fit in row["fits"]
            if tuple(fit["requested_range_s"]) in DECADE_RANGES
        ],
        dtype=float,
    )
    exponent_limits = (
        min(0.67, float(np.nanmin(all_bounds)) - 0.05),
        max(1.20, float(np.nanmax(all_bounds)) + 0.05),
    )
    for column, (discipline, entry) in enumerate(report["results"].items()):
        heading = entry.get("label", discipline.capitalize())
        lags = np.asarray(entry["lags_s"])
        for number, (name, row) in enumerate(entry["altitude_band"].items()):
            for control in range(2):
                fits = [
                    f
                    for f in row["fits"]
                    if f["control_index"] == control
                    and tuple(f["requested_range_s"]) in DECADE_RANGES
                ]
                point = np.array([f["h_eff"] for f in fits])
                bounds = np.array([f["h_eff_percentile_95"] for f in fits], dtype=float)
                x = np.arange(3) + (number - 1.5) * 0.08
                axes[control, column].plot(
                    x,
                    point,
                    color=COLORS[name],
                    marker="o",
                    linestyle="none",
                    label=name,
                )
                axes[control, column].vlines(
                    x, bounds[:, 0], bounds[:, 1], color=COLORS[name], linewidth=1
                )
                for end in bounds.T:
                    axes[control, column].plot(
                        x, end, marker="_", linestyle="none", color=COLORS[name]
                    )
                axes[2, column].loglog(
                    lags,
                    row["n_flights"][control],
                    "-" if control == 0 else "--",
                    color=COLORS[name],
                )
        for control in range(2):
            ax = axes[control, column]
            ax.axhline(1, color="0.5", linewidth=0.6, linestyle=":")
            population = "available" if control == 0 else "fixed long segments"
            ax.set(
                title=f"{heading}: {population}",
                ylabel=r"$H_{\rm eff}$",
                xlim=(-0.4, 2.4),
                ylim=exponent_limits,
                xticks=np.arange(3),
                xticklabels=["10-100", "100-1000", "1000-10000"],
                xlabel="Requested fit range [s]",
            )
            ax.set_title(ax.get_title(loc="left"), fontsize=8, loc="left")
            ax.tick_params(axis="x", labelsize=6.8)
            ax.grid(True, axis="y")
            if control == 0:
                ax.legend(
                    loc="upper left",
                    fontsize=6.3,
                    ncols=2,
                    columnspacing=0.6,
                    handletextpad=0.3,
                )
        axes[2, column].set(
            title="Flight support: solid available, dashed fixed",
            ylabel="Contributing flights",
            xlabel=r"Requested lag $\tau$ [s]",
            xlim=(10, 10000),
        )
        axes[2, column].set_title(
            axes[2, column].get_title(loc="left"), fontsize=7.3, loc="left"
        )
        axes[2, column].grid(True, which="major")
    fig.text(
        0.10,
        0.039,
        "Actual fitted lags: 10-95 s, 107-931 s, and 1049-10000 s "
        "(native requested grid).\n"
        "Dotted line: quadratic growth of the moment. "
        "These are range-dependent exponents;\n"
        "the intervals describe sampling uncertainty "
        "conditional on the estimator and fit range.",
        fontsize=7,
        va="center",
    )
    fig.savefig(out / "altitude_hurst_sensitivity.pdf", metadata=PDF_METADATA)
    plt.close(fig)


def save_tables(report, out):
    """Export all effective exponents and the full curve support for reuse."""
    fits, curves = [], []
    for discipline, entry in report["results"].items():
        for name, row in entry["altitude_band"].items():
            for fit in row["fits"]:
                lo, hi = fit["h_eff_percentile_95"]
                fits.append(
                    {
                        "discipline": entry.get("discipline", discipline),
                        "circuit_type": entry.get("task"),
                        "altitude_band": name,
                        **{k: v for k, v in fit.items() if np.isscalar(v)},
                        "requested_low_s": fit["requested_range_s"][0],
                        "requested_high_s": fit["requested_range_s"][1],
                        "actual_low_s": fit["actual_lags_s"][0],
                        "actual_high_s": fit["actual_lags_s"][-1],
                        "ci95_low": lo,
                        "ci95_high": hi,
                    }
                )
            for control, control_name in enumerate(CONTROL_NAMES):
                for j, lag in enumerate(entry["lags_s"]):
                    curves.append(
                        {
                            "discipline": entry.get("discipline", discipline),
                            "circuit_type": entry.get("task"),
                            "altitude_band": name,
                            "control": control_name,
                            "lag_s": lag,
                            "mean_m2": row["mean_m2"][control][j],
                            "n_flights": row["n_flights"][control][j],
                            "n_clusters": row["n_clusters"][control][j],
                            "pointwise_95_low_m2": row["pointwise_95_m2"][0][control][
                                j
                            ],
                            "pointwise_95_high_m2": row["pointwise_95_m2"][1][control][
                                j
                            ],
                        }
                    )
    pd.DataFrame(fits).to_csv(out / "altitude_hurst_estimates.csv", index=False)
    pd.DataFrame(curves).to_csv(out / "altitude_tamsd_curves.csv", index=False)


def save_thesis_assets(report, figures, out):
    """Export the plotted fit and its complete table to manuscript inputs."""
    out.mkdir(parents=True, exist_ok=True)
    main_range = report["contract"]["main_requested_range_s"]
    header = (
        "% Generated by scripts/esperimenti/ch04_global_transport/"
        "generate_altitude_hurst.py\n"
    )
    task_split = "population" in report
    n_columns = 3 if task_split else 2
    columns = "lcc" if task_split else "lc"
    titles = (
        (r"Altitude band & Fixed cohort & Flights \\")
        if task_split
        else (r"Initial-altitude band & Fixed cohort \\")
    )
    lines = [
        header.rstrip(),
        rf"\begin{{tabular}}{{@{{}}{columns}@{{}}}}",
        r"\toprule",
        titles,
        r"\midrule",
    ]
    lag_counts = set()
    for discipline, entry in report["results"].items():
        heading = entry.get("label", discipline.capitalize())
        lines.extend(
            [
                rf"\multicolumn{{{n_columns}}}{{@{{}}l}}{{\textit{{{heading}}}}} \\",
                r"\addlinespace[2pt]",
            ]
        )
        for name, row in entry["altitude_band"].items():
            cells = []
            fit = next(
                f
                for f in row["fits"]
                if f["control_index"] == FIXED
                and f["requested_range_s"] == main_range
            )
            if fit["status"] != "ok":
                raise ValueError("Thesis exponent table requires supported fits")
            lag_counts.add(fit["n_lags"])
            lo, hi = fit["h_eff_percentile_95"]
            cells.append(rf"${fit['h_eff']:.4f}\;[{lo:.4f},\,{hi:.4f}]$")
            if task_split:
                counts = set(fit["n_flights"])
                if len(counts) != 1:
                    raise ValueError("The fixed cohort must not change with lag")
                cells.append(rf"$\num{{{counts.pop()}}}$")
            lines.append(name + " & " + " & ".join(cells) + r" \\")
        lines.append(r"\addlinespace[3pt]")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    if len(lag_counts) != 1:
        raise ValueError("Thesis text requires a common fitted lag grid")
    values = {
        "StatAltitudeHurstFitLow": f"{main_range[0]:g}",
        "StatAltitudeHurstFitHigh": f"{main_range[1]:g}",
        "StatAltitudeHurstResamples": str(report["contract"]["resamples"]),
        "StatAltitudeHurstLags": str(lag_counts.pop()),
    }
    if "population" in report:
        counts = report["population"]["task_counts"]
        values.update(
            {
                "StatAltitudeHurstOpenFlights": str(counts.get("open", 0)),
                "StatAltitudeHurstClosedFlights": str(counts.get("closed", 0)),
                "StatAltitudeHurstUnknownFlights": str(counts.get("unknown", 0)),
            }
        )
        plains = report["results"]["closed"]["altitude_band"]["Plains"]
        fixed = next(
            f
            for f in plains["fits"]
            if f["control_index"] == 1 and f["requested_range_s"] == main_range
        )
        values["StatAltitudeHurstClosedPlainsFixedFlights"] = str(
            fixed["n_flights_min"]
        )
        values["StatAltitudeHurstClosedPlainsFixedClusters"] = str(
            fixed["n_clusters_min"]
        )
    (out / "ch3_altitude_hurst_values.tex").write_text(
        header
        + "".join(
            rf"\newcommand{{\{key}}}{{{value}}}" + "\n" for key, value in values.items()
        )
    )
    (out / "ch3_altitude_hurst_table.tex").write_text("\n".join(lines) + "\n")
    shutil.copy2(figures / "altitude_msd_hurst.pdf", out / "ch3_altitude_hurst.pdf")
    write(out / "ch3_altitude_hurst.json", report)


def main():
    """Measure into a fresh record, or redraw its existing numerical report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_ARRAYS)
    parser.add_argument(
        "--catalog",
        type=Path,
        help="Byte-identical copy of the parent paraglider catalogue",
    )
    parser.add_argument("--record-dir", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        help="Figure directory (default: a figures/ folder inside --record-dir)",
    )
    parser.add_argument(
        "--thesis-out",
        type=Path,
        help="Also export figure, table, macros and report here",
    )
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260915)
    parser.add_argument(
        "--fit-range",
        type=float,
        nargs=2,
        metavar=("LOW_S", "HIGH_S"),
        default=(10, 10000),
        help="Main requested fit range in seconds (default: 10 10000)",
    )
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    if args.out is None:
        args.out = args.record_dir / "figures"
    if not 10 <= args.fit_range[0] < args.fit_range[1] <= 10000:
        parser.error("--fit-range must satisfy 10 <= LOW_S < HIGH_S <= 10000")
    target = args.record_dir / "report.json"
    if args.render_only:
        report = read_report(target)
    else:
        if target.exists():
            raise ValueError(
                "Preserve the complete report; choose a new record directory"
            )
        report = measure(args)
        args.record_dir.mkdir(parents=True, exist_ok=True)
        write(target, report)
        (args.record_dir / "measurement-source.py.txt").write_bytes(
            Path(__file__).read_bytes()
        )
    render(report, args.out)
    save_tables(report, args.record_dir)
    if args.thesis_out:
        save_thesis_assets(report, args.out, args.thesis_out)
    write(
        args.record_dir / "figure-manifest.json",
        {
            "report_sha256": digest(target),
            "renderer_sha256": digest(Path(__file__)),
            "outputs": {
                str((args.out / name).resolve()): digest(args.out / name)
                for name in ("altitude_msd_hurst.pdf", "altitude_hurst_sensitivity.pdf")
            },
        },
    )
    print(f"Completed: {target}", flush=True)


if __name__ == "__main__":
    main()
