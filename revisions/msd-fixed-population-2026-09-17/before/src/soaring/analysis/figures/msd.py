"""Archive MSD curves with the estimator and sampling unit kept explicit."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from soaring.reporting.style import DISCIPLINE_COLORS

from ..observables.transport import local_slope

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from ..observables.transport import MSDResult, PowerLawFit


def make_msd_figure(
    results: dict[str, MSDResult],
    fits: dict[str, PowerLawFit],
    ta_results: dict[str, MSDResult] | None = None,
    ta_fits: dict[str, PowerLawFit] | None = None,
) -> Figure:
    """Show launch averages and equal-segment TAMSD without fitted model claims.

    Fitted curves remain accepted for compatibility but are not drawn. Percentile
    bands describe variation across flights/segments, not uncertainty on the mean.
    """
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    plt.rcParams.update(
        {
            "font.size": 9.5,
            "axes.titlesize": 10,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )
    colors = DISCIPLINE_COLORS
    fig, axes = plt.subplots(2, 2, figsize=(6.1, 5.6), layout="constrained")

    def draw(ax, result, color):
        ok = np.isfinite(result.msd) & (result.msd > 0)
        if result.p10 is not None:
            band = np.isfinite(result.p10) & np.isfinite(result.p90)
            ax.fill_between(
                result.t[band],
                result.p10[band],
                result.p90[band],
                color=color,
                alpha=0.13,
                lw=0,
            )
            ax.plot(result.t[band], result.p50[band], color=color, lw=1, ls=":")
        ax.plot(result.t[ok], result.msd[ok], color=color, lw=1.6)

    for discipline, result in results.items():
        color = colors[discipline]
        draw(axes[0, 0], result, color)
        good = result.n_flights > 0
        axes[1, 1].loglog(result.t[good], result.n_flights[good], color=color)
    for discipline, result in (ta_results or {}).items():
        color = colors[discipline]
        draw(axes[0, 1], result, color)
        slope, _ = local_slope(result)
        axes[1, 0].semilogx(result.t, slope, color=color)
        good = result.n_flights > 0
        axes[1, 1].loglog(result.t[good], result.n_flights[good], "--", color=color)
    for ax, title, xlabel, ylabel in (
        (
            axes[0, 0],
            "(a) Launch-synchronised MSD",
            "Time since launch t [s]",
            r"$\langle |\mathbf{r}(t)|^2\rangle_f$ [m$^2$]",
        ),
        (
            axes[0, 1],
            "(b) Equal-segment time average",
            r"Lag $\tau$ [s]",
            r"$\langle\overline{\delta^2}(\tau)\rangle_s$ [m$^2$]",
        ),
    ):
        ax.set(xscale="log", yscale="log", title=title, xlabel=xlabel, ylabel=ylabel)
    for reference, label in ((2, "Slope 2"), (1, "Slope 1")):
        axes[1, 0].axhline(reference, color=".6", ls=":", lw=0.8)
        axes[1, 0].text(
            0.97,
            reference,
            label,
            fontsize=9,
            color=".4",
            ha="right",
            va="bottom",
            transform=axes[1, 0].get_yaxis_transform(),
        )
    axes[1, 0].set(
        title="(c) Local slope of (b)",
        xlabel=r"Lag $\tau$ [s]",
        ylabel=r"$d\log M_2/d\log\tau$",
        ylim=(0, 2.6),
    )
    axes[1, 1].set(
        title="(d) Number contributing",
        xlabel=r"Time t or lag $\tau$ [s]",
        ylabel="Flights or segments",
    )
    axes[1, 1].legend(
        handles=[
            Line2D([], [], color=".3", ls=ls, label=label)
            for ls, label in (("-", "Flights, (a)"), ("--", "Segments, (b)"))
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.27),
        frameon=False,
    )
    axes[0, 1].legend(
        handles=[
            Line2D([], [], color=".4", label="Mean"),
            Line2D([], [], color=".4", ls=":", label="Median"),
            Patch(facecolor=".5", alpha=0.15, label="10–90% range"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.27),
        frameon=False,
        ncol=2,
    )
    fig.legend(
        handles=[
            Line2D([], [], color=c, label=d.capitalize()) for d, c in colors.items()
        ],
        loc="outside upper center",
        ncol=2,
        frameon=False,
    )
    for ax in axes.flat:
        ax.grid(visible=True, which="major", color=".9", lw=0.6)
        ax.set_axisbelow(True)
    return fig
