# Flight-phase segmentation

The current viewer decoder allows search to be skipped and uses the Gaussian emission
marginal without turn coherence; see [Current decoder](#current-decoder-optional-search-and-marginal-emissions).

The phase analysis reads the final preprocessed `fixes.parquet` table and writes new
tables in `derived/segmentation/`; it never modifies the input trajectories. A separate
continuous Gaussian HMM is fitted for paragliders and hang gliders. Its decision interval
is 10 s and its four 30-s features are vertical speed, horizontal speed, absolute turn
rate and turn-direction coherence.

The archive-scale fit can start before manual labels exist.  In that case the numerical
components receive an explicitly provisional mechanics-based name; this makes the output
inspectable but is not validation:

```bash
uv run python scripts/segment_flights.py train --discipline paragliders
uv run python scripts/segment_flights.py apply --discipline paragliders
uv run python scripts/segment_flights.py train --discipline "hang gliders"
uv run python scripts/segment_flights.py apply --discipline "hang gliders"
```

`train` fits the best of ten unsupervised initializations. `apply` decodes the archive
with Viterbi and writes the phase tables.  Both stages use up to eight independent worker
processes as configured in `configs/segmentation.yaml`; each fitting worker is limited to
one internal BLAS thread to avoid nested oversubscription.

The completed provisional run can already generate the model and trajectory diagnostics
that Chapter 4 marks as provisional:

```bash
uv run python scripts/reporting/ch4_flight_phases/generate_segmentation_report.py \
  --config configs/segmentation.yaml
```

After both disciplines have been decoded, generate the Chapter-4 diagnostic figures,
confusion matrices and thesis metric macros with:

```bash
uv run python scripts/reporting/ch4_flight_phases/generate_segmentation_report.py \
  --annotations /path/to/phase_annotations.csv
```

## Manual annotations

Annotations are intervals in the processed clock of one preprocessing segment. They must
have these columns; `configs/phase_annotations.example.csv` is a directly reusable
template:

| column | meaning |
| --- | --- |
| `source`, `flight_id`, `segment_id` | exact identity of the preprocessed segment |
| `t_start`, `t_end` | half-open interval `[t_start, t_end)` in seconds; intervals may touch but may not overlap |
| `state` | `transition`, `search`, or `climb` |
| `split` | `train`, `validation`, or `test` |
| `annotator` | person who made the judgement |

The `train` labels never enter Baum--Welch fitting: they only resolve the arbitrary HMM
component order. Validation labels diagnose modelling choices; test labels are held out
until the final evaluation.

Prepare and label the repository's blinded, fixed-split candidate pack with:

```bash
uv run python scripts/reporting/ch4_flight_phases/prepare_annotation_pack.py
uv run python scripts/label_flight_phases.py --annotator "Matteo Di Sante"
```

In the labeler, drag an interval in the altitude panel and press `t` (transition), `s`
(search), or `c` (climb); the arrow keys change candidate and `u` removes the most recent
interval for the current candidate.  Boundaries snap to the 10-s decision grid and the
canonical CSV is saved after every edit.  Leave genuinely ambiguous boundary regions
unlabelled.  The PDF beside the GUI input is a static, blinded cross-check: neither it nor
the GUI shows HMM predictions.

After the CSV contains labels, calibrate the names without refitting or rescanning the
41-GB source table, evaluate validation first, and only then open the test result:

```bash
for discipline in paragliders "hang gliders"; do
  uv run python scripts/segment_flights.py calibrate --discipline "$discipline" \
    --annotations annotations/phase_labeling/phase_annotations.csv
  uv run python scripts/segment_flights.py evaluate --discipline "$discipline" \
    --annotations annotations/phase_labeling/phase_annotations.csv --split validation
done

# Once the method is frozen:
uv run python scripts/reporting/ch4_flight_phases/generate_segmentation_report.py \
  --annotations annotations/phase_labeling/phase_annotations.csv \
  --config configs/segmentation.yaml
```

`calibrate` finds the one-to-one Hungarian assignment from train annotations and
atomically relabels the already decoded point and run tables. The final reporter then
writes both validation/test metrics, flight-bootstrap intervals and held-out confusion
matrices.

## Interactive viewer

Install the optional Qt group and launch the existing trajectory viewer:

```bash
uv sync --group viewer
uv run --group viewer soaring-viewer
```

The **Cleaned colour** selector defaults to **Flight phase (HMM)**. Transition, search,
climb and non-classifiable decision points have fixed colours in both 2-D and 3-D views;
preprocessing-segment and single-colour modes remain available. The viewer does not scan
the multi-gigabyte `phase_points.parquet`: it caches the small discipline model and runs
the same feature/Viterbi path only for the selected, already-cleaned flight. The display
keeps **every native cleaned vertex**: a 10-s decision supplies a colour for the half-open
cell `[t - 5 s, t + 5 s)`, never replacement coordinates. Missing decisions, feature
edges and ineligible segments remain grey. Consecutive colour runs share an endpoint
so every cleaned edge is visible; acquisition gaps and preprocessing segments are never
bridged. This display interpolation adds no temporal precision to the classifier.

Colour, visibility and tick-format changes preserve zoom, pan and the 3-D camera,
including rotations made with the mouse. Zoom controls preserve orientation and the
current centre; orientation controls preserve zoom. Each coordinate/axis combination
remembers its view until another flight is loaded. Home/Reset view explicitly reset it.

Catalog search exposes every matching row through a virtual table, with no 500-flight
cutoff. Pipeline status distinguishes `Kept`, `Dropped` (hover for the archived reason),
`No archived result`, and `Pipeline results unavailable`. A catalog entry without a
pipeline record is not evidence of rejection; it may lack a downloaded trajectory.
Opening a flight recomputes preprocessing with the current configuration, and the status
message reports that current result separately from the archived verdict.

The title and status line say whether state names are provisional or manually calibrated.
A circling trajectory is not by itself a validated `climb` label: the model also uses
30-s vertical/horizontal speed and turning statistics. In the current provisional
paraglider artifact, the component named climb has mean turn coherence approximately
0.999999, versus 0.643 for search. Consequently some rising, circling intervals with
less uniform turning are labelled search. For flight `20279877`, 41 decision points
with mean vertical speed above 0.5 m/s and mean absolute turn rate above 0.12 rad/s
are labelled search, versus 34 labelled climb (diagnostic thresholds, not ground truth).
The plot correction does not change these predictions. Resolving that semantic issue
requires annotated examples and validation of the mapping/emissions, not a colour swap
in the viewer.

## Outputs

- `model/gaussian_hmm.pkl` and `model/metadata.json`: the fitted HMM, train-only scaler,
  feature schema, seed, model parameters and semantic state mapping.
- `model/split_manifest.parquet`: reproducible flight-level train/validation/test split.
- `model/fit_sample_manifest.parquet`: the exact whole feature blocks used by EM,
  including their deterministic order and observation counts.
- `phase_points.parquet`: one 10-s decision point with Viterbi phase and posterior
  probabilities. Feature-window edges are explicitly `unclassified`. A
  `quality_masked` flag identifies an interior non-classifiable window: a 30-s feature
  window touching reconstructed altitude or a Savitzky--Golay edge derivative is not
  decoded and breaks the HMM sequence.
- `phase_segments.parquet`: consecutive phase runs, with duration and left/right
  censoring flags at the observable part of a preprocessing segment.
- `phase_coverage.parquet`: one audit row per preprocessing segment, including slow
  native-cadence segments that were skipped rather than upsampled.
- `metrics_validation.json` and `metrics_test.json`: accuracy, per-phase
  precision/recall/F1, macro-F1 and a flight-cluster bootstrap interval.
- `diagnostics.json`: train/validation/test likelihood per observation, phase
  occupancies, run and censoring counts and uncensored mean durations, plus every restart
  score and convergence flag. The reporting command also writes the model matrices, example trajectories,
  test confusion matrices and the generated thesis metric table.

## Earlier cyclic policy and coverage audit (2026-09-10)

This audit records the initial symmetric cycle policy. The current decoder below
supersedes that policy while preserving the coverage masks and counts.
The viewer explicitly uses `sequence_prior` from `configs/segmentation.yaml`
when decoding the selected flight. State names still require manual validation.
The preference is **transition → search → climb → transition**, with persistence
within each phase. It changes Viterbi decoding and the posterior together, not a
post-hoc recolouring or a deletion of short runs. Every exceptional transition
remains possible; no minimum phase duration is imposed.

For a learned transition row, let `s` be its self-transition probability and `q`
its conditional distribution given an exit. The configured weight is `w = 0.75`.
The decoding row uses:

- `s_new = s + w * max(0, exp(-decision_step_s / 120 s) - s)`;
- `q_new = (1 - w) * q + w * q_cycle`, where `q_cycle` assigns 0.85 to the
  next phase in the cycle and 0.15 to the other exit;
- off-diagonal probabilities `(1 - s_new) * q_new`.

These are provisional modelling choices, not fitted or validated behavioural
frequencies. The 120-s scale is a soft persistence target, not a measured dwell time.
The policy is applied after semantic naming and is invariant to raw component IDs.
Before names are assigned, decoding uses the learned matrix. If an artifact with
an active policy is manually calibrated, its saved features are decoded again:
simply renaming existing predictions would leave the wrong semantic transition prior.

The existing paraglider model favoured climb → search (0.1670 per 10-s decision)
over climb → transition (0.0059). The policy changes those probabilities to 0.0365
and 0.0667, respectively, and increases climb persistence from 0.8270 to 0.8968.
The narrow climb emission distribution discussed above still matters: this policy
cannot guarantee that every visually plausible climb is recognised.

On three already identified retained flights, the number of adjacent classified
phase changes was 48 → 42 (`20279877`), 113 → 111 (`20275040`), and 93 → 93
(`20275270`). Acquisition gaps and unclassified intervals are excluded from those
counts. This checks the effect on fragmentation; **it is not an accuracy score**.
The cropped screenshots do not provide readable flight IDs, so these are separate
reproducible examples, not a claim to have identified every screenshot interval.

Legacy model metadata without a `sequence_prior` field preserves its original
transition matrix. Existing archive phase tables are unchanged. To export the same
policy the viewer uses into a separate archive subdirectory:

```bash
uv run python scripts/segment_flights.py apply --discipline paragliders --sequence-prior
# writes derived/segmentation/sequence-prior/{model,phase_*.parquet}
# Calibrate or evaluate that variant with the same flag and manual annotations:
uv run python scripts/segment_flights.py evaluate --discipline paragliders \
  --sequence-prior --annotations /path/to/phase_annotations.csv --split validation
```

The variant stores its model, policy configuration and fitting manifests together;
it does not replace the legacy tables or refit emissions. Newly trained artifacts
store the configured policy for subsequent decoding. Model diagnostic transition
plots show the effective decoding matrix. Fit log likelihood still describes the
original emission/transition fit, not validation of the added policy.

### What unclassified means

There is **no posterior-confidence cutoff**. Every valid feature window receives
one of the three phases. Grey denotes unavailable inputs/support:

- a centred 30-s feature window extending past a preprocessing segment boundary;
- a feature window touching `z_reconstructed` or preprocessing `edge` fixes;
- a native cadence above the 10-s eligibility limit, so no decision grid is emitted;
- a cleaned tail beyond the final half-open decision cell.

The viewer reports the percentage of its **cleaned fixes** and counts by cause.
For an archive, use the streaming audit, which writes `coverage_summary.json`:

```bash
uv run python scripts/segment_flights.py coverage --discipline paragliders
uv run python scripts/segment_flights.py coverage --discipline "hang gliders"
# Add --sequence-prior to audit an already generated variant.
```

The complete archive audit on 2026-09-10 found:

| Denominator | Paragliders | Hang gliders |
| --- | ---: | ---: |
| Non-classified HMM decisions / all emitted HMM decisions | 6.7662% | 4.6386% |
| Non-classified duration / all retained cleaned-segment duration | 7.4570% | 5.0660% |
| Emitted HMM decisions | 171,856,576 | 7,306,503 |

The duration denominator includes slow segments omitted from the decision grid,
excludes acquisition gaps, and clips decision cells at segment boundaries. It
measures time coverage, not the fraction of flights, segments, or native fixes.
Breakdown as percentages of that total cleaned duration:

| Exclusion | Paragliders | Hang gliders |
| --- | ---: | ---: |
| Windows touching reconstructed altitude / preprocessing edges | 6.3565% | 4.2842% |
| Ineligible native cadence | 0.8010% | 0.5115% |
| Feature-window boundaries | 0.2908% | 0.2653% |
| Tails outside decision cells | 0.0086% | 0.0050% |

The masks are unchanged by the sequence policy. Machine-readable counts, model
metadata hashes, transition matrices and example-flight results are in
[`revisions/segmentation-sequence-2026-09-10.json`](../../revisions/segmentation-sequence-2026-09-10.json).


## Current decoder: optional search and marginal emissions

Flight `20311250` (2021-10-01) exposed two distinct problems. Search must be optional
or brief, whereas climb should preferentially exit to transition. Also, the fitted
climb component's raw turn-coherence standard deviation is only 0.0000883 around a
mean of 0.9999986. Ordinary circling with slightly irregular turning consequently
receives negligible climb likelihood even with positive vertical speed. The hang-glider
artifact has the same defect (coherence standard deviation 0.0000604). A transition
prior alone cannot overcome this emission effect.

The current configuration therefore makes two independent changes:

- `allow_search_skip: true` makes the exit target from transition neutral between
  search and climb. It blends with the learned exit probabilities, so it allows a
  direct transition → climb without forcing either exit.
- `search_mean_dwell_s: 20` gives search a separate soft target. Its persistence is
  blended toward `exp(-decision_step_s / 20)`, including downward changes. Climb and
  transition keep the earlier 120-s persistence floor. Neither scale is a minimum
  duration or a measured behavioural duration. The cyclic exit target from search
  and climb uses `forward_probability: 0.95`, with exceptions still allowed.

For the paraglider model, transition → climb increases from 0.00734 to 0.02320 per
10-s step; search self-transition decreases from 0.90077 to 0.66563; climb exits
prefer transition (0.07442) over search (0.02879).

Separately, `marginalize_turn_coherence: true` decodes the **three-dimensional Gaussian
marginal** over mean vertical speed, mean horizontal speed and mean absolute turn rate.
It integrates out coherence using the retained mean entries and principal covariance
submatrix. It does not condition on a fixed coherence value, alter native fixes, or
retrain the original four-dimensional model. The original Gaussian parameters remain
available. Viterbi and posterior probabilities use the same marginal likelihood.
Coherence is still calculated and saved as a diagnostic feature.

On the reported flight, changing the sequence prior alone leaves 6 decisions labelled
climb. With the marginal emissions, this becomes 32. In the reproducible interval
`t=1640..1810 s` (relative to cleaned-flight start), the rising turn is now continuous
climb; transition starts at `t=1820 s`, without an inserted search at the summit.
This is a targeted regression expectation, not an independent validation annotation.
The retained search regions elsewhere in the flight are not automatically erased.

Four-flight comparisons, including the sequence-only ablation, are recorded in
[`revisions/segmentation-optional-search-2026-09-10.json`](../../revisions/segmentation-optional-search-2026-09-10.json).
The compact numerical regression fixture in `tests/fixtures/segmentation_20311250.json`
contains the original fitted parameters and feature-window excerpt, making this check
independent of the mounted SSD. Tests also verify marginal Gaussian probabilities,
component-permutation invariance, and preservation of the original artifact.

The viewer applies both current options to on-demand decoding. For matching separate
archive exports, `--current-decoder` is an alias of `--sequence-prior` and applies both
the configured sequence policy and emission marginalization:

```bash
uv run python scripts/segment_flights.py apply --discipline paragliders --current-decoder
```

The destination remains `derived/segmentation/sequence-prior/`, with both choices
persisted in its model metadata. Legacy metadata missing the new options reproduces
the old behaviour. Existing archive phase tables and their coverage masks are unchanged.
The three-dimensional marginal can still overlap search and climb; semantic calibration
and accuracy claims require independent manual annotations.
