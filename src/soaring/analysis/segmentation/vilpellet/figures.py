"""Figures that show what the transcribed segmenter decided, at thesis text width.

Three drawings carry the Chapter 5 argument.  A plan view says where a phase happened,
a two-panel comparison puts the Chapter 4 Gaussian decoder beside this one on the same
geometry and the same axes, and a timeline says when a phase happened against the
altitude the glider actually flew.

Everything here follows :mod:`soaring.reporting.style`.  The phase colours come from
:data:`~soaring.reporting.style.PHASE_COLORS`, unclassified fixes take
:data:`~soaring.reporting.style.UNCLASSIFIED_COLOR`, figures are sized against
:data:`~soaring.reporting.style.TEXT_WIDTH_IN`, and :func:`save_figure` strips the
creation timestamp so that rerunning a generator on unchanged input rewrites an
identical file.

Matplotlib is imported inside the functions, never at module scope, so that importing
this module from a numerical pass costs nothing and pulls in no GUI toolkit.  No Qt is
involved at any point.

A trajectory is drawn as one line per ``phase_run``.  Two separate occurrences of one
phase therefore never get joined by a straight line across the flight that happened in
between.  Each run is closed at the first fix of the following run when that fix belongs
to the same ``track_run``, which colours the edge that crosses a phase boundary without
bridging a preprocessing-segment boundary or a logging gap.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from soaring.reporting.style import (
    PDF_METADATA,
    PHASE_COLORS,
    TEXT_WIDTH_IN,
    TRACE_COLOR,
    UNCLASSIFIED_COLOR,
)

from .pipeline import UNCLASSIFIED

if TYPE_CHECKING:  # pragma: no cover - typing only
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch

# The order a legend lists the phases in, which is the order Chapter 4 also uses.
PHASE_ORDER = ("transition", "search", "climb", UNCLASSIFIED)

# Columns a labelled fix table must carry before any of these functions can draw it.
REQUIRED_PLAN_COLUMNS = ("E", "N", "phase")


def phase_palette() -> dict[str, str]:
    """The colour of every phase name a labelled fix table can hold.

    Returns:
        A fresh mapping from phase name to colour, including ``unclassified``.  It is a
        copy, so a caller may add an entry of its own without touching the shared
        palette.
    """
    return {**PHASE_COLORS, UNCLASSIFIED: UNCLASSIFIED_COLOR}


def phase_legend_handles(
    phases: list[str], color_map: dict[str, str] | None = None
) -> list[Patch]:
    """Build one legend patch per phase, in the document's fixed phase order.

    Args:
        phases: The phase names that occur in the drawing.
        color_map: Optional replacement palette; :func:`phase_palette` by default.

    Returns:
        The patches, listing the phases of :data:`PHASE_ORDER` that occur, then any
        further name in sorted order.
    """
    from matplotlib.patches import Patch

    palette = dict(color_map) if color_map is not None else phase_palette()
    present = set(phases)
    ordered = [name for name in PHASE_ORDER if name in present]
    ordered += sorted(present.difference(PHASE_ORDER))
    return [
        Patch(color=palette.get(name, UNCLASSIFIED_COLOR), label=name)
        for name in ordered
    ]


def save_figure(figure: Figure, output: str | Path) -> Path:
    """Write a figure with metadata that does not change between identical runs.

    Args:
        figure: The figure to write.
        output: Destination path; the suffix selects the format.

    Returns:
        The path written.
    """
    import matplotlib.pyplot as plt

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, metadata=dict(PDF_METADATA))
    plt.close(figure)
    return destination


def _ordered(fixes: pd.DataFrame) -> pd.DataFrame:
    """Return the fix table in the order a drawn trajectory traverses it."""
    keys = [column for column in ("segment_id", "t") if column in fixes.columns]
    if keys:
        return fixes.sort_values(keys, kind="stable").reset_index(drop=True)
    return fixes.reset_index(drop=True)


def _run_ids(table: pd.DataFrame) -> np.ndarray:
    """Line-group identifiers, from ``phase_run`` when the table carries one."""
    if "phase_run" in table.columns:
        return table["phase_run"].to_numpy()
    changed = table["phase"].ne(table["phase"].shift())
    if "track_run" in table.columns:
        changed = changed | table["track_run"].ne(table["track_run"].shift())
    elif "segment_id" in table.columns:
        changed = changed | table["segment_id"].ne(table["segment_id"].shift())
    return (changed.cumsum() - 1).to_numpy()


def _require(table: pd.DataFrame, columns: tuple[str, ...], what: str) -> None:
    """Raise when a drawing has been handed a table it cannot read."""
    missing = [column for column in columns if column not in table.columns]
    if missing:
        raise ValueError(f"{what} needs the columns {missing}")
    if table.empty:
        raise ValueError(f"{what} needs at least one fix")


def plot_phase_plan_view(
    ax: Axes,
    fixes: pd.DataFrame,
    *,
    color_map: dict[str, str] | None = None,
    title: str | None = None,
    linewidth: float = 1.0,
    label_axes: bool = True,
) -> list[str]:
    """Draw one labelled trajectory in the horizontal plane, coloured by phase.

    Args:
        ax: The target axes.
        fixes: A labelled fix table with ``E``, ``N`` and ``phase``, and optionally
            ``phase_run`` and ``track_run``.
        color_map: Phase colours; :func:`phase_palette` by default.
        title: Axes title, or ``None`` to leave the title unset.
        linewidth: Width of the trajectory line, in points.
        label_axes: Write the kilometre axis labels.  Switch it off for the right-hand
            panel of a shared-axis pair.

    Returns:
        The phase names actually drawn, so a caller can build a legend covering exactly
        what appears.

    Raises:
        ValueError: If the table is empty or lacks a required column.
    """
    _require(fixes, REQUIRED_PLAN_COLUMNS, "the plan view")
    palette = dict(color_map) if color_map is not None else phase_palette()
    table = _ordered(fixes)
    east = table["E"].to_numpy(dtype=float) / 1000.0
    north = table["N"].to_numpy(dtype=float) / 1000.0
    phases = table["phase"].astype(str).to_numpy()
    runs = _run_ids(table)
    track = (
        table["track_run"].to_numpy()
        if "track_run" in table.columns
        else np.zeros(len(table), dtype=np.int64)
    )
    boundaries = np.r_[0, np.flatnonzero(runs[1:] != runs[:-1]) + 1, len(runs)]
    drawn: list[str] = []
    for first, stop in pairwise(boundaries):
        # Close the run at the next fix of the same physical track, so the edge that
        # crosses a phase boundary is coloured without joining across a gap.
        end = stop + 1 if stop < len(runs) and track[stop] == track[stop - 1] else stop
        name = str(phases[first])
        if name not in drawn:
            drawn.append(name)
        ax.plot(
            east[first:end],
            north[first:end],
            color=palette.get(name, UNCLASSIFIED_COLOR),
            linewidth=linewidth,
            solid_capstyle="round",
        )
    ax.set_aspect("equal", adjustable="box")
    if label_axes:
        ax.set_xlabel("East (km)")
        ax.set_ylabel("North (km)")
    if title is not None:
        ax.set_title(title)
    ax.grid(True, color=".93", linewidth=0.4)
    return [name for name in PHASE_ORDER if name in drawn] + [
        name for name in drawn if name not in PHASE_ORDER
    ]


def _shared_plan_limits(
    frames: list[pd.DataFrame], *, margin: float = 0.04
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The east and north limits that hold every trajectory of a comparison."""
    east = np.concatenate([frame["E"].to_numpy(dtype=float) for frame in frames]) / 1e3
    north = np.concatenate([frame["N"].to_numpy(dtype=float) for frame in frames]) / 1e3
    span = max(float(east.max() - east.min()), float(north.max() - north.min()))
    span = span if span > 0 else 1.0
    pad = margin * span
    centre_e = float(east.min() + east.max()) / 2.0
    centre_n = float(north.min() + north.max()) / 2.0
    half = span / 2.0 + pad
    return (centre_e - half, centre_e + half), (centre_n - half, centre_n + half)


