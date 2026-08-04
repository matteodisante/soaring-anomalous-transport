"""Stage (iv): flight-level filtering (thesis, sec:flightfilter).

After cleaning and trimming some flights are still unfit for the ensemble analysis and
are dropped whole. The step is delicate, because too aggressive a cut biases the
transport statistics in a specific direction: a high minimum duration preferentially
keeps successful long flights and inflates the apparent MSD exponent at long lags, since
the flights that survive such a cut are the ones that kept going.

The strategy is therefore **minimal-threshold**: for each criterion the cut is the
smallest value that still clears the non-genuine flights -- sled runs, tows, aborted or
truncated logs -- so the ensemble is disturbed as little as possible. "Minimal" is read
off the data rather than guessed: each cut sits where the retained-fraction curve is
flat, which is precisely the statement that moving it changes almost nothing, i.e. that
it removes junk and not signal.

Three criteria gate a flight, all evaluated on the trimmed **parent**:

* *duration* -- at least ``min_duration_s`` of *recorded flight*, summed over blocks
  and never across a gap, since a cross-country flight spans many climb-glide cycles;
  and a *span* of at most ``max_duration_s``, a daylight sanity bound that removes
  loggers left running past the flight, whose multi-hour "flights" would poison every
  long-lag analysis. The two bounds deliberately read different quantities. The floor
  asks how much flight was recorded, so it must not count the holes; the ceiling asks
  how long the recorder ran, so it must -- a logger left going overnight is mostly
  hole, and a ceiling read on the gap-excluding sum would stop catching the very case
  it exists for;
* *path length* -- the summed great-circle steps, a floor against degenerate logs;
* *altitude activity* -- the total range of the adopted channel. A positive statement
  about what the flight did, not merely a guard against a dead sensor: a cross-country
  flight lives by climbing, so a record spanning less than that over 40 minutes was not
  soaring;
* *reach* -- no fix may lie further from the first than ``v_xy_max`` could have carried
  it in the time elapsed since: ``|r(t)| <= v_xy_max t``, because the flight started
  there. Stated per fix, and not as the extent against the whole duration, so that it
  is the *same statement* ``verify_dataset.py`` checks on the written table; the weaker
  form would let a fix 100 km out ten seconds in pass, on the grounds that the flight
  went on for three hours. This catches the one defect a per-step rule cannot see,
  because every step of such a flight is plausible: the corrupt fix is the *first* one,
  and it is about to become the origin of the local frame, so the whole trajectory is
  displaced by it. Five paraglider flights sat 4500 km from their own origin -- and five
  in 156017 moved the ensemble MSD by seven orders of magnitude;
* *plausibility of the cleaned record* -- the mean ground speed, ``path / duration``,
  must not exceed the discipline's own fix-level speed bound. A sanity bound of exactly
  the kind the upper duration cut already is, and needed for the same reason: a handful
  of logs are corrupt beyond what fix-level cleaning can repair -- runs of null-island
  ``(0, 0)`` positions scattered through the track -- and each surviving jump adds
  thousands of kilometres of path that were never flown. Asking a *whole-flight average*
  to stay under the bound that already marks a single step impossible is the weakest
  statement that catches them. On the present archive it fires on *no* flight: an
  impossible step is made a segment boundary at the fix level and a long gap is left out
  of the sum below, so the path reaching this test holds only motion, and such a record
  is refused by the reach criterion instead. The cut stays as the cheapest check on that
  chain: if an impossible length ever re-enters the path, its count stops being zero.

The cuts act on the parent even when trimming or cleaning has already split it: the
duration is the sum of its blocks' durations and the path the sum of their path lengths,
never summed across a cut, where the trajectory is unknown. They are **not** re-applied
per segment later -- a segment is short because a gap fell there, which says nothing
about whether the flight was a genuine cross-country one, and re-applying a whole-flight
criterion to a fragment would discard precisely the data recorded around gaps.

Every drop carries its reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..preprocessing import great_circle_m

if TYPE_CHECKING:
    from ..preprocessing import FlightLevelThresholds, SamplingThresholds

DROP_TOO_SHORT = "duration_below_minimum"
DROP_TOO_LONG = "duration_above_maximum"
DROP_SHORT_PATH = "path_below_minimum"
DROP_FLAT = "altitude_range_below_minimum"
DROP_IMPLAUSIBLE = "mean_ground_speed_above_the_fix_level_bound"
DROP_UNREACHABLE = "extent_out_of_reach_of_the_first_fix"

# Slack on the reach test, in metres. It exists for the same reason the dataset
# verifier's does, and carries the same value on purpose: the two must be the same
# statement, or the pipeline can write a table its own checker rejects.
REACH_TOLERANCE_M = 50.0


@dataclass(frozen=True)
class FlightVerdict:
    """The three whole-flight quantities and the verdict on them.

    Attributes:
        duration_s: Airborne duration, summed over the blocks a split left.
        path_km: Flown path length, summed the same way -- never across a cut.
        alt_range_m: Total range of the adopted altitude channel over the airborne
            track (``nan`` if the channel has no value at all).
        extent_km: The farthest any fix lies from the first, in kilometres.
        drop_reason: ``None`` when the flight passes, otherwise the first criterion it
            failed, in the order duration, path, altitude activity.
    """

    duration_s: float
    path_km: float
    alt_range_m: float
    extent_km: float
    drop_reason: str | None


def flight_quantities(
    fixes: pd.DataFrame,
    sampling: SamplingThresholds | None = None,
) -> tuple[float, float, float, float, np.ndarray, np.ndarray]:
    """Duration, path length and altitude range of one trimmed flight.

    Blocks are delimited by the ``split_before`` markers stages (ii) and (iii) left --
    an excised frozen-lock run, a re-acquisition offset, a mid-flight landing -- and by
    any inter-fix gap the resampling would later split at. Duration and path are
    accumulated inside a block and never across the cut that ends it: the trajectory
    there is unknown, and a straight line drawn over it would be counted as flown.

    The gap is the second half of that rule and was missing. A marker is left where a
    *stage* decided something; a long hole in the log is nobody's decision, so no marker
    describes it, and it arrives here unannounced -- while being exactly the case the
    rule is about. Ten minutes of missing record were counted as ten minutes of flight
    and six kilometres of straight line as six kilometres flown. The bound is the same
    ``g_max`` stage (vi) will use, computed from the flight's own cadence, so the two
    stages cut at the same places and a flight cannot be measured over intervals it will
    not be analysed over.

    Args:
        fixes: The trimmed flight, with ``t``, ``lat``, ``lon``, ``alt`` and optionally
            ``split_before``.
        sampling: The resampling thresholds, used only for ``g_max``. ``None`` keeps the
            markers as the only cuts, which is what a caller that has no configuration
            can honestly do.

    Returns:
        ``(duration_s, path_km, alt_range_m, extent_km, reach_m, elapsed_s)``, the
        last two being per-fix arrays: the great-circle distance from the first fix, and
        the time elapsed since it.
    """
    t = fixes["t"].to_numpy(dtype=float)
    if t.size < 2:
        empty = np.zeros(t.size)
        return 0.0, 0.0, float("nan"), 0.0, empty, empty
    lat = fixes["lat"].to_numpy(dtype=float)
    lon = fixes["lon"].to_numpy(dtype=float)
    alt = fixes["alt"].to_numpy(dtype=float)
    cut = (
        fixes["split_before"].to_numpy(dtype=bool)[1:]
        if "split_before" in fixes.columns
        else np.zeros(t.size - 1, dtype=bool)
    )
    gaps = np.diff(t)
    if sampling is not None:
        from .resample import split_bound_s

        dt_native = float(np.median(gaps[gaps > 0])) if (gaps > 0).any() else 0.0
        if dt_native > 0:
            cut = cut | (gaps > float(split_bound_s(dt_native, sampling)))
    step = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    within = ~cut
    duration = float(gaps[within].sum())
    path_km = float(step[within].sum()) / 1000.0
    alt_range = (
        float(np.nanmax(alt) - np.nanmin(alt))
        if np.isfinite(alt).any()
        else float("nan")
    )
    # The extent, and with it the strongest form of the same statement: how far any fix
    # lies *beyond* what the bound allows in the time elapsed to reach it. Comparing the
    # extent against the whole flight's duration would be far weaker -- a fix 100 km out
    # ten seconds in passes that, because the flight went on for three hours -- and it
    # is not the invariant the table is checked against, which is stated per fix.
    reach = great_circle_m(lat[0], lon[0], lat, lon)
    extent_km = float(reach.max()) / 1000.0
    return duration, path_km, alt_range, extent_km, reach, t - t[0]


def filter_flight(
    fixes: pd.DataFrame,
    flight_level: FlightLevelThresholds,
    *,
    max_mean_speed_mps: float | None = None,
    sampling: SamplingThresholds | None = None,
) -> FlightVerdict:
    """Run stage (iv) over one trimmed flight.

    Args:
        fixes: The trimmed flight (stage (iii) output).
        flight_level: The adopted cuts.
        max_mean_speed_mps: The plausibility bound on the mean ground speed; the driver
            passes the discipline's fix-level ``max_horizontal_speed_mps``. ``None``
            skips the check.
        sampling: The resampling thresholds. Passed only so that the duration and the
            path stop at the gaps stage (vi) will split at, and not merely at the
            markers the earlier stages left; ``None`` keeps the markers alone.

    Returns:
        The :class:`FlightVerdict`. A flight with an altitude channel that carries no
        value at all cannot be judged on activity and is not dropped for it: the
        criterion abstains rather than condemning on missing evidence.
    """
    duration, path_km, alt_range, extent_km, reach_m, elapsed_s = flight_quantities(
        fixes, sampling
    )
    if duration < flight_level.min_duration_s:
        reason = DROP_TOO_SHORT
    elif elapsed_s[-1] > flight_level.max_duration_s:
        # The *span*, not the airborne sum, and the two stopped being the same the
        # day the sum learned to skip long gaps. This bound is a daylight sanity
        # check on the record -- it removes a logger left running for sixteen hours
        # -- and such a record is mostly gaps, so a bound read on the gap-excluding
        # sum stops catching exactly the case it was calibrated on. The lower bound
        # keeps the sum, because there the question is the opposite one: how much
        # flight was actually recorded.
        reason = DROP_TOO_LONG
    elif path_km < flight_level.min_path_km:
        reason = DROP_SHORT_PATH
    elif np.isfinite(alt_range) and alt_range < flight_level.min_alt_range_m:
        reason = DROP_FLAT
    elif (
        max_mean_speed_mps is not None
        and duration > 0
        and 1000.0 * path_km / duration > max_mean_speed_mps
    ):
        reason = DROP_IMPLAUSIBLE
    elif max_mean_speed_mps is not None and bool(
        (reach_m > max_mean_speed_mps * elapsed_s + REACH_TOLERANCE_M).any()
    ):
        # Out of reach of its own first fix: the flight cannot have travelled that
        # far from where it started. The cause is always the same -- the *first* fix
        # is the corrupt one, so every step is plausible and the whole track is
        # displaced -- and it is fatal in a way a bad step is not, because that fix
        # is about to become the origin of the frame every coordinate is measured in.
        reason = DROP_UNREACHABLE
    else:
        reason = None
    return FlightVerdict(
        duration_s=duration,
        path_km=path_km,
        alt_range_m=alt_range,
        extent_km=extent_km,
        drop_reason=reason,
    )
