"""Render the saved regional finite-difference report without reading trajectories."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

from soaring.analysis.observables.regional_variations import REGIONS
from soaring.reporting.style import PCA_LAG_COLORS, paper_style

REGION_COLORS = {"Alps": "#207f86", "Pyrenees": "#a04c42", "Channel Coast": "#a07a22"}
ORDER_COLORS = ("#777777", "#207f86", "#a04c42")


def variation_macros(report):
    """Define the reference-lag values used by both thesis and supervisor slides."""
    j = report["contract"]["lags_s"].index(1000)
    output = {"StatVarReferenceLagS": "1000"}
    for name, tag in (("paragliders", "Para"), ("hang gliders", "Hang")):
        result = report["results"][name]
        output[f"StatVar{tag}RegionalFlights"] = str(result["n_regional_flights"])
        output[f"StatVar{tag}StandardStrata"] = str(
            result["standardisation"]["n_strata"]
        )
        for region, short in (
            ("Alps", "Alps"),
            ("Pyrenees", "Pyrenees"),
            ("Channel Coast", "Coast"),
        ):
            prefix = f"StatVar{tag}{short}"
            matched = result["regions"][region]["matched"]
            common = result["regions"][region]["common"]
            output[prefix + "Flights"] = str(matched["n_flights"][j][1])
            output[prefix + "MaxFlights"] = str(matched["n_flights"][-1][1])
            for suffix, value in (
                ("RmsMatched", matched["rms_velocity_change_m_s"][j]),
                ("RmsCommon", common["rms_velocity_change_m_s"][j]),
                ("RatioOne", matched["anisotropy"][j][0]),
                ("RatioTwo", matched["anisotropy"][j][1]),
                ("RatioThree", matched["anisotropy"][j][2]),
                ("AngleTwo", matched["axis_deg"][j][1]),
                ("OrderRatio", matched["v3_over_v2"][j]),
            ):
                if value is not None:
                    output[prefix + suffix] = f"{value:.2f}"
            standard = result["standardisation"]["regions"].get(region)
            if standard:
                output[prefix + "StandardFlights"] = str(standard["n_flights"])
                output[prefix + "RmsStandard"] = (
                    f"{standard['rms_velocity_change_m_s'][j]:.2f}"
                )
            for record in result["distributions"]:
                if (
                    record["region"] == region
                    and record["variant"] == "matched"
                    and record["lag_s"] == 1000
                ):
                    for suffix, value in zip(
                        ("TailShareLow", "TailShareHigh"),
                        record["upper_decile_energy_share_bounds"],
                        strict=True,
                    ):
                        output[prefix + suffix] = f"{100 * value:.1f}"
        for contrast in result["contrasts"]:
            if contrast["variant"] == "common" and contrast["numerator"] == "Alps":
                short = (
                    "Coast"
                    if contrast["denominator"] == "Channel Coast"
                    else "Pyrenees"
                )
                prefix = f"StatVar{tag}AlpsVs{short}"
                for suffix, value in (
                    ("Ratio", contrast["rms_change_ratio"][j]),
                    ("Lower", contrast["simultaneous_95"][0][j]),
                    ("Upper", contrast["simultaneous_95"][1][j]),
                ):
                    if value is not None:
                        output[prefix + suffix] = f"{value:.3f}"
    return output


def array(value):
    """Read JSON null as an unsupported numerical value."""
    return np.asarray(value, dtype=float)


def render_regional_variations(report, directory):
    """Create six complementary figures from the complete aggregate report."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paper_style()
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "pdf.fonttype": 42,
            "savefig.bbox": None,
        }
    )
    lags = array(report["contract"]["lags_s"])
    para = report["results"]["paragliders"]
    paths = []

    def save(fig, name):
        """Keep fixed figure dimensions and record every rendered output."""
        path = directory / f"ch3_{name}.pdf"
        fig.savefig(path, metadata={"CreationDate": None, "ModDate": None})
        plt.close(fig)
        paths.append(path)

    fig, axes = plt.subplots(3, 2, figsize=(6.5, 7.5), layout="constrained")
    for row, region in enumerate(REGIONS):
        data = para["regions"][region]
        left, right = axes[row]
        for variant, style, color, label in (
            ("available", ":", "#777777", "Available order-2 support"),
            ("matched", "-", REGION_COLORS[region], "Orders share support"),
            ("common", "--", "#242424", "Orders and lags share origins"),
        ):
            record = data[variant]
            curve = array(record["rms_velocity_change_m_s"])
            curve[array(record["n_flights"])[:, 1] < 8] = np.nan
            left.loglog(lags, curve, style, color=color, label=label)
            if variant == "matched":
                bounds = array(record["pointwise_95"]["rms_velocity_change_m_s"])
                left.fill_between(lags, *bounds, color=color, alpha=0.18, linewidth=0)
        record = data["matched"]
        for p, color in enumerate(ORDER_COLORS):
            ratio = array(record["anisotropy"])[:, p]
            ratio[array(record["n_flights"])[:, p] < 8] = np.nan
            right.semilogx(lags, ratio, color=color, label=f"Order {p + 1}")
        right.axhline(1, color=".7", lw=0.7)
        left.set(
            title=region, ylabel=r"$\sqrt{V_2}/\tau$ [m/s]", xlabel=r"Lag $\tau$ [s]"
        )
        right.set(
            title="Centred covariance anisotropy",
            ylabel=r"$\lambda_1/\lambda_2$",
            xlabel=r"Lag $\tau$ [s]",
        )
        if row == 0:
            left.legend(loc="upper left")
            right.legend(loc="best")
    save(fig, "regional_variations")

    fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.7), layout="constrained")
    for ax, region in zip(axes, REGIONS, strict=True):
        record = para["regions"][region]["matched"]
        moments = array(record["moments"])
        for lag in report["contract"]["display_lags_s"]:
            j = list(lags).index(lag)
            if record["n_flights"][j][1] < 8:
                continue
            m = moments[j, 1]
            covariance = np.array([[m[2], m[3]], [m[3], m[4]]])
            values = np.linalg.eigvalsh(covariance)
            if values[0] <= 0:
                continue
            scale = np.sqrt(values.sum())
            ax.add_patch(
                Ellipse(
                    (0, 0),
                    2 * np.sqrt(values[1]) / scale,
                    2 * np.sqrt(values[0]) / scale,
                    angle=record["axis_deg"][j][1],
                    fill=False,
                    color=PCA_LAG_COLORS[lag],
                    label=f"{lag:g} s",
                )
            )
        ax.axhline(0, color=".85", lw=0.6)
        ax.axvline(0, color=".85", lw=0.6)
        ax.set(
            title=region,
            xlim=(-1.1, 1.1),
            ylim=(-1.1, 1.1),
            aspect="equal",
            xlabel="East / centred RMS",
            ylabel="North / centred RMS",
            xticks=(-1, 0, 1),
            yticks=(-1, 0, 1),
        )
    axes[-1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=2)
    save(fig, "variation_axes")

    fig, axes = plt.subplots(3, 2, figsize=(6.5, 7.1), layout="constrained")
    for row, region in enumerate(REGIONS):
        record = para["regions"][region]["matched"]
        variation = array(record["variation"])
        supported = array(record["n_flights"])[:, 0] >= 8
        variation[~supported] = np.nan
        left, right = axes[row]
        for p, color in enumerate(ORDER_COLORS):
            left.loglog(lags, variation[:, p], color=color, label=f"$V_{p + 1}$")
        ratio = array(record["v3_over_v2"])
        ratio[~supported] = np.nan
        right.semilogx(lags, ratio, color=REGION_COLORS[region])
        right.fill_between(
            lags,
            *array(record["pointwise_95"]["v3_over_v2"]),
            color=REGION_COLORS[region],
            alpha=0.18,
            linewidth=0,
        )
        right.axhline(3, color=".5", ls=":", label="Brownian + constant drift")
        left.set(title=region, ylabel=r"$V_p$ [m$^2$]", xlabel=r"Lag $\tau$ [s]")
        right.set(
            title="Paired order contrast", ylabel=r"$V_3/V_2$", xlabel=r"Lag $\tau$ [s]"
        )
        if row == 0:
            left.legend()
            right.legend(loc="best")
    save(fig, "variation_orders")

    fig, axes = plt.subplots(2, 2, figsize=(6.5, 5.4), layout="constrained")
    edges = array(report["contract"]["distribution_edges_m_s"])
    for ax, lag in zip(axes.flat, report["contract"]["display_lags_s"], strict=True):
        for region in REGIONS:
            rows = [
                r
                for r in para["distributions"]
                if r["region"] == region
                and r["variant"] == "matched"
                and r["lag_s"] == lag
            ]
            if not rows or rows[0]["n_flights"] < 8:
                continue
            probability = array(rows[0]["probability"])
            cumulative = np.cumsum(probability)
            finite = np.isfinite(edges[1:])
            ax.semilogx(
                edges[1:][finite],
                cumulative[finite],
                color=REGION_COLORS[region],
                label=region,
            )
        ax.set(
            title=rf"$\tau={lag:g}$ s",
            xlabel=r"$|A_2\mathbf{r}|/\tau$ [m/s]",
            ylabel="Equal-flight cumulative probability",
            xlim=(0.001, 100),
            ylim=(0, 1.01),
        )
    axes[0, 0].legend(loc="upper left")
    save(fig, "variation_distributions")

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.0), layout="constrained")
    standard = para["standardisation"]["regions"]
    for region in REGIONS:
        color = REGION_COLORS[region]
        common = para["regions"][region]["common"]
        axes[0].loglog(
            lags, array(common["rms_velocity_change_m_s"]), color=color, label=region
        )
        if region in standard:
            axes[0].loglog(
                lags,
                array(standard[region]["rms_velocity_change_m_s"]),
                "--",
                color=color,
            )
    for contrast in para["contrasts"]:
        if contrast["variant"] != "common" or contrast["numerator"] != "Alps":
            continue
        denominator = contrast["denominator"]
        color = REGION_COLORS[denominator]
        axes[1].semilogx(
            lags,
            array(contrast["rms_change_ratio"]),
            color=color,
            label=f"Alps / {denominator}",
        )
        axes[1].fill_between(
            lags,
            *array(contrast["simultaneous_95"]),
            color=color,
            alpha=0.2,
            linewidth=0,
        )
    axes[0].set(
        title="Common origins; dashed: common contexts",
        xlabel=r"Lag $\tau$ [s]",
        ylabel=r"$\sqrt{V_2}/\tau$ [m/s]",
        xlim=(10, 1000),
    )
    axes[1].set(
        title="Simultaneous 95% bands over 10--1000 s",
        xlabel=r"Lag $\tau$ [s]",
        ylabel="RMS-change ratio",
        xlim=(10, 1000),
    )
    axes[1].axhline(1, color=".5", ls=":")
    for ax in axes:
        ax.legend(loc="best")
    save(fig, "variation_controls")

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.1), layout="constrained")
    for ax, discipline in zip(axes, ("paragliders", "hang gliders"), strict=True):
        for region in REGIONS:
            record = report["results"][discipline]["regions"][region]
            ax.loglog(
                lags,
                array(record["matched"]["n_flights"])[:, 0],
                color=REGION_COLORS[region],
                label=region,
            )
            common = array(record["common"]["n_flights"])[:, 0]
            common[common == 0] = np.nan
            ax.loglog(lags, common, "--", color=REGION_COLORS[region])
        ax.set(
            title=discipline.capitalize(),
            xlabel=r"Lag $\tau$ [s]",
            ylabel="Contributing flights",
        )
    axes[0].legend()
    save(fig, "variation_support")
    return paths