def plot_segmentation_comparison(
    fig: Figure,
    left_fixes: pd.DataFrame,
    right_fixes: pd.DataFrame,
    *,
    left_title: str,
    right_title: str,
    color_map: dict[str, str] | None = None,
    legend: bool = True,
) -> tuple[Axes, Axes]:
    """Put two segmentations of one flight side by side on identical axes.

    The two panels are attached, share both limits and take their colours from one
    palette, so every difference a reader sees between them belongs to the labelling
    rather than to the drawing.

    Args:
        fig: The figure to fill.  Size it at :data:`TEXT_WIDTH_IN` before calling.
        left_fixes: The labelled fix table for the left panel.  Pass an empty table
            to leave that panel for :func:`plot_placeholder_panel`.
        right_fixes: The labelled fix table for the right panel, on the same terms.
        left_title: Title of the left panel.
        right_title: Title of the right panel.
        color_map: Phase colours; :func:`phase_palette` by default.
        legend: Draw one figure-level legend below the panels.

    Returns:
        The left and right axes.

    Raises:
        ValueError: If both tables are empty, or a drawn one lacks a required column.
    """
    palette = dict(color_map) if color_map is not None else phase_palette()
    if left_fixes.empty and right_fixes.empty:
        raise ValueError("a comparison needs at least one labelled trajectory")
    axes = fig.subplots(1, 2, sharex=True, sharey=True)
    left_axis, right_axis = axes[0], axes[1]
    drawn: list[str] = []
    frames: list[pd.DataFrame] = []
    panels = (
        (left_axis, left_fixes, left_title, True),
        (right_axis, right_fixes, right_title, False),
    )
    for axis, table, panel_title, label_axes in panels:
        if table.empty:
            axis.set_title(panel_title)
            axis.set_aspect("equal", adjustable="box")
            axis.grid(True, color=".93", linewidth=0.4)
            continue
        frames.append(table)
        for name in plot_phase_plan_view(
            axis,
            table,
            color_map=palette,
            title=panel_title,
            label_axes=label_axes,
        ):
            if name not in drawn:
                drawn.append(name)
    left_axis.set_ylabel("North (km)")
    for axis in (left_axis, right_axis):
        axis.set_xlabel("East (km)")
    east_limits, north_limits = _shared_plan_limits(frames)
    left_axis.set_xlim(*east_limits)
    left_axis.set_ylim(*north_limits)
    fig.subplots_adjust(wspace=0.04)
    if legend:
        fig.legend(
            handles=phase_legend_handles(drawn, palette),
            loc="lower center",
            ncol=max(len(drawn), 1),
            frameon=False,
            bbox_to_anchor=(0.5, 0.0),
        )
    return left_axis, right_axis


