# Thermal-plane SSD refresh after the Vilpellet archive pass

The offline preparation completed on 2026-09-16 with the current Vilpellet decoder.
The standalone SSD file is 2,036,154,368 bytes. Its exact checksum, source signatures,
per-cell read checks and coverage are in `verification.json`. No raw archive,
HMM model or archive-wide `phase_points.parquet` was modified.

The cell census and HMM climb products remained valid. The preparation regenerated
Vilpellet products for 45,739 distinct flights crossing the 12 selected cells, then
published both methods, the 10 m intersection lattice, summer-day summaries and
background imagery. There are 4,850,515 HMM intersections and 3,438,124 Vilpellet
intersections, with zero missing products. All 12 cells were read through the viewer's
read-only API for their busiest summer day, for both methods; every read returned
saved points without trajectory-edge interpolation. The SQLite integrity check passed.
All 13 aerial images, 13 colour maps and 13 hillshade images are present; each cell's
aerial image retains acquisition dates.

## Why the new Vilpellet output has the same points

Every one of the 120,252 current flight/cell products was joined to the old Vilpellet
cache by discipline, flight and cell. Status and compressed climb-edge arrays match
byte for byte for all of them. The old intermediate cache additionally retains 2,419
products for a formerly selected cell; those are not part of the current 12-cell
comparison. The decoder changes accelerated Viterbi without changing its fitted
parameters, feature construction or labelling rules. Exporting the archive did not
fit a new model.

A separate check reconstructed per-fix labels from the archive's saved phase intervals
for eight real flights (including two fully unclassified flights). They match the
current viewer decoder at every fix. Saved parameter records match the current
configuration for both disciplines, and coverage accounts for every archived fix.
These are implementation and completeness checks, not validation against human labels.

## Execution and validation

Command, run from the repository root:

```bash
MPLCONFIGDIR=/tmp/soaring-mpl-cache XDG_CACHE_HOME=/tmp/soaring-xdg-cache \
  .venv/bin/python scripts/prepare_thermal_planes.py --workers 4
```

The first pass was interrupted by SQLite's five-second write timeout while a
simultaneous read-only comparison held a lock. Running the same command resumed the
remaining 11,271 flights. The final comparison ran only after preparation finished.
The full log, including the interruption and successful resumption, is retained.
Commit `8742233` increases the writer timeout to 120 seconds for future preparation.

Validation: 122 viewer/reference tests, 12 random/tie/zero-mass Viterbi equivalence
tests, the offline export regression, and Ruff checks passed. The final SSD file
requires only reading by Thermal planes. Use **Reload SSD data** in an already open
viewer to reload the published snapshot.
