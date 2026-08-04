"""Stage (vii): Savitzky-Golay smoothing and differentiation (thesis, sec:savgol).

Velocity and acceleration drive the kinematics and the segmentation, but differencing
raw GPS coordinate series amplifies the high-frequency noise. A Savitzky-Golay filter
solves both problems at once: it fits a low-order polynomial to a sliding window by
least squares and reads off that polynomial, or its derivatives, at the window centre,
returning smoothed position, velocity and acceleration in one pass per component. In
the window of ``w`` samples centred on ``t_i``, the coefficients of
``P(t) = sum_k a_k (t - t_i)^k`` minimise the squared residuals; the smoothed value is
``a_0``, the velocity ``a_1``, the acceleration ``2 a_2``. Because the grid is uniform,
the ``a_k`` are fixed linear combinations of the window samples, so the whole filter
is a convolution with precomputed coefficients.

The fit is done in units of samples, so the physical velocity and acceleration are
``a_1 / dt`` and ``2 a_2 / dt^2``, with the flight's own ``dt`` -- ``delta=dt`` in the
call below. **This is the only place the cadence enters, and it is why flights of
different cadences need no common grid** (sec:uniform).

The two hyperparameters come from the measured noise spectrum, not from taste:

* the **window** ``w`` is ``tau_c / dt`` rounded up to the nearest odd integer -- odd,
  so the window has a centre sample to evaluate at -- with a floor at 5 samples, the
  smallest on which a cubic fit is meaningfully determined (:func:`savgol_window`).
  Making ``w`` span ``tau_c`` is a *choice*, the natural one: it puts the filter's
  cut-off at the measured knee of the noise spectrum. At the dominant 1 s cadence the
  two rules coincide, ``w = 5`` spanning exactly ``tau_c``; at every slower cadence the
  floor binds and the five-sample window spans *more* than ``tau_c``. That cost is
  accepted: at those cadences the noise band sits at or beyond the Nyquist frequency, so
  there is little to remove at the noise scale in the first place.
* the **order** is ``p = 3``, the lowest that works. An acceleration needs curvature, so
  ``p >= 2``; one order more is needed for the *velocity*, because on a symmetric window
  adding an even-order term leaves the odd-order coefficients untouched, so the velocity
  of a ``p = 2`` fit is identical to that of a straight-line fit. The cubic term is the
  first whose velocity responds to the acceleration *varying* across the window. Going
  higher only lets the fit follow more noise.

The vertical is treated separately from the horizontal and conditioned on the flight's
``alt_source``. The a-priori expectation was asymmetric -- a shorter window for the
smooth barometric channel, a longer one for the noisy GNSS vertical -- and the
measurement disconfirmed it: the three knees coincide at ``f_c ~ 0.2 Hz`` because
every channel's floor is the IGC format's own rounding, not receiver noise. The
per-channel machinery stays, for the noisy GNSS minority, but the adopted windows are
equal today.

**The window never crosses a segment boundary**: the filter runs per segment, with
``mode='interp'``, so the terminal half-windows are fitted on the edge window and
evaluated off-centre rather than on padded data. An off-centre evaluation extrapolates
the fitted polynomial, and the variance of a least-squares polynomial grows towards the
ends of its fitting interval, so the first and last ``w // 2`` samples of a segment
carry a larger uncertainty than the interior ones. They are flagged ``edge`` -- the same
per-sample flag mechanism as ``interpolated`` -- so that an observable sensitive to it
can be recomputed on interior samples only, which is the empirical check sec:savgol asks
for.

What this stage does **not** do is validate its own hyperparameters. The acceptance
criteria of sec:savgol -- a flat residual spectrum above ``f_c``, smoothed kinematics
inside the physical envelopes, stability under a one-step change of ``w`` -- are a
diagnostic on a held-out sample, and ``tau_c`` itself is provisional until it is re-read
on the cleaned ensemble.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .resample import FIX_COLUMNS, Resampled

if TYPE_CHECKING:
    from ..config import SavgolParams

# The kinematic columns this stage adds, in order: velocity then acceleration, per ENU
# component. `E`, `N` and `z` are overwritten in place by their smoothed values -- only
# the filter's outputs are stored, never both a raw and a filtered copy of one
# quantity.
KINEMATIC_COLUMNS = ["v_E", "v_N", "v_z", "a_E", "a_N", "a_z"]

# Columns of the per-fix table this stage produces, in order (carried-through columns
# follow). `edge` joins `interpolated` as the second per-sample caution flag.
SMOOTHED_COLUMNS = [*FIX_COLUMNS, *KINEMATIC_COLUMNS, "edge"]

# The smallest window this stage will use, whatever the cadence says (sec:savgol): five
# samples, the least on which a cubic fit is meaningfully determined.
MIN_WINDOW = 5

# A segment the window does not fit into cannot be smoothed at all. The segment gate of
# stage (vi) covers this at every common cadence -- 90 s carries at least five samples
# up to dt = 22.5 s -- so this bites only in the thin tail of very slow loggers.
DROP_WINDOW_TOO_WIDE = "shorter_than_smoothing_window"


@dataclass(frozen=True)
class SavgolWindows:
    """The filter as it was configured for one flight: what ``flights_meta`` records.

    Attributes:
        horizontal: Window in samples for ``E`` and ``N``.
        vertical: Window in samples for ``z``, conditioned on the flight's
            ``alt_source``. Equal to ``horizontal`` under the adopted timescales, which
            the measurement found to coincide; the two are kept apart because the
            machinery, not the current value, is what the noisy GNSS minority needs.
        polyorder: The polynomial order, ``p = 3``.
    """

    horizontal: int
    vertical: int
    polyorder: int


@dataclass(frozen=True)
class Smoothed:
    """One flight after stage (vii): the pipeline's final per-fix table.

    Attributes:
        fixes: One row per grid point, columns :data:`SMOOTHED_COLUMNS` followed by the
            carried-through columns. ``E``, ``N`` and ``z`` are now the smoothed
            positions; the velocities and accelerations are the same fit's first and
            second derivatives, in m/s and m/s^2.
        segments: The segment table of stage (vi), with any segment too short for the
            window now marked dropped (:data:`DROP_WINDOW_TOO_WIDE`).
        windows: The filter configuration this flight was run with, or ``None`` for a
            flight that reached this stage already dropped and so was never filtered.
        drop_reason: ``None`` when at least one segment survived, otherwise
            :data:`DROP_WINDOW_TOO_WIDE` -- or, unchanged, the reason stage (vi) had
            already recorded.
    """

    fixes: pd.DataFrame
    segments: pd.DataFrame
    windows: SavgolWindows | None
    drop_reason: str | None


def savgol_window(tau_c_s: float, dt_s: float, polyorder: int) -> int:
    """The smoothing window in samples, from a noise timescale and a cadence.

    ``tau_c / dt`` rounded up to the nearest odd integer, floored at the smallest
    window a fit of this order can carry (:data:`MIN_WINDOW` for the adopted ``p = 3``,
    and ``p + 2`` rounded up to odd for any other order -- one sample more than the
    ``p + 1`` that would determine the polynomial exactly, so it stays a least-squares
    fit).

    Args:
        tau_c_s: The channel's smoothing timescale, in seconds.
        dt_s: The flight's native sampling interval, in seconds.
        polyorder: The polynomial order.

    Returns:
        An odd window length in samples.
    """
    window = int(np.ceil(tau_c_s / dt_s))
    window += window % 2 == 0  # up to the nearest odd integer: it needs a centre sample
    floor = max(MIN_WINDOW, polyorder + 2)
    floor += floor % 2 == 0
    return max(window, floor)


def savgol_windows(
    savgol: SavgolParams, dt_s: float, *, alt_source: str = "baro"
) -> SavgolWindows:
    """The per-flight filter configuration (thesis, sec:savgol item (iii)).

    Args:
        savgol: The adopted order and the three smoothing timescales.
        dt_s: The flight's native sampling interval, in seconds.
        alt_source: ``"baro"`` or ``"gnss"``, the channel stage (i) adopted for this
            flight; it selects which vertical timescale applies.

    Returns:
        The :class:`SavgolWindows` for this flight.

    Raises:
        ValueError: If ``alt_source`` is neither ``"baro"`` nor ``"gnss"``.
    """
    if alt_source not in {"baro", "gnss"}:
        raise ValueError(f"alt_source must be 'baro' or 'gnss', not {alt_source!r}")
    tau_vertical = (
        savgol.tau_c_vertical_baro_s
        if alt_source == "baro"
        else savgol.tau_c_vertical_gnss_s
    )
    return SavgolWindows(
        horizontal=savgol_window(savgol.tau_c_horizontal_s, dt_s, savgol.polyorder),
        vertical=savgol_window(tau_vertical, dt_s, savgol.polyorder),
        polyorder=savgol.polyorder,
    )


def smooth_segment(
    segment: pd.DataFrame, windows: SavgolWindows, dt_s: float
) -> pd.DataFrame:
    """Filter and differentiate one segment's three channels.

    Args:
        segment: The segment's grid points, with columns ``E``, ``N``, ``z`` (finite
            everywhere -- the completeness invariant of stage (vi)) on a uniform grid of
            step ``dt_s``, plus whatever else it carries.
        windows: The filter configuration.
        dt_s: The grid step, in seconds. It enters only here, as the ``delta`` that
            turns the fit's per-sample coefficients into physical units.

    Returns:
        The segment with ``E``, ``N``, ``z`` replaced by their smoothed values,
        :data:`KINEMATIC_COLUMNS` added, and the ``edge`` flag set on the samples the
        filter had to evaluate off-centre.

    Raises:
        ValueError: If the segment is shorter than the widest window, which
            ``mode='interp'`` cannot fit.
    """
    # Lazy, as elsewhere in this package: importing the module must not require the
    # optional `analysis` dependency group.
    from scipy.signal import savgol_filter

    widest = max(windows.horizontal, windows.vertical)
    if len(segment) < widest:
        raise ValueError(
            f"segment of {len(segment)} samples is shorter than the {widest}-sample "
            "smoothing window"
        )

    out = segment.copy()
    channels = {"E": windows.horizontal, "N": windows.horizontal, "z": windows.vertical}
    for channel, window in channels.items():
        values = segment[channel].to_numpy(dtype=float)
        for deriv, name in enumerate([channel, f"v_{channel}", f"a_{channel}"]):
            out[name] = savgol_filter(
                values,
                window_length=window,
                polyorder=windows.polyorder,
                deriv=deriv,
                delta=dt_s,
                # Fit the terminal half-windows on the edge window and evaluate
                # off-centre, rather than padding the segment with data it does not
                # have. The window never crosses a boundary (sec:savgol).
                mode="interp",
            )
    half = widest // 2
    edge = np.zeros(len(segment), dtype=bool)
    edge[:half] = True
    edge[len(segment) - half :] = True
    out["edge"] = edge
    return out


def smooth_flight(
    resampled: Resampled, savgol: SavgolParams, *, alt_source: str = "baro"
) -> Smoothed:
    """Run stage (vii) over one resampled flight, segment by segment.

    Args:
        resampled: The output of stage (vi). Its ``dt_s`` is the grid step, and its
            ``segments`` table is carried forward and updated.
        savgol: The adopted order and smoothing timescales.
        alt_source: The flight's adopted altitude channel, ``"baro"`` or ``"gnss"``.

    Returns:
        The :class:`Smoothed` record. A segment the window does not fit into is dropped
        alone, with its reason written into the segment table, exactly as at stage (vi);
        the flight is lost only if no segment survives. A flight that arrives already
        dropped passes straight through, keeping the reason it came with.
    """
    if resampled.drop_reason is not None:
        return Smoothed(
            fixes=_empty_smoothed(resampled.fixes),
            segments=resampled.segments,
            windows=None,
            drop_reason=resampled.drop_reason,
        )
    windows = savgol_windows(savgol, resampled.dt_s, alt_source=alt_source)
    segments = resampled.segments.copy()
    widest = max(windows.horizontal, windows.vertical)

    smoothed: list[pd.DataFrame] = []
    for segment_id, group in resampled.fixes.groupby("segment_id", sort=True):
        if len(group) < widest:
            row = segments["segment_id"] == segment_id
            segments.loc[row, "kept"] = False
            segments.loc[row, "n_fix"] = 0
            segments.loc[row, "drop_reason"] = DROP_WINDOW_TOO_WIDE
            continue
        smoothed.append(smooth_segment(group, windows, resampled.dt_s))

    if not smoothed:
        return Smoothed(
            fixes=_empty_smoothed(resampled.fixes),
            segments=segments,
            windows=windows,
            drop_reason=DROP_WINDOW_TOO_WIDE,
        )
    return Smoothed(
        fixes=_ordered(pd.concat(smoothed, ignore_index=True)),
        segments=segments,
        windows=windows,
        drop_reason=None,
    )


def _empty_smoothed(fixes: pd.DataFrame) -> pd.DataFrame:
    """The output table of a flight that contributed no fixes, dtypes and all."""
    empty = fixes.iloc[:0].copy()
    for name in KINEMATIC_COLUMNS:
        empty[name] = pd.Series(dtype="float64")
    empty["edge"] = pd.Series(dtype="bool")
    return _ordered(empty)


def _ordered(fixes: pd.DataFrame) -> pd.DataFrame:
    """Put the table in :data:`SMOOTHED_COLUMNS` order, carried columns last."""
    carried = [c for c in fixes.columns if c not in SMOOTHED_COLUMNS]
    return fixes[[*SMOOTHED_COLUMNS, *carried]]
