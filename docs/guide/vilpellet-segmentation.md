# The Vilpellet segmenter

`soaring.analysis.segmentation.vilpellet` is a transcription of Jérémie Vilpellet's
flight-phase segmenter, the one behind the phase-resolved results of
[`vilpellet2026`](bibliography.md). It assigns **transition**, **search** and **climb**
to individual fixes from three binary indicators and a three-state hidden Markov model.
It runs beside the Gaussian model of [the segmentation guide](flight-phase-segmentation.md),
which answers the same question from standardised kinematic means on a ten-second grid.
Keeping both runnable is what allows the choice between them to be settled by
measurement.

This package reproduces an existing segmentation. Every parameter is read from
`configs/segmentation_vilpellet.yaml` and applied as it stands. Nothing in this
repository fits or tunes any of them.

## Provenance of the fitted parameters

The reference implementation is `flight_phase_inference_minimal.py` of the internship
package, an inference-only extract of `scripts/hmm/train_hmm.py` in the same package.
The model was fitted once, by Baum-Welch, on 2019 paraglider flights from four Alpine
take-off sites. Those fitted emission, transition and initial vectors are applied
unchanged to every flight this repository decodes, including hang-glider flights, 2021
and 2022 seasons, and sites outside the Alps.

The straightness thresholds come from a separate part of the same work
(`scripts/radius_treshold_kernel/`), where Vilpellet read them off a kernel density
estimate of the turn-angle distribution, one per glider class:

| Discipline | `alpha_straight_rad` (radians per fix) |
| --- | --- |
| `paragliders` | 0.20960958 |
| `hang gliders` | 0.17398039 |
| `sailplanes` | 0.1 |

A literal transcription of the reference script was run beside this port on five real
IGC flights. The ENU coordinates, the smoothed turn increment, the vertical speed, the
observation matrix, the raw Viterbi path and the majority-smoothed path agree
bit for bit. That check establishes implementation identity. It establishes nothing
about how well the labels describe the pilots' behaviour.

## Input, and the double smoothing that follows

`input.source` selects the trajectory the features are built from.

| Value | Trajectory |
| --- | --- |
| `cleaned` (default) | This repository's preprocessed ENU columns `E`, `N`, `z`, so that the two segmenters see identical geometry |
| `raw_gnss` | Latitude, longitude and GNSS altitude read straight out of the `.igc` file, which is the input the reference implementation consumes |

`input.pre_smooth` is true, and it stays true on cleaned input. The Gaussian position
smoothing below belongs to the feature definition that the straightness threshold was
calibrated against, so removing it would compare a fitted threshold against a quantity
of different variance. The consequence is a double smoothing on the default path: the
[preprocessing pipeline](preprocessing-pipeline.md) has already fitted a cubic
Savitzky-Golay polynomial over five-second windows, and the Gaussian six-fix rolling
mean is then applied on top of that output. That differs from the reference pipeline,
which smooths raw GNSS coordinates once. Its effect on the decoded labels has not been
measured. Passing `--input raw_gnss` to the command line is the way to see how much of
the difference it accounts for.

## The three binary features

Windows below are counts of fixes. Write `theta_k = atan2(y_k - y_{k-1}, x_k - x_{k-1})`
for the heading of the step arriving at fix `k`. The intermediate quantities, in the
order they are computed:

1. A centred Gaussian rolling mean of six fixes, standard deviation `6 / 6 = 1`, applied
   to each of `E`, `N` and `z`. The first and last partial windows stay missing.
2. `turn_k = wrap_to_pi(theta_{k+1} - theta_k)` in radians per fix, then a centred
   rolling mean of six fixes with `min_periods=1`. The reference code names this
   `radius_curvature_lat_long_sgn`; the quantity it holds is an angle, and the
   straightness threshold is compared against it directly.
3. `v_z = (z_k - z_{k-1}) / (t_k - t_{k-1})`, then a centred rolling mean over the
   30-fix persistence window with `min_periods=1`.

With `alpha` the discipline's straightness threshold and `beta = 0.9` the persistence
fraction, the three emitted indicators are:

