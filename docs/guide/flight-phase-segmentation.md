# Flight-phase segmentation

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
the same feature/Viterbi path only for the selected, already-cleaned flight. Equal phases
separated in time, acquisition gaps and preprocessing segments are drawn as independent
runs, so the display never inserts a false connecting line. The title and status line say
whether state names are provisional or manually calibrated.

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
