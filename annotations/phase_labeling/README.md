# Manual flight-phase labels

The current pack is [`20260910T221820Z-05d36ab4/`](20260910T221820Z-05d36ab4/), generated from the
complete cleaning 2.2.0 archive on 11 September 2026. It contains 40 candidate
flights: per discipline, 4 train, 8 validation and 8 test candidates. No human
reference intervals have been supplied. The task is to mark transition, search
and climb independently of the HMM so that classification errors can be measured.

The unversioned files in this parent directory preserve the first pack from the
earlier cleaned archive. Use the versioned pack above for the current analysis;
keep earlier packs and any labels as historical material.

The blinded pack shows trajectories and kinematics, without HMM predictions or
posterior scores. Processed clocks, segment identities and available windows can
change after cleaning, so each rebuild creates a separate pack.

Start from the repository root with the training candidates:

```bash
uv run python scripts/label_flight_phases.py \
  --pack-dir annotations/phase_labeling/20260910T221820Z-05d36ab4 \
  --annotator "Matteo Di Sante" --split train
```

After a future rebuild, use its newly printed pack directory. Drag a time interval
in the altitude panel, then press:

- `t` — **transition**: sustained directed travel between lift regions, usually
  little turning and neutral or negative mean vertical speed;
- `s` — **search**: exploratory, reversing or recentering turns without a sustained
  established climb;
- `c` — **climb**: sustained exploitation of lift, usually positive mean vertical
  speed with circling. A small reversal does not automatically disqualify a climb.

Label all clearly interpretable parts of a candidate. Leave ambiguous boundaries
or behaviours outside this vocabulary unlabelled. Do not label a turn as climb
solely because coherence approaches one. Ridge soaring and straight flight in lift
can be ambiguous: note these separately instead of forcing a circularity rule.

Use the toolbar to zoom; altitude and all feature panels share the time zoom.
Left/right arrows change candidate; `u` removes the rightmost existing interval
in that candidate. Times snap to the actual 10-s decision grid, including segments
whose clock origin is not a multiple of ten. Every edit autosaves to
`phase_annotations.csv`; selecting one split preserves labels from the other splits.

Use `--split validation` for model comparison. Keep test predictions and test
scores unopened until the annotation rules and decoder are fixed, then use
`--split test`. Do not inspect a model-coloured version of a candidate while
labelling it. Train labels name the components; they do not fit the HMM emissions.

The fixed test candidates exclude previously inspected development/example flights
20275040 and 20279877 (paragliders) and 975 (hang gliders). Their nominal archive
split is test, but they cannot support an untouched test score. This exclusion is
also enforced by candidate preparation for future packs.

`annotation_windows.csv` fixes selection and clock bounds;
`annotation_candidates.parquet` supplies the GUI, and `annotation_pack.pdf` is a
static blinded view. The 2026-09-10 audit aligned three offset-clock window bounds
to their existing decision rows before any labels were written. No candidate flight,
decision row or split changed. The `complete_segment` flag means a complete valid
feature block; it need not span an entire preprocessing segment or flight. Held-out
windows are at most 30 minutes, and may be shorter when support is limited.

`pack_provenance.json` binds the windows and candidate rows to their source archive.
The labeler refuses changed pack inputs or changed cleaned inputs or split assignments when the archive is
mounted. The candidate checksums also allow an intact copied pack to be used offline;
offline use cannot verify the current state of an unavailable archive.

Only `phase_annotations.csv` should change during labelling. Regenerating a pack
with existing labels is refused; use a new output directory for a different pack.
For a second independent observer, copy the pack and keep their labels in a separate
CSV. Do not merge conflicting judgments before measuring agreement.

The existing evaluator supplies precision, recall, F1 and a flight-bootstrap
interval. Human agreement, annotation coverage, boundary error and generalization
to new places or seasons are further measurements, not already validated results.
Since candidates were chosen for varied conditions, an unweighted score describes
this pack and should not be called an unbiased archive-wide accuracy estimate.