| Feature | Definition |
| --- | --- |
| `persistent_straight` | 1 when the mean of the per-fix indicator `-alpha < turn < alpha` over the centred 30-fix window exceeds `beta`. A missing increment compares false against both bounds, so the two ends of a track read as 0 |
| `positive_mean_v_z` | 1 when the 30-fix centred mean of `v_z` is strictly positive |
| `persistent_turn_sign` | 1 when, among the `30 // 2 = 15` increments of largest magnitude in the window, the more numerous sign covers at least `ceil(beta * 15) = 14` of them |

Selecting the 15 largest magnitudes keeps the near-zero increments of straight flight,
whose sign carries no information, from diluting the count. The window at fix `k` spans
`k - 15` to `k + 14`, with the track reflected at both ends. That asymmetry belongs to
the source implementation and is kept.

## The eight-category emission law, Viterbi, and the majority vote

The three indicators form a triple that indexes one of eight categories, enumerated

```
0:(0,0,0)  1:(0,0,1)  2:(0,1,0)  3:(0,1,1)  4:(1,0,0)  5:(1,0,1)  6:(1,1,0)  7:(1,1,1)
```

with the triple read as (persistent straightness, positive mean vertical speed,
persistent turn sign). Each of the three hidden components carries one categorical law
over those eight values. Rounded to three digits, the fitted emissions are:

| Component | `(0,0,0)` | `(0,0,1)` | `(0,1,0)` | `(0,1,1)` | `(1,0,0)` | `(1,0,1)` | `(1,1,0)` | `(1,1,1)` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0, climb | 0.000 | 0.001 | 0.000 | 0.999 | 0.000 | 0.000 | 0.000 | 0.000 |
| 1, search | 0.326 | 0.178 | 0.496 | 0.001 | 0.000 | 0.000 | 0.000 | 0.000 |
| 2, transition | 0.000 | 0.000 | 0.000 | 0.000 | 0.738 | 0.014 | 0.241 | 0.006 |

The transition matrix is strongly diagonal, with per-fix persistences 0.9896, 0.9900 and
0.9919. The initial distribution puts 0.0566 on component 0 and 0.9434 on component 1;
its third entry is numerically zero, so the fit never starts a flight in the straight
component. The exact values live in `configs/segmentation_vilpellet.yaml`.

Decoding is Viterbi under those parameters. The recursion renormalises the scores at
every step, which keeps the product of twenty thousand transition probabilities from
underflowing and cannot change the selected path, because one positive factor divides
every state at a step. Ties in the predecessor scan resolve toward the lowest state
index, matching the source's strict comparison.

A rolling majority vote of width 90 fixes is then applied to the decoded path, ties
resolved toward the label that sorts first. The vote removes the one- and two-fix flips
a per-fix decoder produces at a phase boundary. It also erases genuinely short phases,
so a run-duration study reads a distribution this smoother has already truncated from
below.

Decoding one 21,125-fix cleaned flight takes about 0.11 s on this machine, so the cost
of running the segmenter over an archive is dominated by reading the fix table.

## Eligibility, and the restriction to roughly 1 Hz logging

Every window above is a count of fixes. Six fixes, 30 fixes and 90 fixes only mean 6 s,
30 s and 90 s when the logger writes one fix per second, and `alpha` was calibrated in
radians per fix against a distribution of per-fix turn angles. On a track logged every
5 s the same 30-fix window covers 150 s of flight and the same threshold describes a
five times slower turn. The gate below is what keeps that reading from happening
silently:

| Gate | Value | `phase_reason` when it fires |
| --- | --- | --- |
| Mean logging step of the segment | strictly below 1.2 s | `cadence_above_gate` |
| Times strictly increasing and unique | required | `non_increasing_or_repeated_time` |
| Fixes in the segment | at least the 30-fix persistence window | `segment_shorter_than_persistence_window` |
| Fixes in the whole flight | at least 3600 | `flight_shorter_than_author_guard` |

The unit of work is one preprocessing segment, which is contiguous and uniformly
sampled, so no feature window and no state transition crosses a boundary the cleaning
drew. A segment that fails any gate comes back unlabelled with the reason recorded,
rather than decoded on a cadence the sample-count windows were never calibrated for.
`segment_flight(..., enforce_flight_guard=False)` lifts the 3600-fix flight guard alone;
it changes which fixes get a label and changes no label.

