# The preprocessing pipeline

`soaring.analysis.preproc.pipeline.run_flight` transforms one parsed IGC recording;
`scripts/preprocess.py` applies it to an archive and writes four Parquet tables.
Chapter 2 explains the scientific choices. `configs/preprocessing.yaml` supplies the
working thresholds, loaded by `load_preproc_config`.

Raw tracks are preserved. A rebuild replaces derived tables, so it must finish before
those tables are treated as a complete dataset. The [combined workflow](rebuilding.md)
then regenerates all downstream manuscript inputs, including segmentation.

## Stages and their order

| Stage | Operation | Code in `analysis.preproc` |
|---|---|---|
| i | Admit the GNSS altitude channel and determine global barometric-witness eligibility | `altchannel.py` |
| ii | Clean time/position defects and invalidate unsupported altitude values | `cleaning.py` |
| iii | Estimate outer ground phases; check interior slow intervals | `trimming.py` |
| iv | Apply recorded-duration, path, elapsed-span and altitude-range gates | `flightfilter.py` |
| v | Convert horizontal coordinates to a local east–north frame | `enu.py` |
| vi | Split gaps and resample each segment at the native interval | `resample.py` |
| vii | Fit local polynomials for position and derivatives | `smoothing.py` |

The integrity criterion belongs to cleaning but is evaluated after trimming, because
its denominator is the estimated airborne window. The driver records rejected flights
and segments as well as retained trajectories. Stage counters can overlap; their sum
is not generally a count of distinct rejected fixes.

## Altitude and the barometric witness

Every admitted flight uses the numerical GNSS altitude field. Its finite, nonzero
coverage must reach 0.95 and its full-record range must reach 30 m. These are admission
criteria, not proof of sensor accuracy or a universal distinction between soaring and
non-soaring. Zero is treated as an absent-field sentinel, including a genuine height
that happens to round to zero. Absent raw pressure values are normalised before duplicate
records are combined.

The barometer has its own 0.95 coverage and 30 m range requirements. Global eligibility
is insufficient to witness a particular interval: every candidate fix in that interval
must have a contemporaneous finite barometric value. The witness is never interpolated.
A missing local witness causes abstention from that pressure-based decision.

Requiring both channels at every fix before any cleaning would select a different
recorder population and discard usable horizontal information. The pipeline instead
keeps GNSS-only flights eligible and makes the weaker alternative rules explicit.
The GNSS field is not harmonised across recorder geoid/ellipsoid conventions; using
one channel name does not establish one absolute vertical datum.

## Position and clock defects

The Hampel identifier compares a horizontal fix with a local median and a scaled MAD.
Its output is a diagnostic flag. It never deletes a fix on its own and is not required
by the impossibility gate: see ADR-0001 in `docs/adr/`.

The impossibility gate uses the discipline's speed bound, 45 m/s for paragliders and
55 m/s for hang gliders. A candidate position block is removed when it is unreachable
from the last accepted fix and its removal permits a reachable rejoin. Steps still
above the bound after the detectors create mandatory boundaries. Later interpolation
and smoothing need not preserve that inequality, which the verifier therefore checks
again on the written coordinates.

Duplicate timestamps are combined. Non-wrap backward timestamps are handled by retaining
a longest strictly increasing subsequence, rather than discarding every fix after a
forward clock jump. The parser separately unwraps midnight crossings.

A frozen-position candidate must satisfy all geometric, witness and duration criteria.
Its bounding diameter must be below 15 m and its span at least 60 s. Exact repeated
coordinates satisfy the recorder-repeat witness. Otherwise an eligible barometer must
be locally complete and the medians of the candidate's first and last quarters must
differ by less than 5 m. That comparison tests net change, not the absence of every
interior altitude excursion. If the barometer is globally ineligible, more than half
of the fixes must carry a `V` flag or missing GNSS altitude. If an eligible barometer
is missing locally, this declaration fallback is not substituted. These rules support
an operational removal; they do not prove the receiver's internal lock state.
Removed frozen intervals are split and never interpolated across.

