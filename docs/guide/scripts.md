# Commands and generated results

The numerical library lives in `src/soaring/`; `scripts/` contains its command-line
entry points. The executable rebuild order is `configs/rebuild.yaml`.
The [provenance index](provenance.md) maps generated files and macros to their writers.

## Where a script lives

Scripts are grouped by the document that quotes what they write. A script under
`tesi/` writes numbers, tables and figures into `thesis/generated/` for `main.pdf`.
A script under `esperimenti/` does the same for `esperimenti.pdf`. Inside each of the
two folders there is one subfolder per chapter, named with the chapter number printed
in that PDF.

| Folder | Holds |
|---|---|
| `tesi/ch02_dataset/` | Chapter 2 of `main.pdf`: the dataset |
| `tesi/ch03_fixed_transport/` | Chapter 3 of `main.pdf`: horizontal transport and displacement scaling |
| `esperimenti/ch03_global_observables/` | Chapter 3 of `esperimenti.pdf`: global observables |
| `esperimenti/ch04_global_transport/` | Chapter 4 of `esperimenti.pdf`: preliminary global transport |
| `esperimenti/ch05_flight_phases/` | Chapter 5 of `esperimenti.pdf`: flight phases |
| `esperimenti/ch06_vilpellet_segmentation/` | Chapter 6 of `esperimenti.pdf`: the Vilpellet segmentation |
| `condivisi/` | Scripts whose output is quoted by both volumes or read by a script of the other volume |
| `pipeline/` | Entry points that build or check the archive: cleaning, verification, segmentation, and the rebuild and review drivers |
| `checks/` | Checks that run around a build |
| `tools/` | Standalone helpers for inspection and one-off preparation |

Chapter 7 and Appendix 4.C of `esperimenti.pdf` have no folder of their own. Their
figures come from `generate_revision_diagnostics.py` and `generate_scaling_schematics.py`
in `esperimenti/ch04_global_transport/`.

A new script goes where the text that quotes its output lives. When both volumes quote
it, or a script of the other volume reads a file it writes, it goes in `condivisi/`.
[The provenance index](provenance.md) lists, for every generated file, the chapters that
use it.

Scripts in the same folder may import each other by module name, and several record
their sibling files in the hash of a result. Move a script together with the ones it
imports.

## Complete workflow