The gate leaves the interpretation of a decoded window approximate even when it passes.
A track at a mean step of 1.1 s still has its 30-fix window covering 33 s.

## Which component is which behaviour

Component 0 is climb, component 1 is search, component 2 is transition, and
`configs/segmentation_vilpellet.yaml` sets `state_names: [climb, search, transition]`
accordingly.

The reference implementation's own naming line disagrees:

```python
regime_map = {0: "transition", 1: "search", 2: "climb"}
```

Every other artefact of the same package reads 0 as thermaling, 1 as ARS and 2 as
commute: `scripts/data_stats/get_thermal_segment.py` keeps `regime == 0` segments in
order to measure *thermal* radii, and `docs/pipeline.md`, the initial-parameter comments
of `train_hmm.py` and `HMM_code_review.md` all say the same. The line above transposes
the first and third components. Setting `literal_minimal_script: true` in the
configuration reproduces that line deliberately, for anyone who needs to compare against
output the reference script printed.

Two pieces of evidence settle the direction. The first is the emission table above:
component 0 puts 0.999 of its mass on `(0,1,1)`, which reads as turning, rising and
holding one turn direction, and component 2 puts 0.738 plus 0.241 on `(1,0,0)` and
`(1,1,0)`, which reads as straight with no persistent turn sign.

The second is measurement on real flights. Five 2021 FFVL paraglider flights
(`20308851`, `20308854`, `20308841`, `20308842`, `20308843`, all from
`raw/igc/2021-2022/`) were decoded on their cleaned trajectories, and each decoded fix
was described by quantities the decoder did not use to reach its decision:

| Component | Mean `v_z` | Fraction straight | Turn-sign coherence |
| --- | --- | --- | --- |
| 0, climb | +0.63 to +1.83 m/s | 0.31 to 0.66 | 0.86 to 0.94 |
| 1, search | −0.33 to +0.70 m/s | 0.57 to 0.67 | 0.24 to 0.42 |
| 2, transition | −1.04 to −0.64 m/s | 0.98 to 0.99 | 0.10 to 0.20 |

Each cell gives the range of the per-flight value over those five flights. `Mean v_z` is
the mean of this repository's own vertical Savitzky-Golay derivative, which the binary
features never see. `Fraction straight` is the fraction of the component's fixes whose
smoothed turn increment satisfies `|turn| < alpha`, read before the persistence gate.
`Turn-sign coherence` is the fraction whose `persistent_turn_sign` indicator fires.
Component 0 rises while holding a turn direction, component 2 descends in a straight
line, and component 1 sits between them on all three quantities. The behavioural
reading follows from that, and it is opposite to the `regime_map` line.

These numbers describe five flights of one season and one site cluster. They fix the
component ordering. They measure no accuracy.

## The author's usage recommendations

The reference script closes with three pieces of advice from its author: discard the
last ten minutes of each flight, keep a search run only when a climb follows it, and
prefer long runs because short ones are the least reliably identified. The
configuration records all three, and all three are inactive by default:

| Key | Default | Effect when set |
| --- | --- | --- |
| `recommendations.drop_tail_s` | `0.0` | Fixes in the final `drop_tail_s` seconds return to `unclassified` with reason `dropped_flight_tail` |
| `recommendations.min_run_s` | `0.0` | Decoded runs shorter than this return to `unclassified` with reason `run_shorter_than_minimum` |
| `recommendations.search_requires_following_climb` | `false` | A search run with no climb after it returns to `unclassified` with reason `search_not_followed_by_climb` |

They select which decoded runs an analysis keeps, so they belong to that analysis rather
than to the segmentation. The segmentation itself labels every eligible fix. Each
rejected fix keeps its own reason, so discarded time stays countable instead of merging
into one unclassified total. `with_recommendations(config, ...)` switches them on for one
call without editing the configuration file.

Switching them on changes what any coverage or duration number means, because the
denominator of a phase fraction then excludes time that was decoded and thrown away.
State which of the three were active alongside any number produced under them.

## Running it

The Python API takes a cleaned fix table and returns the same table with labels:

