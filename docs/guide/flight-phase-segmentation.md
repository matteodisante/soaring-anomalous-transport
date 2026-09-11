# Flight-phase segmentation

The segmenter assigns **transition**, **search** and **climb** to 10-second decisions.
Names are provisional until checked against independent human labels. The code has
numerical regression tests; it does not yet have measured behavioural accuracy.

## Input, features and quality support

`derived/fixes.parquet` supplies the smoothed trajectory and its derivatives. Each
preprocessing segment is treated independently. A native cadence above 10 s is excluded.
At eligible cadences, centred 30-s windows integrate the piecewise-linear interpolants
of four quantities calculated at native fixes:

| Feature | Definition |
| --- | --- |
| Mean vertical speed | Window integral of `v_z`, divided by 30 s |
| Mean horizontal speed | Window integral of `sqrt(v_E² + v_N²)`, divided by 30 s |
| Mean absolute turn rate | Window integral of the interpolated native `abs(omega)`, divided by 30 s |
| Turn coherence | Absolute signed-turn integral / absolute-turn integral; zero if the radian denominator is at most float64 epsilon; round-off clipped to [0,1] |

Here `omega = (v_E*a_N - v_N*a_E)/(v_E² + v_N²)` when horizontal speed is at least
1 m/s, and zero below that floor. Taking the absolute value **before** interpolation
matters at reversals: integrating interpolated `abs(omega)` is different from integrating
the absolute value of interpolated `omega`. Coherence remains between zero and one.

A window is unavailable if its native interpolation support includes `z_reconstructed`,
`z_derivative_reconstructed`, or `edge`. The propagated derivative flag includes the
whole vertical Savitzky–Golay fit support. Native fixes bracketing window endpoints also
belong to the support. Unavailable decisions break HMM sequences. There is no posterior
confidence threshold: grey means missing or excluded support, not low confidence.

Fresh feature extraction requires the propagated derivative flag, introduced with
preprocessing 2.2.0. Re-decoding previously saved features remains possible, but its
historical coverage is explicitly identified in the audit. Those old counts do not
measure the corrected mask. Rebuild cleaning and segmentation to update them.

## Fitting and current decoding

A separate full-covariance, four-dimensional Gaussian HMM is fitted per discipline.
The scaler is estimated from the selected training observations and then frozen.
Flight identities determine a stable 70/15/15 train/validation/test partition.
Whole valid feature blocks are selected deterministically within the configured memory
caps. Longer blocks receive greater likelihood weight; flights are not equally weighted.

`SOARING_MAX_WORKERS` limits concurrent restart workers and defaults to one. The effective
worker count is the minimum of that limit, configured `n_jobs`, and `n_restarts`.
All configured restarts still run with the same seeds; this changes scheduling, not
the scientific fitting protocol. The rebuild driver sets the limit from `--jobs`
(default one), limits BLAS threads to one, and runs workers at low process priority.

The current decoder makes two changes to the fitted model:

1. It integrates turn coherence out of the Gaussian, retaining the three other mean
   entries and their covariance submatrix. This is a **marginal of the fitted 4D
   model**, not a refitted 3D model or a conditional distribution at fixed coherence.
2. It applies the explicit transition policy in `configs/segmentation.yaml` to both
   Viterbi paths and forward–backward posterior probabilities.

The transition-policy weight is 0.75. Transition and climb persistence increase toward
`exp(-10/120)` if the fitted persistence is lower. Search persistence blends toward
`exp(-10/20)` in either direction. Conditional exits from transition have equal target
weights for search and climb; exits from search and climb favour the next phase in
transition → search → climb → transition with target probability 0.95. These are
provisional choices for validation, not observed durations, minimum run lengths, or
measured pilot transition frequencies. An absorbing fitted row receives equal exit
weights and persistence capped below one.

The coherence problem motivating marginalization is recorded in the numerical fixture
`tests/fixtures/segmentation_20311250.json`. It is a development example, not independent
validation. A separately fitted 3D model remains a necessary validation comparison.

The original library stopping flag accepted both the iteration cap and negative final
likelihood changes. New fits record convergence only for a finite last gain in
`[0, tol)` and reject non-finite scores. Earlier artifacts retain an explicit legacy
flag definition. The covariance initialization parameter `min_covar` is not a permanent
eigenvalue floor; Chapter 4 gives the actual covariance update and its limitation.

## Rebuild after a cleaning change

Cleaning changes coordinates, derivatives, quality masks and sometimes segment IDs or
processed time. Refit, reapply, recompute coverage and regenerate every report. The
canonical per-discipline stages are:

```bash
uv run python scripts/segment_flights.py train --discipline paragliders
uv run python scripts/segment_flights.py apply --discipline paragliders
uv run python scripts/segment_flights.py coverage --discipline paragliders
```

Repeat with `--discipline "hang gliders"`. `train` persists the current configuration;
`apply` then uses that configuration in `derived/segmentation/`. Human labels are not
needed for provisional fitting. Do not pass annotations from a different cleaning
snapshot without checking their processed-clock and segment correspondence.

Then regenerate the chapter reports in this order:

```bash
uv run python scripts/reporting/ch4_flight_phases/generate_segmentation_report.py
uv run python scripts/reporting/ch4_flight_phases/generate_decoder_audit.py
```

The audit first reproduces the saved archive using its own decoder configuration.
It then compares the current decoder with the fitted 4D/no-prior reference, reconstructed
from the same model. Thus the comparison works for both historical and freshly rebuilt
archives. Validation examples are selected by fixed manifest priority and decoded as
complete valid blocks before an eight-minute display excerpt is taken. Neither reporter
uses test trajectories for illustrative model development.

