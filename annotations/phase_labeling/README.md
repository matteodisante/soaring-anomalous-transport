# Manual flight-phase labels

This pack is deliberately blind: it contains the trajectory and four continuous
features, but no HMM prediction.  Keep it blind until validation is complete.

Launch the autosaving interval labeler from the repository root:

```bash
uv run python scripts/label_flight_phases.py --annotator "Matteo Di Sante"
```

For each candidate, drag a time interval in the altitude panel and press:

- `t` — **transition**: sustained directed/relatively straight glide between lift
  regions; low turning intensity, usually neutral or negative mean vertical speed;
- `s` — **search**: exploratory, reversing or recentering turns without sustained
  coherent positive climb;
- `c` — **climb**: sustained exploitation of lift, normally positive mean vertical
  speed together with coherent circling.

Use left/right arrows to change candidate and `u` to undo the last interval on the
current candidate.  Buttons provide the same actions.  Times snap to the 10-s decision
grid, and `phase_annotations.csv` is saved after every edit.

Label all clearly interpretable portions of every candidate, including train,
validation and test.  Do not force a label at an ambiguous boundary: leave a short gap
instead.  Do not inspect the model-coloured viewer while assigning these intervals.
Train candidates are longer because their labels resolve the arbitrary numerical-state
permutation; validation and test candidates are independent 30-minute windows wherever
the source segment supports one.

The static `annotation_pack.pdf` has one page per candidate and is useful as a second
view. `annotation_windows.csv` records the immutable selection, while
`annotation_candidates.parquet` is the GUI input.  Only `phase_annotations.csv` should
be edited by the labeling process.
