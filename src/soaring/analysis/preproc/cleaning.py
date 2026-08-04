"""Stage (ii): fix-level cleaning (thesis, sec:fixlevel and impl:fixlevel).

Corrupt or physically impossible fixes must go without discarding the flight around
them. Every removed fix also modifies the trajectory whose statistics are about to be
measured, so an over-aggressive cleaning biases the result as much as dirty data would.
The cleaning therefore assumes as little as possible about the motion -- only smoothness
at the sampling scale, never a model of the transport -- and **defaults to keeping**: a
fix is removed only on positive evidence of a defect.

The two errors are not symmetric. A spurious fix that survives lies at worst a speed
bound times a native step from the true track, tens of metres, which the smoothing
absorbs. A genuine fix removed from a slow, horizontally localized phase -- a search, a
climb -- erases a real trapping event, and nothing downstream can restore it.

**The invariant**: a usable horizontal position is never discarded. A fix is deleted
only
when its own position or timestamp is corrupt or invented; when only the altitude is
wrong, the fix stays and that channel is marked missing, restored once at resampling
(sec:uniform). The asymmetry is deliberate: ten kept-but-positionless fixes would look
to the resampler like ten samples of a continuously recorded stretch, the gap rule would
never fire, and an invented straight line would be laid across an interval that may hold
a full thermalling circle. Deleting them leaves the hole visible.

Everything runs on the **raw geodetic coordinates**, before the Cartesian conversion, so
distances are great-circle (haversine): replacing the ellipsoid by a sphere perturbs an
inter-fix distance by at most ~0.3 %, about 3 cm on a 10 m step, far below the
metre-scale GPS noise on the same quantity.

The detectors run in a fixed order, and the order matters -- a speed or a residual is
only meaningful once the time base is monotone and free of duplicates:

1. **time defects** -- backward steps by minimal removal, then duplicate seconds merged
   to their centroid;
2. **position outliers** -- the Hampel identifier *flags*, and an absolute ``v_xy``
   bound must corroborate before anything is deleted;
3. **frozen-lock runs** -- cut only on three agreeing signatures, and marked as a gap;
4. **altitude** -- absolute bounds only, no local test.

Why no Hampel test on the altitude, when there is one on the position (sec:fixlevel):
an absolute bound is *sufficient* on ``z`` and insufficient on ``xy`` -- the vertical
envelope is narrow and known, while a 50 m horizontal spike is impossible at a 1 s
cadence and unremarkable at 10 s; a local test on ``z`` would flag the physics, since
the
residual from a local median is largest exactly at the thermal entries the segmentation
is built on; and the costs differ, because an interpolation laid across a thermal entry
erases the transition rather than restoring it.

The **integrity gate** is not applied here. It counts over the *airborne* window --
defects in a ground phase that trimming removes anyway must not condemn a flight -- and
that window does not exist until stage (iii) has run. :func:`integrity_gate` is
therefore
called by the driver, after trimming, with the record this stage returns.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..census import great_circle_m

if TYPE_CHECKING:
    from ..config import FixLevelThresholds

# Per-fix columns this stage adds. `split_before` is consumed by stage (vi), which
# realises the cut; the other two are the per-fix record of what the cleaning did, and
# travel all the way into the `fixes` table.
CLEANING_COLUMNS = ["hampel_flagged", "alt_invalidated", "split_before"]

# Why a fix was deleted. Recorded per fix, not merely counted: the removal audit of
# sec:fixlevel needs to know which rule fired, and where.
REMOVED_BACKWARD_TIME = "backward_timestamp"
REMOVED_POSITION_SPIKE = "position_spike"
REMOVED_FROZEN_RUN = "frozen_lock_run"

# The flight-level verdict of :func:`integrity_gate`.
DROP_INTEGRITY = "cleaning_rebuilt_too_much"

# Rescales the median absolute deviation into an estimate of a Gaussian standard
# deviation (thesis, Eq. eq:hampel).
_MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class CleaningReport:
    """What the cleaning did to one flight: the per-rule counters of the audit.

    Every field is a count, and every count is over the whole flight; the integrity gate
    re-counts the deletions over the airborne window alone. ``n_flagged_kept`` is the
    number the thesis calls the per-flight anomaly count: fixes the Hampel identifier
    flagged but the speed bound refused to condemn, kept and recorded.
    """

    n_fix_raw: int
    n_fix_clean: int
    n_merged_duplicates: int
    n_removed_backward: int
    n_removed_spike: int
    n_removed_frozen: int
    n_alt_out_of_band: int
    n_alt_vz_spike: int
    n_flagged_kept: int
    n_splits: int
    n_vz_runs: int
    n_alt_level_shift: int
    split_jump_max_m: float
    n_v_flag: int
    n_boundaried: int


@dataclass(frozen=True)
class Cleaned:
    """One flight after stage (ii).

    Attributes:
        fixes: The surviving fixes, with :data:`CLEANING_COLUMNS` added and the adopted
            ``alt`` set to ``nan`` wherever the cleaning invalidated it.
        removed: One row per deleted fix -- ``t`` and ``reason`` -- so the removals can
            be counted inside any window and attributed to the rule that made them.
        report: The per-rule counters.
    """

    fixes: pd.DataFrame
    removed: pd.DataFrame
    report: CleaningReport


def longest_non_decreasing(values: np.ndarray) -> np.ndarray:
    """Indices of a longest non-decreasing subsequence of ``values``.

    The minimal-removal rule for backward timestamps (impl:fixlevel): delete the
    smallest set of fixes whose removal leaves a clock that never goes back, i.e. keep a
    longest non-decreasing subsequence. Ties are kept, because two fixes in one UTC
    second are a *duplicate*, handled by the merge that runs next, not a backward step.

    The naive alternative -- clamping with a running maximum, as the parser used to --
    would condemn every fix after a single forward-jumped clock instead of the one fix
    that carries the corrupt time.

    Args:
        values: The (possibly non-monotonic) timestamps.

    Returns:
        The kept indices, ascending. Patience sorting, ``O(n log n)``.
    """
    tails: list[float] = []
    tail_index: list[int] = []
    predecessor = np.full(values.size, -1, dtype=np.int64)
    for i, value in enumerate(values):
        pos = bisect.bisect_right(tails, value)
        if pos:
            predecessor[i] = tail_index[pos - 1]
        if pos == len(tails):
            tails.append(value)
            tail_index.append(i)
        else:
            tails[pos] = value
            tail_index[pos] = i
    keep: list[int] = []
    node = tail_index[-1] if tail_index else -1
    while node >= 0:
        keep.append(node)
        node = int(predecessor[node])
    return np.array(keep[::-1], dtype=np.int64)


def unwrap_longitude(lon_deg: np.ndarray) -> np.ndarray:
    """Put a flight's longitudes on one continuous branch, across the antimeridian.

    Three of the detectors here work *componentwise* on longitude -- the Hampel window
    median, the bounding box of a candidate frozen run, the centroid of a duplicate
    second -- and every one of them is wrong on a track that crosses 180 degrees, where
    consecutive fixes are written ``+179.99`` and ``-179.99``.

    The failure is not the obvious one. Great-circle distance is *correctly* aware of
    the wrap, so the two numerical extremes of a straddling window read as five metres
    apart: the bounding box of a wing moving at 12 m/s collapses to nothing and the
    frozen-lock rule fires on genuine motion. The componentwise mean fails the other
    way, placing the centroid of ``+179.99`` and ``-179.99`` at longitude zero -- the
    null island, which is the very artefact the cleaning exists to remove.

    Unwrapping once, here, fixes all three: on a continuous branch (``179.99``,
    ``180.01``, ...) a median, a min, a max and a mean all mean what they say. Nothing
    downstream minds -- distances and the ENU rotation are trigonometric and periodic --
    so only the stored coordinate is wrapped back, at the end of the pass.

    Today's archive never triggers this: the FFVL flights reach 169 degrees east and 150
    west. It is the further, non-French sources that would.

    Args:
        lon_deg: Longitudes in degrees.

    Returns:
        The same longitudes on a branch with no jumps, possibly outside [-180, 180].
    """
    return np.degrees(np.unwrap(np.radians(lon_deg)))


def wrap_longitude(lon_deg: np.ndarray) -> np.ndarray:
    """Bring longitudes back into ``[-180, 180)``, the convention readers expect."""
    return ((np.asarray(lon_deg, dtype=float) + 180.0) % 360.0) - 180.0


def hampel_flags(
    t: np.ndarray, lat: np.ndarray, lon: np.ndarray, fix_level: FixLevelThresholds
) -> np.ndarray:
    """The Hampel identifier on the horizontal position (thesis, Eq. eq:hampel).

    In the window of fixes within ``+/- w`` of ``t_k``, take the componentwise medians
    of
    latitude and longitude; the residual ``r_k`` is the great-circle distance of the fix
    from that median point, and the local scale is ``sigma_k = 1.4826 med{r_j}`` over
    the
    same window. The fix is flagged when ``r_k > max(k sigma_k, eps_min)``.

    Both halves of that threshold earn their place. The multiple of ``sigma_k`` makes
    the
    test context-sensitive -- a 30 m/s step out of a 12 m/s glide is flagged, the same
    step passes where it is ordinary -- and the floor ``eps_min`` stops the test chasing
    GPS noise on a very smooth stretch, where ``sigma_k -> 0`` and any sub-metre wiggle
    would otherwise clear ``k sigma_k``.

    The window is a *time* window, not a sample count, so it adapts to the native
    cadence
    and to irregular sampling. Where it holds fewer than ``hampel_min_window_fixes``,
    the
    local scale is not estimable and the fix is left to the absolute bounds alone.

    This is the *identifier*, the detection half of the eponymous filter, never the
    median-substituting filter: the local median enters only as the reference for the
    residual, never as an output value. A flag does not delete on its own.

    Args:
        t: Fix times in seconds, strictly increasing.
        lat: Latitudes in degrees.
        lon: Longitudes in degrees.
        fix_level: The adopted thresholds.

    Returns:
        A boolean array, ``True`` where the fix is off the local trend.
    """
    index = pd.to_timedelta(t, unit="s")
    roll = {
        "window": pd.Timedelta(seconds=2.0 * fix_level.hampel_window_s),
        "center": True,
        "closed": "both",  # the inclusive |t_j - t_k| <= w of eq:hampelresid
        "min_periods": 1,
    }
    med_lat = pd.Series(lat, index=index).rolling(**roll).median().to_numpy()
    med_lon = pd.Series(lon, index=index).rolling(**roll).median().to_numpy()
    populated = pd.Series(lat, index=index).rolling(**roll).count().to_numpy()
    residual = great_circle_m(lat, lon, med_lat, med_lon)
    mad = pd.Series(residual, index=index).rolling(**roll).median().to_numpy()
    threshold = np.maximum(
        fix_level.hampel_k * _MAD_TO_SIGMA * mad, fix_level.hampel_eps_min_m
    )
    return (populated >= fix_level.hampel_min_window_fixes) & (residual > threshold)


def _step_speeds(t: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Horizontal speed between consecutive fixes, in m/s (``inf`` on a zero step)."""
    dt = np.diff(t)
    step = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dt > 0, step / dt, np.inf)


