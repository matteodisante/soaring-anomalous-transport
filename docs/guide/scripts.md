# Commands and generated results

The numerical library lives in `src/soaring/`; `scripts/` contains its command-line
entry points. The executable rebuild order is `configs/rebuild.yaml`.
The [provenance index](provenance.md) maps generated files and macros to their writers.

## Complete workflow

```bash
uv run python scripts/rebuild_thesis.py --clean --jobs 8 --full-speed
```

This regenerates the cleaned tables, verifies them, recomputes the analyses, trains and
applies both segmentation models, prepares a new annotation pack and builds the thesis.
Omit `--clean` only when the existing complete archive matches the current cleaning code
and configuration. `--dry-run` prints the ordered commands without executing them.
The default resource setting is one worker at low scheduling priority; the command above
explicitly enables eight workers and normal priority. Native numerical threads are limited
to one per worker. See [rebuilding](rebuilding.md) for prerequisites and failure handling.

A rebuild stores its intermediate arrays, logs and manifest in
`<audit-dir>/runs/<run-id>/`, normally on `/Volumes/SSD_DISANTE/derived-audit`.
Its annotation pack has a separate directory under `annotations/phase_labeling/`.
These paths preserve earlier runs and human labels.

## Cleaning and validation

| Command | Inputs and purpose | Outputs |
|---|---|---|
| `preprocess.py` | Raw IGC files and current preprocessing configuration; `--discipline`, `--jobs`, `--limit`, `--seed` | Four derived Parquet tables and a cleaning manifest |
| `verify_dataset.py` | Full scan of cleaned tables; checks structural and numerical invariants | `verify.tex`; fails on violations |
| `check_reproducible.py` | Reprocesses a seeded sample of retained raw flights and compares all stored columns; `--sample`, `--seed` | Terminal/log report; fails on discrepancies |
| `segment_flights.py` | `train`, `apply`, `coverage` with a discipline and segmentation configuration | Model, decoded flights, intervals, feature coverage and run reports |
| `label_flight_phases.py` | Opens a prepared annotation pack for manual review | Human labels and review status |

The verifier establishes the listed invariants. It does not measure the cleaner's error
rate against independently labelled defects. Reproduction checks implementation identity
on a sample; independent phase labels are needed to evaluate segmentation accuracy.

## Chapter 2 reports

These scripts are under `scripts/reporting/ch2_dataset/`.

| Script | Reads or computes | Main outputs in `thesis/generated/` |
|---|---|---|
| `generate_stats.py` | Versioned season-index snapshots | Acquisition counts and season tables |
| `generate_preproc_figure.py` | Raw track scan and bounded fix-level sample; `--rescan` refreshes caches | Flight, fix, gap and sampling diagnostics |
| `generate_census_stats.py` | Raw track-scan cache | Raw census values |
| `generate_pipeline_census.py` | Current flight metadata | Retention cascade and reasons |
| `generate_dataset_stats.py` | Current metadata and catalogue | Dataset values and seasonal coverage |
| `generate_altitude_noise_figure.py` | Paired uninterrupted raw GNSS/barometer stretches | Altitude spectra and noise values |
| `generate_alt_offset_stats.py` | Seeded raw-flight sample and height-reference controls | Offset values and scan cache |
| `generate_alt_offset_figure.py` | Offset cache | Offset figure |
| `generate_savgol_figure.py` | Configured smoothing kernels | Filter-response illustrations |
| `generate_savgol_spectrum_figure.py` | Seeded raw trajectories; `--rescan` | Raw coordinate spectra and sample counts |
| `generate_cleaning_explainers.py` | Synthetic defects and configured altitude rules | Defect and median-speed schematics |
| `generate_cleaning_examples.py` | Actual raw tracks and the current cleaner | Three empirical defect examples with provenance |
| `generate_terrain_figure.py` | Take-off positions and elevation data | Terrain map and coverage values |
| `generate_prelim_figure.py` | Archive MSD audit arrays, catalogue and metadata | Take-off map, duration/path/cadence distributions, directional and stratum controls |

The current workflow forces fresh raw diagnostics after cleaning. Individual reports can
reuse a compatible cache, but a redraw alone does not recompute the observations.

## Chapter 3 reports

