"""The time-averaged MSD, stratified by how long the flight lasted.

The ergodicity question Chapter 3 hands on (Sec. sec:obs-global, App. app:ctrw) is
whether the time-averaged MSD depends on the total duration of the record it is read
from. For the CTRW with power-law waiting times, App. app:ctrw derives
:math:`\\mathrm{TAMSD}(t,T) \\sim K_\\alpha\\,T^{\\alpha-1}\\,t`: a *T*-dependent
prefactor is the aging signature, present however the estimator is read, and absent for
an ergodic process whose TA-MSD collapses onto one curve regardless of how long the
record was. Nothing here assumes the archive is a CTRW of that kind -- it plainly is not,
being super-diffusive rather than sub-diffusive -- only that the same question (does the
curve move with *T*?) is asked of it directly, on the same segments the pooled TA-MSD of
Fig. fig:msd already uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from ..observables.transport import MSDResult


def make_msd_duration_figure(
    pooled: dict[str, MSDResult],
    cohorts: dict[str, dict[float, MSDResult]],
    thresholds_s: tuple[float, ...],
    ergodicity: dict[str, dict] | None = None,
) -> Figure:
    """The pooled TA-MSD against its own fixed-duration cohorts, and the direct test.

    Top row: each cohort curve cut at half its own threshold, since a segment of length
    at least :math:`T` answers a lag only up to :math:`T/2` before the population inside
    that cohort starts thinning again. Curves that coincide say the time average does not
    depend on how long the record was; curves that separate say it does. On this archive
    the separation is real but modest -- tens of per cent -- and a log--log panel spanning
    the whole record hides exactly that size of effect: two curves 40 % apart sit 0.15
    decades apart on an axis covering eight, which is why the bottom row exists.

    Bottom row: the ergodicity-breaking parameter, App. app:ctrw's own quantity, measured
    directly on the archive's flights rather than proxied by a duration split (see
    :func:`~scripts.reporting.ch3_global_transport.generate_msd_duration_figure.
    ergodicity_breaking`), at one lag held fixed and swept over the duration threshold T --
    the T dependence is the question App. app:ctrw poses, not the lag dependence. A dashed
    line at zero marks the ergodic limit the CTRW model tends to only as
    :math:`\\alpha\\to1`; a value that sits above it and does not fall towards it as T
    grows is the aging signature read off the archive's own scatter across flights, not
    off a fitted slope.

    Args:
        pooled: Mapping ``discipline -> MSDResult`` for the pooled time-averaged MSD.
        cohorts: Mapping ``discipline -> {threshold_s -> MSDResult}`` for the
            fixed-duration cohorts.
        thresholds_s: The cohort thresholds, in seconds, in the order to draw and label
            them.
        ergodicity: Mapping ``discipline -> {"thresholds_s", "eb", "n_flights", "lag_s"}``,
            or ``None`` / missing a discipline to draw the top row alone for it.

    Returns:
        The Matplotlib figure (not saved).
    """
    import numpy as np
    import matplotlib.pyplot as plt

    colors = {"paragliders": "#3477a8", "hang gliders": "#b5482a"}
    styles = ["-", "--", "-.", ":"]
    ergodicity = ergodicity or {}

    disciplines = [d for d in pooled if d in cohorts]
    has_ergo = any(d in ergodicity for d in disciplines)
    n_rows = 2 if has_ergo else 1
    fig, axes = plt.subplots(
        n_rows, len(disciplines), figsize=(5.7 * len(disciplines), 4.6 * n_rows), squeeze=False
    )

    for col, discipline in enumerate(disciplines):
        color = colors.get(discipline, "gray")
        ax = axes[0, col]
        result = pooled[discipline]
        ok = np.isfinite(result.msd)
        ax.plot(
            result.t[ok],
            result.msd[ok],
            color=color,
            lw=2.2,
            label="all segments",
            zorder=3,
        )
        for threshold, style in zip(thresholds_s, styles[1:]):
            curve = cohorts[discipline].get(threshold)
            if curve is None:
                continue
            keep = np.isfinite(curve.msd) & (curve.t <= threshold / 2.0)
            if not keep.any():
                continue
            ax.plot(
                curve.t[keep],
                curve.msd[keep],
                color=color,
                lw=1.4,
                ls=style,
                alpha=0.85,
                label=rf"$\geq${threshold / 3600:.0f} h",
            )
        ax.set(
            xscale="log",
            yscale="log",
            xlabel="lag $t$ [s]",
            ylabel=r"$\langle\overline{\delta^2}(t)\rangle$ [m$^2$]",
            title=discipline,
        )
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=8, loc="lower right", title="flight duration")

        if has_ergo:
            eb_ax = axes[1, col]
            ergo = ergodicity.get(discipline)
            if ergo is not None:
                thresholds_h = np.asarray(ergo["thresholds_s"]) / 3600.0
                eb = np.asarray(ergo["eb"])
                good = np.isfinite(eb)
                eb_ax.plot(thresholds_h[good], eb[good], "o-", color=color, ms=4, lw=1.4)
                eb_ax.axhline(0.0, color="0.4", lw=0.8, ls="--")
                eb_ax.set_title(rf"$t=${ergo['lag_s']:.0f} s", fontsize=9)
            eb_ax.set(
                xlabel="duration threshold $T$ [h]",
                ylabel=r"$\mathrm{EB}(T)=\mathrm{Var}_f/\mathrm{Mean}_f^2$",
            )
            eb_ax.grid(alpha=0.3, which="both")

    fig.tight_layout()
    return fig
