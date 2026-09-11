"""Compare within-site and pooled scatter of barometric-minus-GNSS offsets.

Draws what :mod:`soaring.analysis.alt_offset` measures. Nothing here is a measurement:
every number the caption or the body quotes comes from the estimators there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from matplotlib.figure import Figure


def make_alt_offset_figure(
    site_sigma: dict[str, "np.ndarray"], mix_sigma: dict[str, float]
) -> Figure:
    r"""Distribution of within-site offset scales, with the pooled scale as reference.

    Each site contributes one Gaussian-scaled MAD to the histogram. Dashed lines show
    the same scale statistic over all eligible flight offsets in each discipline.
    Site grouping does not isolate weather, and a difference between these statistics
    is not an additive variance decomposition or an effect of mixing altitude channels.

    Args:
        site_sigma: Mapping ``discipline -> per-site sigma`` (metres), one value per
            site with enough flights to support a scale estimate.
        mix_sigma: Mapping ``discipline -> the across-flight sigma`` (metres) of the
            same offset, unrestricted by site.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt
    import numpy as np

    from soaring.reporting.style import DISCIPLINE_COLORS, TEXT_WIDTH_IN, paper_style

    paper_style()
    colors = DISCIPLINE_COLORS
    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 3.5), layout="constrained")

    upper = max(float(np.max(sigma)) for sigma in site_sigma.values())
    bins = np.linspace(0.0, max(upper, 1.0), 26)

    for discipline, sigma in site_sigma.items():
        color = colors.get(discipline, "gray")
        ax.hist(
            sigma,
            bins=bins,
            color=color,
            histtype="step",
            linewidth=1.1,
            density=True,
            label=f"{discipline}, per site (n={sigma.size})",
        )
        ax.axvline(
            mix_sigma[discipline],
            color=color,
            ls="--",
            lw=1.1,
            label=f"{discipline}, across all flights ({mix_sigma[discipline]:.0f} m)",
        )

    ax.set(
        xlabel="Scaled MAD of altitude offset (m)",
        ylabel=r"Density (m$^{-1}$)",
        title="Within-site and pooled offset scatter",
    )
    ax.grid(False)
    ax.legend(fontsize=8, loc="upper right")
    return fig