For an existing older artifact, `apply --current-decoder` remains available as a separate
export to `derived/segmentation/sequence-prior/`. This historical directory name covers
both transition policy and Gaussian marginalization. Use the same flag for its coverage,
calibration and evaluation. A newly trained canonical archive already uses the current
configuration and needs no duplicate export.

## Manual labels: what to do next

The existing 40-flight pack belongs to the earlier cleaning snapshot. Preserve it as a
record. After the rebuild, prepare a **new** pack tied to that snapshot:

```bash
uv run python scripts/reporting/ch4_flight_phases/prepare_annotation_pack.py \
  --output-dir annotations/phase_labeling/<snapshot-id>
uv run python scripts/label_flight_phases.py \
  --pack-dir annotations/phase_labeling/<snapshot-id> \
  --annotator "Matteo Di Sante" --split train
```

Replace `<snapshot-id>` with the rebuild identifier. The manifest records candidate
checksums and source file identities. The labeler checks intact local input files and,
when mounted, the cleaned source and split manifest. It refuses an outdated pack
after those inputs change. Model calibration can change predictions without invalidating
the blinded pack;
an intact copied pack can still be labelled offline. Pack preparation refuses to replace
a directory containing human labels.

Drag an interval on altitude, then press `t`, `s` or `c`; edits autosave. All time axes
share the zoom. Arrows change candidates and `u` removes the rightmost existing interval.
Boundaries snap to the actual 10-s grid, including offset clock origins. Model predictions
are hidden. Label all clearly interpretable parts and leave uncertain boundaries or
behaviours outside the vocabulary unlabelled. Keep a separate CSV for each observer.

Train labels resolve the component permutation. Use validation labels to compare decoder
choices, then freeze the procedure before opening test predictions or scores. Flights
20275040, 20279877 and 975 have already been inspected despite nominal test membership
and are excluded from annotation test candidates. Flight-level separation alone does not
remove dependencies between repeated pilots, dates or sites; new-region or new-season
claims require grouped holdouts.

For the freshly rebuilt canonical archive, evaluate one stage explicitly:

```bash
uv run python scripts/segment_flights.py calibrate --discipline paragliders \
  --annotations annotations/phase_labeling/<snapshot-id>/phase_annotations.csv
uv run python scripts/segment_flights.py evaluate --discipline paragliders \
  --annotations annotations/phase_labeling/<snapshot-id>/phase_annotations.csv \
  --split validation
```

Repeat per discipline; use `--split test` only after model choices are frozen. With a
semantic transition policy, calibration re-decodes after changing names, because the
policy depends on those names. The Hungarian assignment optimizes agreement for the
component path before that re-decoding; it does not guarantee the optimum agreement
of the final path. Check the resulting train agreement explicitly. It does not fit
emission parameters. The evaluator gives
precision, recall, F1, macro-F1 and flight-bootstrap intervals. Annotation coverage,
boundary error, observer agreement and grouped generalization are still to be measured.
Scores describe this deliberately varied candidate pack; they are not automatically
unbiased archive-wide accuracy estimates.

## Outputs and figures

| Product | Meaning |
| --- | --- |
| `model/gaussian_hmm.pkl`, `metadata.json` | Fitted parameters, scaler, mapping, settings, feature-support and convergence definitions |
| `model/split_manifest.parquet` | Fixed flight partition |
| `model/fit_sample_manifest.parquet` | Exact fitted blocks and counts |
| `phase_points.parquet` | Decisions, four features, masks, hard phase and posterior |
| `phase_segments.parquet` | Equal-phase runs, decision-cell duration and boundary-censoring flags |
| `phase_coverage.parquet`, `coverage_summary.json` | Available support, including ineligible segments |
| `metrics_validation.json`, `metrics_test.json` | Explicitly requested manual-label scores |
| `thesis/generated/segmentation_decoder_audit.json` | Model and feature identities, decoder comparisons, coverage and figure inputs |

Coverage is classified decision-cell duration divided by retained cleaned-segment
duration. Cells are clipped to segment bounds; acquisition gaps are excluded and slow
segments remain in the denominator. The viewer's percentage of classified native fixes
has a different denominator. Neither quantity is classification accuracy.

The viewer (`uv run --group viewer soaring-viewer`) decodes only the selected current
cleaned flight. It preserves native coordinates and colours each vertex by its 10-s
half-open decision cell. Acquisition gaps and unavailable support remain visible. Its
colours and phase names follow the same model settings used by the current reporter.

## Reading the chapter's indicators

Chapter 4 now develops the HMM probability law before its application: latent Markov
states, conditional emissions, likelihood, forward–backward posteriors, Viterbi
decoding and Gaussian Baum–Welch updates. A graph shows the conditional dependencies.
The generic maximum-likelihood formulas are distinguished from the installed covariance
regularization and the configured marginal decoder and transition preference.

The phase-figure quantity table defines every time-series axis, physical unit and
probability range. A separate schematic shows coherence 1, 0 and 1/2 for equal turning
amounts with different cancellation. Standardized features use training mean and
population standard deviation (divisor n), frozen on holdout flights. Posterior
probabilities sum to one over classified decisions and are conditional on the model.

Coverage fractions use clipped decision-cell durations divided by all retained
cleaned-segment time, including segments too slow to classify. Numerical restart
scores are relative log likelihood per fitted observation; the final EM gain is an
unnormalized log-likelihood difference. Coherence means and widths in the audit table
are transformed Gaussian-component parameters, not empirical moments of hard-labelled
climbs. These quantities do not measure classification accuracy.
