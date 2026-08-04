"""Stage (iii): trimming of ground phases (thesis, sec:trimming).

The logger starts recording before take-off and stops after landing, and those ground
phases must be stripped before any kinematic analysis. Detection uses the **horizontal**
speed alone -- the vertical plays no role here -- through the sustained-speed rule of
Eq. eq:trimming, read forward for take-off and time-reversed for landing::

    t_on  = min{ t : v_xy > v0 throughout [t, t + T0] }
    t_off = max{ t : v_xy > v0 throughout [t - T0, t] }

Reading the landing rule backward from the end matters. "Cut at the first sustained drop
below ``v0``" would fire in the middle of the flight, because a wing soaring into wind
can hold a ground speed near zero while genuinely flying. The persistence ``T0`` stops a
gust or a GPS glitch on the ground from being read as take-off; it is set between two
scales rather than tuned -- long enough to outlast those artefacts, short enough that
misfiring costs at most ``T0`` at each end, negligible against the minimum duration a
retained flight has to reach anyway.

**The clock is re-zeroed here**, at the first fix of free flight, so that ``t`` is
elapsed flight time from then on (sec:notation). The spatial origin is set one stage
later, at the same fix (sec:enu). The window in the *recorded* clock is kept in the
report, because the integrity gate of stage (ii) has to count its removals inside it.

**Interior ground stints.** The rule above trims only the outer phases: a mid-flight
landing and relaunch recorded in one log -- a top-landing -- would survive as an
interior
near-zero-speed stint and read downstream as a false long wait in the tail of
``psi(tau)``. The guard is built like the frozen-lock rule, and cuts only on
corroborated
evidence, because its dangerous error is the opposite one -- the soaring-into-wind
failure mode. A stint is excised only when **both** hold: ``v_xy < v0`` continuously for
at least ``T_ground``, far beyond any search phase; **and** the adopted altitude flat
over the whole stint once its slow drift has been removed. The detrending is not a
detail -- the barometric reference itself wanders by tens of metres over an hour, which
over ``T_ground`` is already of the order of the tolerance, so testing the raw range
would let a perfectly stationary pilot fail the flatness condition on a pressure change
alone.

A cut stint is excised and the flight is split at the excision, exactly as at a long
gap.
Shorter stints meeting the same predicate are not cut but **flagged**: they are returned
as a list of suspect intervals, for the ``psi(tau)`` fits to be re-run with and without
them as a sensitivity check -- the same flag-without-deleting pattern as the outlier
identifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..preprocessing import great_circle_m

if TYPE_CHECKING:
    from ..preprocessing import TrimmingThresholds

# A flight with no sustained airborne stretch at all has no airborne segment.
DROP_NO_FLIGHT = "no_sustained_flight"

# Suspect (slow and flat) stints shorter than this are not reported. The floor is
# tau_freeze, reused rather than invented: below two thermalling periods a slow, flat
# stretch is not distinguishable from a genuine tight climb -- the same argument the
# frozen-lock rule makes when it abstains -- and reporting every such stretch would bury
# the mid-flight landings the list exists to surface.
_SUSPECT_MIN_SPAN_KEY = "frozen_tau_s"


@dataclass(frozen=True)
class Trimmed:
    """One flight after stage (iii).

    Attributes:
        fixes: The airborne stretch, with the clock re-zeroed at its first fix and
            ``split_before`` set where an interior ground stint was excised.
        t_on: Take-off, in the *recorded* clock (the one the input carried).
        t_off: Landing, in the same clock.
        trimmed_fraction: Share of the span *this stage* received that it removed.
            Its distribution over the archive bounds the exposure to the one structural
            failure of this rule -- a launch straight into ridge lift, clipped along
            with the ground phase, since a ground speed cannot tell the two apart. It
            is trimming's *marginal* share, and often zero on real data: a pilot
            standing still writes a collapsed, flat-barometer run, so the frozen-lock
            rule of stage (ii) has usually removed the ground phase already. What each
            stage took is then read from the fix counts of the two reports, and this
            number stays what the ridge-lift diagnostic needs it to be.
        suspect_intervals: Slow-and-flat stints too short to excise, as ``t_start`` /
            ``t_end`` in the re-zeroed clock.
        n_interior_excised: How many interior ground stints were cut.
        drop_reason: :data:`DROP_NO_FLIGHT` when no sustained stretch exists.
    """

    fixes: pd.DataFrame
    t_on: float
    t_off: float
    trimmed_fraction: float
    suspect_intervals: pd.DataFrame
    n_interior_excised: int
    drop_reason: str | None


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Maximal runs of ``True`` in ``mask``, as half-open index ranges."""
    edges = np.flatnonzero(np.diff(np.concatenate([[False], mask, [False]])))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2], strict=True)]


