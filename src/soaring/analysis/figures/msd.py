"""The mean-squared-displacement figure.

Draws what :mod:`soaring.analysis.observables.transport` computes. Nothing here is a
measurement: every number the caption or the body quotes comes from the estimators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

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
    """The two MSD estimators side by side, with the ensemble behind each.

    Four panels. (a) The **ensemble** MSD: the mean over flights at a fixed elapsed
    time, with the 10-90 band across flights and the median, and the fitted power law
    over its range. (b) The **time-averaged** MSD: the same displacement statistic
    averaged over starting times *within* each segment, so a lag is seen wherever it
    occurs rather than only at a fixed time since take-off. (c) The local logarithmic
    slope of both, which is what shows whether one exponent describes a curve. (d) How
    many flights, or segments, contribute at each lag.

    Reading (a) against (b) is the point of the figure rather than a bonus. The
    ensemble is synchronised at take-off -- every flight starts there -- so a feature it
    shows at a fixed elapsed time belongs to that common origin, and the time average is
    what says whether the same feature is a property of the motion. Neither is a proxy for
    the other and both are reported. On this archive the reading comes out asymmetric: (a)
    crosses over where the population leaves its launch area, so what it yields is that
    timescale rather than one exponent, while (b) is a power law over two and a half
    decades and is where the exponent is read (sec:obs-global). The gap between the two
    fitted slopes is *not* read as an aging signature, since that comparison presupposes
    two exponents and (a) does not supply one -- which constrains the form of the
    ergodicity test, not the usefulness of either estimator.

    Args:
        results: Mapping ``discipline -> MSDResult`` for the ensemble MSD.
        fits: Its fitted power laws.
        ta_results: The same for the time-averaged MSD; omit to leave (b) empty.
        ta_fits: Its fitted power laws.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    colors = {"paragliders": "#3477a8", "hang gliders": "#b5482a"}
    ta_results = ta_results or {}
    ta_fits = ta_fits or {}
    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.0))
    flat = axes.ravel()

    def draw(ax, result, fit, color, label):
        """One estimator's curve, band, median and fit on one axis."""
        ok = np.isfinite(result.msd)
        if result.p10 is not None:
            # The 10-90 band across flights, not an error on the mean: it says how broad
            # the ensemble is at each lag, the context the mean needs. Where the mean
            # leaves the band it is being carried by the tail, not by the bulk.
            band = np.isfinite(result.p10) & np.isfinite(result.p90)
            ax.fill_between(
                result.t[band],
                result.p10[band],
                result.p90[band],
                color=color,
                alpha=0.13,
                lw=0,
            )
            ax.plot(result.t[band], result.p50[band], color=color, lw=1.0, ls=":")
        ax.plot(result.t[ok], result.msd[ok], color=color, lw=1.8, label=label)
        if fit is not None:
            span = np.geomspace(fit.t_min, fit.t_max, 20)
            ax.plot(span, fit.prefactor * span**fit.alpha, color="0.2", ls="--", lw=1.1)
            ax.axvspan(fit.t_min, fit.t_max, color=color, alpha=0.05, lw=0)

    # The lags over which the ensemble is still *growing*: a flight answers a lag only
    # at or above its own native interval, so each cadence class joins the average there
    # and brings its own displacement distribution. Over the paraglider archive the
    # population more than doubles between 2 s and 120 s, and the bumps a reader sees at
    # the short-lag end sit at the common cadences rather than in the motion -- an
    # ensemble restricted to 1 Hz loggers grows by 0.6 % over the same span and is
    # smooth. It is shaded rather than hidden, and no fit begins inside it.
    def joining_region(curve):
        n = curve.n_flights
        rising = np.flatnonzero(n[1:] > n[:-1] * 1.001)
        return (curve.t[0], float(curve.t[rising.max() + 1])) if rising.size else None

    for discipline, result in results.items():
        color = colors.get(discipline, "gray")
        span = joining_region(result)
        if span is not None:
            for axis in (flat[0], flat[2]):
                axis.axvspan(*span, color="0.85", zorder=0, lw=0)
        draw(flat[0], result, fits.get(discipline), color, discipline)
        curve_slope, curve_error = local_slope(result)
        shown = np.isfinite(curve_slope)
        flat[2].fill_between(
            result.t[shown],
            (curve_slope - curve_error)[shown],
            (curve_slope + curve_error)[shown],
            color=color,
            alpha=0.18,
            lw=0,
        )
        flat[2].plot(result.t[shown], curve_slope[shown], color=color, lw=1.6)
        flat[3].plot(
            result.t[result.n_flights > 0],
            result.n_flights[result.n_flights > 0],
            color=color,
            lw=1.6,
            label=f"{discipline} (ensemble)",
        )
    for discipline, result in ta_results.items():
        color = colors.get(discipline, "gray")
        draw(flat[1], result, ta_fits.get(discipline), color, discipline)
        ta_slope, _ = local_slope(result)
        flat[2].plot(result.t, ta_slope, color=color, lw=1.2, ls="-.")
        flat[3].plot(
            result.t[result.n_flights > 0],
            result.n_flights[result.n_flights > 0],
            color=color,
            lw=1.2,
            ls="-.",
            label=f"{discipline} (segments, TA)",
        )

    def annotate(ax, fitted):
        """The fitted exponents, one line per discipline."""
        note = "\n".join(
            rf"{d}: $\alpha$ = {f.alpha:.3f} $\pm$ {f.alpha_err:.3f}"
            for d, f in fitted.items()
        )
        if note:
            ax.text(0.03, 0.97, note, transform=ax.transAxes, fontsize=8, va="top")

    annotate(flat[0], fits)
    annotate(flat[1], ta_fits)
    flat[0].plot([], [], color="0.4", lw=1.0, ls=":", label="median")
    flat[0].fill_between([], [], [], color="0.4", alpha=0.13, lw=0, label="10--90 band")
    for ax, title, ylabel in (
        (
            flat[0],
            "(a) Ensemble MSD (from take-off)",
            r"$\langle |\mathbf{r}(t)|^2\rangle$ [m$^2$]",
        ),
        (
            flat[1],
            "(b) Time-averaged MSD (within segments)",
            r"$\langle\overline{\delta^2}(t)\rangle$ [m$^2$]",
        ),
    ):
        ax.set(
            xscale="log", yscale="log", xlabel="lag $t$ [s]", ylabel=ylabel, title=title
        )
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=7, loc="lower right")

    for reference, label in ((2.0, "ballistic"), (1.0, "diffusive")):
        flat[2].axhline(reference, color="0.6", ls=":", lw=1.0)
        flat[2].text(
            0.99,
            reference,
            label,
            fontsize=7,
            color="0.4",
            ha="right",
            va="bottom",
            transform=flat[2].get_yaxis_transform(),
        )
    flat[2].plot([], [], color="0.4", lw=1.6, label="ensemble")
    flat[2].plot([], [], color="0.4", lw=1.2, ls="-.", label="time-averaged")
    flat[2].set(
        xscale="log",
        xlabel="lag $t$ [s]",
        title="(c) Local slope",
        ylabel=r"$\mathrm{d}\log\,\mathrm{MSD}/\mathrm{d}\log t$",
        ylim=(0.0, 2.6),
    )
    flat[2].grid(alpha=0.3)
    flat[2].legend(fontsize=7, loc="lower left")

    flat[3].set(
        xscale="log",
        yscale="log",
        xlabel="lag $t$ [s]",
        ylabel="curves contributing",
        title="(d) Ensemble size vs lag",
    )
    flat[3].grid(alpha=0.3, which="both")
    flat[3].legend(fontsize=7, loc="lower left")

    fig.tight_layout()
    return fig