```python
from soaring.analysis.segmentation.vilpellet import (
    load_vilpellet_config, phase_runs, segment_flight,
)

config = load_vilpellet_config()
track = segment_flight(result.fixes, config, discipline="paragliders")
runs = phase_runs(track.fixes, config)
climb = track.fixes.loc[track.fixes["phase"] == "climb"]
```

`track.fixes` carries `phase`, `phase_reason`, `phase_component` (nullable integer),
`track_run` and `phase_run`. Those are exactly the columns
`soaring.viewer.data.phases_on_cleaned_fixes` produces for the Gaussian segmenter, so
the two are interchangeable wherever a labelled trajectory is drawn.
`track.eligible`, `track.reasons`, `track.discipline` and `track.alpha_straight_rad`
record what the gate decided and which threshold was used.
`phase_runs` collapses the fix table into one row per uninterrupted run, with
`left_censored` and `right_censored` marking the runs whose true length was cut by a gap
or by the end of the flight. The lower-level entry points `build_observation_frame`,
`observation_matrix`, `viterbi`, `rolling_majority`, `emission_probabilities` and
`segment_eligibility` are exported for tests and for inspecting one stage at a time.

`scripts/segment_flights_vilpellet.py` is the command line around the same calls. It
has three actions.

```bash
# One file, decoded and reported without writing anything
uv run python scripts/segment_flights_vilpellet.py flight \
  --igc /Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2021-2022/2021-09-01_20308851.igc

# The same file on the reference implementation's own input
uv run python scripts/segment_flights_vilpellet.py flight \
  --igc <path>.igc --input raw_gnss --out /tmp/one-flight

# A whole archive, appended flight by flight, across several worker processes
uv run python scripts/segment_flights_vilpellet.py apply --discipline paragliders

# Re-read what apply wrote and rewrite the coverage record from it
uv run python scripts/segment_flights_vilpellet.py coverage --discipline paragliders
```

The `flight` action prints the composition of one flight:

```
2021-09-01_20308851 [cleaned]: 21125 fixes over 352.1 min
  discipline paragliders, alpha = 0.20960958 rad/fix, eligible = True
  phase             fixes  fix frac  time frac   runs
  climb              5814     0.275      0.274     50
  search             1342     0.064      0.063     29
  transition        13969     0.661      0.663     42
  reasons: classified=21125
```

`--igc` runs the preprocessing pipeline over that one file on demand, so the result
reflects the cleaning as configured now. `--discipline` is inferred from the path when
the file sits inside a configured archive and is required otherwise. `--input` overrides
`input.source` for the `flight` action only, `--out` writes that flight's tables into a
directory of your choice, `--limit` stops `apply` after a number of flights, `--config`
points at a replacement YAML file, `--jobs` overrides the worker count `apply` decodes
with (default: the machine's core count minus two, so an archive-wide pass leaves the
rest of the machine usable; pass `1` to force single-process decoding), and
`--with-points` additionally writes the fix-level table described below.

`apply` and `coverage` write only below `derived/segmentation/vilpellet/` on the
selected archive. They never change the `fixes.parquet` input and never touch the
Gaussian segmenter's tables one directory up.

| File | Contents | Written |
| --- | --- | --- |
| `phase_segments.parquet` | One row per run: identity, `phase`, `t_start`, `t_end`, `duration_s`, `n_fixes`, `left_censored`, `right_censored` | Always |
| `phase_coverage.parquet` | One row per cleaned preprocessing segment: identity, `t_start`, `t_end`, `n_native_fixes`, `native_cadence_s`, `n_classified_fixes`, `status` (`classified`, or the `phase_reason` that excluded the whole segment) | Always |
| `model/parameters.json` | The exact configuration this export applied: window sizes, `alpha_straight_rad`, the eligibility gate, and the fitted emission, transition and initial arrays, for later audit | Always |
| `phase_points.parquet` | `source`, `flight_id`, `segment_id`, `t`, `E`, `N`, `z`, `phase`, `phase_component`, `phase_reason` | Only with `--with-points` |
| `coverage.json` | Flight and fix counts, per-phase fix and time fractions, run counts, and the fix count behind every `phase_reason` | Always |

