"""The pre-processing diagnostic figures.

Drawing is kept out of the modules that compute, so that a change to a panel cannot touch
an estimator and a module can be imported without pulling in Matplotlib. The numbers these
draw come from :mod:`soaring.analysis.census`; nothing here computes a statistic that the
thesis quotes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

_DISC_COLOR = {
    "paragliders": "#3477a8",
    "hang gliders": "#b5482a",
    "sailplanes": "#3d8c54",
}

from ..census import _FIXLEVEL_QUANTITIES, fraction_retained, retention_curve
from ..config import load_preproc_config

if TYPE_CHECKING:
    from matplotlib.figure import Figure


def make_flightlevel_diagnostics_figure(
    scans: dict[str, pd.DataFrame], flight_level: FlightLevelThresholds
) -> Figure:
    """Flight-level filtering diagnostics, per discipline, from full-census track data.

    Six panels, each overlaying every discipline. Top row, the distribution of the
    quantity each of the three track criteria cuts on: (a) recorded flight duration,
    (b) total flown path length, (c) whole-flight barometric altitude range, with the
    adopted cut marked. Bottom row, (d)/(e)/(f) the fraction of flights retained versus
    that cut, computed for **that cut alone** (marginal, not cascaded), so each curve
    isolates the effect of one criterion.

    The altitude-range panels need no extra scan: the range is
    ``baro_alt_max_m - baro_alt_min_m``, both already columns of the cached census.

    Args:
        scans: Mapping ``discipline -> per-flight table`` (``duration_s``, ``path_km``,
            ``baro_alt_min_m``, ``baro_alt_max_m``), each a full census
            (:func:`scan_tracks` over every track).
        flight_level: The adopted thresholds to mark.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(2, 3, figsize=(13.2, 6.8))

    dur_grid = np.linspace(5.0, 150.0, 80)  # minutes
    path_grid = np.logspace(np.log10(1.0), np.log10(500.0), 80)  # km
    alt_grid = np.logspace(np.log10(5.0), np.log10(5000.0), 80)  # m

    for disc, s in scans.items():
        color = _DISC_COLOR.get(disc, "gray")
        dur_h = pd.to_numeric(s["duration_s"], errors="coerce") / 3600.0
        dur_h = dur_h[dur_h > 0]
        path = pd.to_numeric(s["path_km"], errors="coerce")
        path = path[path > 0]
        # Restricted to flights that actually adopt the barometric channel. The scan
        # stores only the barometric extremes, so a GNSS-fallback flight reads a
        # range of zero here whatever its real altitude activity: pooling the two
        # would put ~30 % of paragliders at the bottom of the distribution for a
        # reason that has nothing to do with how they flew. Auditing the cut on the
        # fallback minority needs the GNSS extremes in the scan, i.e. a full rescan
        # (thesis, sec:flightfilter).
        present = pd.to_numeric(s["baro_present_frac"], errors="coerce")
        has_baro = present >= BARO_PRESENT_MIN
        alt_range = pd.to_numeric(s["baro_alt_max_m"], errors="coerce") - pd.to_numeric(
            s["baro_alt_min_m"], errors="coerce"
        )
        alt_range = alt_range[has_baro & (alt_range > 0)]

        axes[0, 0].hist(
            dur_h[dur_h <= 12],
            bins=np.linspace(0, 12, 70),
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[0, 1].hist(
            path,
            bins=np.logspace(np.log10(0.5), np.log10(1000), 70),
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[0, 2].hist(
            alt_range,
            bins=np.logspace(np.log10(1.0), np.log10(10000), 70),
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[1, 0].plot(
            dur_grid,
            100.0 * retention_curve(dur_h * 60.0, dur_grid)[1],
            color=color,
            lw=1.6,
            label=disc,
        )
        axes[1, 1].plot(
            path_grid,
            100.0 * retention_curve(path, path_grid)[1],
            color=color,
            lw=1.6,
            label=disc,
        )
        axes[1, 2].plot(
            alt_grid,
            100.0 * retention_curve(alt_range, alt_grid)[1],
            color=color,
            lw=1.6,
            label=disc,
        )

    axes[0, 0].axvline(flight_level.min_duration_s / 3600.0, **line_kw)
    axes[0, 0].set(
        xlabel="recorded flight duration [h]",
        ylabel="density",
        title="(a) Duration",
        xlim=(0, 12),
    )
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].axvline(flight_level.min_path_km, **line_kw)
    axes[0, 1].set(
        xlabel="flown path length [km]",
        ylabel="density",
        title="(b) Path length",
        xscale="log",
    )

    axes[0, 2].axvline(flight_level.min_alt_range_m, **line_kw)
    axes[0, 2].set(
        xlabel="whole-flight altitude range [m]",
        ylabel="density",
        title="(c) Altitude activity",
        xscale="log",
    )

    axes[1, 0].axvline(flight_level.min_duration_s / 60.0, **line_kw)
    axes[1, 0].set(
        xlabel=r"minimum duration $T_{\min}$ [min]",
        ylabel="flights retained [%]",
        title="(d) Retention vs duration cut (this cut alone)",
    )
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].axvline(flight_level.min_path_km, **line_kw)
    axes[1, 1].set(
        xlabel="minimum path length [km]",
        ylabel="flights retained [%]",
        title="(e) Retention vs path cut (this cut alone)",
        xscale="log",
    )
    axes[1, 1].grid(alpha=0.3)

    axes[1, 2].axvline(flight_level.min_alt_range_m, **line_kw)
    axes[1, 2].set(
        xlabel="minimum altitude range [m]",
        ylabel="flights retained [%]",
        title="(f) Retention vs altitude-range cut (this cut alone)",
        xscale="log",
    )
    axes[1, 2].grid(alpha=0.3)

    fig.tight_layout()
    return fig


def make_gap_diagnostics_figure(
    scans: dict[str, pd.DataFrame], sampling: SamplingThresholds
) -> Figure:
    """Sampling-regularity diagnostics: how the gap-based exclusion would act.

    Mirrors :func:`make_flightlevel_diagnostics_figure`. Two panels overlay every
    discipline's distribution -- (a) the largest single gap **in units of that
    flight's own effective split bound** ``g_max``, and (b) the fraction of a
    uniform grid at the native interval left uncovered (see :func:`track_stats`) --
    and two show the marginal retention curve for each cut alone, with the adopted
    threshold marked.

    Panel (a) is normalised by ``g_max``, not by ``dt``, on purpose. The bound
    actually applied is ``min(max_gap_factor * dt, max(max_gap_seconds, 2 * dt))``,
    which is not a fixed multiple of ``dt``: at 1 s the relative term binds, from 2
    s to 10 s the absolute cap does, above that the ``2 * dt`` floor. Plotting ``gap
    / dt`` against a line at ``max_gap_factor`` would therefore draw a cut that is
    not the one in force for most cadences. Dividing each flight's gap by its own
    ``g_max`` puts the true criterion at exactly 1 for every flight.

    Args:
        scans: Mapping ``discipline -> per-flight table`` with ``max_gap_ratio``,
            ``dt_s`` and ``missing_fraction`` (:func:`scan_tracks` over every track).
        sampling: The adopted thresholds to mark.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 6.8))

    # Clean per-discipline series once.
    gaps: dict[str, np.ndarray] = {}
    misses: dict[str, np.ndarray] = {}
    for disc, s in scans.items():
        ratio = pd.to_numeric(s["max_gap_ratio"], errors="coerce")
        dt = pd.to_numeric(s["dt_s"], errors="coerce")
        # Each flight's own effective bound, then the gap in units of it: the cut is
        # then at 1 for every flight whatever its cadence (see the docstring). The
        # bound comes from the stage that applies it, so the figure cannot draw a cut
        # the pipeline does not make.
        g_max = split_bound_s(dt, sampling)
        g = (ratio * dt) / g_max
        ok = np.isfinite(g) & (g > 0) & np.isfinite(dt) & (dt > 0)
        gaps[disc] = g[ok].to_numpy()
        m = pd.to_numeric(s["missing_fraction"], errors="coerce")
        misses[disc] = m[np.isfinite(m)].to_numpy()

    # Distribution panels (a)/(b): fit the x-range to where the mass and the cut are,
    # not a fixed constant, so it adapts to any dataset. These quantities have a very
    # heavy tail (a few flights with a huge relative gap), so a high percentile would
    # stretch the axis far past the bulk. We take the bulk (90th percentile) but keep a
    # margin past the adopted cut so it stays in view; the heavy tail is not lost, the
    # retention panels (c)/(d) sweep the whole range.
    pooled_gap = np.concatenate(
        [g for g in gaps.values() if g.size] or [np.array([1.0])]
    )
    pooled_miss = np.concatenate(
        [m for m in misses.values() if m.size] or [np.array([0.0])]
    )
    gap_hi = float(max(np.quantile(pooled_gap, 0.90), 2.0))
    # Only a little past the cut (not 2x): the 90th percentile already sits almost
    # exactly at the cut, so a wider margin would just add empty axis past it.
    miss_hi = float(
        max(np.quantile(pooled_miss, 0.90), sampling.max_missing_fraction * 1.1)
    )
    # Linear, not log: panel (a) only shows the bulk (up to gap_hi, a modest ~1-20
    # here), and unlike the retention curve below it does not need to span orders of
    # magnitude. A log-spaced grid would also make the bins vary widely in width,
    # which is a bad match for a quantity whose common values sit at small integers
    # (a gap of exactly k missed native-rate fixes).
    gap_bins = np.linspace(0.0, gap_hi, 50)
    miss_bins = np.linspace(0.0, miss_hi, 50)

    # Retention curves (c)/(d) sweep a wide range to show the full saturating shape.
    gap_grid = np.logspace(-1.0, np.log10(max(20.0, gap_hi)), 80)  # in units of g_max
    miss_grid = np.linspace(0.0, max(0.6, miss_hi), 80)  # fraction

    for disc in scans:
        color = _DISC_COLOR.get(disc, "gray")
        axes[0, 0].hist(
            gaps[disc],
            bins=gap_bins,
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[0, 1].hist(
            misses[disc],
            bins=miss_bins,
            density=True,
            histtype="step",
            lw=1.5,
            color=color,
            label=disc,
        )
        axes[1, 0].plot(
            gap_grid,
            100.0 * retention_curve(gaps[disc], gap_grid, mode="at_most")[1],
            color=color,
            lw=1.6,
            label=disc,
        )
        axes[1, 1].plot(
            miss_grid,
            100.0 * retention_curve(misses[disc], miss_grid, mode="at_most")[1],
            color=color,
            lw=1.6,
            label=disc,
        )

    axes[0, 0].axvline(1.0, **line_kw)
    axes[0, 0].set(
        xlabel=r"largest gap / this flight's $g_{\max}$",
        ylabel="density",
        title="(a) Largest gap (in units of the split bound)",
        xlim=(0.0, gap_hi),
    )
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].axvline(sampling.max_missing_fraction, **line_kw)
    axes[0, 1].set(
        xlabel="missing fraction of the uniform grid",
        ylabel="density",
        title="(b) Missing fraction",
        xlim=(0.0, miss_hi),
    )

    axes[1, 0].axvline(1.0, **line_kw)
    axes[1, 0].set(
        xlabel=r"cut on largest gap, in units of $g_{\max}$",
        ylabel="flights retained [%]",
        title="(c) Retention vs gap cut (this cut alone)",
        xscale="log",
    )
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].axvline(sampling.max_missing_fraction, **line_kw)
    axes[1, 1].set(
        xlabel="cut on missing fraction",
        ylabel="flights retained [%]",
        title="(d) Retention vs missing-fraction cut (this cut alone)",
    )
    axes[1, 1].grid(alpha=0.3)

    fig.tight_layout()
    return fig


def make_sampling_figure(scans: dict[str, pd.DataFrame]) -> Figure:
    """Native sampling-interval distribution per discipline (full-census track data).

    The native interval (the flight's own median inter-fix time) is, in practice, a
    *discrete* quantity, not a continuous one: checked on the full census, it lands on
    an exact whole second for 99.9% of paragliders and 100% of hang gliders (a
    logger reports at one of a handful of fixed configured rates; the rare
    non-integer values are single flights with genuinely mixed cadence). The bins are
    therefore one full second wide, centred on each integer, so each bar reads as
    "the fraction of flights at exactly this rate" rather than as an arbitrary,
    sub-integer slice of a smooth curve the data does not have. With unit-width bins,
    ``density=True`` (kept for symmetry with the other diagnostics) is numerically the
    same thing as that fraction, since dividing by a bin width of 1 changes nothing --
    the axis is labelled accordingly.

    Args:
        scans: Mapping ``discipline -> per-flight table`` with a ``dt_s`` column.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    upper = 11  # aggregates the long, thin tail beyond it (up to a few tens of
    # seconds for a handful of flights) into one bin, rather than stretching the axis
    bins = np.arange(0.5, upper + 1.5, 1.0)
    for disc, s in scans.items():
        dt = pd.to_numeric(s["dt_s"], errors="coerce")
        dt = dt[(dt > 0) & np.isfinite(dt)]
        ax.hist(
            dt.clip(upper=upper),
            # matplotlib's stub omits the array-of-edges form of `bins`.
            bins=bins,  # type: ignore[arg-type]
            density=True,
            histtype="step",
            lw=1.5,
            color=_DISC_COLOR.get(disc, "gray"),
            label=disc,
        )
    ax.set_xticks(range(1, upper + 1))
    ax.set_xticklabels([str(i) for i in range(1, upper)] + [f"$\\geq${upper}"])
    ax.set_xlabel(r"native sampling interval $\Delta t$ [s]")
    ax.set_ylabel("fraction of flights")
    ax.set_title("Native sampling interval, per flight")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def make_fixlevel_diagnostics_figure(
    distributions: dict[str, dict[str, np.ndarray]], fix_level: FixLevelThresholds
) -> Figure:
    """Fix-level cleaning diagnostics: the per-fix distributions the bounds act on.

    Three panels, each overlaying every discipline, for the quantities the fix-level
    cuts test between/at consecutive fixes: (a) horizontal speed ``v_xy``, (b)
    barometric vertical speed ``|v_z|``, (c) barometric altitude. Unlike the
    flight-level figure these are distributions over individual *fixes*, not per-flight
    summaries: a bound removes only the few offending fixes of an otherwise good
    flight, so what justifies it is that it sits in the physically-implausible tail
    (a GPS error, not signal) and removes a negligible fraction of fixes, annotated on
    each panel. The y-axis is logarithmic so that tail, where the cuts act, is visible.
    Panel (a) marks one cut *per discipline*, colour-matched to that discipline's
    histogram (horizontal-speed envelopes differ too much between paragliders and hang
    gliders for one shared bound); panels (b)/(c) mark one shared cut/band instead,
    since neither the vertical-speed nor the altitude bounds are meant to track a
    discipline-specific performance limit.

    Args:
        distributions: Mapping ``discipline -> {quantity -> per-fix values}`` from
            :func:`fix_level_distributions`.
        fix_level: The adopted bounds to mark.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    shared_line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.7))

    def _hist_panel(
        ax, key, xlabel, title, *, all_cut_values, wide_tail, integer_aligned=False
    ):
        # x-range fitted to the data and extended to keep every cut in view. Two
        # regimes: the per-discipline speed panels default to a WIDE tail (see
        # _per_discipline_panel) -- the 99.9th percentile of the pooled sample sits
        # right at the cut by construction (that is where the cuts were chosen), so it
        # would crop the view almost exactly at the line, hiding how much, and what, is
        # left out. The shared-band panel (altitude) keeps the narrower, original
        # calculation instead: its cuts sit far out in an otherwise tight, unimodal
        # distribution, and widening it the same way mostly shrinks the informative
        # part of the panel to make room for a rare secondary population already
        # visible at the narrower range.
        per_disc = [
            d[key] for d in distributions.values() if d.get(key, np.empty(0)).size
        ]
        pooled = np.concatenate(per_disc or [np.array([0.0])])
        lo = min(float(np.quantile(pooled, 0.001)), *all_cut_values)
        if wide_tail:
            tail_hi = max(
                (float(np.quantile(v, 0.9999)) for v in per_disc), default=0.0
            )
            hi = max(tail_hi, *(c * 1.8 for c in all_cut_values))
        else:
            hi = max(
                float(np.quantile(pooled, 0.999)), *(c * 1.05 for c in all_cut_values)
            )
        span = (hi - lo) or 1.0
        lo, hi = lo - 0.02 * span, hi + 0.02 * span
        if integer_aligned:
            # The underlying quantity is itself quantised to whole units (barometric
            # vertical speed, from an integer-metre altitude log): a fine, arbitrarily
            # placed grid of bins picks up an inconsistent share of each integer's
            # spike depending on where the bin edges happen to fall relative to it,
            # which reads as random-looking noise rather than the smooth envelope the
            # data actually has. One bin per integer -- centred on it, not edged on it
            # -- removes that artefact instead of just resampling it differently.
            bins = np.arange(np.floor(lo) - 0.5, np.ceil(hi) + 1.5, 1.0)
        else:
            bins = np.linspace(lo, hi, 60)
        for disc, d in distributions.items():
            v = d.get(key, np.empty(0))
            if v.size:
                ax.hist(
                    v,
                    bins=bins,
                    density=True,
                    histtype="step",
                    lw=1.5,
                    color=_DISC_COLOR.get(disc, "gray"),
                    label=disc,
                )
        ax.set(
            xlabel=xlabel, ylabel="density", title=title, yscale="log", xlim=(lo, hi)
        )
        return pooled

    def _per_discipline_panel(
        ax, key, cuts_by_disc, xlabel, title, *, integer_aligned=False
    ):
        """One upper cut per discipline, colour-matched, each with its own fraction."""
        _hist_panel(
            ax,
            key,
            xlabel,
            title,
            all_cut_values=cuts_by_disc.values(),
            wide_tail=True,
            integer_aligned=integer_aligned,
        )
        for i, (disc, cut) in enumerate(cuts_by_disc.items()):
            color = _DISC_COLOR.get(disc, "gray")
            ax.axvline(cut, color=color, ls="--", lw=1.2)
            v = distributions.get(disc, {}).get(key, np.empty(0))
            frac = float(np.mean(v > cut)) * 100.0 if v.size else float("nan")
            ax.text(
                0.97,
                0.95 - 0.09 * i,
                f"{disc}: cut removes {frac:.2g}%",
                transform=ax.transAxes,
                fontsize=7.5,
                ha="right",
                va="top",
                color=color,
            )

    def _shared_cut_panel(
        ax, key, cuts, xlabel, title, *, wide_tail, integer_aligned=False
    ):
        """One shared cut/band, the same for every discipline.

        E.g. vertical speed (one upper-bound cut) or altitude (a lower+upper band).
        """
        pooled = _hist_panel(
            ax,
            key,
            xlabel,
            title,
            all_cut_values=cuts,
            wide_tail=wide_tail,
            integer_aligned=integer_aligned,
        )
        for c in cuts:
            ax.axvline(c, **shared_line_kw)
        if len(cuts) == 1:
            frac = float(np.mean(pooled > cuts[0])) * 100.0
            note = f"cut removes {frac:.2g}% of fixes"
        else:
            frac = float(np.mean((pooled < cuts[0]) | (pooled > cuts[1]))) * 100.0
            note = f"band removes {frac:.2g}% of fixes"
        ax.text(
            0.97,
            0.95,
            note,
            transform=ax.transAxes,
            fontsize=7.5,
            ha="right",
            va="top",
            color="0.25",
        )

    _per_discipline_panel(
        axes[0],
        "v_xy",
        fix_level.max_horizontal_speed_mps,
        r"horizontal speed $v_{xy}$ [m/s]",
        "(a) Horizontal speed",
    )
    axes[0].legend(fontsize=8)
    _shared_cut_panel(
        axes[1],
        "v_z",
        (fix_level.max_vertical_speed_mps,),
        r"barometric $|v_z|$ [m/s]",
        "(b) Vertical speed",
        wide_tail=True,
        integer_aligned=True,
    )
    _shared_cut_panel(
        axes[2],
        "altitude",
        (fix_level.min_altitude_m, fix_level.max_altitude_m),
        "barometric altitude [m]",
        "(c) Altitude",
        wide_tail=False,
    )
    fig.tight_layout()
    return fig