def _scan_positions(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    flagged: np.ndarray,
    max_speed_mps: float,
    block_span_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """One left-to-right scan: delete corroborated spikes, split at discontinuities.

    The scan carries the last accepted fix as an anchor, so it never re-walks the track.
    What condemns a fix is the **impossibility gate**: it is unreachable from the last
    accepted fix at the absolute speed bound, and removing the block it belongs to makes
    the bracketing neighbours rejoin within that bound. Both halves matter. The first
    keeps a genuine tight thermalling circle safe -- its fixes sit on opposite sides of
    their own window median, but a circling wing flies at an ordinary speed and is never
    a candidate. The second is what attributes the defect: a speed belongs to the
    segment *between* two fixes and does not say which endpoint is wrong, and the block
    whose removal restores the trend is the answer.

    The Hampel flag is recorded for every fix (the per-flight anomaly count) but is not
    required for the deletion, and that is a deliberate departure from the
    two-conditions rule as sec:fixlevel first stated it. The reason is the identifier's
    own 50 % breakdown point. Where more than half of a window is corrupt -- runs of
    null-island ``(0, 0)`` fixes are the case seen in the archive -- the *median itself*
    moves onto the corruption, the corrupt fixes score a residual of zero and go
    unflagged, and it is the good fixes around them that get flagged instead. Requiring
    the flag there does not make the rule conservative, it makes it blind, and what
    survives is a 5000 km step. The impossibility gate has no local scale in it, so
    contamination cannot break it; the protection the flag was there to provide -- never
    cutting a real manoeuvre -- is provided by the speed bound itself.

    A burst is absorbed as one block, the smallest whose removal lets the trend rejoin.
    When no removal restores continuity -- a re-acquisition offset, where the track
    jumps and stays -- the scan stops deleting and marks a split at the step: both sides
    are genuine, only the transition between them is unknown.

    Args:
        t: Fix times, strictly increasing.
        lat: Latitudes in degrees.
        lon: Longitudes in degrees.
        flagged: The Hampel flags, recorded per fix.
        max_speed_mps: The discipline's absolute horizontal-speed bound.
        block_span_s: Longest a tentatively removed block may run before the scan calls
            the step a discontinuity instead. It bounds what an excursion deletion can
            cost in genuine samples, and it sets the scale at which the two cases part:
            an offset smaller than ``max_speed_mps * block_span_s`` becomes reachable
            from the anchor before the cap expires and is therefore removed as an
            excursion rather than split. That is a real limit of the rule, and a bounded
            one -- at most this many seconds of genuine fixes, at a discontinuity.

    Returns:
        ``(delete, split_before)``, two boolean arrays over the fixes. The invariant
        that no impossible step survives inside a segment is *not* established here:
        two later passes still delete fixes, so it is enforced once, on the final
        surviving set, by :func:`_boundary_impossible_steps`.
    """
    n = t.size
    delete = np.zeros(n, dtype=bool)
    split = np.zeros(n, dtype=bool)
    step_speed = _step_speeds(t, lat, lon)
    # The overwhelmingly common case: nothing off the trend and no impossible step, so
    # the scan below would accept every fix in turn. Skipping it keeps the archive-wide
    # cost in the parser rather than in this loop.
    if not flagged.any() and np.all(step_speed <= max_speed_mps):
        return delete, split

    anchor = 0
    pending: list[int] = []
    for i in range(1, n):
        if not pending and step_speed[i - 1] <= max_speed_mps:
            anchor = i
            continue
        gap = t[i] - t[anchor]
        reach = great_circle_m(lat[anchor], lon[anchor], lat[i], lon[i])
        speed = reach / gap if gap > 0 else np.inf
        if speed <= max_speed_mps:
            delete[pending] = True  # this block's removal restored the trend
            pending = []
            anchor = i
        elif not pending or t[i] - t[pending[0]] <= block_span_s:
            pending.append(i)
        else:
            split[pending[0]] = True
            pending = []
            anchor = i
    if pending:
        # A block still open when the track ends is the mirror of one that opens it, and
        # takes the mirror decision. The scan never got to finish its argument here:
        # a block is confirmed corrupt by the track *rejoining* after it, and there is
        # no after. What can be said is that the block is short -- the loop splits and
        # resets as soon as a block outlives `block_span_s`, so one still pending at the
        # end spans at most that -- and that the two readings of it cost very different
        # amounts. If the block is corrupt, deleting it costs seconds near the landing,
        # which the trimming would very likely take anyway. If instead the *anchor* were
        # the corrupt one, keeping the block would mean trusting a handful of fixes over
        # the whole flight that preceded them. And keeping it is not free: the fix stays
        # in the record, becomes the farthest point from the origin, and the flight is
        # refused whole by the reach bound of sec:flightfilter -- one corrupt trailing
        # fix discarding four thousand seconds of perfect flight.
        delete[pending] = True

    # There is no rule here for a corrupt block that *opens* the record, and its
    # absence is the decision rather than an omission. Such a block is real: the
    # first fix of the trimmed track becomes the origin of the local frame
    # (sec:enu), so a corrupt one displaces every coordinate of the flight, and five
    # paraglider flights sat 4500 km from their own origin because of it. The
    # temptation is to delete the prefix.
    #
    # It was tried twice, and both rules were wrong, in opposite directions. Firing
    # on the first impossible step accuses the *earlier* end always, so an ordinary
    # spike three seconds in deleted the good fixes and promoted the spike to
    # origin. Firing instead on a split the scan declares near the start looks sound
    # -- a split means no bounded removal after the step restored the trend -- but
    # the split index is `pending[0]`, the first fix of the block that could not be
    # rejoined, and that block is *after* the step whenever the corruption simply
    # outlasts `block_span_s`. A 50 s corrupt run five seconds in therefore deleted
    # five good fixes, kept fifty bad ones, and left the origin 5039 km out. The
    # scan's verdict says a discontinuity exists; it does not say which side of it
    # the record belongs to, and at the very start there is no trend behind the step
    # to settle it.
    #
    # So the discontinuity is left as a discontinuity, and the guarantee is taken
    # where it can be stated without attributing blame: at the flight level, where a
    # record whose own first fix is out of reach of the rest is refused whole
    # (sec:flightfilter). That bound never depended on this rule. What the rule
    # would have bought is the recovery of two flights in 156017 -- against a
    # failure mode that has now been demonstrated twice.

    # Postcondition, and the reason it is stated as one rather than left to the scan:
    # whatever the scan decided, no step *between two surviving fixes* may still break
    # the absolute bound. Where the scan keeps a block it could neither rejoin nor
    # explain, the step back out of that block is exactly such a step, and without this
    # it would enter a segment as flown motion -- a 40 km jump inside one second, which
    # then carries every average computed over that segment. A step the bound rejects
    # is a transition of unknown course, so it is made a boundary, on the same footing
    # as a long gap. It is enforced on the final surviving set, in `clean_flight`.
    return delete, split


def _frozen_runs(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    alt: np.ndarray,
    valid: np.ndarray,
    fix_level: FixLevelThresholds,
    alt_source: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Frozen-lock runs: the three-signature rule of Eq. eq:frozenlock.

    When the receiver loses its lock, many loggers repeat the last position for tens of
    seconds while the clock keeps running. Such a run passes every other test -- speed
    zero, altitude in range, valid timestamps -- and if kept it enters the analysis as a
    long *waiting time*, contaminating exactly the tail of ``psi(tau)`` where the
    anomalous exponent is read. Cutting too eagerly is the mirror error: tight
    thermalling climbs are also slow and horizontally localized, and an erased trapping
    event is unrecoverable where a kept freeze is merely flagged.

    A run is cut only when three independent signatures agree:

    (i) *collapsed* -- the run is the maximal stretch whose bounding diameter stays
    below
        ``delta_xy``. A circling wing traces a disc of 30-100 m, above ``delta_xy`` by a
        factor of at least two, and clears the test on the diameter alone;
    (ii) *witnessed* -- on a barometric flight by a flat barometer, since a lock loss
        freezes the GNSS position while the pressure sensor, a separate instrument,
        keeps
        recording a real climb; on a GNSS-fallback flight by the recorder's own
        declarations, which is all that is left, because the GNSS altitude comes from
        the
        very receiver whose lock is in doubt. A byte-identical repeat of the coordinates
        overrules either: no moving receiver rewrites the same bits;
    (iii) *long enough* -- at least ``tau_freeze``, about two thermalling periods, so a
        run long enough to be cut spans at least two full circles of any genuine climb,
        whose diameter test (i) then sees in full.

    Below ``tau_freeze`` the rule deliberately abstains: at a few tens of seconds a
    collapsed run and a genuine slow stretch are not distinguishable by these
    signatures,
    and a kept short freeze lengthens one waiting time by at most ``tau_freeze``, where
    a
    wrongly cut climb removes one outright.

    Returns:
        ``(delete, split_before)``: the run's fixes are deleted -- the positions are
        invented -- and the fix after the run is marked, so the trajectory is split
        there
        rather than interpolated across even at a cadence whose gap bound would
        otherwise
        bridge the hole the deletion leaves.
    """
    n = t.size
    delete = np.zeros(n, dtype=bool)
    split = np.zeros(n, dtype=bool)
    if n < 2:
        return delete, split

    # Two families of candidate run, because the byte-identical signature has to be
    # tested on the stretch that actually is byte-identical: a greedy collapsed run
    # reaches one fix past the freeze -- the wing has not yet moved delta_xy away -- and
    # that one fix would break an exact-equality test that is meant to be conclusive.
    runs = _identical_runs(lat, lon) + _collapsed_runs(t, lat, lon, fix_level)
    for i, j in runs:
        if t[j] - t[i] < fix_level.frozen_tau_s:
            continue
        if _is_witnessed(
            lat[i : j + 1],
            lon[i : j + 1],
            alt[i : j + 1],
            valid[i : j + 1],
            fix_level,
            alt_source,
        ):
            delete[i : j + 1] = True
    # One split per deleted block, at the first fix that survives it.
    edges = np.flatnonzero(np.diff(np.concatenate([[False], delete, [False]])))
    for stop in edges[1::2]:
        if stop < n:
            split[stop] = True
    return delete, split


def _identical_runs(lat: np.ndarray, lon: np.ndarray) -> list[tuple[int, int]]:
    """Maximal runs of byte-identically repeated coordinates, as inclusive ranges.

    Exact equality on the decoded values, which is exactly the test on the raw record:
    the ``DDMM.mmm`` field is a fixed-width integer count of thousandths of an arc-
    minute,
    so the decode is injective and two records are byte-identical in latitude and
    longitude iff their decoded values compare equal.
    """
    same = (lat[1:] == lat[:-1]) & (lon[1:] == lon[:-1])
    edges = np.flatnonzero(np.diff(np.concatenate([[False], same, [False]])))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2], strict=True)]


def _collapsed_runs(
    t: np.ndarray, lat: np.ndarray, lon: np.ndarray, fix_level: FixLevelThresholds
) -> list[tuple[int, int]]:
    """Maximal runs whose bounding diameter stays below ``delta_xy``, greedily.

    A vectorised pre-filter first: a run that can qualify must keep the wing inside
    ``delta_xy`` for at least ``tau_freeze``, so the bounding box of every trailing
    ``tau_freeze`` window must be that small somewhere. On a real track it never is --
    a glide covers hundreds of metres in a minute -- so the exact scan below runs on a
    vanishing share of the archive's fixes and the whole rule stays linear.
    """
    eps = fix_level.frozen_eps_m
    index = pd.to_timedelta(t, unit="s")
    roll = {
        "window": pd.Timedelta(seconds=fix_level.frozen_tau_s),
        "closed": "both",
        "min_periods": 1,
    }
    lat_s, lon_s = pd.Series(lat, index=index), pd.Series(lon, index=index)
    diagonal = great_circle_m(
        lat_s.rolling(**roll).min().to_numpy(),
        lon_s.rolling(**roll).min().to_numpy(),
        lat_s.rolling(**roll).max().to_numpy(),
        lon_s.rolling(**roll).max().to_numpy(),
    )
    # A trailing window only means what it says once it *is* a window: with
    # `min_periods=1` the first fix of every flight has a bounding box of zero and would
    # open a candidate region, from which the expansion below walks the whole track --
    # on a 1 Hz flight every consecutive step is under delta_xy, so nothing stops it.
    # Requiring the window to span tau_freeze is the same condition the rule applies
    # anyway, moved to where it saves the work.
    candidate = (diagonal < eps) & ((t - t[0]) >= fix_level.frozen_tau_s)
    if not candidate.any():
        return []

    step = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    small = np.concatenate([step < eps, [False]])
    runs: list[tuple[int, int]] = []
    edges = np.flatnonzero(np.diff(np.concatenate([[False], candidate, [False]])))
    for first, last in zip(edges[::2], edges[1::2], strict=True):
        # The window is a trailing one, so the run may start before the first flagged
        # fix; it may equally continue past the last, as long as the steps stay small.
        start = int(np.searchsorted(t, t[first] - fix_level.frozen_tau_s))
        stop = int(last) - 1
        while stop + 1 < t.size and small[stop]:
            stop += 1
        i = start
        while i <= stop:
            j = i
            lo_lat = hi_lat = lat[i]
            lo_lon = hi_lon = lon[i]
            while j + 1 <= stop:
                new = (
                    min(lo_lat, lat[j + 1]),
                    min(lo_lon, lon[j + 1]),
                    max(hi_lat, lat[j + 1]),
                    max(hi_lon, lon[j + 1]),
                )
                if float(great_circle_m(*new)) >= eps:
                    break
                lo_lat, lo_lon, hi_lat, hi_lon = new
                j += 1
            runs.append((i, j))
            i = j + 1
    return runs


def _is_witnessed(
    lat: np.ndarray,
    lon: np.ndarray,
    alt: np.ndarray,
    valid: np.ndarray,
    fix_level: FixLevelThresholds,
    alt_source: str,
) -> bool:
    """The witness ``W`` of Eq. eq:frozenlock, for one candidate run."""
    byte_identical = bool(np.all(lat == lat[0]) and np.all(lon == lon[0]))
    if byte_identical:
        # Exact equality and no tolerance: a tolerance would turn the one conclusive
        # signature into the jittering-freeze case it exists to exclude.
        return True
    if alt_source == "baro":
        # Between medians of the run's ends, so an altitude spike inside the run -- not
        # yet cleaned, the altitude pass runs last -- cannot fake a climb.
        end = max(1, alt.size // 4)
        if not (np.isfinite(alt[:end]).any() and np.isfinite(alt[-end:]).any()):
            return False  # no barometer to witness with: in doubt, the run is kept
        head, tail = np.nanmedian(alt[:end]), np.nanmedian(alt[-end:])
        return abs(tail - head) < fix_level.frozen_delta_z_m
    # GNSS fallback: the recorder's own declarations are the only witness left, and they
    # must speak for the run rather than for a stray fix in it.
    declared = ~valid.astype(bool) | ~np.isfinite(alt)
    return bool(declared.mean() > 0.5)


def _largest_boundary_jump(fixes: pd.DataFrame) -> float:
    """The largest displacement across a boundary this stage declared, in metres.

    A boundary is a statement that the trajectory between two fixes is unknown, and the
    two kinds this stage produces differ in a way that matters downstream. Excising a
    frozen-lock run leaves the position on either side genuine; splitting at a
    re-acquisition offset does not, because the jump is the instrument's and everything
    after it carries an unknown constant. Segments keep the parent's origin
    (sec:uniform), so that constant enters the *ensemble* MSD, which is built from
    absolute position -- while leaving the time-averaged one, built from increments,
    untouched.

    Measured on the cleaned track, which is *before* trimming, so it is an upper bound
    on the displacement that actually reaches the analysis rather than that displacement
    itself -- a jump inside a ground phase counts here and is then trimmed away. On the
    archive the two differ at the tail and nowhere else: the largest value over retained
    paraglider flights is thousands of kilometres while their largest retained extent is
    555 km, which is exactly such a ground-phase jump. The quantity that matters is the
    displacement across a boundary of a *retained* segment, and it is measured where it
    can be measured honestly -- on the written table, by ``scripts/verify_dataset.py``,
    which streams it anyway.

    No rule is applied to either: the effect is small and bounding it is worth more than
    guessing at it. On a sample of the archive the median such displacement is 20 m for
    paragliders and 80 m for hang gliders, the 90th percentile 150 m and 450 m; only
    0.55 % and 1.25 % of flights carry one over a kilometre, and the handful over
    100 km are the corrupt records the reach bound of sec:flightfilter refuses whole.
    Reporting the maximum per flight is what lets that statement be checked rather than
    asserted, and lets an analysis of absolute position exclude on it if it must.
    """
    if "split_before" not in fixes.columns or len(fixes) < 2:
        return 0.0
    at = np.flatnonzero(fixes["split_before"].to_numpy(dtype=bool))
    at = at[at > 0]
    if not at.size:
        return 0.0
    lat = fixes["lat"].to_numpy(dtype=float)
    lon = fixes["lon"].to_numpy(dtype=float)
    return float(great_circle_m(lat[at - 1], lon[at - 1], lat[at], lon[at]).max())


def _clean_altitude(
    t: np.ndarray, alt: np.ndarray, fix_level: FixLevelThresholds
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Absolute bounds on the adopted altitude channel (thesis, tab:cleaning).

    Two rules, both marking the altitude missing and neither touching the fix:

    * *out of band* -- outside the sensor-plausibility window. The lower bound is
      negative, not zero: the barometric altitude is referenced to the ICAO standard
      atmosphere rather than to the day's sea-level pressure, so on a high-pressure day
      a sea-level take-off reads a few tens of metres negative;
    * *isolated vertical spike* -- an altitude the record jumps away from and back to
      within one step each way, both steps past the climb/sink envelope. Requiring the
      *out-and-back* is what implements the isolation check of impl:fixlevel: a
      run-shaped excess of the same size is a sustained manoeuvre -- a spiral dive holds
      15-20 m/s of real sink -- and calls for a raised bound or an exemption, not for
      censoring. Such runs are counted and left alone.

    A third shape exists and is neither of these: a *level shift*, one single super-
    threshold step that is never undone: a barometric re-reference, or a one-record
    corruption. It matches neither rule, so before this counter existed it was
    censored by nothing and counted by nothing, and the smoothing stage
    differentiated it into a vertical velocity of up to 5117 m/s in the written
    table. It is not rare: on a sample of the archive, 8.3 % of paraglider flights
    and 6.2 % of hang-glider flights carry at least one. It is counted here so that
    it is visible and auditable; what to *do* about it is an open decision, since
    the three candidate treatments -- split the flight there, re-reference the
    altitude after it, or invalidate a window around it -- each change a rule the
    thesis argues, and none is implied by the specification (sec:fixlevel).

    Returns:
        ``(out_of_band, vz_spike, n_runs, n_level_shifts)``: two boolean arrays over
        the fixes, the number of coherent super-threshold runs left in place as a
        diagnostic, and the number of unreturned single steps.
    """
    out_of_band = (alt < fix_level.min_altitude_m) | (alt > fix_level.max_altitude_m)
    dt = np.diff(t)
    with np.errstate(invalid="ignore"):
        v_z = np.where(dt > 0, np.diff(alt) / dt, 0.0)
    excess = np.abs(v_z) > fix_level.max_vertical_speed_mps
    excess = np.nan_to_num(excess, nan=False).astype(bool)

    spike = np.zeros(alt.size, dtype=bool)
    if excess.size >= 2:
        both = excess[:-1] & excess[1:]
        opposite = np.sign(v_z[:-1]) * np.sign(v_z[1:]) < 0
        spike[1:-1] = both & opposite
    # A coherent run is two or more consecutive excessive steps that are not an
    # out-and-back pair -- the signature of a genuine manoeuvre, not of a sensor error.
    runs = np.flatnonzero(np.diff(np.concatenate([[False], excess, [False]])))
    n_runs = int(
        sum(
            1
            for start, stop in zip(runs[::2], runs[1::2], strict=True)
            if stop - start >= 2 and not spike[start + 1 : stop].any()
        )
    )
    # A level shift: an isolated excessive step that the record does not come back from
    # within a few samples. "Comes back" is measured against the step itself rather than
    # against an absolute tolerance, so the test scales with the size of the jump.
    isolated = excess.copy()
    if excess.size >= 2:
        isolated[:-1] &= ~excess[1:]
        isolated[1:] &= ~excess[:-1]
    n_level_shifts = 0
    for i in np.flatnonzero(isolated):
        jump = abs(alt[i + 1] - alt[i])
        window = alt[i + 1 : min(i + 6, alt.size)]
        window = window[np.isfinite(window)]
        if not window.size or np.min(np.abs(window - alt[i])) > 0.3 * jump:
            n_level_shifts += 1
    return out_of_band & np.isfinite(alt), spike, n_runs, n_level_shifts


def clean_flight(
    fixes: pd.DataFrame,
    fix_level: FixLevelThresholds,
    *,
    discipline: str,
    alt_source: str = "baro",
) -> Cleaned:
    """Run stage (ii) over one flight, in the fixed detector order.

    Args:
        fixes: The flight after stage (i): columns ``t``, ``lat``, ``lon``, ``alt``,
            ``valid``, plus anything carried. ``t`` may hold backward steps and
            duplicate
            seconds -- repairing them is this stage's first job, not the parser's.
        fix_level: The adopted thresholds.
        discipline: Key into ``max_horizontal_speed_mps`` (``"paragliders"``,
            ``"hang gliders"``): the two types have markedly different speed envelopes,
            so one shared bound is either too loose for the slower or clips the faster.
        alt_source: The channel stage (i) adopted, which decides the frozen-lock
        witness.

    Returns:
        The :class:`Cleaned` record.

    Raises:
        ValueError: If a required column is missing or the discipline has no bound.
    """
    required = ["t", "lat", "lon", "alt", "valid"]
    missing = [c for c in required if c not in fixes.columns]
    if missing:
        raise ValueError(f"the per-fix table is missing the column(s) {missing}")
    if discipline not in fix_level.max_horizontal_speed_mps:
        raise ValueError(
            f"no horizontal-speed bound for discipline {discipline!r}; known: "
            f"{sorted(fix_level.max_horizontal_speed_mps)}"
        )
    max_speed = fix_level.max_horizontal_speed_mps[discipline]
    n_raw = len(fixes)
    removed_t: list[np.ndarray] = []
    removed_reason: list[str] = []

    # (1) Time defects -- backward steps first, so that the duplicate merge and every
    #     window below see a clock that only ever moves forward.
    work = fixes.reset_index(drop=True)
    # Before anything reads a longitude componentwise (see :func:`unwrap_longitude`).
    work["lon"] = unwrap_longitude(work["lon"].to_numpy(dtype=float))
    t = work["t"].to_numpy(dtype=float)
    if t.size and not np.all(np.diff(t) >= 0):
        keep = longest_non_decreasing(t)
        dropped = np.setdiff1d(np.arange(t.size), keep)
        removed_t.append(t[dropped])
        removed_reason += [REMOVED_BACKWARD_TIME] * dropped.size
        work = work.iloc[keep].reset_index(drop=True)
    work, n_merged = _merge_duplicate_seconds(work)

    t = work["t"].to_numpy(dtype=float)
    lat = work["lat"].to_numpy(dtype=float)
    lon = work["lon"].to_numpy(dtype=float)
    alt = work["alt"].to_numpy(dtype=float)
    valid = work["valid"].to_numpy(dtype=bool)
    if t.size < 2:
        return _empty_result(work, n_raw, n_merged, removed_t, removed_reason)

    # (2) Position outliers: the identifier flags, the speed bound corroborates.
    flagged = hampel_flags(t, lat, lon, fix_level)
    spike, split = _scan_positions(
        t, lat, lon, flagged, max_speed, fix_level.hampel_window_s
    )

    # (3) Frozen-lock runs, on the fixes the spike pass leaves standing.
    frozen, frozen_split = _frozen_runs(t, lat, lon, alt, valid, fix_level, alt_source)
    frozen &= ~spike
    split |= frozen_split

    # (4) Altitude: absolute bounds alone, marking missing and never deleting.
    out_of_band, vz_spike, n_vz_runs, n_level_shifts = _clean_altitude(
        t, alt, fix_level
    )
    invalidated = out_of_band | vz_spike
    if alt_source == "gnss":
        # A V flag certifies a degraded GNSS altitude, so on a fallback flight it is the
        # corrupt-altitude case; on a barometric flight the fix is untouched by it.
        invalidated |= ~valid

    deleted = spike | frozen
    # The postcondition, applied where it can hold: after *every* pass that deletes.
    # Enforcing it inside the position scan would be too early -- the frozen-lock pass
    # runs next and its deletions create new adjacencies of their own, one of which can
    # be an impossible step no rule has yet declared a boundary.
    n_boundaried = _boundary_impossible_steps(t, lat, lon, deleted, split, max_speed)
    removed_t += [t[spike], t[frozen]]
    removed_reason += [REMOVED_POSITION_SPIKE] * int(spike.sum())
    removed_reason += [REMOVED_FROZEN_RUN] * int(frozen.sum())

    out = work.loc[~deleted].copy()
    out["lon"] = wrap_longitude(out["lon"].to_numpy(dtype=float))
    out["alt"] = np.where(invalidated[~deleted], np.nan, alt[~deleted])
    out["hampel_flagged"] = flagged[~deleted]
    out["alt_invalidated"] = invalidated[~deleted]
    out["split_before"] = split[~deleted]
    out = out.reset_index(drop=True)

    report = CleaningReport(
        n_fix_raw=n_raw,
        n_fix_clean=len(out),
        n_merged_duplicates=n_merged,
        n_removed_backward=removed_reason.count(REMOVED_BACKWARD_TIME),
        n_removed_spike=int(spike.sum()),
        n_removed_frozen=int(frozen.sum()),
        n_alt_out_of_band=int((out_of_band & ~deleted).sum()),
        n_alt_vz_spike=int((vz_spike & ~deleted).sum()),
        n_flagged_kept=int((flagged & ~deleted).sum()),
        n_splits=int(split[~deleted].sum()),
        n_vz_runs=n_vz_runs,
        n_alt_level_shift=n_level_shifts,
        split_jump_max_m=_largest_boundary_jump(out),
        n_v_flag=int((~valid).sum()),
        n_boundaried=n_boundaried,
    )
    removed = pd.DataFrame(
        {
            "t": np.concatenate(removed_t) if removed_t else np.empty(0),
            "reason": removed_reason,
        }
    )
    return Cleaned(fixes=out, removed=removed, report=report)


def _merge_duplicate_seconds(fixes: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Collapse fixes sharing one UTC second to a single fix at that second's centroid.

    Componentwise and unweighted: the mean of the latitudes and longitudes and the mean
    of the altitude over the members that have one. The ``valid`` flag of the merged fix
    is the logical *and* of the members' -- equivalently, the ``V`` flag is their
    logical *or* -- so a degraded member cannot be averaged away.

    A centroid rather than "keep the first": keeping the first privileges an arbitrary
    member and, for a genuine 2 Hz logger, would silently halve the cadence, whereas the
    centroid is order-independent and the sub-second resolution it discards is discarded
    anyway once the flight is resampled. One dilution case is accepted: if one member is
    itself a position spike, the centroid halves its amplitude before the outlier pass
    sees it; a large spike is still flagged at half size, and one small enough to slip
    under the local scale afterwards is within what the smoother absorbs.
    """
    t = fixes["t"].to_numpy(dtype=float)
    if t.size < 2 or not (np.diff(t) == 0).any():
        return fixes, 0
    grouped = fixes.groupby("t", sort=True)
    merged = grouped.mean(numeric_only=True)
    if "valid" in fixes.columns:
        merged["valid"] = grouped["valid"].all()
    merged = merged.reset_index()
    return merged[[c for c in fixes.columns if c in merged.columns]], t.size - len(
        merged
    )


def _empty_result(
    work: pd.DataFrame,
    n_raw: int,
    n_merged: int,
    removed_t: list[np.ndarray],
    removed_reason: list[str],
) -> Cleaned:
    """A flight left with fewer than two fixes: nothing to test, nothing to detect."""
    out = work.copy()
    if "lon" in out.columns and len(out):
        out["lon"] = wrap_longitude(out["lon"].to_numpy(dtype=float))
    for column in CLEANING_COLUMNS:
        out[column] = np.zeros(len(out), dtype=bool)
    return Cleaned(
        fixes=out,
        removed=pd.DataFrame(
            {
                "t": np.concatenate(removed_t) if removed_t else np.empty(0),
                "reason": removed_reason,
            }
        ),
        report=CleaningReport(
            n_fix_raw=n_raw,
            n_fix_clean=len(out),
            n_merged_duplicates=n_merged,
            n_removed_backward=len(removed_reason),
            n_removed_spike=0,
            n_removed_frozen=0,
            n_alt_out_of_band=0,
            n_alt_vz_spike=0,
            n_flagged_kept=0,
            n_splits=0,
            n_vz_runs=0,
            n_alt_level_shift=0,
            split_jump_max_m=0.0,
            n_v_flag=0,
            n_boundaried=0,
        ),
    )


def integrity_gate(
    cleaned: Cleaned,
    t_on: float,
    t_off: float,
    fix_level: FixLevelThresholds,
) -> tuple[float, str | None]:
    """The flight-level integrity gate, over the airborne window (sec:fixlevel).

    Cleaning acts fix by fix, but it also keeps count of how much it had to do. Past a
    small fraction the flight is being *rebuilt* rather than cleaned, and is dropped
    whole. The counters are taken over the airborne window on purpose: defects in a
    ground phase that trimming removes anyway must not condemn the flight -- which is
    why this is called after stage (iii) and not inside :func:`clean_flight`.

    Merged duplicates are not counted against the flight. A merge repairs the record
    without losing a sample of the path, and counting it would drop every genuine 2 Hz
    logger for having recorded too well.

    Args:
        cleaned: The record :func:`clean_flight` returned.
        t_on: Start of the airborne window, in the flight's own clock.
        t_off: End of the airborne window.
        fix_level: The adopted thresholds.

    Returns:
        ``(fraction, drop_reason)``: the deleted-plus-invalidated share of the airborne
        fixes, and :data:`DROP_INTEGRITY` when it exceeds the gate.
    """
    kept = cleaned.fixes["t"].to_numpy(dtype=float)
    in_window = (kept >= t_on) & (kept <= t_off)
    removed_t = cleaned.removed["t"].to_numpy(dtype=float)
    removed_in_window = int(((removed_t >= t_on) & (removed_t <= t_off)).sum())
    invalidated = int(
        (cleaned.fixes["alt_invalidated"].to_numpy(dtype=bool) & in_window).sum()
    )
    n_airborne_raw = int(in_window.sum()) + removed_in_window
    if n_airborne_raw == 0:
        return 0.0, None
    fraction = (removed_in_window + invalidated) / n_airborne_raw
    reason = DROP_INTEGRITY if fraction > fix_level.integrity_max_fraction else None
    return fraction, reason


def _boundary_impossible_steps(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    deleted: np.ndarray,
    split: np.ndarray,
    max_speed_mps: float,
) -> int:
    """Make every impossible step between two surviving fixes a segment boundary.

    The invariant the rest of the pipeline leans on: *no step between two fixes that
    reach the analysis may break the absolute speed bound*. Whatever the detectors
    resolved, a step they leave standing past that bound is a transition whose course is
    unknown, which is what a long gap is, so it is marked as one (sec:fixlevel).

    Stated and enforced as a property of the output rather than as one more case inside
    a detector, so that it holds by construction instead of by the detectors having
    enumerated every way a track can be corrupt -- and applied after all of them, since
    each deletion creates adjacencies the previous pass never saw.

    Args:
        t: Fix times.
        lat: Latitudes in degrees.
        lon: Longitudes in degrees.
        deleted: Which fixes the detectors removed.
        split: The split markers, updated in place.
        max_speed_mps: The discipline's absolute horizontal-speed bound.

    Returns:
        How many boundaries this had to add that no detector had marked. Returned rather
        than kept quiet: a repair made in silence is a diagnosis lost, and a large count
        would indict the detectors rather than the data.
    """
    surviving = np.flatnonzero(~deleted)
    if surviving.size < 2:
        return 0
    impossible = (
        _step_speeds(t[surviving], lat[surviving], lon[surviving]) > max_speed_mps
    )
    landing = surviving[1:][impossible]
    added = int((~split[landing]).sum())
    split[landing] = True
    return added
