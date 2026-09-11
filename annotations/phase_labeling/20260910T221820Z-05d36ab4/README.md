# Phase annotation pack — 11 September 2026

Source: complete cleaning 2.2.0 and numerical run `20260910T221820Z-05d36ab4`.
There are 40 flights: 4 train, 8 validation and 8 test candidates per discipline.
The pack contains no HMM labels or posterior probabilities, and no human reference
labels have yet been supplied.

Follow the [annotation protocol](../README.md). From the repository root:

```bash
uv run python scripts/label_flight_phases.py \
  --pack-dir annotations/phase_labeling/20260910T221820Z-05d36ab4 \
  --annotator "Matteo Di Sante" --split train
```

Start with training windows to settle the behavioural convention. Keep validation
and test separate; do not use model-coloured versions of these windows while
labelling. Preserve uncertain intervals as unlabelled rather than forcing a class.

`annotation_candidates.parquet` supplies the offline interface;
`annotation_windows.csv` fixes the candidates, splits and clock bounds;
`annotation_pack.pdf` is the static blinded view. `pack_provenance.json` records
checksums and source identities. Only `phase_annotations.csv`, created by the
labeler, should change during annotation. The intact pack can be used with the SSD
disconnected, although source-archive identity can then only be checked when it is
mounted again.
