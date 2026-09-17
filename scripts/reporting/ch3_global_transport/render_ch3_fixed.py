"""Redraw Chapter 3 using only report.json: no trajectories or bootstrap rerun."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from write_ch3_text import write_text

COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")
NAMES = {"para": "Paragliders", "hang": "Hang gliders"}
COORDS = (r"$|\Delta E|$", r"$|\Delta N|$", r"$R$")


def array(value):
    """Read JSON null as NaN."""
    return np.asarray(value, dtype=float)


def band(ax, x, stats, color, label, index=None, scale=1):
    """Distinguish measured points, connecting lines and percentile shading."""
    ys = [array(stats[k]) for k in ("point", "low", "high")]
    if index is not None:
        ys = [y[index] for y in ys]
    point, low, high = [y / scale for y in ys]
    ax.fill_between(x, low, high, color=color, alpha=0.20, linewidth=0)
    ax.plot(
        x, point, "o-", ms=3.1, lw=1.0, mew=0.6, mfc="white", color=color, label=label
    )


def axes_style(ax, *, logy=False, lag=True):
    """Apply compact paper typography and unobtrusive grids."""
    if lag:
        ax.set_xscale("log")
        ax.set_xlabel(r"Lag $\tau$ (s)")
    if logy:
        ax.set_yscale("log")
    ax.grid(True, which="major", color="0.9", lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


def save(fig, out, name):
    """Write one reusable vector figure."""
    fig.savefig(
        out / f"ch3_transport_{name}.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def figures(report, out):
    """Render general transport, population effects and fixed-law diagnostics."""
    results = report["results"]
    lags = array(report["lags_s"])
    probs = array(report["probabilities"])
    orders = array(report["orders"])
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "pdf.fonttype": 42,
        }
    )
    fig, axs = plt.subplots(2, 2, figsize=(7.1, 6.1), layout="constrained")
    for row, (slug, d) in enumerate(results.items()):
        g = d["general"]
        x = array(g["lags"])
        ax = axs[row, 0]
        scatter = array(g["ensemble_p5_median_p95"]) / 1e6
        ax.fill_between(
            x,
            scatter[0],
            scatter[2],
            color=COLORS[row],
            alpha=0.18,
            label="Flight scatter: 5-95%",
        )
        ax.plot(
            x,
            array(g["ensemble_mean"]) / 1e6,
            "o-",
            color=COLORS[row],
            ms=3,
            mfc="white",
            lw=1,
            label="Mean",
        )
        ax.plot(
            x,
            scatter[1],
            "s-",
            color="0.3",
            ms=2.5,
            mfc="white",
            lw=0.8,
            label="Median",
        )
        origin_fit = g["ensemble_global_fit"]
        ax.plot(
            lags,
            10 ** origin_fit["intercept"] * lags ** origin_fit["slope"] / 1e6,
            "--",
            color="0.2",
            lw=1,
            label=f"Mean fit: H = {origin_fit['slope'] / 2:.3f}",
        )
        ax.set_title(f"{NAMES[slug]}: from post-trim origin")
        ax.set_ylabel(r"Squared distance (km$^2$)")
        axes_style(ax, logy=True)
        ax.legend(loc="upper left")
        ax = axs[row, 1]
        band(ax, x, g["tamsd"], COLORS[row], "Equal-flight TA-MSD", scale=1e6)
        fit = g["tamsd_global_fit"]
        ax.plot(
            lags,
            10 ** fit["intercept"]["point"] * lags ** fit["exponent"]["point"] / 1e6,
            "--",
            color="0.2",
            lw=1,
            label=f"10-10000 s fit: H = {fit['hurst']['point']:.3f}",
        )
        ax.set_title(f"{NAMES[slug]}: available population")
        ax.set_ylabel(r"MSD (km$^2$)")
        axes_style(ax, logy=True)
        ax.legend(loc="upper left")
    save(fig, out, "general")

    fig, axs = plt.subplots(1, 2, figsize=(7.1, 2.8), layout="constrained")
    for ax, (slug, d) in zip(axs, results.items(), strict=True):
        g = d["general"]
        x = array(g["lags"])
        keep = x <= 10000
        for key, color, marker, label in (
            ("ensemble_local_h", COLORS[0], "o", "Origin: mean"),
            ("ensemble_median_local_h", "0.45", "s", "Origin: median"),
        ):
            ax.plot(
                x[keep],
                array(g[key])[keep],
                marker + "-",
                color=color,
                ms=3,
                mfc="white",
                lw=1,
                label=label,
            )
        band(ax, x[keep], g["tamsd_local_h"], COLORS[1], "TA-MSD", keep)
        ax.axhline(1, color="0.5", ls=":", lw=0.8)
        ax.set_title(NAMES[slug])
        ax.set_ylabel(r"Local $H=\frac{1}{2}d\log M_2/d\log\tau$")
        axes_style(ax)
        ax.legend(loc="lower left")
    save(fig, out, "general_slopes")

    fig, axs = plt.subplots(2, 2, figsize=(7.1, 5.7), layout="constrained")
    for col, (slug, d) in enumerate(results.items()):
        x = array(d["msd_lags"])
        for c, color, label in (
            (1, COLORS[2], "C100"),
            (2, COLORS[1], "C1000"),
            (3, COLORS[0], "C10000"),
        ):
            band(axs[0, col], x, d["msd"], color, label, c, scale=1e6)
        fit = d["fits"]["10-10000"]
        axs[0, col].plot(
            lags,
            10 ** fit["intercept"]["point"] * lags ** fit["exponent"]["point"] / 1e6,
            "--",
            color="0.2",
            lw=1,
            label=f"Main fit: H = {fit['hurst']['point']:.3f}",
        )
        axs[0, col].set_title(NAMES[slug])
        axs[0, col].set_ylabel(r"MSD (km$^2$)")
        axes_style(axs[0, col], logy=True)
        axs[0, col].legend(loc="upper left")
        for c, color, label in (
            (1, COLORS[2], "C100 / C10000"),
            (2, COLORS[1], "C1000 / C10000"),
            (0, "0.45", "Available / C10000"),
        ):
            band(axs[1, col], x, d["cohort_ratios"][str(c)], color, label)
        axs[1, col].axhline(1, color="0.4", lw=0.8, ls=":")
        axs[1, col].set_ylabel("MSD ratio")
        axes_style(axs[1, col])
        axs[1, col].legend(loc="best")
        for ax in axs[:, col]:
            ax.set_xlim(8, 12500)
    save(fig, out, "cohorts")

    fig, axs = plt.subplots(1, 2, figsize=(7.1, 3.4), layout="constrained", sharey=True)
    d = results["para"]
    for ax, task in zip(axs, ("open", "closed"), strict=True):
        total = sum(d["groups"][f"{task}_{i}"]["flights"] for i in range(4))
        for i, color in enumerate(COLORS):
            group = d["groups"][f"{task}_{i}"]
            band(
                ax,
                lags,
                group["curve"],
                color,
                f"{group['altitude']} (n={group['flights']:,})",
                scale=1e6,
            )
            fit = group["fit"]
            ax.plot(
                lags,
                10 ** fit["intercept"]["point"]
                * lags ** fit["exponent"]["point"]
                / 1e6,
                "--",
                color=color,
                lw=0.75,
                alpha=0.8,
            )
        ax.set_title(f"{task.capitalize()} (n={total:,})")
        axes_style(ax, logy=True)
        ax.legend(loc="upper left")
    axs[0].set_ylabel(r"MSD (km$^2$)")
    save(fig, out, "task_altitude")

    fig, axs = plt.subplots(1, 2, figsize=(7.1, 2.8), layout="constrained")
    for ax, (slug, d) in zip(axs, results.items(), strict=True):
        band(ax, lags, d["fixed_local_h"], COLORS[0], "Local slope")
        h = d["fits"]["10-10000"]["hurst"]
        ax.axhspan(h["low"], h["high"], color=COLORS[1], alpha=0.2)
        ax.axhline(h["point"], color=COLORS[1], ls="--", label="Global fit")
        ax.set_title(NAMES[slug])
        ax.set_ylabel("Effective H")
        axes_style(ax)
        ax.legend()
    save(fig, out, "fixed_slopes")

    for slug, d in results.items():
        fig, axs = plt.subplots(2, 3, figsize=(7.1, 4.9), layout="constrained")
        for c, coordinate in enumerate(COORDS):
            for p, color in enumerate(COLORS):
                band(
                    axs[0, c],
                    lags,
                    d["quantiles"],
                    color,
                    f"Q{int(probs[p] * 100)}",
                    (slice(None), c, p),
                    scale=1000,
                )
            axes_style(axs[0, c], logy=True)
            axs[0, c].set_title(coordinate)
            axs[0, c].set_ylabel("Displacement (km)")
            axs[0, c].legend(loc="upper left", ncol=2)
            band(
                axs[1, c], lags, d["quantile_ratio"], COLORS[0], None, (slice(None), c)
            )
            axes_style(axs[1, c])
            axs[1, c].set_ylabel(r"$Q_{25}/Q_{90}$")
        save(fig, out, f"quantiles_{slug}")

    fig, axs = plt.subplots(2, 3, figsize=(7.1, 4.5), layout="constrained", sharex=True)
    for row, (slug, d) in enumerate(results.items()):
        s = d["scaling_fits"]["10-10000"]
        for c, coordinate in enumerate(COORDS):
            y, low, high = [
                array(s["quantile_h"][k])[c] for k in ("point", "low", "high")
            ]
            axs[row, c].errorbar(
                probs * 100,
                y,
                yerr=[y - low, high - y],
                fmt="o-",
                ms=4,
                mfc="white",
                capsize=3,
                color=COLORS[row],
                lw=1,
            )
            axes_style(axs[row, c], lag=False)
            axs[row, c].set_title(f"{NAMES[slug]}: {coordinate}")
            axs[row, c].set_xlabel("Quantile (%)")
            axs[row, c].set_ylabel(r"$H_p$ (10-10000 s)")
            axs[row, c].set_xticks(probs * 100)
    save(fig, out, "quantile_exponents")

    fig, axs = plt.subplots(2, 3, figsize=(7.1, 4.5), layout="constrained", sharex=True)
    for row, (slug, d) in enumerate(results.items()):
        s = d["scaling_fits"]["10-10000"]
        for c, coordinate in enumerate(COORDS):
            ax = axs[row, c]
            band(ax, orders, s["zeta"], COLORS[row], "Measured", c)
            ax.plot(
                orders,
                orders * s["common_moment_h"]["point"][c],
                "--",
                color="0.4",
                lw=1,
                label=r"Fit $qH$",
            )
            axes_style(ax, lag=False)
            ax.set_title(f"{NAMES[slug]}: {coordinate}")
            ax.set_xlabel("Moment order q")
            ax.set_ylabel(r"$\zeta(q)$")
            ax.legend()
    save(fig, out, "spectrum")

    fig, axs = plt.subplots(1, 2, figsize=(7.1, 2.9), layout="constrained")
    for ax, (slug, d) in zip(axs, results.items(), strict=True):
        for c, label in enumerate((r"Signed $\Delta E$", r"Signed $\Delta N$")):
            band(ax, lags, d["kurtosis"], COLORS[c], label, (slice(None), c))
        ax.axhline(0, color="0.3", ls="--", lw=0.8)
        ax.set_title(NAMES[slug])
        ax.set_ylabel("Excess kurtosis")
        axes_style(ax)
        ax.legend()
    save(fig, out, "kurtosis")


def interval(s, digits=3):
    """Typeset an estimate followed by its bootstrap interval."""
    return f"{s['point']:.{digits}f} [{s['low']:.{digits}f}, {s['high']:.{digits}f}]"


def tables(report, out):
    """Create small factual tables from the same saved report as the figures."""
    r = report["results"]

    def write(name, columns, header, rows):
        text = [
            r"\begin{tabular}{" + columns + "}",
            r"\toprule",
            header + r"\\",
            r"\midrule",
            *[" & ".join(row) + r"\\" for row in rows],
            r"\bottomrule",
            r"\end{tabular}",
        ]
        (out / f"ch3_transport_{name}.tex").write_text("\n".join(text) + "\n")

    rows = []
    for slug, d in r.items():
        for limit, c in d["cohorts"].items():
            rows.append(
                [
                    NAMES[slug],
                    limit,
                    f"{c['flights']:,}",
                    f"{c['segments']:,}",
                    f"{c['groups']:,}",
                ]
            )
    write(
        "cohort_table",
        "llrrr",
        r"Discipline & $\tau_{\max}$ (s) & Flights & Segments & Groups",
        rows,
    )
    rows = []
    for slug, d in r.items():
        g = d["general"]
        x = array(g["lags"])
        last = np.flatnonzero(array(g["tamsd_support"]) > 0)[-1]
        for idx in [np.flatnonzero(x == t)[0] for t in (10, 100, 1000, 10000)] + [last]:
            rows.append(
                [
                    NAMES[slug],
                    str(int(x[idx])),
                    f"{g['tamsd_support'][idx]:,}",
                    f"{g['ensemble_support'][idx]:,}",
                ]
            )
    write(
        "support_table",
        "lrrr",
        r"Discipline & Lag (s) & TA-MSD flights & Origin-distance flights",
        rows,
    )
    rows = []
    for slug, d in r.items():
        s = d["interpolation"]["10000"]
        rows.append(
            [
                NAMES[slug],
                f"{s['grid_points']:,}",
                f"{s['grid_exact']:,}",
                f"{s['grid_interpolated']:,}",
                f"{100 * s['new_interpolation_fraction']:.2f}\\%",
            ]
        )
    write(
        "interpolation_table",
        "lrrrr",
        r"Discipline & Grid fixes & Coincident & Interpolated & Fraction",
        rows,
    )
    rows = []
    for slug, d in r.items():
        for key, fit in d["fits"].items():
            rows.append(
                [
                    NAMES[slug],
                    key.replace("-", "--"),
                    interval(fit["hurst"]),
                    f"{fit['rms_dex']['point']:.3f}",
                ]
            )
    write(
        "fit_table",
        "llrr",
        r"Discipline & Fit range (s) & $H$ [5--95\%] & RMS (dex)",
        rows,
    )
    rows = []
    for task in ("open", "closed"):
        for i in range(4):
            g = r["para"]["groups"][f"{task}_{i}"]
            rows.append(
                [
                    task.capitalize(),
                    g["altitude"],
                    f"{g['flights']:,}",
                    f"{g['clusters']:,}",
                    interval(g["fit"]["hurst"]),
                    f"{g['amplitude_10000_m2']['point'] / 1e6:.0f}",
                ]
            )
    write(
        "task_table",
        "llrrrr",
        (
            r"Circuit & Initial altitude & $N$ & $G$ & $H$ [5--95\%] "
            r"& $M_2(10^4)$ (km$^2$)"
        ),
        rows,
    )
    rows = []
    for slug, d in r.items():
        for limit in ("100", "1000"):
            c = d["cohorts"][limit]
            rows.append(
                [
                    NAMES[slug],
                    "10--" + limit,
                    interval(c["fit"]["hurst"]),
                    interval(c["main_fit_on_same_range"]["hurst"]),
                ]
            )
    write(
        "cohort_fit_table",
        "llrr",
        r"Discipline & Fit range (s) & Dedicated cohort $H$ & Main cohort $H$",
        rows,
    )
    rows = []
    for slug, d in r.items():
        s = d["scaling_fits"]["10-10000"]
        for c, name in enumerate((r"$|\Delta E|$", r"$|\Delta N|$", "$R$")):
            vals = [
                {k: s[field][k][c] for k in ("point", "low", "high")}
                for field in ("H25_minus_H90", "H4_minus_H025")
            ]
            rows.append(
                [NAMES[slug], name, interval(vals[0]), interval(vals[1], digits=4)]
            )
    write(
        "scaling_table",
        "llrr",
        r"Discipline & Amplitude & $H_{25}-H_{90}$ & $\zeta(4)/4-\zeta(0.25)/0.25$",
        rows,
    )


def main():
    """Render once on SSD and optionally copy publication artifacts to the thesis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--publish", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    report = json.loads((args.data / "report.json").read_text())
    if report["status"] != "complete":
        raise ValueError("Only complete, validated reports may be published")
    out = args.data / "figures"
    out.mkdir(exist_ok=True)
    figures(report, out)
    tables(report, out)
    write_text(report, out)
    if args.publish:
        args.publish.mkdir(parents=True, exist_ok=True)
        for path in out.glob("ch3_transport_*.*"):
            target = args.publish / path.name
            shutil.copyfile(path, target)
            target.chmod(0o644)
        target = args.publish / "ch3_transport_report.json"
        shutil.copyfile(args.data / "report.json", target)
        target.chmod(0o644)
    print(f"Redraw complete in {time.monotonic() - started:.1f}s: {out}")


if __name__ == "__main__":
    main()