def plot_placeholder_panel(ax: Axes, message: str) -> None:
    """Fill one panel of a comparison with a stated reason for its being empty.

    A panel left blank invites a reader to assume the segmenter found nothing.  This
    writes the real reason into the panel instead.

    Args:
        ax: The target axes.
        message: The sentence to write, already wrapped where it needs to be.
    """
    ax.text(
        0.5,
        0.5,
        message,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=8.5,
        color=TRACE_COLOR,
        wrap=True,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)


def _fix_step(t: np.ndarray, connected: np.ndarray) -> float:
    """The median logging step of a track, used to give each fix a strip width."""
    steps = np.diff(t)[connected]
    positive = steps[steps > 0]
    return float(np.median(positive)) if positive.size else 1.0


def _connected(table: pd.DataFrame) -> np.ndarray:
    """Which consecutive fix pairs belong to one uninterrupted stretch of flight."""
    t = table["t"].to_numpy(dtype=float)
    steps = np.diff(t)
    if "track_run" in table.columns:
        run = table["track_run"].to_numpy()
        same = run[1:] == run[:-1]
    elif "segment_id" in table.columns:
        segment = table["segment_id"].to_numpy()
        same = segment[1:] == segment[:-1]
    else:
        same = np.ones(max(len(t) - 1, 0), dtype=bool)
    positive = steps[steps > 0]
    cadence = float(np.median(positive)) if positive.size else np.inf
    return same & (steps > 0) & (steps <= 1.5 * cadence)


