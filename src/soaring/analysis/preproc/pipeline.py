"""The seven stages, chained: one IGC file in, three table rows out.

This is the only place the pipeline order of sec:preproc is written down as code, and it
is not an implementation choice -- it is argued in the thesis and is fixed::

    (i)   altitude channel      -> alt_source, and the adopted `alt`
    (ii)  fix-level cleaning    -> deletions, invalidations, split markers
    (iii) ground trimming       -> the airborne window, and the clock zero
          integrity gate        -> counted over that window, hence here and not in (ii)
    (iv)  flight-level filter   -> keep or drop, with the reason
    (v)   geographic -> ENU     -> the local frame, and its origin
    (vi)  uniform resampling    -> segments, and the reconstructed points
    (vii) Savitzky-Golay        -> the smoothed kinematics

Stages (i)-(iv) act on the raw geographic coordinates, because the only geometry they
need is a scalar distance, which the haversine formula gives directly from latitude and
longitude. The conversion (v) then runs on the cleaned, trimmed track, so the tangent
frame is built from good data, and (vi)-(vii) come last because they produce *vector*
quantities, which need Cartesian axes to be expressed in.

A flight that fails a gate stops there. It still produces a ``flights_meta`` row, with
the reason: the census of what the pipeline removed is as much a result as the
trajectories it keeps.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from .altchannel import adopt_alt_channel
from .cleaning import clean_flight, integrity_gate
from .enu import to_local_frame
from .flightfilter import filter_flight
from .resample import resample_flight
from .smoothing import smooth_flight
from .trimming import trim_flight

if TYPE_CHECKING:
    from ..config import PreprocConfig

# Bumped whenever a stage changes what it produces, so a stored table can be told apart
# from one written by an older pipeline (design principle: traceability).
#
# 1.1.0 -- three rules changed after the first full-archive run exposed defects the
#          specification had not anticipated: the impossibility gate deletes without
#          requiring the Hampel flag (the identifier's 50 % breakdown point is exceeded
#          by scattered null-island runs), an impossible step that survives the scan is
#          made a segment boundary and counted, and a flight whose mean ground speed
#          exceeds the fix-level bound is dropped (sec:fixlevel, sec:flightfilter).
# 1.3.0 -- the vertical channel's reconstruction is recorded. A z the logger never
#          wrote, or the cleaning removed, was bridged by a straight line of unbounded
#          length while `interpolated` -- a statement about the *time base* -- reported
#          the grid point as measured: 500 s of invented altitude, 540 m of error, and
#          `was_resampled` False. New per-fix `z_reconstructed`, per-segment
#          `frac_z_reconstructed`, per-flight `z_gap_max_s` (sec:uniform). In the same
#          pass, from the adversarial audit of the same day: the ground-flatness test
#          reads a central span instead of a full range, which is a maximum statistic
#          that grew with the stint and stopped the guard firing at all (sec:trimming);
#          an unreturned vertical step -- neither spike nor run, and present on 8 % of
#          flights -- is counted as `n_alt_level_shift`; the reach bound is stated per
#          fix, as the invariant is; a flight the pipeline raised on carries the fixed
#          reason `pipeline_raised` instead of an exception string the census cannot
#          count; and `suspect_intervals` is written rather than discarded.
# 1.2.0 -- two rules added for the corrupt *first* fix, a defect no per-step test can
#          see because every step of such a flight is plausible: a corrupt block at the
#          very start is deleted rather than made a boundary, and a flight whose extent
#          exceeds what the speed bound allows in its duration is dropped. That first
#          fix becomes the origin of the local frame, so getting it wrong displaces
#          every coordinate of the record (sec:fixlevel, sec:flightfilter).
PIPELINE_VERSION = "1.3.0"

# The reason a flight carries when the driver could not run the pipeline over it at all
# -- an unreadable file, a parser failure, a bug. It lives here, with the other stage
# reasons, so the census that enumerates them cannot miss it: a free-form message would
# be counted in `attempted` and shown in no row.
DROP_ERROR = "pipeline_raised"

# Columns of the per-fix table that leave this module, in order. Identity first, then
# the kinematics, then the per-sample cautions and the cleaning flags.
FIX_TABLE_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "t",
    "E",
    "N",
    "z",
    "v_E",
    "v_N",
    "v_z",
    "a_E",
    "a_N",
    "a_z",
    "interpolated",
    "z_reconstructed",
    "edge",
    "hampel_flagged",
    "alt_invalidated",
]

# Columns the raw parse carries that no later stage needs: the channel not adopted, and
# the validity flag whose only consumers are the frozen-lock witness and the altitude
# rule, both of which have already run by the time the local frame is built.
_CONSUMED_BY_CLEANING = ["baro_alt", "gnss_alt", "valid"]


@dataclass
class FlightRecord:
    """The ``flights_meta`` row of one flight: what it was, and what happened to it."""

    source: str
    flight_id: str
    pipeline_version: str = PIPELINE_VERSION
    drop_stage: str | None = None
    drop_reason: str | None = None
    error_detail: str | None = None
    # Stage (i)
    alt_source: str | None = None
    baro_present_frac: float | None = None
    baro_range_m: float | None = None
    n_alt_missing_raw: int | None = None
    # Stage (ii)
    n_fix_raw: int | None = None
    n_fix_clean: int | None = None
    n_merged_duplicates: int | None = None
    n_removed_backward: int | None = None
    n_removed_spike: int | None = None
    n_removed_frozen: int | None = None
    n_alt_out_of_band: int | None = None
    n_alt_vz_spike: int | None = None
    n_flagged_kept: int | None = None
    n_vz_runs: int | None = None
    n_alt_level_shift: int | None = None
    split_jump_max_m: float | None = None
    n_boundaried: int | None = None
    integrity_fraction: float | None = None
    # Stage (iii)
    ground_phase_start_s: float | None = None
    ground_phase_end_s: float | None = None
    trimmed_fraction: float | None = None
    n_interior_excised: int | None = None
    n_suspect_stints: int | None = None
    # Stage (iv)
    duration_flight_s: float | None = None
    path_km: float | None = None
    alt_range_m: float | None = None
    extent_km: float | None = None
    # Stage (v)
    lat0: float | None = None
    lon0: float | None = None
    alt0: float | None = None
    # Stage (vi)
    dt_native_s: float | None = None
    g_max_s: float | None = None
    n_segments: int | None = None
    n_segments_kept: int | None = None
    frac_interpolated: float | None = None
    frac_z_reconstructed: float | None = None
    z_gap_max_s: float | None = None
    was_resampled: bool | None = None
    # Stage (vii)
    savgol_order: int | None = None
    savgol_window_horiz: int | None = None
    savgol_window_vert: int | None = None


@dataclass
class FlightResult:
    """Everything one flight contributes to the three tables."""

    meta: FlightRecord
    fixes: pd.DataFrame = field(default_factory=pd.DataFrame)
    segments: pd.DataFrame = field(default_factory=pd.DataFrame)
    suspect_intervals: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def kept(self) -> bool:
        """Whether the flight survived every gate."""
        return self.meta.drop_reason is None


def run_flight(
    fixes: pd.DataFrame,
    cfg: PreprocConfig,
    *,
    source: str,
    flight_id: str,
    discipline: str,
) -> FlightResult:
    """Run the whole pre-processing pipeline over one parsed flight.

    Args:
        fixes: The parsed IGC table (``soaring.analysis.igc.parse_igc``).
        cfg: The adopted thresholds, loaded from ``configs/preprocessing.yaml``.
        source: ``"paraglider"`` / ``"hangglider"`` / ``"sailplane"`` -- the value
            of the ``source`` column, which is how a new data source enters the schema.
        flight_id: The flight's identifier; the primary key is ``(source, flight_id)``.
        discipline: The key the per-discipline speed bound is stored under
            (``"paragliders"`` / ``"hang gliders"``).

    Returns:
        The :class:`FlightResult`. When a gate stops the flight, the tables come back
        empty and ``meta.drop_stage`` / ``meta.drop_reason`` say which gate and why.
    """
    meta = FlightRecord(source=source, flight_id=flight_id)
    meta.n_fix_raw = len(fixes)
    if len(fixes) < 2:
        meta.drop_stage, meta.drop_reason = "parse", "fewer_than_two_fixes"
        return FlightResult(meta=meta)

    # (i) which altitude channel this flight is going to use.
    with_alt, channel = adopt_alt_channel(fixes, cfg.alt_channel)
    meta.alt_source = channel.alt_source
    meta.baro_present_frac = channel.baro_present_frac
    meta.baro_range_m = channel.baro_range_m
    meta.n_alt_missing_raw = channel.n_missing

    # (ii) fix-level cleaning.
    cleaned = clean_flight(
        with_alt, cfg.fix, discipline=discipline, alt_source=channel.alt_source
    )
    report = asdict(cleaned.report)
    for key in (
        "n_fix_clean",
        "n_merged_duplicates",
        "n_removed_backward",
        "n_removed_spike",
        "n_removed_frozen",
        "n_alt_out_of_band",
        "n_alt_vz_spike",
        "n_flagged_kept",
        "n_vz_runs",
        "n_alt_level_shift",
        "split_jump_max_m",
        "n_boundaried",
    ):
        setattr(meta, key, report[key])

    # (iii) trimming, which also sets the clock zero of sec:notation.
    trimmed = trim_flight(
        cleaned.fixes,
        cfg.trimming,
        suspect_min_span_s=cfg.fix.frozen_tau_s,
        max_drift_mps=cfg.fix.frozen_delta_z_m / cfg.fix.frozen_tau_s,
    )
    meta.ground_phase_start_s = trimmed.t_on
    meta.ground_phase_end_s = trimmed.t_off
    meta.trimmed_fraction = trimmed.trimmed_fraction
    meta.n_interior_excised = trimmed.n_interior_excised
    meta.n_suspect_stints = len(trimmed.suspect_intervals)
    if trimmed.drop_reason is not None:
        meta.drop_stage, meta.drop_reason = "trimming", trimmed.drop_reason
        return FlightResult(meta=meta)

    # The integrity gate belongs to (ii) but is counted over the airborne window, which
    # only exists now: defects in a ground phase trimming removes must not condemn.
    fraction, integrity_reason = integrity_gate(
        cleaned, trimmed.t_on, trimmed.t_off, cfg.fix
    )
    meta.integrity_fraction = fraction
    if integrity_reason is not None:
        meta.drop_stage, meta.drop_reason = "cleaning", integrity_reason
        return FlightResult(meta=meta)

    # (iv) the whole-flight cuts, on the trimmed parent.
    verdict = filter_flight(
        trimmed.fixes,
        cfg.flight,
        max_mean_speed_mps=cfg.fix.max_horizontal_speed_mps[discipline],
        # So that stage (iv) measures the flight over the intervals stage (vi) will
        # analyse it over, and not over the holes between them.
        sampling=cfg.sampling,
    )
    meta.duration_flight_s = verdict.duration_s
    meta.path_km = verdict.path_km
    meta.alt_range_m = verdict.alt_range_m
    meta.extent_km = verdict.extent_km
    if verdict.drop_reason is not None:
        meta.drop_stage, meta.drop_reason = "flight_filter", verdict.drop_reason
        return FlightResult(meta=meta)

    # (v) into the local Cartesian frame.
    local, frame = to_local_frame(
        trimmed.fixes.drop(columns=_CONSUMED_BY_CLEANING, errors="ignore")
    )
    meta.lat0, meta.lon0, meta.alt0 = frame.lat0_deg, frame.lon0_deg, frame.alt0_m

    # (vi) one uniform grid per segment.
    resampled = resample_flight(local, cfg.sampling)
    meta.dt_native_s = resampled.dt_s
    meta.g_max_s = resampled.g_max_s
    meta.frac_interpolated = resampled.frac_interpolated
    meta.frac_z_reconstructed = resampled.frac_z_reconstructed
    meta.z_gap_max_s = resampled.z_gap_max_s
    meta.was_resampled = resampled.was_resampled
    meta.n_segments = len(resampled.segments)

    # (vii) smoothing and differentiation.
    smoothed = smooth_flight(resampled, cfg.savgol, alt_source=channel.alt_source)
    if smoothed.windows is not None:
        meta.savgol_order = smoothed.windows.polyorder
        meta.savgol_window_horiz = smoothed.windows.horizontal
        meta.savgol_window_vert = smoothed.windows.vertical
    segments = smoothed.segments
    meta.n_segments_kept = int(segments["kept"].sum()) if len(segments) else 0
    if smoothed.drop_reason is not None:
        meta.drop_stage, meta.drop_reason = "resampling", smoothed.drop_reason
        return FlightResult(meta=meta, segments=_key(segments, source, flight_id))

    return FlightResult(
        meta=meta,
        fixes=_key(smoothed.fixes, source, flight_id).reindex(
            columns=FIX_TABLE_COLUMNS
        ),
        segments=_key(segments, source, flight_id),
        suspect_intervals=_key(trimmed.suspect_intervals, source, flight_id),
    )


def _key(table: pd.DataFrame, source: str, flight_id: str) -> pd.DataFrame:
    """Prefix a table with its ``(source, flight_id)`` primary key."""
    out = table.copy()
    out.insert(0, "flight_id", flight_id)
    out.insert(0, "source", source)
    return out
