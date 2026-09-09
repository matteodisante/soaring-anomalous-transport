# Flight-phase segmentation

The phase analysis reads the final preprocessed `fixes.parquet` table and writes new
tables in `derived/segmentation/`; it never modifies the input trajectories. A separate
continuous Gaussian HMM is fitted for paragliders and hang gliders. Its decision interval
is 10 s and its four 30-s features are vertical speed, horizontal speed, absolute turn
rate and turn-direction coherence.

```bash
uv run python scripts/segment_flights.py all --discipline paragliders \
  --annotations /path/to/phase_annotations.csv
```

`train` fits the unsupervised model and maps numerical states to phase names from the
train annotations. `apply` decodes the archive with Viterbi and writes phase tables.
`evaluate` produces validation or test metrics without refitting the model.

After both disciplines have been decoded, generate the Chapter-4 diagnostic figures,
confusion matrices and thesis metric macros with:

```bash
uv run python scripts/reporting/ch4_flight_phases/generate_segmentation_report.py \
  --annotations /path/to/phase_annotations.csv
```

## Manual annotations

Annotations are intervals in the processed clock of one preprocessing segment. They must
have these columns:

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

## Outputs

- `model/gaussian_hmm.pkl` and `model/metadata.json`: the fitted HMM, train-only scaler,
  feature schema, seed, model parameters and semantic state mapping.
- `model/split_manifest.parquet`: reproducible flight-level train/validation/test split.
- `phase_points.parquet`: one 10-s decision point with Viterbi phase and posterior
  probabilities. Feature-window edges are explicitly `unclassified`. A
  `quality_masked` flag identifies an interior non-classifiable window: a 30-s feature
  window touching reconstructed altitude or a Savitzky--Golay edge derivative is not
  decoded and breaks the HMM sequence.
- `phase_segments.parquet`: consecutive phase runs, with duration and left/right
  censoring flags at the observable part of a preprocessing segment.
- `metrics_validation.json` and `metrics_test.json`: accuracy, per-phase
  precision/recall/F1, macro-F1 and a flight-cluster bootstrap interval.
