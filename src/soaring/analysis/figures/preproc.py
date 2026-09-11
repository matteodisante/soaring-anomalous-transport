"""The pre-processing diagnostic figures.

Drawing is separate from estimation, so panel changes do not alter estimators.
The displayed data come from :mod:`soaring.analysis.census`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from soaring.reporting.style import DISCIPLINE_COLORS, SAILPLANE_COLOR, paper_style

from ..census import retention_curve
from ..preproc.resample import split_bound_s

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from ..config import (
        AltChannelThresholds,
        FixLevelThresholds,
        FlightLevelThresholds,
        SamplingThresholds,
    )

_DISC_COLOR = {**DISCIPLINE_COLORS, "sailplanes": SAILPLANE_COLOR}


def make_flightlevel_diagnostics_figure(
    scans: dict[str, pd.DataFrame],
    flight_level: FlightLevelThresholds,
    alt_channel: AltChannelThresholds,
) -> Figure:
    """Flight-level filtering diagnostics, per discipline, from full-census track data.

    Six panels, each overlaying every discipline. Left column: distributions of the
    three raw-track diagnostic quantities: (a) recorded flight duration,
    (c) total flown path length, (e) whole-flight altitude range on the adopted
    channel, with the adopted cut marked. Right column, (b)/(d)/(f) the fraction of
    flights retained versus that cut, computed for **that cut alone** (marginal, not
    cascaded), so each curve isolates the effect of one criterion.

    The altitude-range panels need no extra scan: the range is
    ``gnss_alt_max_m - gnss_alt_min_m``, both already columns of the cached census.

    They describe the **whole population**, which they could not do before. The panels
    used to be restricted to flights carrying a barometer, because the scan stored only
    the barometric extremes and a GNSS-derived flight therefore read a range of zero
    whatever its real altitude activity -- putting some 30 % of paragliders at the
    bottom of the distribution for a reason that had nothing to do with how they flew.
    The scan now carries both channels, so the panel describes the cut on the channel
    the cut actually acts on, over every flight (thesis, sec:flightfilter).

    Args:
        scans: Mapping ``discipline -> per-flight table`` (``duration_s``, ``path_km``,
            ``gnss_alt_min_m``, ``gnss_alt_max_m``), each a full census
            (:func:`scan_tracks` over every track).
        flight_level: The adopted thresholds to mark.
        alt_channel: The altitude-channel thresholds, for the presence gate that decides
            which flights have an adopted channel to describe at all.

    Returns:
        The Matplotlib figure (not saved).
    """
    import matplotlib.pyplot as plt

    paper_style()

    line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, grid = plt.subplots(3, 2, figsize=(6.1, 7.4), layout="constrained")
    axes = grid.T

    dur_grid = np.linspace(5.0, 150.0, 80)  # minutes
    path_grid = np.logspace(np.log10(1.0), np.log10(500.0), 80)  # km
    alt_grid = np.logspace(np.log10(5.0), np.log10(5000.0), 80)  # m

    for disc, s in scans.items():
        color = _DISC_COLOR.get(disc, "gray")
        dur_h = pd.to_numeric(s["duration_s"], errors="coerce") / 3600.0
        dur_h = dur_h[dur_h > 0]
        path = pd.to_numeric(s["path_km"], errors="coerce")
        path = path[path > 0]
        # On the adopted channel, over every flight that has one. A flight whose GNSS
        # altitude is absent is dropped by the channel gate before this cut is ever
        # reached (sec:altchannel), so it does not belong in the distribution the cut is
        # read off either.
        present = pd.to_numeric(s["gnss_present_frac"], errors="coerce")
        has_alt = present >= alt_channel.gnss_present_min
        alt_range = pd.to_numeric(s["gnss_alt_max_m"], errors="coerce") - pd.to_numeric(
            s["gnss_alt_min_m"], errors="coerce"
        )
        alt_range = alt_range[has_alt & (alt_range > 0)]

        for ax, values, edges in (
            (axes[0, 0], dur_h, np.linspace(0, 12, 70)),
            (axes[0, 1], path, np.logspace(np.log10(0.5), np.log10(1000), 70)),
            (axes[0, 2], alt_range, np.logspace(0, 4, 70)),
        ):
            values = np.asarray(values, dtype=float)
            values = values[np.isfinite(values)]
            counts, _ = np.histogram(values, bins=edges)
            ax.stairs(
                counts / max(values.size, 1) / np.diff(edges),
                edges,
                color=color,
                lw=1.5,
                label=disc.capitalize(),
            )
        axes[1, 0].plot(
            dur_grid,
            100.0 * retention_curve(dur_h * 60.0, dur_grid)[1],
            color=color,
            lw=1.6,
            label=disc.capitalize(),
        )
        axes[1, 1].plot(
            path_grid,
            100.0 * retention_curve(path, path_grid)[1],
            color=color,
            lw=1.6,
            label=disc.capitalize(),
        )
        axes[1, 2].plot(
            alt_grid,
            100.0 * retention_curve(alt_range, alt_grid)[1],
            color=color,
            lw=1.6,
            label=disc.capitalize(),
        )

    axes[0, 0].axvline(flight_level.min_duration_s / 3600.0, **line_kw)
    axes[0, 0].set(
        xlabel="Recorded flight duration [h]",
        ylabel="Density",
        title="(a) Duration",
        xlim=(0, 12),
    )
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].axvline(flight_level.min_path_km, **line_kw)
    axes[0, 1].set(
        xlabel="Flown path length [km]",
        ylabel="Density",
        title="(c) Path length",
        xscale="log",
    )

    axes[0, 2].axvline(flight_level.min_alt_range_m, **line_kw)
    axes[0, 2].set(
        xlabel="Whole-flight altitude range [m]",
        ylabel="Density",
        title="(e) Altitude range",
        xscale="log",
    )

    axes[1, 0].axvline(flight_level.min_duration_s / 60.0, **line_kw)
    axes[1, 0].set(
        xlabel=r"Minimum duration $T_{\min}$ [min]",
        ylabel="Flights retained [%]",
        title="(b) Duration criterion",
    )
    axes[1, 0].grid(visible=True, which="major", color=".9", lw=0.5)

    axes[1, 1].axvline(flight_level.min_path_km, **line_kw)
    axes[1, 1].set(
        xlabel="Minimum path length [km]",
        ylabel="Flights retained [%]",
        title="(d) Path criterion",
        xscale="log",
    )
    axes[1, 1].grid(visible=True, which="major", color=".9", lw=0.5)

    axes[1, 2].axvline(flight_level.min_alt_range_m, **line_kw)
    axes[1, 2].set(
        xlabel="Minimum altitude range [m]",
        ylabel="Flights retained [%]",
        title="(f) Altitude-range criterion",
        xscale="log",
    )
    axes[1, 2].grid(visible=True, which="major", color=".9", lw=0.5)

    if fig.get_layout_engine() is None:
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

    paper_style()

    line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(2, 2, figsize=(6.1, 5.5), layout="constrained")

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
        for ax, values, edges in (
            (axes[0, 0], gaps[disc], gap_bins),
            (axes[0, 1], misses[disc], miss_bins),
        ):
            counts, _ = np.histogram(values, bins=edges)
            ax.stairs(
                counts / max(values.size, 1) / np.diff(edges),
                edges,
                color=color,
                lw=1.5,
                label=disc.capitalize(),
            )
        axes[1, 0].plot(
            gap_grid,
            100.0 * retention_curve(gaps[disc], gap_grid, mode="at_most")[1],
            color=color,
            lw=1.6,
            label=disc.capitalize(),
        )
        axes[1, 1].plot(
            miss_grid,
            100.0 * retention_curve(misses[disc], miss_grid, mode="at_most")[1],
            color=color,
            lw=1.6,
            label=disc.capitalize(),
        )

    axes[0, 0].axvline(1.0, **line_kw)
    axes[0, 0].set(
        xlabel=r"Largest gap / this flight's $g_{\max}$",
        ylabel="Density",
        title="(a) Largest gap",
        xlim=(0.0, gap_hi),
    )
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].axvline(sampling.max_missing_fraction, **line_kw)
    axes[0, 1].set(
        xlabel="Missing fraction",
        ylabel="Density",
        title="(b) Missing fraction",
        xlim=(0.0, miss_hi),
    )

    axes[1, 0].axvline(1.0, **line_kw)
    axes[1, 0].set(
        xlabel=r"Gap threshold / $g_{\max}$",
        ylabel="Flights retained [%]",
        title="(c) Gap criterion",
        xscale="log",
    )
    axes[1, 0].grid(visible=True, which="major", color=".9", lw=0.5)

    axes[1, 1].axvline(sampling.max_missing_fraction, **line_kw)
    axes[1, 1].set(
        xlabel="Cut on missing fraction",
        ylabel="Flights retained [%]",
        title="(d) Missing-fraction criterion",
    )
    axes[1, 1].grid(visible=True, which="major", color=".9", lw=0.5)

    if fig.get_layout_engine() is None:
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

    paper_style()

    fig, ax = plt.subplots(figsize=(6.1, 3.0), layout="constrained")
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
            lw=1.2,
            color=_DISC_COLOR.get(disc, "gray"),
            label=disc.capitalize(),
        )
    ax.set_xticks(range(1, upper + 1))
    ax.set_xticklabels([str(i) for i in range(1, upper)] + [f"$\\geq${upper}"])
    ax.set_xlabel(r"Native sampling interval $\Delta t$ [s]")
    ax.set_ylabel("Fraction of flights")
    ax.legend(loc="best")
    ax.grid(visible=True, which="major", color=".9", lw=0.5)
    return fig


def _finite(values) -> np.ndarray:
    """The finite samples of one channel, as a float array.

    Every per-fix channel can arrive with gaps -- the vertical speed most of all, since
    it is a difference of altitudes and a fix without one leaves a nan behind -- and the
    range calculations below are all quantiles, which propagate a single nan into every
    bin edge.
    """
    array = np.asarray(values if values is not None else (), dtype=float)
    return array[np.isfinite(array)]


def make_fixlevel_diagnostics_figure(
    distributions: dict[str, dict[str, np.ndarray]], fix_level: FixLevelThresholds
) -> Figure:
    """Fix-level cleaning diagnostics: the per-fix distributions the bounds act on.

    Three panels, each overlaying every discipline, for the quantities the fix-level
    cuts test at consecutive fixes or over a neighbourhood of them: (a) horizontal speed
    ``v_xy``, (b) the *windowed* GNSS vertical speed ``v_z_local`` -- the median of
    ``|v_z|`` over a centred window
    (:func:`soaring.analysis.preproc.cleaning.local_vz`), which is what
    ``max_vertical_speed_mps`` actually bounds -- (c) GNSS altitude. Unlike the
    flight-level figure these are distributions over individual *fixes*, not
    per-flight summaries. The annotations measure raw-sample bound exceedances,
    not the number of fixes removed by the complete cleaning pipeline. A sparse
    tail alone does not establish that an observation is corrupt. The y-axis is
    logarithmic so that tail is visible; all horizontal axes are linear to show
    distances from the bounds.
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

    paper_style()

    shared_line_kw = {"color": "0.25", "ls": "--", "lw": 1.2}
    fig, axes = plt.subplots(1, 3, figsize=(6.1, 3.2))

    def _hist_panel(
        ax,
        key,
        xlabel,
        title,
        *,
        all_cut_values,
        wide_tail,
        integer_aligned=False,
        xscale="linear",
        min_hi=None,
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
        # Non-finite samples are dropped before anything is measured off them: one of
        # them makes every quantile below nan, and a nan bin edge reaches numpy as
        # "arange: cannot compute length" -- an error naming the histogram rather than
        # the channel that carried it. The vertical speed is where they come from, being
        # a difference of altitudes: a fix whose altitude is missing leaves one behind.
        samples = {disc: _finite(d.get(key)) for disc, d in distributions.items()}
        per_disc = [v for v in samples.values() if v.size]
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
        if min_hi is not None:
            hi = max(hi, min_hi)
        if xscale == "log":
            # A log axis cannot show a value <= 0, and the 0.1th-percentile floor
            # above can land at or below zero for a quantity with a spike at exactly
            # zero (a windowed median that falls in an all-zero window). Clip to the
            # smallest positive sample instead, and space the bins geometrically so
            # they read as equal-width on the log axis (linear bins would bunch up
            # against the left edge).
            positive = pooled[pooled > 0]
            lo = max(lo, float(np.min(positive)) if positive.size else 1e-3)
            bins = np.geomspace(lo, hi, 60)
        elif integer_aligned:
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
        for disc, v in samples.items():
            if v.size:
                ax.hist(
                    v,
                    bins=bins,
                    density=True,
                    histtype="step",
                    lw=1.5,
                    color=_DISC_COLOR.get(disc, "gray"),
                    label=disc.capitalize(),
                )
        ax.set(
            xlabel=xlabel,
            ylabel="Density",
            title=title,
            yscale="log",
            xscale=xscale,
            xlim=(lo, hi),
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
                f"{disc}: {frac:.2g}% above bound",
                transform=ax.transAxes,
                fontsize=7.5,
                ha="right",
                va="top",
                color=color,
            )

    def _shared_cut_panel(
        ax,
        key,
        cuts,
        xlabel,
        title,
        *,
        wide_tail,
        integer_aligned=False,
        xscale="linear",
        min_hi=None,
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
            xscale=xscale,
            min_hi=min_hi,
        )
        for c in cuts:
            ax.axvline(c, **shared_line_kw)
        if len(cuts) == 1:
            frac = float(np.mean(pooled > cuts[0])) * 100.0
            note = f"{frac:.2g}% above {cuts[0]:g} m/s"
        else:
            frac = float(np.mean((pooled < cuts[0]) | (pooled > cuts[1]))) * 100.0
            note = f"{frac:.2g}% of values outside band"
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
        "v_z_local",
        (fix_level.max_vertical_speed_mps,),
        r"windowed GNSS $\mathrm{med}|v_z|$ [m/s]",
        "(b) Vertical speed",
        wide_tail=False,
        min_hi=60.0,
        # Not integer-aligned: unlike the raw per-step value, a rolling median is not
        # itself a metre-quantized quantity, even though every sample feeding it is.
        integer_aligned=False,
        xscale="linear",
    )
    _shared_cut_panel(
        axes[2],
        "altitude",
        (fix_level.min_altitude_m, fix_level.max_altitude_m),
        "GNSS altitude [m]",
        "(c) Altitude",
        wide_tail=False,
        # The data and the cut alone would stop well short of this: forced out to
        # 10 km regardless, so the panel reads against the whole plausible envelope
        # (close to the highest altitude a paraglider or hang glider could ever
        # reach), not just the narrow band the adopted bound and the sample happen
        # to populate.
        min_hi=10_000.0,
    )
    for axis in axes:
        axis.tick_params(labelsize=8)
        axis.xaxis.label.set_size(9)
        axis.yaxis.label.set_size(9)
        axis.title.set_fontsize(9)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    if fig.get_layout_engine() is None:
        fig.tight_layout()
    return fig