## Vertical-speed tests

The current working cutoff is 10 m/s. It is motivated by the transition into the slower
raw-distribution tail, where the discipline densities cross near 9–10 m/s. It does not
identify a proven physical maximum, nor establish that every exceedance is an error.

For each step, compute `v_z = Δalt/Δt` and the median of `abs(v_z)` over step midpoints
within ±5 s, including endpoints. A median needs at least five finite steps; otherwise
that step's own magnitude is used. The historical key `vz_min_window_fixes` therefore
counts **steps**. A fix's altitude is invalidated when both its incoming and outgoing
window statistics exceed the bound. An additional out-and-back rule detects adjacent
opposite-sign steps whose magnitudes both exceed the bound. The horizontal fix survives
these altitude decisions. Figures in Chapter 2 show both the window and the two-sided
logical test.

Out-of-band altitude, invalid recorder flags and the speed rules are tracked separately.
An isolated super-threshold altitude step is counted when none of the finite readings
among the next five fix positions returns within 30% of the jump amplitude. This is a
short-horizon candidate test, not proof of a permanent sensor offset. The count precedes
later trimming and segment rejection and does not count defects surviving in the final
trajectory. Candidates are not automatically repaired; their effect on derivatives and
phase labels remains a sensitivity question.

## Ground phases and flight selection

Outer ground phases use sustained horizontal speed: 5 m/s over 30 s. Interior slow
intervals are excised only when they last at least 600 s and satisfy the locally complete
barometric flatness test: at least three complete readings, an absolute least-squares
slope at most `5/60 m/s`, and a 95th-minus-5th percentile range at most `5 m` after
removing that fitted line. Without usable pressure data the interior-ground detector
abstains; it has no speed-only fallback. Shorter slow/flat intervals are saved in
`suspect_intervals.parquet` for a proposed sensitivity analysis, not an implemented
waiting-time result.

The integrity fraction counts deleted and altitude-invalidated fixes in the airborne
window, divided by the surviving-plus-deleted fixes there. Duplicate merging does not
enter that numerator. Fractions above 0.1 reject the flight.

The flight gates then require at least 2400 s of recorded duration and 20 km of path
within contiguous blocks, an elapsed span no greater than 57600 s, and a GNSS altitude
range of at least 600 m. Recorded duration excludes long gaps and mandatory boundaries;
elapsed span includes them. The altitude-range gate can reject real soaring flights.
These rules define the analysed population, not an exhaustive set of genuine flights.

## Coordinates, gaps and smoothing

The horizontal frame is local ENU about the first trimmed fix. The working vertical
coordinate is the adopted altitude, not the rotation's `U`, and is not re-zeroed.
The ECEF calculation uses recorded GNSS altitude as an approximate ellipsoidal height;
the unresolved datum is discussed in the geodesy appendix.

For native interval `Δt`, the gap bound is `max(10 Δt, 20 s)`. Longer gaps and mandatory
boundaries split segments. PCHIP interpolates horizontal coordinates and linear
interpolation fills altitude. Missing altitude at an existing horizontal fix does not
open a time gap and has no duration limit for filling; endpoint values extend beyond
the first and last finite altitude within a segment. Its quality flags must therefore
be used by vertical-dynamics analyses.

A retained segment spans at least 90 s, has at most 0.1 of its grid times marked
`interpolated`, and has finite coordinates. These coverage criteria do not bound
altitude-only reconstruction. Segments keep the parent's clock and origin; flight gates
are not reapplied after individual segment rejection.

Savitzky–Golay fitting uses a cubic polynomial and configured five-second target windows,
converted to admissible odd sample counts. A window of `w` samples spans `(w-1) Δt`.
First and second derivatives have physical time units. Edge evaluations use the nearest
full fit window inside its interval, not extrapolation beyond the observations.
`z_derivative_reconstructed` marks every output whose vertical fit uses a reconstructed
altitude. The mask follows the actual polynomial support, including edges, and never
crosses a segment boundary. A smooth output is not evidence that missing observations
have been recovered accurately.

