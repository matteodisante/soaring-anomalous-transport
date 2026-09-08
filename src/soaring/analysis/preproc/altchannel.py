"""Stage (i): the altitude channel, and the witness beside it (thesis, sec:altchannel).

The analysis reads the **GNSS** altitude, for every flight, end to end. One channel for
the whole population is what makes the vertical coordinate the same physical quantity in
every record: a per-flight choice between two sensors leaves the population mixed, and
any correlation between which sensor a flight carried and how it flew -- logger model,
era, discipline, club -- then enters the statistics as a selection effect that no
downstream analysis can undo.

The two channels cost the same at the median. Both are written to whole metres by the
IGC format, and their median Welch spectra coincide across the band, both flattened by
that quantization rather than by receiver noise (fig:altnoise). What separates them is
the *spread*: the GNSS band fans out at high frequency on a minority of flights whose
size is measured rather than inferred (sec:altchannel). The barometric channel is the
uniformly clean one, but it is clean about a reference that is itself moving -- pressure
altitude is referred to the ICAO standard atmosphere, so it is not a geometric height
and its zero drifts with the weather -- while the GNSS altitude is geometric throughout.

**The barometer is not discarded; it is demoted to an instrument.** A flight that
carries a usable pressure channel keeps it as the *witness* of the frozen-lock rule
(sec:fixlevel), which is the one place a second, independent sensor is indispensable: a
lost GNSS lock freezes the position while the pressure sensor, on a different physical
principle, keeps recording a real climb. The adopted altitude cannot play that part,
coming as it does from the very receiver whose lock is in doubt. Read there and nowhere
else, the barometer enters no observable, so this is not a return to a mixed population.

A flight is admitted when its GNSS channel is both **present** and **alive**:

* present -- it covers at least ``gnss_present_min`` of the flight's fixes. Presence is
  essentially all-or-nothing (a logger with nothing to write puts the whole channel at
  zero), so any cut in the middle of the range separates the same two populations, and
  the threshold sits high because a partially filled channel is worse than a missing
  one: its ``v_z`` would rest on a channel with holes, interpolated over stretches long
  enough to erase transitions;
* alive -- its total range over the flight reaches ``gnss_min_range_m``. A stuck sensor
  writes a constant non-zero value, passes the presence check, and would feed the
  segmentation a vertical velocity of identically zero.

Failing either, the flight has no vertical coordinate at all and is **dropped** -- there
is no second channel to move it to any more, and that is the price of the single-channel
policy, paid in flights and counted in the cascade rather than absorbed silently.
 The few individual fixes with no value on the adopted channel are **not** back-filled
from the barometer: the value is left missing, and the hole is closed once, at
resampling
(sec:uniform), like every other reconstruction in the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from ..config import AltChannelThresholds

# The flight-level verdict when the adopted channel is unusable.
DROP_NO_ALTITUDE = "no_usable_altitude_channel"

# The IGC standard writes an absent altitude channel as zero, so a zero is read as "no
# value here" rather than as a measurement. On the GNSS channel a genuine zero would be
# a wing at exactly the ellipsoid; on the barometric one, a sea-level take-off on a
# standard-pressure day. Both are possible in principle and neither is distinguishable
# from an absent value in the format, so the format's convention wins -- at the cost of
# one missing altitude per flight in the vanishingly rare case, restored at resampling.
_ABSENT_ALT_M = 0.0


@dataclass(frozen=True)
class AltChannel:
    """One flight's altitude verdict, and the evidence for it.

    Attributes:
        gnss_present_frac: Share of fixes carrying a non-zero GNSS altitude.
        gnss_range_m: Total GNSS range over the flight, the liveness statistic (``0``
            when the channel is absent).
        baro_witness: Whether the raw barometric channel is present and alive enough
            to witness a frozen-lock run with. Diagnostic only: it selects a *test*,
            never a measured quantity.
        baro_present_frac: Share of fixes carrying a non-zero barometric altitude, the
            witness evidence and the archive census.
        baro_range_m: Total barometric range over the flight.
        n_missing: Fixes with no value on the adopted channel, left missing here and
            restored at resampling.
        drop_reason: :data:`DROP_NO_ALTITUDE` when the GNSS channel fails either test,
            and ``None`` when the flight is admitted.
    """

    gnss_present_frac: float
    gnss_range_m: float
    baro_witness: bool
    baro_present_frac: float
    baro_range_m: float
    n_missing: int
    drop_reason: str | None


def _presence_and_range(values: np.ndarray) -> tuple[float, float]:
    """The presence fraction and the total range of one raw channel.

    ``nan`` is what a blank or unusable altitude field decodes to, and ``nan != 0``
    is ``True``, so a channel written entirely blank used to be counted as fully
    present and adopted. Four flights in the archive reached the analysis dataset that
    way.
    """
    present = np.isfinite(values) & (values != _ABSENT_ALT_M)
    fraction = float(present.mean()) if values.size else 0.0
    span = (
        float(values[present].max() - values[present].min()) if present.any() else 0.0
    )
    return fraction, span


def adopt_alt_channel(
    fixes: pd.DataFrame, alt_channel: AltChannelThresholds
) -> tuple[pd.DataFrame, AltChannel]:
    """Run stage (i) over one flight: gate the GNSS channel, rate the barometric one.

    Args:
        fixes: One flight's parsed table (``soaring.analysis.igc.parse_igc``), with
            ``baro_alt`` and ``gnss_alt`` columns in metres and zero where absent.
        alt_channel: The adopted presence and liveness thresholds.

    Returns:
        ``(fixes, channel)``: the input table with an ``alt`` column added -- the
        GNSS channel, ``nan`` where it has no value at that fix -- and the
        :class:`AltChannel` record. The raw channels are left in place: the fix-level
        cleaning still needs the barometer as a frozen-lock witness and the recorder's
        own declarations besides, and only the local-frame conversion of stage (v)
        drops them.

    Raises:
        ValueError: If a required column is missing.
    """
    missing = [c for c in ("baro_alt", "gnss_alt") if c not in fixes.columns]
    if missing:
        raise ValueError(f"the parsed table is missing the column(s) {missing}")

    gnss = fixes["gnss_alt"].to_numpy(dtype=float)
    baro = fixes["baro_alt"].to_numpy(dtype=float)
    gnss_frac, gnss_range = _presence_and_range(gnss)
    baro_frac, baro_range = _presence_and_range(baro)

    drop_reason = (
        DROP_NO_ALTITUDE
        if gnss_frac < alt_channel.gnss_present_min
        or gnss_range < alt_channel.gnss_min_range_m
        else None
    )
    baro_witness = (
        baro_frac >= alt_channel.baro_witness_present_min
        and baro_range >= alt_channel.baro_witness_min_range_m
    )

    alt = gnss.copy()
    alt[alt == _ABSENT_ALT_M] = np.nan
    out = fixes.copy()
    out["alt"] = alt
    return out, AltChannel(
        gnss_present_frac=gnss_frac,
        gnss_range_m=gnss_range,
        baro_witness=baro_witness,
        baro_present_frac=baro_frac,
        baro_range_m=baro_range,
        n_missing=int(np.isnan(alt).sum()),
        drop_reason=drop_reason,
    )