def airborne_window(
    t: np.ndarray, lat: np.ndarray, lon: np.ndarray, trimming: TrimmingThresholds
) -> tuple[float, float] | None:
    """The ``[t_on, t_off]`` of Eq. eq:trimming, or ``None`` if the flight never flew.

    Args:
        t: Fix times, strictly increasing.
        lat: Latitudes in degrees.
        lon: Longitudes in degrees.
        trimming: The adopted thresholds.

    Returns:
        The window in the input clock, or ``None`` when no stretch holds ``v_xy > v0``
        continuously for ``T0``.
    """
    if t.size < 2:
        return None
    dt = np.diff(t)
    step = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    with np.errstate(divide="ignore", invalid="ignore"):
        fast = np.where(dt > 0, step / dt, 0.0) > trimming.takeoff_speed_mps
    sustained = [
        (start, stop)
        for start, stop in _runs(fast)
        if t[stop] - t[start] >= trimming.sustained_s
    ]
    if not sustained:
        return None
    return float(t[sustained[0][0]]), float(t[sustained[-1][1]])


def _is_flat(
    t: np.ndarray, alt: np.ndarray, tolerance_m: float, max_drift_mps: float
) -> bool:
    """Whether the altitude is flat over a stint once its linear drift is removed.

    Two conditions, not one. The detrended spread must stay within the tolerance --
    that is the test sec:trimming states -- but detrending alone cannot separate a
    pressure drift from a steady climb, because both are linear and the fit removes
    either completely. A wing thermalling at 1 m/s in still air holds a ground speed
    near zero and gains 700 m over a ``T_ground`` stint, and its detrended residual is
    *zero*: without a second condition it would be excised as a mid-flight landing,
    which is exactly the failure this guard is built to avoid.

    What separates the two is the *rate*. Barometric drift runs at tens of metres per
    hour; a soaring climb runs two orders of magnitude faster. The bound on the fitted
    slope is therefore ``max_drift_mps``, and the driver derives it from the
    frozen-lock rule's own statement of what counts as motionless,
    ``frozen_delta_z_m / frozen_tau_s`` -- a rate the configuration already fixes, not a
    new threshold.

    The spread is the *central* one, the span from the 5th to the 95th percentile of
    the residual, and not its full range. A full range is a maximum statistic: over
    zero-mean noise it grows without bound with the number of samples, by roughly ``2
    sigma sqrt(2 ln n)``. At the metre-scale barometric noise of this archive it reads
    4.6 m over a 60-sample stint and 7.1 m over 3000, so with a 5 m tolerance the test
    passed on short stints and failed on long ones, on noise alone; and an interior
    stint must last minutes to be considered at all, so it failed on every one of
    them. The rule could not fire. The central span has the same units and the same
    reading, and for Gaussian noise it sits at 3.3 sigma whatever the stint's length,
    so the threshold means the same thing on a one-minute stint and a one-hour one. A
    genuine climb of hundreds of metres exceeds it either way.
    """
    finite = np.isfinite(alt)
    if finite.sum() < 3:
        return False  # in doubt, the stint is kept
    slope, intercept = np.polyfit(t[finite], alt[finite], 1)
    residual = alt[finite] - (slope * t[finite] + intercept)
    spread = float(np.percentile(residual, 95) - np.percentile(residual, 5))
    return bool(spread <= tolerance_m and abs(slope) <= max_drift_mps)


