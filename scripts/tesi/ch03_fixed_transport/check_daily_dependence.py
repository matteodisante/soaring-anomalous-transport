"""Diagnose daily dependence of fixed-cohort MSD and fitted-H contributions.

Reuses the validated per-flight caches. Keeps the original estimator and all
flights; monthly centring is a separate descriptive sensitivity check. No block
length, significance threshold, corrected interval or independence claim is chosen.
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
    daily_contributions,
    daily_correlogram,
    diagnostic_influence,
)
from soaring.analysis.observables.fixed_transport import LAGS

PREFIX = "ch3_transport_daily_dependence"


def measure(data, out, max_days):
    """Validate the archive and aggregate all fixed-cohort flight contributions."""
    reference = json.loads((data / "report.json").read_text())
    if reference.get("status") != "complete":
        raise ValueError("The source report must be complete")
    report = {
        "status": "complete",
        "scope": "Descriptive dependence check; published estimates unchanged",
        "source_report": signature(data / "report.json"),
        "max_days": max_days,
        "statistics": list(STATISTICS),
        "daily_contribution": "sum of centred per-flight influence contributions",
        "empty_dates": "zero contribution to observed estimator, calendar preserved",
        "rho": "sum(U[d]*U[d+h]) / sum(U[d]**2), full calendar",
        "variance_factor": "1 + 2 sum_{1<=h<L} (1-h/L) rho(h)",
        "variance_reference": "independent days, not the site-day bootstrap",
        "seasonal_check": "subtract flight-weighted month-of-year means across years",
        "interpretation": "No independence test or stationarity assumption verified",
        "results": {},
    }
    for slug in NAMES:
        frame, cohort, values, _, provenance = load_inputs(data, slug, reference)
        scores = diagnostic_influence(LAGS, values)
        dates = frame.loc[cohort, "date"]
        result = {"provenance": provenance, "variants": {}}
        saved = {}
        for variant, centre in (("raw", False), ("month_centred", True)):
            calendar, daily, counts, monthly = daily_contributions(
                dates, scores, centre_months=centre
            )
            np.testing.assert_allclose(daily.sum(axis=0), 0, atol=1e-7)
            diagnostic = daily_correlogram(daily, counts, max_days)
            result["variants"][variant] = {
                key: value.tolist() for key, value in diagnostic.items()
            }
            saved[variant] = daily
        saved["calendar"] = calendar.to_numpy(dtype="datetime64[D]")
        saved["flight_counts"] = counts
        saved["monthly_mean_contributions"] = monthly
        np.savez_compressed(out / f"{slug}-daily.npz", **saved)
        result.update(
            {
                "flights": len(values),
                "first_date": str(calendar[0].date()),
                "last_date": str(calendar[-1].date()),
                "calendar_days": len(calendar),
                "occupied_days": int(np.count_nonzero(counts)),
                "largest_day_flights": int(counts.max()),
                "monthly_mean_contributions": monthly.tolist(),
            }
        )
        report["results"][slug] = result
        print(
            f"{slug}: {len(values)} flights, {len(calendar)} calendar days", flush=True
        )
    return report


def render(report, out):
    """Draw the correlograms and export every calendar separation."""
    if report.get("status") != "complete":
        raise ValueError("Refusing to render an incomplete daily-dependence report")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "legend.fontsize": 8,
            "pdf.fonttype": 42,
        }
    )
    fig, axs = plt.subplots(1, 2, figsize=(7.1, 2.9), layout="constrained", sharex=True)
    titles = [
        r"MSD at $\tau=1000$ s",
        r"$H$: fit over 10--10000 s",
    ]
    shown = {1: axs[0], 3: axs[1]}
    h = np.arange(report["max_days"] + 1)
    rows, macros = [], {}
    for slug, color in (("para", "#0072B2"), ("hang", "#D55E00")):
        result = report["results"][slug]
        for variant, style in (("raw", "-"), ("month_centred", "--")):
            diag = result["variants"][variant]
            rho = np.asarray(diag["rho"])
            for j, name in enumerate(STATISTICS):
                if j in shown:
                    shown[j].plot(
                        h[1:],
                        rho[1:, j],
                        color=color,
                        linestyle=style,
                        linewidth=0.9,
                        alpha=0.9,
                    )
                for k in h:
                    rows.append(
                        {
                            "discipline": slug,
                            "statistic": name,
                            "variant": variant,
                            "days": int(k),
                            "rho": float(rho[k, j]),
                            "occupied_day_pairs": diag["occupied_pairs"][k],
                            "bartlett_variance_factor": diag["variance_factor"][k][j]
                            if k
                            else None,
                        }
                    )
        raw = np.asarray(result["variants"]["raw"]["rho"])
        centred = np.asarray(result["variants"]["month_centred"]["rho"])
        end = report["max_days"]
        start = min(17, end)
        stem = f"ChThree{slug.capitalize()}Daily"
        macros.update(
            {
                f"{stem}Rho": f"{raw[1, 1]:.2f}",
                f"{stem}RhoCentred": f"{centred[1, 1]:.2f}",
                f"{stem}Tail": f"{raw[start:, 1].mean():.3f}",
                f"{stem}TailCentred": f"{centred[start:, 1].mean():.3f}",
            }
        )
    for ax, title in zip(axs.flat, titles, strict=True):
        ax.set_title(title)
        ax.axhline(0, color="0.4", linewidth=0.7)
        ax.set_xlim(1, report["max_days"])
        ax.set_ylabel(r"Autocovariance ratio $\widehat{\rho}(h)$")
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axs:
        ax.set_xlabel("Calendar separation h (days)")
    from matplotlib.lines import Line2D

    handles = [
        Line2D([], [], color=c, label=NAMES[s])
        for s, c in (("para", "#0072B2"), ("hang", "#D55E00"))
    ]
    handles += [
        Line2D([], [], color="0.3", linestyle=style, label=label)
        for style, label in (
            ("-", "Original contributions"),
            ("--", "Month-centred contributions"),
        )
    ]
    fig.legend(handles=handles, loc="outside lower center", ncol=2, frameon=False)
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
    """Measure from the archive or redraw the portable report offline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--publish", type=Path)
    parser.add_argument("--max-days", type=int, default=64)
    parser.add_argument("--redraw", action="store_true")
    args = parser.parse_args()
    if args.max_days < 1:
        parser.error("--max-days must be positive")
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
            parser.error("Report exists; use --redraw or a fresh output directory")
        args.out.mkdir(parents=True, exist_ok=True)
        report = measure(args.data, args.out, args.max_days)
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