The run and per-segment tables are what `apply` writes by default. The labels are
piecewise constant within a preprocessing segment (the segmenter classifies a whole
eligible segment or excludes it for one uniform reason), so `phase_segments.parquet`
reconstructs every per-fix label exactly; on the paraglider archive it measures 0.18
byte per fix against the fix-level table's 24 byte per fix, 0.22 GB against 30 GB.
`--with-points` writes the larger table anyway, for a use that genuinely needs one row
per fix (the annotation pack, for instance) rather than one row per run.

`apply` streams the fix table one flight at a time, decodes independent flights across
several worker processes, and flushes its Parquet writers in bounded batches, so an
interrupt leaves a readable prefix of the archive and a coverage record that says it was
interrupted. The `coverage` action re-derives `coverage.json` from whichever written
table is richest -- the fix-level table when `--with-points` produced one, otherwise the
per-segment table, which is exact for flight and fix totals and for the
classified/unclassified split. It refuses to overwrite an existing `coverage.json` with
one that reports fewer flights, so a re-derivation that can see less than `apply` already
recorded cannot silently erase what `apply` wrote. The `fix_fraction` in `coverage.json`
divides by every fix seen; the `time_fraction` divides by summed run duration, where a
run spans its first fix to its last one and so counts one logging step less than the
time it occupies. Neither quantity measures classification accuracy.

`scripts/reporting/ch5_vilpellet/generate_vilpellet_report.py` decodes one named flight
with both segmenters on identical cleaned geometry and writes the chapter's comparison
figure, its timeline, its numerical macros and a JSON provenance record.

## Seeing it in the viewer

The viewer (`uv run --group viewer soaring-viewer`) draws the selected cleaned flight and
can colour it by either segmenter. Set **Cleaned colour** to `Flight phase (HMM)` first:
the two controls below are enabled exactly while phase colouring is selected, and they
mean nothing under the segment or single-colour modes.

| Control | Options and effect |
| --- | --- |
| **Segmentation** combo | `Chapter 4 HMM (this work)` colours the trajectory with the Gaussian model of [the segmentation guide](flight-phase-segmentation.md). `Vilpellet (Jérémie)` colours it with the transcribed model of this page. `Compare side by side` puts the two in adjacent panels on the same flight |
| **Thermals only (climb)** | Keeps the climb fixes and hides the rest of the flight, which is the selection `get_thermal_segment.py` makes in the reference package |
| **Full screen** | Gives the plot canvas the whole window |
| **Save PDF…** | Writes whatever is currently drawn, including a comparison |

The comparison panels share axes and geometry, so a disagreement between the two models
reads off one screen. Reading it that way shows where the two differ. It does not show
which one is right, because neither panel carries a human label.

The viewer decodes only the flight currently selected, preserves native coordinates and
keeps acquisition gaps visible. Its percentage of classified native fixes has a different
denominator from the `coverage.json` fractions above, and neither quantity is accuracy.

## What is not validated

Nothing here has been checked against independent human labels. The port has been
checked against the reference implementation value by value, and the component ordering
has been checked against measured vertical speed, straightness and turn-sign coherence.
Both checks concern the code and the naming.

The open points are:

- **No independent manual annotation.** No set of human phase labels has been compared
  against these decoded labels, on any flight, in either discipline. Precision, recall
  and boundary error are unmeasured. The same limitation holds for the Gaussian model,
  and [the annotation workflow](flight-phase-segmentation.md#manual-labels-what-to-do-next)
  is the route to removing it for both.
- **Parameters transferred across archive and year.** The emissions, transitions and
  initial distribution were fitted on 2019 paraglider flights from four Alpine sites,
  and this repository applies them to 2021 and 2022 FFVL flights from the whole French
  domain, and to hang gliders through a straightness threshold alone. Transfer of that
  kind is assumed here, and it is untested.
- **The double smoothing** on the default cleaned input has no measured effect.
- **The 90-fix majority vote** truncates the run-length distribution from below by an
  amount nobody has quantified.
- **The eligibility gate admits a range of cadences**, and the fix-counted windows mean
  slightly different durations across that range.

Coverage fractions, run counts and phase fractions describe what the decoder decided.
They do not describe how often it was right.