def trim_flight(
    fixes: pd.DataFrame,
    trimming: TrimmingThresholds,
    *,
    suspect_min_span_s: float,
    max_drift_mps: float,
) -> Trimmed:
    """Run stage (iii) over one cleaned flight.

    Args:
        fixes: The flight after stage (ii): ``t``, ``lat``, ``lon``, ``alt``, plus the
            per-fix cleaning columns. ``t`` must be strictly increasing.
        trimming: The adopted thresholds.
        suspect_min_span_s: Shortest slow-and-flat stint worth reporting as suspect;
            the driver passes ``fix_level.frozen_tau_s`` (see the module note).
        max_drift_mps: Largest fitted altitude slope a stint may show and still count as
            flat; the driver passes ``frozen_delta_z_m / frozen_tau_s`` (see
            :func:`_is_flat`).

    Returns:
        The :class:`Trimmed` record. When no airborne window exists the fixes come back
        empty and ``drop_reason`` says so -- counted and recorded, never silently lost.

    Raises:
        ValueError: If a required column is missing.
    """
    missing = [c for c in ("t", "lat", "lon", "alt") if c not in fixes.columns]
    if missing:
        raise ValueError(f"the per-fix table is missing the column(s) {missing}")

    work = fixes.reset_index(drop=True)
    t = work["t"].to_numpy(dtype=float)
    lat = work["lat"].to_numpy(dtype=float)
    lon = work["lon"].to_numpy(dtype=float)
    recorded_span = float(t[-1] - t[0]) if t.size >= 2 else 0.0

    window = airborne_window(t, lat, lon, trimming)
    if window is None:
        return Trimmed(
            fixes=work.iloc[:0].copy(),
            t_on=float("nan"),
            t_off=float("nan"),
            trimmed_fraction=1.0,
            suspect_intervals=pd.DataFrame({"t_start": [], "t_end": []}),
            n_interior_excised=0,
            drop_reason=DROP_NO_FLIGHT,
        )

    t_on, t_off = window
    airborne = (t >= t_on) & (t <= t_off)
    out = work.loc[airborne].reset_index(drop=True)
    t = out["t"].to_numpy(dtype=float)
    excise, suspect = _interior_ground(
        t,
        out["lat"].to_numpy(dtype=float),
        out["lon"].to_numpy(dtype=float),
        out["alt"].to_numpy(dtype=float),
        trimming,
        suspect_min_span_s,
        max_drift_mps,
    )
    n_excised = len(_runs(excise))
    if "split_before" not in out.columns:
        out["split_before"] = False
    split = out["split_before"].to_numpy(dtype=bool).copy()
    for _, stop in _runs(excise):
        if stop < split.size:
            split[stop] = True
    out["split_before"] = split
    out = out.loc[~excise].reset_index(drop=True)
    # The clock zero of sec:notation: elapsed flight time from the first fix of free
    # flight. The spatial origin follows at the same fix, one stage later.
    out["t"] = out["t"].to_numpy(dtype=float) - t_on

    airborne_span = t_off - t_on
    return Trimmed(
        fixes=out,
        t_on=t_on,
        t_off=t_off,
        trimmed_fraction=(
            1.0 - airborne_span / recorded_span if recorded_span > 0 else 0.0
        ),
        suspect_intervals=pd.DataFrame(
            {
                "t_start": [t[a] - t_on for a, _ in suspect],
                "t_end": [t[b - 1] - t_on for _, b in suspect],
            }
        ),
        n_interior_excised=n_excised,
        drop_reason=None,
    )


def _interior_ground(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    alt: np.ndarray,
    trimming: TrimmingThresholds,
    suspect_min_span_s: float,
    max_drift_mps: float,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Interior ground stints: which fixes to excise, and which to merely flag.

    Returns:
        ``(excise, suspect)``: a boolean array over the fixes, and the half-open index
        ranges of the slow-and-flat stints that were too short to cut.
    """
    excise = np.zeros(t.size, dtype=bool)
    suspect: list[tuple[int, int]] = []
    if t.size < 3:
        return excise, suspect
    dt = np.diff(t)
    step = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    with np.errstate(divide="ignore", invalid="ignore"):
        slow = np.where(dt > 0, step / dt, 0.0) < trimming.takeoff_speed_mps
    for start, stop in _runs(slow):
        stop = stop + 1  # a run of steps [start, stop) spans the fixes [start, stop]
        span = t[stop - 1] - t[start]
        if span < min(suspect_min_span_s, trimming.interior_ground_s):
            continue
        if not _is_flat(
            t[start:stop],
            alt[start:stop],
            trimming.ground_flatness_m,
            max_drift_mps,
        ):
            continue
        if span >= trimming.interior_ground_s:
            excise[start:stop] = True
        else:
            suspect.append((start, stop))
    return excise, suspect