```bash
uv run python scripts/pipeline/rebuild_thesis.py --clean --jobs 8 --full-speed
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

These commands are in `scripts/pipeline/`.

| Command | Inputs and purpose | Outputs |
|---|---|---|
| `preprocess.py` | Raw IGC files and current preprocessing configuration; `--discipline`, `--jobs`, `--limit`, `--seed` | Four derived Parquet tables and a cleaning manifest |
| `verify_dataset.py` | Full scan of cleaned tables; checks structural and numerical invariants | `verify.tex`; fails on violations |
| `check_reproducible.py` | Reprocesses a seeded sample of retained raw flights and compares all stored columns; `--sample`, `--seed` | Terminal/log report; fails on discrepancies |
| `segment_flights.py` | `train`, `apply`, `coverage` with a discipline and segmentation configuration | Model, decoded flights, intervals, feature coverage and run reports |
| `segment_flights_vilpellet.py` | `flight`, `apply`, `coverage` with the transcribed Vilpellet model, whose parameters are read from `configs/segmentation_vilpellet.yaml` and applied without fitting | A printed per-flight composition, or decoded fixes, runs and a coverage record under `derived/segmentation/vilpellet/` |
| `label_flight_phases.py` | Opens a prepared annotation pack for manual review | Human labels and review status |
| `rebuild_thesis.py`, `review_thesis.py` | The rebuild driver and the manuscript-only review; see [rebuilding](rebuilding.md) | Run manifest, PDFs and review record |

The verifier establishes the listed invariants. It does not measure the cleaner's error
rate against independently labelled defects. Reproduction checks implementation identity
on a sample; independent phase labels are needed to evaluate segmentation accuracy.

The two segmenters write to separate directories and share no parameters. [The phase
guide](flight-phase-segmentation.md) specifies the Gaussian model and [the Vilpellet
guide](vilpellet-segmentation.md) specifies the transcribed one, including its
eligibility gate and the cadences it refuses.

## Thesis, Chapter 2: the dataset

These scripts are under `scripts/tesi/ch02_dataset/`.

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
| `generate_trimming_figure.py` | Cached scan of the take-off and landing trims, and the flight metadata | Trim-split and interior-excision figures, `trim.tex` |
| `generate_terrain_figure.py` | Take-off positions and elevation data | Terrain map and coverage values |
| `audit_msd_report.py` | The audit arrays of `condivisi/audit_msd.py` and `msd_curve.csv` | `audit.tex` |
| `audit_witness_coverage.py` | Legacy endpoint-only and complete paired-pressure witness rules, at a fixed 30 m/s setting | `cleaning_witness_audit.tex`, a dated historical output that the rebuild does not regenerate |

The current workflow forces fresh raw diagnostics after cleaning. Individual reports can
reuse a compatible cache, but a redraw alone does not recompute the observations.

## Thesis, Chapter 3: fixed-cohort transport

These scripts are under `scripts/tesi/ch03_fixed_transport/`. They are a separate entry
point from `configs/rebuild.yaml`; [the chapter guide](chapter3-fixed-transport.md) gives
the commands, the statistical contract and the checks.

| Script | Purpose |
|---|---|
| `run_ch3_fixed.py` | Reproduces the chapter from cleaned data, or redraws directly from saved results |
| `prepare_ch3_native.py` | Streams native cleaned fixes once for short lags, launch curves and the grid audit |
| `audit_ch3_inputs.py` | Verifies every reused coordinate and segment against the current cleaned archive |
| `measure_ch3_fixed.py` | Measures with fixed segments and one coupled equal-flight bootstrap |
| `summarize_ch3_fixed.py` | Reduces the saved measurements into a standalone report |
| `render_ch3_fixed.py` | Redraws from `report.json` alone |
| `write_ch3_text.py` | Writes the numerical macros the chapter cites; the prose is in `thesis/tesi/04-fixed-transport.tex` |
| `check_grid_bootstrap.py` | Bootstrap validation for cell, launch-altitude class and month-of-year groups |
| `check_bootstrap_reliability.py` | Calendar-block uncertainty from saved flight MSDs |
| `check_daily_dependence.py` | Daily dependence of the fixed-cohort MSD and fitted-H contributions |
| `check_origin_dependence.py` | Whether the increment law depends on the origin's position |

## Shared between the volumes

These scripts are under `scripts/condivisi/`. Each one writes a file that is quoted
by both volumes or read by a script of the other volume.

| Script | Scope | Outputs |
|---|---|---|
| `measure_msd.py` | Streams the complete cleaned archive | `msd_<slug>.npz`: launch and segment curves; `msd_segments_<slug>.parquet`: row identities and support |
| `generate_msd_figure.py` | Reduces those arrays; `--redraw` uses the existing curve CSV | `msd.pdf` and `msd.tex` for the experiments, and `msd_curve.csv`, which `audit_msd_report.py` reads |
| `audit_msd.py` | Streams the archive and keeps flight identities and per-time position/velocity/acceleration samples | `audit_positions_<slug>.npz`, `audit_flights_<slug>.parquet`, read by `audit_msd_report.py`, `generate_prelim_figure.py` and the kinematic-isotropy figure |
| `generate_prelim_figure.py` | Archive MSD audit arrays, catalogue and metadata | `prelim.tex`, quoted by both volumes: take-off map, duration/path/cadence distributions, directional and stratum controls |

`<slug>` is `para` or `hang`. Measurements take `--out`; array reductions take
`--audit-dir`.

## Experiments, Chapter 3: global observables

These scripts are under `scripts/esperimenti/ch03_global_observables/`.

| Script | Scope | Outputs |
|---|---|---|
| `generate_msd_weights.py` | Reweights the same stored segment curves three ways | `ch3_msd_weights.pdf`, `.tex`, `.csv` |
| `generate_kinematic_isotropy_figure.py` | Paired component ratios by discipline, region and EN equipment class | Five kinematic figures, values and per-time support in JSON |
| `generate_regional_pca.py` | Preserved `positions.bin` and `flights.json`; checks identities against the reference report | PCA figure, macros and JSON in an explicit `--output-dir`; works without transport increment caches |
| `generate_regional_variations.py`, `measure_regional_variations.py`, `render_regional_variations.py` | Regional finite differences on a rebuild's freshly collected coordinates: the first runs the other two, which measure and draw | `ch3_regional_variations.pdf` and its values |
| `generate_terrain_axis_comparison.py` | Independent terrain axes next to the current 10,000-s flight PCA | Terrain-axis figures and values |
| `generate_channel_wind_comparison.py`, `measure_channel_flight_altitude.py` | The coastal PCA against ERA5 wind at the measured mean flight altitude; the second measures the altitude on the windows supporting the long-lag PCA | `ch3_channel_wind.*`, `ch3_channel_flight_altitude.json` |

## Experiments, Chapter 4: preliminary global transport

These scripts are under `scripts/esperimenti/ch04_global_transport/`.

| Script | Scope | Outputs |
|---|---|---|
| `generate_duration_equipment.py` | Identified full-archive segment curves and EN catalogue classes | Duration, equipment and class-mixture figures, slopes, counts and JSON |
| `generate_grouped_tamsd.py` | Verified native-grid flight TAMSDs grouped by region and initial GNSS altitude | `ch3_grouped_tamsd.json` and its values |
| `generate_altitude_hurst.py` | Paraglider altitude-band exponents by declared open and closed circuit | `ch3_altitude_hurst.*` |
| `generate_temporal_scaling.py`, `measure_temporal_scaling.py`, `render_temporal_scaling.py` | Signed and two-interval scaling on verified coordinates: the first runs the other two, which measure and draw | `ch3_temporal_scaling_*.pdf` |
| `generate_revision_diagnostics.py` | All eligible flights and segments; disk-backed arrays and bounded parallel workers; `--sample` is development only | Transport, component/radial and signed joint-law figures, values, JSON and a checked cache; also the figures of Chapter 7 and Appendix 4.C |
| `generate_scaling_schematics.py` | Analytical scaling examples | Quantile, closed-loop and Lévy-walk moment-spectrum schematics |

The common-grid archive report computes variation, quantiles, moments,
centred multivariate kurtosis, regional PCA and velocity correlations on 10, 60 and
300 second averaging scales. It uses every segment admitted by its cadence and lag-support requirements, with
flight IDs and exclusions recorded explicitly. Fixed-population controls retain all
eligible long flights and common within-segment origins. The old duplicate
report paths and their unused figures have been removed; reusable observable estimators
and their numerical regression tests remain in the library.

See [global transport](global-transport.md) for weighting, supported fit ranges and the
limits of the model comparisons. Use [figure conventions](figures.md) for all new plots.

## Experiments, Chapter 5: flight phases

These scripts are under `scripts/esperimenti/ch05_flight_phases/`.

- `generate_segmentation_report.py` reads the current models and decoded archive to
  write phase summaries, distributions and trajectory examples.
- `generate_decoder_audit.py` measures decoder changes, feature coverage and transition
  behaviour, with short examples selected by a fixed rule. These are internal diagnostics.
- `prepare_annotation_pack.py --output-dir <new-directory>` prepares the review windows,
  plots and source identities for human annotation. It does not supply reference labels.

The combined driver runs training, application and coverage for both disciplines before
these reports. [The phase guide](flight-phase-segmentation.md) specifies the feature and
decoder conventions.

## Experiments, Chapter 6: the Vilpellet segmentation

`scripts/esperimenti/ch06_vilpellet_segmentation/generate_vilpellet_report.py` decodes one named flight
with the Chapter 5 Gaussian model and with the transcribed Vilpellet model on identical
cleaned geometry. It writes the plan-view comparison, an altitude timeline under the
Vilpellet labels, every fixed model constant as a LaTeX macro, and a JSON record of
where each number came from. It fits nothing. See [the Vilpellet
guide](vilpellet-segmentation.md) for the features, the provenance of the parameters and
what remains unvalidated.

## Build checks and tools

| Script | Purpose |
|---|---|
| `checks/check_generated_macros.py` | Checks generated macro names and manuscript uses before compilation |
| `checks/generate_provenance.py` | Writes the producer index; `--check` validates it without rewriting |
| `checks/generate_snapshot_status.py` | Marks the manuscript current only after the required producers completed; `--pending` explicitly marks an intermediate document |
| `tools/write_ssd_readme.py` | Inventories actual SSD paths, files, table row counts and manifest states; updates its root README |
| `tools/show_dataset.py` | Prints actual table schemas and example rows for inspection |
| `tools/build_basemap.py` | Builds the versioned Natural Earth basemap |
| `tools/estimate_savgol_timescales.py` | Investigates smoothing timescales from ENU spectra |
| `tools/refresh_seasons_index.py` | Copies the season-index snapshots from SSD into `data/` |
| `pipeline/review_thesis.py` | Compiles manuscript-only edits against unchanged results of a completed rebuild; writes a separate review record |
| `pipeline/build_docs.sh` | `thesis` compiles existing inputs without regenerating statistics; `stats` updates acquisition statistics only. Neither validates a complete analytical rebuild. |

`scripts/pipeline/regenerate.sh` is a compatibility entry point for `rebuild_thesis.py`.
Historical experiment reports may remain on the SSD; their presence does not make them
inputs to the current thesis.