## Raw diagnostic caches

`track_scan.parquet` stores per-flight summaries of the raw archive. It supports channel
coverage, duration, path, altitude-range, gap and cadence diagnostics. Raw marginal
retention curves are not the sequential retention rates of cleaned flights.
`fixlevel_scan.parquet` stores a seeded sample of raw diagnostic values; its histograms
retain the full finite-sample denominator when displayed tails are clipped.

The complete rebuild rescans these caches. PSD comparisons use paired uninterrupted
intervals where both altitude channels are required; selection and cache version are
recorded. Noise attribution remains conditional on a measurement model.

## Output schema

### `fixes` (one row per fix)

One Parquet per discipline, zstd, written in bounded batches (400 flights or about one million fixes) (**a row group is
not a batch** — read it through `soaring.analysis.derived.stream_flights`). Only filter
*outputs* are stored; everything else is lazy. Nineteen columns, in this order — the list
is `pipeline.FIX_TABLE_COLUMNS` and this table is checked against it by
`test_the_documented_fix_schema_matches_the_code`.

| column | dtype | note |
|---|---|---|
| `source` | string | `paraglider` / `hangglider` / `sailplane` |
| `flight_id` | string | key is `(source, flight_id)` — see [flight_id](#catalog-quirks) |
| `segment_id` | int16 | 0-based within the flight; a split at a long gap / excised run increments it (thesis `sec:uniform`) |
| `t` | float32 | s; `t=0` at first airborne fix of the **parent flight** (segments keep the parent clock) |
| `E`, `N` | float32 | ENU, smoothed (`deriv=0`); the raw frame is zeroed at the first trimmed fix; smoothing can shift its first output |
| `z` | float32 | adopted altitude channel at its measured value, smoothed; never re-zeroed (thesis `sec:enu`) |
| `v_E`, `v_N`, `v_z` | float32 | velocity (`deriv=1`) |
| `a_E`, `a_N`, `a_z` | float32 | acceleration (`deriv=2`) |
| `interpolated` | bool | the **time base** had no fix within half a step, so all three channels were reconstructed at resampling |
| `z_reconstructed` | bool | this grid point's **altitude** did not come from a measured one — either `interpolated`, or the fix it came from carried no altitude. A vertical hole opens no time gap, so it forces no split and `interpolated` stays False: preserve this original mask; vertical derivatives must use `z_derivative_reconstructed` |
| `z_derivative_reconstructed` | bool | the vertical Savitzky–Golay fit uses at least one reconstructed input altitude; includes edge-window support, stays within a segment (pipeline 2.2.0) |
| `edge` | bool | within a half-window of a segment boundary, where the Savitzky–Golay polynomial is evaluated off-centre and so has different weights and generally different variance (thesis `sec:savgol`) |
| `hampel_flagged` | bool | the local-outlier test flagged this fix; recorded, never a gate (thesis `sec:fixlevel`) |
| `alt_invalidated` | bool | the **cleaning** removed this altitude, as opposed to the logger never writing one |

Lazy (never stored), e.g. `v_tot=√(v_E²+v_N²+v_z²)`, `θ_xy=atan2(v_N,v_E)`,
`ω=(v_E a_N − v_N a_E)/(v_E²+v_N²)`. (`z` is already absolute; no `U_origin` offset exists.)

### `segments` (one row per segment)

Single Parquet. Key `(source, flight_id, segment_id)`: `t_start`, `t_end`, `n_fix`
(grid points contributed to `fixes`), `n_fix_raw` (measured fixes), `frac_interpolated`,
`frac_z_reconstructed`, and the boundary-censoring flags `censored_start`/`censored_end` for phases truncated at
either end (thesis `sec:uniform`). Per-flight aggregates stay in `flights_meta`.

Two implementation choices, made when stage (vi) was built:

- **Every segment the split produced gets a row**, retained or not, with `kept` (bool)
  and `drop_reason` (null when kept, else `shorter_than_min_segment_duration` /
  `missing_fraction_above_max`). `segment_id` is assigned at split time and stays stable,
  so a gap in the numbering *is* the record of a drop. Same principle as `flights_meta`:
  the reason is recorded, not just the removal — and this is the material the gap-cap
  sweep of `sec:uniform` needs.
- **`censored_*` is True only at a boundary a split created.** The parent flight's own
  first and last boundary truncate the phase in progress too, but they are a different
  thing, and are told apart by these flags being False on the first/last segment.

### `flights_meta` (one row per flight)

Single Parquet, 50 columns, one row per flight **attempted** — the dropped ones are kept,
because the census of what was removed is as much a result as what was kept. Checked against
`pipeline.FlightRecord`:

- **identity** — `source`, `flight_id`, `pipeline_version`;
- **fate** — `drop_stage`, `drop_reason`, `error_detail`. Null on a retained flight; the
  removal cascade of the thesis is read off them;
- **altitude channel** — `gnss_present_frac`, `gnss_range_m` (the adopted channel, gated:
  a flight failing either is dropped, there being no second channel to fall back to),
  `baro_witness`, `baro_present_frac`, `baro_range_m` (barometer eligibility for the frozen-position and interior-ground witnesses), `n_alt_missing_raw`;
- **cleaning counters** — `n_fix_raw`, `n_fix_clean`, `n_merged_duplicates`,
  `n_removed_backward`, `n_removed_spike`, `n_removed_frozen`, `n_alt_out_of_band`,
  `n_alt_vz_sustained` (the windowed rule), `n_alt_vz_spike` (the isolated out-and-back
  rule), `n_flagged_kept`, `n_vz_runs`, `n_alt_level_shift`, `split_jump_max_m`,
  `n_boundaried`, `integrity_fraction`;
- **trimming** — `ground_phase_start_s`, `ground_phase_end_s`, `trimmed_fraction`,
  `n_interior_excised`, `n_suspect_stints`;
- **flight-level quantities the filter reads** — `duration_flight_s`, `path_km`,
  `alt_range_m`, `extent_km`;
- **georeference** — `lat0`, `lon0`, `alt0` (the measured altitude at the origin fix,
  informational only);
- **resampling** — `dt_native_s`, `g_max_s`, `n_segments`, `n_segments_kept`,
  `frac_interpolated`, `frac_z_reconstructed`, `z_gap_max_s`, `was_resampled`;
- **smoothing** — `savgol_order`, `savgol_window_horiz`, `savgol_window_vert`.

Fields unavailable for a source stay `null`. Run-level fingerprints belong to `run_manifest.json`; they are not repeated per fix.

## Rebuilding and verification

Use `uv run python scripts/rebuild_thesis.py --clean --jobs 8 --full-speed` to
regenerate the complete current dataset and manuscript. For low-priority processing,
use `--jobs 1` and omit `--full-speed`. The [rebuild guide](rebuilding.md) explains
locks, incomplete-run markers, version checks, logs and the independent reprocessing
sample. The [data guide](data-on-disk.md) covers safe table reading.

Automated checks establish numerical invariants and agreement with implemented rules.
They do not establish complete error detection, optimal thresholds or segmentation
accuracy. Remaining scientific checks include threshold/window sensitivity, the effect
of unreturned altitude shifts, conditional analyses excluding reconstructed support,
and independent manual phase labels.

## Catalog quirks

Catalogue distance, duration, task and wing-class fields are metadata, not replacements
for measurements from the recording. Unknown certification classes remain eligible for
pooled analyses but cannot be assigned to an equipment contrast. The primary key is
`(source, flight_id)` because separate archives can reuse a numerical ID. Dates can be
incomplete; a filename date is not proof that the recording clock has been validated.
Keep the original XML and catalogue acquisition state alongside the raw IGC files.
