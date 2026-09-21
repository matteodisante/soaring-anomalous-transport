"""Draw what the ground-phase trimming rule spends and how often it cuts mid-flight.

Both figures read :mod:`soaring.analysis.trim_census`'s per-flight scan, and neither
is a measurement of its own: every number the caption quotes is a column of that scan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from soaring.reporting.style import DISCIPLINE_COLORS, paper_style

if TYPE_CHECKING:
    import pandas as pd
    from matplotlib.figure import Figure

_DISC_COLOR = DISCIPLINE_COLORS


def make_trim_split_figure(scans: dict[str, pd.DataFrame]) -> Figure:
    r"""Distributions of the takeoff-trimmed and landing-trimmed durations, per flight.

    Two panels, one discipline overlay each: (a) the time cut from the start of the
    record up to the estimated onset :math:`t_{\mathrm{on}}`, (b) the time cut from
    the estimated end :math:`t_{\mathrm{off}}` to the end of the record. Both are a
    consequence of the same rule (thesis, eq:trimming, sec:trimming): a receiver
    logging before the sustained fast stretch begins, or after it ends. Neither
    duration is bounded by ``T0``, only by how long the record ran before/after the
    airborne window; some of that mass is a receiver switched on well before rigging
    up, not the persistence window itself.

    Args:
        scans: Mapping ``discipline -> per-flight table``
            (:func:`soaring.analysis.trim_census.scan_trim_split`), columns
            ``takeoff_trimmed_s`` / ``landing_trimmed_s``.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    paper_style()
    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.0), layout="constrained")

    edges = np.logspace(0, np.log10(6 * 3600), 70)  # 1 s to 6 h
    for disc, s in scans.items():
        color = _DISC_COLOR.get(disc, "gray")
        for ax, col in ((axes[0], "takeoff_trimmed_s"), (axes[1], "landing_trimmed_s")):
            values = s[col].to_numpy(dtype=float)
            values = values[np.isfinite(values) & (values > 0)]
            counts, _ = np.histogram(values, bins=edges)
            ax.stairs(
                counts / max(values.size, 1) / np.diff(edges),
                edges,
                color=color,
                lw=1.5,
                label=f"{disc.capitalize()} (n={s.shape[0]})",
            )
            median = float(np.median(s[col].to_numpy(dtype=float)))
            ax.axvline(median, color=color, ls=":", lw=1.1)

    axes[0].set(
        xlabel="Time cut before onset [s]",
        ylabel="Density",
        title="(a) Takeoff-trimmed duration",
        xscale="log",
    )
    axes[0].legend(fontsize=7, loc="upper left")
    axes[1].set(
        xlabel="Time cut after end [s]",
        title="(b) Landing-trimmed duration",
        xscale="log",
    )
    for ax in axes:
        ax.grid(visible=True, which="major", color=".9", lw=0.5)
    return fig


def make_interior_excision_figure(scans: dict[str, pd.DataFrame]) -> Figure:
    """Discrete distribution of interior ground stints excised per flight.

    One log-scale bar panel per discipline: how many flights had 0, 1, 2, ... interior
    ground stints cut by the flatness-and-witness rule of sec:trimming. Log scaling on
    the flight count, not on the excision count, which stays a small integer: the
    population is overwhelmingly at zero, so a linear axis would draw every non-zero
    bar at the resolution of the page's ink.

    Args:
        scans: Mapping ``discipline -> per-flight table``, column
            ``n_interior_excised``.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    paper_style()
    fig, axes = plt.subplots(1, len(scans), figsize=(6.1, 2.8), layout="constrained")
    if len(scans) == 1:
        axes = [axes]

    for ax, (disc, s) in zip(axes, scans.items(), strict=True):
        color = _DISC_COLOR.get(disc, "gray")
        counts = s["n_interior_excised"].to_numpy(dtype=int)
        values, tally = np.unique(counts, return_counts=True)
        ax.bar(values, tally, color=color, width=0.7)
        for v, c in zip(values, tally, strict=True):
            ax.annotate(
                f"{c}",
                (v, c),
                textcoords="offset points",
                xytext=(0, 3),
                ha="center",
                fontsize=7,
            )
        ax.set(
            xlabel="Interior stints excised",
            ylabel="Flights" if ax is axes[0] else None,
            title=disc.capitalize(),
            yscale="log",
            xticks=values,
        )
        ax.set_ylim(top=tally.max() * 3)
        ax.grid(visible=True, which="major", axis="y", color=".9", lw=0.5)
    return fig


def make_takeoff_alt_shift_figure(scans: dict[str, pd.DataFrame]) -> Figure:
    r"""Size of the altitude jump the ground-phase trimming makes at the start, per flight.

    One histogram per discipline of :math:`|z_{\mathrm{trim}}-z_{\mathrm{raw}}|`: the
    absolute difference between the GNSS altitude of the first fix of the trimmed track
    and that of the first fix of the raw log (thesis, sec:trimming). The first is the
    launch altitude :math:`z_0` that sec:conditional-orography classifies flights by,
    so this is the error made by taking the start of the trimmed track for the start of
    the log. Bins are logarithmic in whole metres and the height is the fraction of flights per
    decade; differences of 0 m and 1 m share the first bin.

    Args:
        scans: Mapping ``discipline -> per-flight table``, column
            ``takeoff_alt_shift_m``.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    paper_style()
    fig, ax = plt.subplots(figsize=(6.1, 3.0), layout="constrained")

    # Altitudes are logged in whole metres, so logarithmic edges are rounded to
    # integers: sub-metre bins would stay empty and the small-value bars would flicker.
    edges = np.unique(np.round(np.logspace(0, np.log10(5000.0), 36)))
    for disc, s in scans.items():
        color = _DISC_COLOR.get(disc, "gray")
        values = np.abs(s["takeoff_alt_shift_m"].to_numpy(dtype=float))
        values = values[np.isfinite(values)]
        counts, _ = np.histogram(np.clip(values, edges[0], edges[-1]), bins=edges)
        ax.stairs(
            counts / max(values.size, 1) / np.diff(np.log10(edges)),
            edges,
            color=color,
            lw=1.5,
            label=f"{disc.capitalize()} (n={values.size})",
        )
        ax.axvline(float(np.median(values)), color=color, ls=":", lw=1.1)

    ax.set(
        xlabel=r"$|z_{\mathrm{trim}}-z_{\mathrm{raw}}|$ [m]",
        ylabel="Fraction of flights per decade",
        xscale="log",
        yscale="log",
    )
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(visible=True, which="major", color=".9", lw=0.5)
    return fig