def make_fixlevel_histogram_figure(
    histograms: dict, fix_level: FixLevelThresholds
) -> Figure:
    """Render streamed, unconditional densities and full-sample exceedance counts.

    Each quantity record has ``edges``, ``counts``, ``n_finite`` and ``n_outside``.
    Truncating the displayed x range does not renormalize the displayed density.
    """
    import matplotlib.pyplot as plt

    paper_style()

    fig, axes = plt.subplots(1, 3, figsize=(6.1, 3.2), layout="constrained")
    labels = [
        ("v_xy", "(a) Horizontal speed", r"$v_{xy}$ [m/s]"),
        ("v_z_local", "(b) Vertical speed", r"window median $|v_z|$ [m/s]"),
        ("altitude", "(c) Altitude", "GNSS altitude [m]"),
    ]
    for ax, (key, title, xlabel) in zip(axes, labels, strict=True):
        for disc, stats in histograms.items():
            h = stats[key]
            density = h["counts"] / max(h["n_finite"], 1) / np.diff(h["edges"])
            ax.stairs(
                density,
                h["edges"],
                color=_DISC_COLOR.get(disc, ".5"),
                lw=1.3,
                label=disc.capitalize(),
            )
            if key == "v_xy":
                ax.axvline(
                    fix_level.max_horizontal_speed_mps[disc],
                    color=_DISC_COLOR.get(disc, ".5"),
                    ls="--",
                    lw=1,
                )
        if key != "v_xy":
            cuts = (
                [fix_level.max_vertical_speed_mps]
                if key == "v_z_local"
                else [fix_level.min_altitude_m, fix_level.max_altitude_m]
            )
            for cut in cuts:
                ax.axvline(cut, color=".25", ls="--", lw=1)
            n = sum(stats[key]["n_finite"] for stats in histograms.values())
            outside = sum(stats[key]["n_outside"] for stats in histograms.values())
            ax.text(
                0.97,
                0.95,
                f"{100 * outside / max(n, 1):.3g}% outside",
                ha="right",
                va="top",
                transform=ax.transAxes,
                fontsize=8,
                color=".25",
            )
        ax.set(xlabel=xlabel, ylabel="Density", title=title, yscale="log")
        ax.set_xlim(h["edges"][0], h["edges"][-1])
        ax.tick_params(labelsize=8)
        ax.xaxis.label.set_size(9)
        ax.yaxis.label.set_size(9)
        ax.title.set_fontsize(9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    return fig
