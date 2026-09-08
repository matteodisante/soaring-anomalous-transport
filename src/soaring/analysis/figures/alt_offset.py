"""The barometric-minus-GNSS offset: site-to-site scatter against the mix's own.

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
    r"""The weather's site-to-site scatter against the mix's across-flight one.

    One histogram per discipline of the per-site offset scatter
    (:func:`soaring.analysis.alt_offset.group_scatter` grouped by site alone): a site
    never mixes channels, so this is what the weather alone costs a barometric-only
    dataset. A dashed line per discipline marks the offset's scatter across the *whole*
    flight population (:func:`soaring.analysis.alt_offset.sigma_mad` of ``med_offset``,
    unrestricted by site) -- the wander mixing the two channels adds. Each line sitting
    inside its histogram's own bulk, rather than off to one side of it, is the "no more
    scatter than the weather already does" claim, drawn rather than argued.

    Args:
        site_sigma: Mapping ``discipline -> per-site sigma`` (metres), one value per
            site with enough flights to support a scale estimate.
        mix_sigma: Mapping ``discipline -> the across-flight sigma`` (metres) of the
            same offset, unrestricted by site.

    Returns:
        The Matplotlib figure (not saved).
    """
    import numpy as np
    import matplotlib.pyplot as plt

    colors = {"paragliders": "#3477a8", "hang gliders": "#b5482a"}
    fig, ax = plt.subplots(figsize=(6.4, 4.2))

    upper = max(float(np.percentile(sigma, 98)) for sigma in site_sigma.values())
    bins = np.linspace(0.0, upper, 26)

    for discipline, sigma in site_sigma.items():
        color = colors.get(discipline, "gray")
        ax.hist(
            sigma, bins=bins, color=color, alpha=0.55, density=True,
            label=f"{discipline}, per site (n={sigma.size})",
        )
        ax.axvline(
            mix_sigma[discipline], color=color, ls="--", lw=1.6,
            label=f"{discipline}, across all flights ({mix_sigma[discipline]:.0f} m)",
        )

    ax.set(
        xlabel=r"offset scatter $\sigma$ [m]",
        ylabel="density",
        title="Weather's site-to-site scatter vs. the mix's own",
    )
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    return fig
