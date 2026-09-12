# Soaring Anomalous Transport

A master's thesis on anomalous transport in soaring flights, together with the pipeline
that turns raw IGC flight-recorder tracks into the trajectories the analysis measures.

## Language

### Fix-level cleaning (sec:fixlevel)

**Fix**:
One decoded IGC record — a `(t, lat, lon, alt, valid)` tuple at one instant.
_Avoid_: point, sample, record.

**Hampel identifier / Hampel flag**:
The robust local-outlier test on horizontal position: a fix is flagged when its distance
from the local-window median exceeds both the scaled MAD threshold and the metre floor,
with adequate local support. A flag never deletes a fix on its own.
_Avoid_: Hampel filter (the filter substitutes values; this only identifies).

**Impossibility gate**:
The test that actually deletes a horizontal fix: unreachable from the last accepted fix
at the discipline's absolute horizontal-speed bound, with the removal of its block
restoring reachability. Reachability is measured on the chord from that anchor, which
stays put while a block is open, so the test relaxes as time passes.

**Block**:
The contiguous span of fixes the position scan tentatively removes together — the
smallest one whose removal lets the track rejoin the trend. A block may stay open for at
most `hampel_window_s`, reused as that cap; when nothing rejoins inside it the scan
deletes nothing and marks a segment boundary at the block's first fix instead. A
displacement past `max_speed * hampel_window_s` can never rejoin, so a re-acquisition
offset at the kilometre scale always takes the boundary.

**Off-the-trend defect**:
A horizontal fix that disagrees with its neighbours (a spike, or an out-and-back jump).
The Hampel identifier can flag it; the impossibility gate decides deletion independently
of that flag, including when contamination moves the local median onto the defect.

**On-the-trend defect**:
A horizontal fix that geometrically agrees with its neighbours but is structurally wrong
(duplicate timestamp, backward timestamp, frozen-lock run). Caught by rules that read the
record's own bookkeeping, not its geometry.

**Frozen-lock run**:
A recorded stretch consistent with a receiver repeating its last position while the
clock keeps running. Cut when three joint conditions hold — collapsed, witnessed,
long enough — and always split, never bridged. These conditions support a cleaning
decision; they do not independently prove the receiver's internal lock state.

**Witness**:
Evidence used to corroborate a frozen-lock candidate. Exact coordinate repetition
passes directly. Otherwise an eligible barometric channel requires complete local
support and a small difference between its first- and last-quarter medians; missing
local support causes abstention. Without an eligible barometer, a majority of invalid
GNSS declarations or missing altitudes supplies the fallback. These signatures do not
prove the receiver's internal state, and the barometric comparison measures net change.

**Bridge-or-split rule (gap rule)**:
The resampling-stage rule that compares both inter-fix gaps and the elapsed time
between consecutive finite altitudes with `g_max`: interpolated at or below that
limit, split above it. A long altitude-only hole excludes the intervening horizontal
fixes too. Missing altitude outside finite support is excluded without extrapolation.
Explicit cleaning boundaries always split.

**`z_reconstructed`**:
The altitude-channel analogue of `interpolated`. Within a retained segment, short
altitude holes are reconstructed from finite readings no more than `g_max` apart and
flagged. Longer holes split the full trajectory. Unsupported intervals remain recorded
as rejected candidates in the segment table; their fixes never enter the output.

**Level shift**:
A candidate isolated vertical step above the speed threshold, with no return within
30% of its jump amplitude among the next five available fix positions (finite altitude
readings only). The count `n_alt_level_shift` is made before later trimming and segment
selection; it neither proves a persistent sensor offset nor counts defects remaining in
the final dataset. Automatic correction is not implemented. The possible effect on
phase features requires a separate sensitivity analysis.

**Boundaried step**:
A step between two surviving fixes that still breaks the speed bound after every
detector has run. Forced into a segment boundary as a postcondition on the output, not by
any one detector.
