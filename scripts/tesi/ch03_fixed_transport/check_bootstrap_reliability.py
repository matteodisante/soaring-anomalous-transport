"""Check calendar-block uncertainty using saved flight MSDs, without trajectories.

Write a separate report and replicate curves; never overwrite the published
site-day bootstrap. --redraw needs only the new report.json, including offline.
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import hashlib
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
from soaring.analysis.observables.bootstrap_reliability import (
    CALENDAR_ANCHOR,
    STATISTICS,
    block_support,
    boundary_offsets,
    calendar_blocks,
    diagnostic_statistics,
    uncertainty_summary,
)
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means, cluster_draws
from soaring.analysis.observables.fixed_transport import LAGS

PREFIX = "ch3_transport_bootstrap_reliability"
NAMES = {"para": "Paragliders", "hang": "Hang gliders"}


def signature(path):
    """Fingerprint each source file without changing the saved run."""
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest}


def load_inputs(data, slug, reference):
    """Validate cohort identity, native cached lag grid and published baseline."""
    directory = data / slug
    frame = pd.read_parquet(directory / "flights.parquet")
    if frame.flight_id.duplicated().any():
        raise ValueError("Flight identities must be unique")
    manifest = json.loads((directory / "cohort-10000.json").read_text())
    digest = manifest.pop("sha256")
    if (
        hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        != digest
    ):
        raise ValueError("Invalid cohort manifest hash")
    cohort = frame.cohort_10000.to_numpy(dtype=bool)
    indices = np.array([m["frame_index"] for m in manifest["members"]], dtype=int)
    np.testing.assert_array_equal(np.flatnonzero(cohort), indices)
    np.testing.assert_array_equal(
        frame.flight_id.iloc[indices].astype(str),
        [m["flight_id"] for m in manifest["members"]],
    )
    with np.load(directory / "msd.npz") as cached:
        lags = cached["lags"]
        baseline = cached["curves"][:, 3]
        published = reference["results"][slug]
        np.testing.assert_array_equal(lags, published["msd_lags"])
        np.testing.assert_allclose(
            cached["curves"][0],
            np.asarray(published["msd"]["point"], dtype=float),
            equal_nan=True,
        )
    if len(baseline) - 1 != published["resamples"]:
        raise ValueError("Published bootstrap replicate count differs from cache")
    take = np.flatnonzero((lags >= 10) & (lags <= 10000))
    np.testing.assert_array_equal(lags[take], LAGS)
    values = np.load(directory / "flight-msd.npy", mmap_mode="r")
    if values.shape != (len(frame), 4, len(lags)):
        raise ValueError("Unexpected per-flight MSD dimensions")
    values = np.asarray(values[indices, 3][:, take])
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Fixed-cohort MSD needs finite, nonnegative full-lag support")
    baseline = baseline[:, take]
    np.testing.assert_allclose(values.mean(axis=0), baseline[0], rtol=1e-10)
    labels = frame.cluster.to_numpy(dtype=int)
    draws = np.load(directory / "cluster-draws.npy", mmap_mode="r")
    if draws.shape != (len(baseline), labels.max() + 1):
        raise ValueError("Baseline draws and archived group identities differ")
    # Reproduce every saved baseline replicate before changing group definitions.
    reconstructed = bootstrap_means(values, labels[cohort], draws)
    np.testing.assert_allclose(reconstructed, baseline, rtol=1e-10, equal_nan=True)
    _, missing = calendar_blocks(frame.date, 1)
    if missing[cohort].any():
        raise ValueError(
            "Missing cohort dates prevent calendar blocking; no silent drop"
        )
    paths = [
        "flights.parquet",
        "flight-msd.npy",
        "msd.npz",
        "cluster-draws.npy",
        "cohort-10000.json",
    ]
    provenance = {name: signature(directory / name) for name in paths}
    provenance["cohort_sha256"] = digest
    return frame, cohort, values, baseline, provenance


def measure(data, out, block_days, seeds):
    """Reuse baseline draws and rerun the same estimator under wider blocks."""
    reference = json.loads((data / "report.json").read_text())
    if reference.get("status") != "complete":
        raise ValueError("The source report must be complete")
    report = {
        "status": "complete",
        "scope": "Sensitivity only; published intervals are not replaced",
        "source_report": signature(data / "report.json"),
        "calendar_anchor": CALENDAR_ANCHOR,
        "block_days": block_days,
        "seeds": seeds,
        "offset_rule": "unique offsets 0, floor(L/3), floor(2L/3)",
        "spatial_grouping": "all sites in each calendar interval",
        "sampling_frame": "occupied blocks in eligible archive, then fixed cohort",
        "empty_calendar_intervals": "not resampled; date differences preserve gaps",
        "cohort": "10000 s; fixed flights and retained segments",
        "statistics": list(STATISTICS),
        "fit_interval_s": [10, 10000],
        "units": {"msd": "m^2", "hurst": "dimensionless"},
        "results": {},
    }
    for slug in NAMES:
        frame, cohort, values, baseline, provenance = load_inputs(data, slug, reference)
        labels = frame.cluster.to_numpy(dtype=int)
        baseline_summary = uncertainty_summary(diagnostic_statistics(LAGS, baseline))
        if any(s["se"] <= 0 for s in baseline_summary.values()):
            raise ValueError("Positive baseline SEs are required for a ratio")
        baseline_entry = {
            "support": block_support(labels, cohort),
            "statistics": baseline_summary,
        }
        n_resamples = len(baseline) - 1
        result = {
            "provenance": provenance,
            "resamples": n_resamples,
            "baseline": baseline_entry,
            "configurations": [],
        }
        _, missing = calendar_blocks(frame.date, 1)
        result["missing_archive_dates"] = int(missing.sum())
        result["missing_cohort_dates"] = 0
        curves_to_save = {"lags": LAGS, "baseline": baseline}
        for days in block_days:
            for offset in boundary_offsets(days):
                labels, _ = calendar_blocks(frame.date, days, offset)
                support = block_support(labels, cohort)
                for seed in seeds:
                    actual_seed = int(
                        np.random.SeedSequence([seed, days, offset]).generate_state(1)[
                            0
                        ]
                    )
                    draws = cluster_draws(labels, n_resamples, actual_seed)
                    curves = bootstrap_means(values, labels[cohort], draws)
                    del draws
                    np.testing.assert_allclose(curves[0], baseline[0], rtol=1e-10)
                    stats = uncertainty_summary(diagnostic_statistics(LAGS, curves))
                    for name, item in stats.items():
                        item["se_ratio"] = item["se"] / baseline_summary[name]["se"]
                    key = f"days_{days}_offset_{offset}_seed_{seed}"
                    curves_to_save[key] = curves
                    result["configurations"].append(
                        {
                            "days": days,
                            "offset_days": offset,
                            "seed": seed,
                            "rng_seed": actual_seed,
                            "support": support,
                            "statistics": stats,
                            "replicate_key": key,
                        }
                    )
                print(
                    f"{slug}: {days} days, offset {offset}, "
                    f"{support['contributing_blocks']} contributing blocks",
                    flush=True,
                )
        np.savez_compressed(out / f"{slug}-replicates.npz", **curves_to_save)
        report["results"][slug] = result
    return report


def render(report, out):
    """Produce a compact figure, full audit CSV and data-driven numerical prose."""
    if report.get("status") != "complete":
        raise ValueError("Refusing to render an incomplete reliability report")
    days = report["block_days"]
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "pdf.fonttype": 42,
        }
    )
    fig, axs = plt.subplots(2, 2, figsize=(7.1, 5.1), layout="constrained", sharex=True)
    titles = [
        r"MSD at $\tau=100$ s",
        r"MSD at $\tau=1000$ s",
        r"MSD at $\tau=10000$ s",
        r"$H$: fit over 10--10000 s",
    ]
    rows, macros = [], {}
    for slug, color, shift in (("para", "#0072B2", -0.035), ("hang", "#D55E00", 0.035)):
        result = report["results"][slug]
        configs = result["configurations"]
        for ax, name, title in zip(axs.flat, STATISTICS, titles, strict=True):
            grouped = [
                [c["statistics"][name]["se_ratio"] for c in configs if c["days"] == day]
                for day in days
            ]
            middle = np.array([np.median(g) for g in grouped])
            lower = middle - np.array([min(g) for g in grouped])
            upper = np.array([max(g) for g in grouped]) - middle
            x = np.asarray(days) * 2**shift
            ax.errorbar(
                x,
                middle,
                yerr=[lower, upper],
                color=color,
                marker="o",
                markersize=3.5,
                linewidth=1,
                capsize=3,
                label=NAMES[slug],
            )
            ax.set_title(title)
        for config in configs:
            for name in STATISTICS:
                rows.append(
                    {
                        "discipline": slug,
                        "statistic": name,
                        **{k: config[k] for k in ("days", "offset_days", "seed")},
                        **config["support"],
                        **config["statistics"][name],
                    }
                )
        for name, stats in result["baseline"]["statistics"].items():
            rows.append(
                {
                    "discipline": slug,
                    "statistic": name,
                    "days": 0,
                    "offset_days": 0,
                    "seed": "archived",
                    **result["baseline"]["support"],
                    **stats,
                    "se_ratio": 1.0,
                }
            )
        first = [c for c in configs if c["days"] == days[0]]
        last = [c for c in configs if c["days"] == days[-1]]

        def limits(configs, names, field="se_ratio"):
            vals = [c["statistics"][name][field] for c in configs for name in names]
            return f"{min(vals):.2f}--{max(vals):.2f}"

        counts = [c["support"]["contributing_blocks"] for c in last]
        count_range = (
            str(min(counts))
            if min(counts) == max(counts)
            else f"{min(counts)}--{max(counts)}"
        )
        max_mass = 100 * max(c["support"]["largest_block_fraction"] for c in last)
        stem = f"ChThree{slug.capitalize()}Block"
        macros.update(
            {
                f"{stem}HurstShort": limits(first, ["hurst"]),
                f"{stem}HurstLong": limits(last, ["hurst"]),
                f"{stem}MsdSpan": limits(last, list(STATISTICS[:3])),
                f"{stem}Count": count_range,
                f"{stem}MaxPct": f"{max_mass:.2f}",
            }
        )
    for ax in axs.flat:
        ax.axhline(1, color="0.45", linewidth=0.8, linestyle="--")
        ax.set_xscale("log", base=2)
        ax.set_xticks(days, [str(d) for d in days])
        ax.set_ylabel("SE / site-day SE")
        ax.grid(axis="y", color="0.9", linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axs[-1]:
        ax.set_xlabel("Calendar block duration (days)")
    axs[0, 0].legend(frameon=False)
    fig.savefig(
        out / f"{PREFIX}.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)
    pd.DataFrame(rows).to_csv(out / f"{PREFIX}.csv", index=False)
    # The chapter prose is hand-written; only these values are generated.
    (out / f"{PREFIX}_values.tex").write_text(
        f"% Generated by {Path(__file__).name}\n"
        + "\n".join(
            f"\\newcommand{{\\{name}}}{{{value}}}"
            for name, value in sorted(macros.items())
        )
        + "\n"
    )


def main():
    """Measure from immutable caches or redraw the standalone diagnostic report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Published Chapter 3 run")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--publish", type=Path)
    parser.add_argument("--block-days", nargs="+", type=int, default=[1, 2, 4, 8, 16])
    parser.add_argument("--seeds", nargs="+", type=int, default=[20260918, 20260919])
    parser.add_argument("--redraw", action="store_true")
    args = parser.parse_args()
    if args.block_days != sorted(set(args.block_days)) or min(args.block_days) < 1:
        parser.error("--block-days must be positive, unique and increasing")
    if len(set(args.seeds)) != len(args.seeds) or min(args.seeds) < 0:
        parser.error("--seeds must be distinct nonnegative integers")
    if args.redraw:
        report = json.loads((args.out / "report.json").read_text())
    else:
        if args.data is None:
            parser.error("--data is required for measurement")
        if (
            args.out.resolve() == args.data.resolve()
            or args.data.resolve() in args.out.resolve().parents
        ):
            parser.error("Use a separate output directory outside the published run")
        if (args.out / "report.json").exists():
            parser.error(
                "Report already exists; use --redraw or a fresh output directory"
            )
        args.out.mkdir(parents=True, exist_ok=True)
        report = measure(args.data, args.out, args.block_days, args.seeds)
        report["code"] = signature(Path(__file__))
        report["analysis_code"] = signature(
            ROOT / "src/soaring/analysis/observables/bootstrap_reliability.py"
        )
        (args.out / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
    render(report, args.out)
    if args.publish:
        args.publish.mkdir(parents=True, exist_ok=True)
        for suffix in (".pdf", ".csv", "_values.tex"):
            shutil.copy2(args.out / f"{PREFIX}{suffix}", args.publish)
        shutil.copy2(args.out / "report.json", args.publish / f"{PREFIX}.json")


if __name__ == "__main__":
    main()