These scripts are under `scripts/reporting/ch3_global_transport/`.

| Script | Scope | Outputs |
|---|---|---|
| `measure_msd.py` | Streams the complete cleaned archive | `msd_<slug>.npz`: launch and segment curves; `msd_segments_<slug>.parquet`: row identities and support |
| `generate_msd_figure.py` | Reduces those arrays; `--redraw` uses the existing curve CSV | `msd.pdf`, `msd.tex`, `msd_curve.csv` |
| `generate_duration_equipment.py` | Identified full-archive segment curves and EN catalogue classes | Duration, equipment and class-mixture figures, slopes, counts and JSON |
| `audit_msd.py` | Streams the archive and keeps flight identities and per-time position/velocity/acceleration samples | `audit_positions_<slug>.npz`, `audit_flights_<slug>.parquet` |
| `audit_msd_report.py` | Reduces the audit arrays | `audit.tex` |
| `generate_kinematic_isotropy_figure.py` | Paired component ratios by discipline, region and EN equipment class | Five kinematic figures, values and per-time support in JSON |
| `generate_revision_diagnostics.py` | All eligible flights and segments; disk-backed arrays and bounded parallel workers; `--sample` is development only | Transport, component/radial and signed joint-law figures, values, JSON and a checked cache |
| `generate_scaling_schematics.py` | Analytical scaling examples | Quantile, closed-loop and Lévy-walk moment-spectrum schematics |

`<slug>` is `para` or `hang`. Measurements take `--out`; array reductions take
`--audit-dir`. The common-grid archive report computes variation, quantiles, moments,
centred multivariate kurtosis, regional PCA and velocity correlations on 10, 60 and
300 second averaging scales. It uses every segment admitted by its cadence and lag-support requirements, with
flight IDs and exclusions recorded explicitly. Fixed-population controls retain all
eligible long flights and common within-segment origins. The old duplicate
report paths and their unused figures have been removed; reusable observable estimators
and their numerical regression tests remain in the library.

See [global transport](global-transport.md) for weighting, supported fit ranges and the
limits of the model comparisons. Use [figure conventions](figures.md) for all new plots.

## Chapter 4 reports

These scripts are under `scripts/reporting/ch4_flight_phases/`.

- `generate_segmentation_report.py` reads the current models and decoded archive to
  write phase summaries, distributions and trajectory examples.
- `generate_decoder_audit.py` measures decoder changes, feature coverage and transition
  behaviour, with short examples selected by a fixed rule. These are internal diagnostics.
- `prepare_annotation_pack.py --output-dir <new-directory>` prepares the review windows,
  plots and source identities for human annotation. It does not supply reference labels.

The combined driver runs training, application and coverage for both disciplines before
these reports. [The phase guide](flight-phase-segmentation.md) specifies the feature and
decoder conventions.

## Build checks and tools

| Script | Purpose |
|---|---|
| `reporting/checks/check_generated_macros.py` | Checks generated macro names and manuscript uses before compilation |
| `reporting/checks/generate_provenance.py` | Writes the producer index; `--check` validates it without rewriting |
| `reporting/checks/generate_snapshot_status.py` | Marks the manuscript current only after the required producers completed; `--pending` explicitly marks an intermediate document |
| `reporting/tools/write_ssd_readme.py` | Inventories actual SSD paths, files, table row counts and manifest states; updates its root README |
| `reporting/tools/show_dataset.py` | Prints actual table schemas and example rows for inspection |
| `reporting/tools/build_basemap.py` | Builds the versioned Natural Earth basemap |
| `reporting/tools/estimate_savgol_timescales.py` | Investigates smoothing timescales from ENU spectra |
| `reporting/tools/refresh_seasons_index.py` | Copies the season-index snapshots from SSD into `data/` |
| `review_thesis.py` | Compiles manuscript-only edits against unchanged results of a completed rebuild; writes a separate review record |
| `build_docs.sh` | `thesis` compiles existing inputs without regenerating statistics; `stats` updates acquisition statistics only. Neither validates a complete analytical rebuild. |

`scripts/regenerate.sh` is a compatibility entry point for `rebuild_thesis.py`.
Historical experiment reports may remain on the SSD; their presence does not make them
inputs to the current thesis.
