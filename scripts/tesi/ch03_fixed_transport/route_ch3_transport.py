"""Measure and redraw the closed-route MSD of Section 3.2 by route type and altitude.

The four declared closed routes (flat triangle, FAI triangle, quadrilateral,
out-and-return) are crossed with the four initial-altitude classes. Cohort,
estimator, fit window and archived paired site--day draws are those of
conditional_ch3_transport.py; only the route split is new.
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import shutil
import sys
from itertools import combinations, product
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from check_bootstrap_reliability import load_inputs, signature
from conditional_ch3_transport import interval, macro_key
from conditional_plot_style import ROUTE_COLORS
from render_ch3_fixed import axes_style, band
from summarize_ch3_fixed import fit_summary, portable, summary

from soaring.analysis.observables.conditional_transport import BANDS, strata
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means
from soaring.analysis.observables.fixed_transport import LAGS, log_fit
from soaring.analysis.observables.global_diagnostics import closed_route_type

PREFIX = "ch3_route"
ROUTES = {
    "flat_triangle": "Flat triangle",
    "fai_triangle": "FAI triangle",
    "quadrilateral": "Quadrilateral",
    "out_and_return": "Out-and-return",
}
CLASSES = {
    "all": "All initial altitudes",
    **{f"alt{i}": b for i, b in enumerate(BANDS)},
}
# The descriptive-band minimum of summarize_ch3_fixed.py: fewer site-day groups
# give no interval.
MIN_GROUPS = 20
# Last season in which all four route labels are in regular use. The "early"
# groups keep only flights up to it, so that every route shares the same years.
LAST_FOUR_LABEL_YEAR = 2011
ERAS = ("", "early_")


def measure(data, out):
    """Validate the published closed groups, then split them by route type."""
    reference = json.loads((data / "report.json").read_text())
    if reference.get("status") != "complete":
        raise ValueError("A complete source report is required")
    published_path = ROOT / "thesis/generated/ch3_conditional.json"
    published = json.loads(published_path.read_text())
    frame, cohort, values, _, provenance = load_inputs(data, "para", reference)
    members = frame.loc[cohort].copy()
    masks = strata(members)
    labels = members.cluster.to_numpy(dtype=int)
    archived = np.load(data / "para/cluster-draws.npy", mmap_mode="r")
    route = members.flight_type.map(closed_route_type).to_numpy()
    year = pd.to_datetime(members.date, errors="coerce").dt.year.to_numpy()
    # The four routes must partition exactly the closed flights already published.
    np.testing.assert_array_equal(np.isin(route, list(ROUTES)), masks["closed"])

    def curves(mask):
        occupied, local = np.unique(labels[mask], return_inverse=True)
        draws = archived[:, occupied]
        return bootstrap_means(values[mask], local, draws), len(occupied)

    for key in ("closed", "triangle", *(f"closed_{i}" for i in range(4))):
        np.testing.assert_allclose(
            curves(masks[key])[0][0],
            published["groups"][key]["msd"]["point"],
            rtol=1e-10,
        )
    groups, exponents = {}, {}
    early = year <= LAST_FOUR_LABEL_YEAR
    for era, name, cls in product(ERAS, ROUTES, CLASSES):
        key = f"{name}_{era}{cls}"
        mask = (route == name) & masks[cls] & (early | (era == ""))
        curve, clusters = curves(mask)
        np.testing.assert_allclose(curve[0], values[mask].mean(axis=0), rtol=1e-12)
        complete = bool(np.isfinite(curve).all() and (curve > 0).all())
        row = {
            "flights": int(mask.sum()),
            "clusters": clusters,
            "complete_support": complete,
            "supported": complete and clusters >= MIN_GROUPS,
            "median_year": float(np.nanmedian(year[mask])),
            "four_label_era_flights": int((year[mask] <= LAST_FOUR_LABEL_YEAR).sum()),
        }
        if row["supported"]:
            exponents[key] = log_fit(LAGS, curve)["slope"] / 2
            row["msd"] = summary(curve)
            row["fit"] = fit_summary(LAGS, curve, (10, 10000))
        groups[key] = row
        print(f"{key}: {row['flights']} flights, {clusters} groups", flush=True)
    contrasts = {}

    def contrast(key, terms):
        if all(group in exponents for group, _ in terms):
            differences = sum(weight * exponents[group] for group, weight in terms)
            contrasts[key] = {"terms": terms, "hurst": summary(differences)}

    # Route pairs within one altitude class, all years and early years.
    for era, cls in product(ERAS, CLASSES):
        for first, second in combinations(ROUTES, 2):
            contrast(
                f"{second}_{first}_{era}{cls}",
                [(f"{second}_{era}{cls}", 1), (f"{first}_{era}{cls}", -1)],
            )
    # Altitude pairs within one route, and the FAI-minus-flat gap between them.
    for i, j in combinations(range(4), 2):
        for name in ROUTES:
            contrast(
                f"{name}_alt{i}_alt{j}", [(f"{name}_alt{i}", 1), (f"{name}_alt{j}", -1)]
            )
        contrast(
            f"fai_triangle_flat_triangle_alt{i}_alt{j}",
            [
                (f"fai_triangle_alt{i}", 1),
                (f"flat_triangle_alt{i}", -1),
                (f"fai_triangle_alt{j}", -1),
                (f"flat_triangle_alt{j}", 1),
            ],
        )
    return portable(
        {
            "status": "complete",
            "source_report": signature(data / "report.json"),
            "source_files": provenance,
            "published_groups": signature(published_path),
            "measurement_script": signature(Path(__file__)),
            "contract": {
                **published["contract"],
                "routes": ROUTES,
                "route_source": "catalogue flight_type, closed_route_type",
                "minimum_groups_for_interval": MIN_GROUPS,
                "last_four_label_year": LAST_FOUR_LABEL_YEAR,
            },
            "lags_s": LAGS,
            "groups": groups,
            "contrasts": contrasts,
        }
    )


def table(groups, era):
    """Tabulate every route in each altitude class with two supported routes."""
    lines = [
        r"\begin{tabular}{llrrcrr}",
        r"\toprule",
        r"Initial altitude & Route & $N$ & $G$ & $H$ [5--95\%] & "
        r"$M_2(10^4)$ (km$^2$) & Year \\",
    ]
    for cls, title in CLASSES.items():
        rows = [groups[f"{name}_{era}{cls}"] for name in ROUTES]
        if sum(row["supported"] for row in rows) < 2:
            continue
        lines.append(r"\midrule")
        for i, (label, row) in enumerate(zip(ROUTES.values(), rows, strict=True)):
            h = row["fit"]["hurst"] if row["supported"] else None
            fit = f"{h['point']:.3f} [{h['low']:.3f}, {h['high']:.3f}]" if h else "--"
            amplitude = f"{row['msd']['point'][-1] / 1e6:.0f}" if h else "--"
            lines.append(
                f"{title if i == 0 else ''} & {label} & {row['flights']:,} & "
                f"{row['clusters']:,} & {fit} & {amplitude} & "
                f"{row['median_year']:.0f}" + r" \\"
            )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines) + "\n"


def render(report, out):
    """Draw one panel per altitude class and export the table and TeX macros."""
    if report.get("status") != "complete":
        raise ValueError("Refusing incomplete route report")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
        }
    )
    lags = np.asarray(report["lags_s"])
    groups = report["groups"]
    fig, axes = plt.subplots(
        2, 2, figsize=(7.1, 6.6), layout="constrained", sharex=True, sharey=True
    )
    for ax, cls in zip(axes.flat, [c for c in CLASSES if c != "all"], strict=True):
        omitted = []
        for name, label in ROUTES.items():
            row = groups[f"{name}_{cls}"]
            if not row["supported"]:
                omitted.append(f"{label}: n={row['flights']}, G={row['clusters']}")
                continue
            color = ROUTE_COLORS[label]
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
            ax.plot(
                lags,
                10 ** row["fit"]["intercept"]["point"] * lags ** (2 * h["point"]) / 1e6,
                "--",
                color=color,
                lw=0.9,
            )
        axes_style(ax, logy=True)
        ax.set(xlim=(10, 10000), ylim=(2e-3, 2e4), title=CLASSES[cls])
        ax.legend(loc="upper left", fontsize=6.8)
        if omitted:
            ax.text(
                0.98,
                0.03,
                f"Fewer than {MIN_GROUPS} site-day groups:\n" + "\n".join(omitted),
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=6.5,
                color="0.35",
            )
    for ax in axes[:, 0]:
        ax.set_ylabel(r"$M_{2,g}(\tau)$ (km$^2$)")
    for ax in axes[0]:
        ax.set_xlabel("")
    fig.savefig(
        out / f"{PREFIX}_altitude.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)
    for era, name in (("", "table"), ("early_", "early_table")):
        (out / f"{PREFIX}_{name}.tex").write_text(table(groups, era))
    macros = [rf"\newcommand{{\RouteMinGroups}}{{{MIN_GROUPS}}}"]
    macros.append(rf"\newcommand{{\RouteLastFourLabelYear}}{{{LAST_FOUR_LABEL_YEAR}}}")
    for key, row in groups.items():
        tag = macro_key(key)
        macros += [
            rf"\newcommand{{\Route{tag}N}}{{{row['flights']}}}",
            rf"\newcommand{{\Route{tag}G}}{{{row['clusters']}}}",
        ]
        if row["supported"]:
            macros.append(
                rf"\newcommand{{\Route{tag}H}}{{{interval(row['fit']['hurst'])}}}"
            )
    for name in ROUTES:
        row = groups[f"{name}_all"]
        pct = 100 * row["four_label_era_flights"] / row["flights"]
        macros.append(rf"\newcommand{{\Route{macro_key(name)}EarlyPct}}{{{pct:.0f}}}")
    for key, row in report["contrasts"].items():
        macros.append(
            rf"\newcommand{{\Route{macro_key(key)}Delta}}{{{interval(row['hurst'])}}}"
        )
    (out / f"{PREFIX}_values.tex").write_text(
        "% Generated closed-route transport measurements.\n" + "\n".join(macros) + "\n"
    )
    (out / f"{PREFIX}.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )


def main():
    """Keep measurement separate from the archived source and allow offline redraw."""
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
