"""Stage (i): which altitude channel a flight uses (thesis, sec:altchannel).

The analysis adopts the **barometric** altitude for the vertical dynamics. Both channels
are written to whole metres by the IGC format, so their resolution is the same; what
distinguishes the barometric one is that its errors are *slow* -- an offset from the
ICAO
reference of up to ~100 m, and a drift of tens of metres over a flight -- and slow
errors
are annihilated by the differencing every dynamical quantity involves. The GNSS altitude
carries no atmospheric offset but is vertically noisier, because the satellite geometry
resolves the vertical coordinate worst (the vertical dilution of precision), and a
substantial minority of flights carry a high-frequency floor one to two orders of
magnitude above their barometric one. Since the vertical velocity is a finite
difference,
which amplifies exactly that band, and since one cannot know in advance which flights
have poor reception, the uniformly clean channel is the safe choice.

**One channel per flight, end to end.** The two are never spliced within a flight: a
mid-flight switch between references offset by tens of metres would inject a spurious
jump. The choice is recorded as ``alt_source`` so the two source groups stay separable
in every downstream analysis.

A flight is barometric when the channel is both **present** and **alive**:

* present -- it covers at least ``baro_present_min`` of the flight's fixes.
  Presence is essentially all-or-nothing (a logger without a pressure sensor writes the
  whole channel as zero), so any cut in the middle of the range separates the same two
  populations; 95 % is high on purpose, because a partially filled channel is worse for
  the vertical analysis than a uniformly sourced GNSS one -- its ``v_z`` would rest on a
  channel with holes, interpolated over stretches long enough to erase transitions.
* alive -- its total range over the flight reaches ``baro_min_range_m``. A stuck sensor
  writes a constant non-zero value, passes the presence check, and would feed the
  segmentation a vertical velocity of identically zero.

Otherwise the flight falls back to the GNSS altitude, unfiltered.

The few individual fixes with no value on the adopted channel are **not** back-filled
from the other one: the value is left missing, and the hole is closed once, at
resampling (sec:uniform), like every other reconstruction in the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from ..config import AltChannelThresholds

# The two values ``alt_source`` can take, and the raw column each adopts.
ALT_SOURCES = {"baro": "baro_alt", "gnss": "gnss_alt"}

# The IGC standard writes an absent altitude channel as zero, so a zero is read as "no
# value here" rather than as a measurement. On the barometric channel the reading is
# referenced to the ICAO standard atmosphere and a genuine zero would be a sea-level
# take-off on a standard-pressure day; on the GNSS channel it would be a wing at exactly
# the ellipsoid. Both are possible in principle and neither is distinguishable from an
# absent value in the format, so the format's convention wins -- at the cost of one
# missing altitude per flight in the vanishingly rare case, restored at resampling.
_ABSENT_ALT_M = 0.0


@dataclass(frozen=True)
class AltChannel:
    """The channel one flight adopted, and the evidence for the choice.

    Attributes:
        alt_source: ``"baro"`` or ``"gnss"``; the ``alt_source`` field of
            ``flights_meta``.
        baro_present_frac: Share of fixes carrying a non-zero barometric altitude.
        baro_range_m: Total barometric range over the flight, the liveness statistic
            (``0`` when the channel is absent).
        n_missing: Fixes with no value on the *adopted* channel, left missing here and
            restored at resampling.
        fallback_reason: Why the flight is not barometric -- ``"absent"`` (the presence
            test) or ``"stuck"`` (the liveness test) -- and ``None`` when it is.
    """

    alt_source: str
    baro_present_frac: float
    baro_range_m: float
    n_missing: int
    fallback_reason: str | None


def adopt_alt_channel(
    fixes: pd.DataFrame, alt_channel: AltChannelThresholds
) -> tuple[pd.DataFrame, AltChannel]:
    """Run stage (i) over one flight: choose the channel and materialise it.

    Args:
        fixes: One flight's parsed table (``soaring.analysis.igc.parse_igc``), with
            ``baro_alt`` and ``gnss_alt`` columns in metres and zero where absent.
        alt_channel: The adopted liveness threshold.

    Returns:
        ``(fixes, channel)``: the input table with an ``alt`` column added -- the
        adopted channel, ``nan`` where the channel has no value at that fix -- and the
        :class:`AltChannel` record of the choice. The raw channels are left in place:
        the fix-level cleaning still needs the recorder's own declarations (the ``V``
        flag, a zeroed GNSS altitude) as frozen-lock witnesses, and only the local-frame
        conversion of stage (v) drops them.

    Raises:
        ValueError: If a required column is missing.
    """
    missing = [c for c in ("baro_alt", "gnss_alt") if c not in fixes.columns]
    if missing:
        raise ValueError(f"the parsed table is missing the column(s) {missing}")

    baro = fixes["baro_alt"].to_numpy(dtype=float)
    present = baro != _ABSENT_ALT_M
    present_frac = float(present.mean()) if baro.size else 0.0
    baro_range = (
        float(baro[present].max() - baro[present].min()) if present.any() else 0.0
    )

    if present_frac < alt_channel.baro_present_min:
        source, reason = "gnss", "absent"
    elif baro_range < alt_channel.baro_min_range_m:
        source, reason = "gnss", "stuck"
    else:
        source, reason = "baro", None

    alt = fixes[ALT_SOURCES[source]].to_numpy(dtype=float).copy()
    alt[alt == _ABSENT_ALT_M] = np.nan
    out = fixes.copy()
    out["alt"] = alt
    return out, AltChannel(
        alt_source=source,
        baro_present_frac=present_frac,
        baro_range_m=baro_range,
        n_missing=int(np.isnan(alt).sum()),
        fallback_reason=reason,
    )