def plot_feature_timeline(
    fig: Figure,
    frame: pd.DataFrame,
    *,
    column: str = "z",
    ylabel: str = "Altitude (m)",
    color_map: dict[str, str] | None = None,
    title: str | None = None,
    duration_s: float | None = None,
    legend: bool = True,
) -> tuple[Axes, Axes]:
    """Draw one quantity against time with the phase colour strip beneath it.

    Args:
        fig: The figure to fill.
        frame: A labelled fix table with ``t``, ``phase`` and ``column``.
        column: The quantity to draw, typically ``z`` for altitude or ``v_z`` for
            vertical speed.
        ylabel: Axis label of that quantity, including its unit.
        color_map: Phase colours; :func:`phase_palette` by default.
        title: Title of the upper panel, or ``None``.
        duration_s: Keep only this many seconds from the first fix.  ``None`` draws the
            whole flight.
        legend: Draw one figure-level legend below the strip.

    Returns:
        The trace axes and the strip axes.

    Raises:
        ValueError: If the table is empty, lacks a required column, or is left empty by
            the requested excerpt.
    """
    _require(frame, ("t", "phase", column), "the feature timeline")
    palette = dict(color_map) if color_map is not None else phase_palette()
    table = _ordered(frame)
    origin = float(table["t"].iloc[0])
    if duration_s is not None:
        table = table.loc[table["t"] <= origin + float(duration_s)].reset_index(
            drop=True
        )
        if table.empty:
            raise ValueError("the requested excerpt holds no fix")
    elapsed = (table["t"].to_numpy(dtype=float) - origin) / 60.0
    values = table[column].to_numpy(dtype=float).copy()
    phases = table["phase"].astype(str).to_numpy()
    connected = _connected(table)
    step = _fix_step(table["t"].to_numpy(dtype=float), connected) / 60.0
    trace_axis, strip_axis = fig.subplots(
        2, 1, sharex=True, gridspec_kw={"height_ratios": [1.0, 0.13]}
    )
    # A break in physical continuity becomes a gap in the curve instead of a straight
    # line across time the recorder never reported.
    values[1:][~connected] = np.nan
    trace_axis.plot(elapsed, values, color=TRACE_COLOR, linewidth=1.0)
    trace_axis.set_ylabel(ylabel)
    trace_axis.grid(True, color=".93", linewidth=0.4)
    if title is not None:
        trace_axis.set_title(title)
    boundaries = np.r_[
        0,
        np.flatnonzero((phases[1:] != phases[:-1]) | ~connected) + 1,
        len(phases),
    ]
    drawn: list[str] = []
    for first, stop in pairwise(boundaries):
        name = str(phases[first])
        if name not in drawn:
            drawn.append(name)
        strip_axis.axvspan(
            elapsed[first] - step / 2.0,
            elapsed[stop - 1] + step / 2.0,
            color=palette.get(name, UNCLASSIFIED_COLOR),
            linewidth=0,
        )
    strip_axis.set(yticks=[], ylabel="Phase", xlabel="Time from first fix (min)")
    strip_axis.spines[["top", "right", "left"]].set_visible(False)
    strip_axis.set_xlim(float(elapsed[0]), float(elapsed[-1]))
    if legend:
        fig.legend(
            handles=phase_legend_handles(drawn, palette),
            loc="lower center",
            ncol=len(drawn),
            frameon=False,
            bbox_to_anchor=(0.5, 0.0),
        )
    return trace_axis, strip_axis


def make_plan_figure(width_in: float = TEXT_WIDTH_IN, height_in: float = 3.6) -> Figure:
    """A figure sized for the thesis text block, with room for a legend below.

    Args:
        width_in: Figure width in inches.
        height_in: Figure height in inches.

    Returns:
        The empty figure.
    """
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(width_in, height_in))
    figure.subplots_adjust(left=0.10, right=0.98, bottom=0.20, top=0.90)
    return figure
