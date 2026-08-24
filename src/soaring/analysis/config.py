"""Pre-processing thresholds, loaded from ``configs/preprocessing.yaml``.

Every value the pipeline acts on lives in that file rather than in code, so a threshold
can be changed, quoted in the thesis through a generated macro, and audited, without a
source edit. This module is the typed view of it: one frozen dataclass per pipeline stage
and one loader that fails loudly on a missing key.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
# Mean Earth radius (metres), the usual choice for a haversine great-circle distance.

# The authoritative threshold file (repo ``configs/preprocessing.yaml``).
DEFAULT_PREPROC_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "preprocessing.yaml"
)

# Per-discipline colours, shared with the thesis figure palette.

# A flight "has" a barometric channel when at least this fraction of its fixes carry a
# non-zero pressure altitude (presence is essentially all-or-nothing). Vertical speed
# and altitude are only physical on such flights; on a GNSS-only flight the barometric
# field is a constant-zero placeholder and is excluded from the fix-level distributions.
# Single source of truth: the constant lives in altitude_noise, so the census, the PSD
# diagnostic and the cleaning cannot drift apart.


@dataclass(frozen=True)
class FixLevelThresholds:
    """Physical bounds for fix-level cleaning (loaded from the config).

    The speeds are great-circle (haversine) speeds between consecutive fixes, on the raw
    geographic coordinates (no conversion yet). The vertical-speed and altitude bounds
    apply to the adopted barometric channel. Inter-fix gaps are not bounded here: they
    are handled once, at the flight level, by :class:`SamplingThresholds`.

    ``max_horizontal_speed_mps`` is keyed by discipline (``"paragliders"``,
    ``"hang gliders"``, later ``"sailplanes"``): the two types have markedly different
    horizontal-speed envelopes (thesis, fig:fixlevel), so one shared bound is either too
    loose for the slower type or clips real dynamics of the faster one.
    ``max_vertical_speed_mps`` and the altitude bounds are *not* split by discipline:
    the two disciplines' vertical-speed distributions are close enough that splitting
    it buys nothing, and the altitude bounds are about the barometric sensor's
    plausible reading range, not a discipline-specific performance limit.
    """

    max_horizontal_speed_mps: dict[str, float]
    max_vertical_speed_mps: float
    min_altitude_m: float
    max_altitude_m: float
    # Robust local-outlier test (Hampel identifier) and structural rules: working
    # values, to be finalized by the injected-defect calibration (thesis impl:fixlevel).
    hampel_window_s: float
    hampel_k: float
    hampel_eps_min_m: float
    hampel_min_window_fixes: int
    frozen_eps_m: float
    frozen_delta_z_m: float
    frozen_tau_s: float
    integrity_max_fraction: float


@dataclass(frozen=True)
class AltChannelThresholds:
    """Altitude-channel presence and liveness bounds (loaded from the config).

    Two conditions decide whether a flight uses its barometric channel. It must be
    *present*: at least ``baro_present_min`` of the fixes carry a non-zero pressure
    altitude. And it must be *alive*: a barometric channel can be present yet dead, a
    stuck sensor writing a constant value that passes the presence check and would feed
    the segmentation a vertical velocity of identically zero, so below
    ``baro_min_range_m`` of range over the flight the channel is treated as absent too.
    Failing either, the flight falls back to GNSS.
    """

    baro_present_min: float
    baro_min_range_m: float


@dataclass(frozen=True)
class FlightLevelThresholds:
    """Population thresholds for flight-level filtering (loaded from the config).

    A separate minimum-fix-count cut is intentionally omitted: it is redundant with the
    duration cut -- even a slow logger (~10 s, the slowest common hang-glider rate) over
    ``min_duration_s`` gives ~240 fixes, ample for the kinematics.
    """

    min_duration_s: float
    min_path_km: float
    max_duration_s: float
    min_alt_range_m: float


@dataclass(frozen=True)
class TrimmingThresholds:
    """Ground-phase trimming bounds on the horizontal speed (loaded from config)."""

    takeoff_speed_mps: float
    sustained_s: float
    interior_ground_s: float
    ground_flatness_m: float


@dataclass(frozen=True)
class SamplingThresholds:
    """Intra-flight sampling-regularity bounds (loaded from the config).

    The split bound on an inter-fix gap is ``min(max_gap_factor * dt,
    max(max_gap_seconds, 2 * dt))``: relative to the native cadence (tolerating logger
    hiccups in proportion, and capping the number of interpolated grid points), but
    never beyond an absolute cap set by the motion's own timescales rather than the
    logger's; the ``2 * dt`` floor keeps "one missed fix never splits" true at every
    cadence (thesis, sec:uniform).
    """

    max_gap_factor: float
    max_gap_seconds: float
    max_missing_fraction: float
    min_segment_duration_s: float


@dataclass(frozen=True)
class SavgolParams:
    """Savitzky-Golay parameters (loaded from the config; window is set per flight).

    Two vertical timescales, not one: the vertical smoothing window is conditioned on
    the flight's ``alt_source`` (thesis, sec:savgol) -- the barometric channel is
    smoother than the horizontal and takes a shorter window, the GNSS vertical is
    noisier and takes a longer one.
    """

    polyorder: int
    tau_c_horizontal_s: float
    tau_c_vertical_baro_s: float
    tau_c_vertical_gnss_s: float


@dataclass(frozen=True)
class PreprocConfig:
    """The full set of pre-processing thresholds, grouped by pipeline level."""

    fix: FixLevelThresholds
    alt_channel: AltChannelThresholds
    trimming: TrimmingThresholds
    flight: FlightLevelThresholds
    sampling: SamplingThresholds
    savgol: SavgolParams


def load_preproc_config(path: str | Path | None = None) -> PreprocConfig:
    """Load the pre-processing thresholds from the YAML config.

    Args:
        path: Config file; defaults to :data:`DEFAULT_PREPROC_CONFIG_PATH`.

    Returns:
        The populated :class:`PreprocConfig`.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    import yaml

    p = Path(path) if path is not None else DEFAULT_PREPROC_CONFIG_PATH
    if not p.is_file():
        raise FileNotFoundError(f"Pre-processing config not found: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return PreprocConfig(
        fix=FixLevelThresholds(**raw["fix_level"]),
        alt_channel=AltChannelThresholds(**raw["alt_channel"]),
        trimming=TrimmingThresholds(**raw["trimming"]),
        flight=FlightLevelThresholds(**raw["flight_level"]),
        sampling=SamplingThresholds(**raw["sampling"]),
        savgol=SavgolParams(**raw["savgol"]),
    )
