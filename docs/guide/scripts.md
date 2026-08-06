# The scripts, and what each one reads and writes

Everything under `scripts/` is a command-line entry point. The library under `src/soaring/`
holds the estimators and the pipeline; the scripts drive them, and every number the thesis
quotes is written by one of them into `thesis/generated/`.

They fall into three kinds, and the difference matters because it is a difference of hours.

**Pipeline** — turns the raw archive into the four Parquet tables on the SSD. Run once per
archive, or again when a threshold changes.

**Passes** — stream `fixes.parquet` end to end and write an intermediate array outside the
repository. These are the expensive step: the paraglider table is 1.36 × 10⁹ rows, and a pass
over it costs minutes to hours depending on what it computes per flight.

**Reductions** — read an intermediate array, or the small tables, and write `.tex` macros and
`.pdf` figures. Seconds to minutes. This is the split that lets a stratification be a row
selection rather than another traversal.

`scripts/regenerate.sh` runs all of them in the one order that is correct, and its header
explains why the order is a constraint rather than a convenience.

---

## Where the intermediate arrays go

Not into the repository and not onto the SSD. `regenerate.sh` uses

```
AUDIT_DIR=${AUDIT_DIR:-${TMPDIR:-/tmp}/soaring-audit}
```

and every pass takes `--out`, every reduction `--audit-dir`. They are analysis products
rather than thesis products: reproducible from the SSD by re-running the pass, and large
enough that versioning them would be wrong.

| file | written by | paragliders | hang gliders |
|---|---|---|---|
| `audit_positions_<slug>.npz` | `audit_msd.py` | 74 MB | 3 MB |
| `audit_flights_<slug>.parquet` | `audit_msd.py` | 14.4 MB | 0.6 MB |
| `variations_<slug>.npz` | `measure_variations.py` | 46.5 MB | 1.9 MB |
| `variation_flights_<slug>.parquet` | `measure_variations.py` | 3.2 MB | 0.2 MB |
| `shape_<slug>.npz` | `measure_shape.py` | 204 MB | 6.8 MB |
| `propagator_<slug>.npz` | `measure_propagator.py` | 0.46 MB | 0.15 MB |

`<slug>` is `para` or `hang`. Every size is what the file actually came out at on the current
archive, measured rather than estimated. The whole set is about 350 MB, which is why it lives
outside the repository.

---

## Pipeline

### `scripts/preprocess.py`
Runs the seven-stage pipeline over an archive and writes `fixes.parquet`,
`segments.parquet`, `flights_meta.parquet` and `suspect_intervals.parquet` into
`<data_root>/derived/`. `--discipline`, `--jobs`, `--limit`, `--seed`.

### `scripts/verify_dataset.py`
Checks the written tables against the invariants Chapter 2 claims for them, and writes
`thesis/generated/verify.tex`. A full traversal. Step 1 of `regenerate.sh`, because a failure
here invalidates everything downstream.

### `scripts/check_reproducible.py`
Draws a seeded sample of retained flights, finds their raw IGC files, runs them through
`run_flight` as it stands now, and compares the result with the stored rows column by column.
`--sample` (default 250 per discipline), `--seed`. Answers a different question from
`verify_dataset.py`: not whether the tables satisfy the invariants, but whether they are the
tables *this code* would write.

---

## Passes

Each streams `fixes.parquet` and writes an array to `--out`.

### `scripts/reporting/audit_msd.py`
Keeps each flight's position at every lag, rather than the average over flights, so the audit
can ask whether the averaged curve's shape survives a fixed cadence, a fixed duration and the
removal of the common heading — questions the averaged curve cannot be asked afterwards.
`--discipline`, `--out`.

### `scripts/reporting/measure_variations.py`
One filtered-variation curve per flight per filter order, with the flight's cadence, wing
class, season and declared task alongside. Every stratification in Chapter 3 is then a row
selection on that table. `--discipline`, `--out`.

### `scripts/reporting/measure_shape.py`
The observables that need the increments themselves: the moment spectrum, the velocity
autocorrelation, and the persistence runs. The longest step — about two and a half hours on
the paraglider archive, because the runs are decomposed per segment at three thresholds.
`--discipline`, `--out`.

### `scripts/reporting/measure_propagator.py`
Histograms of `|Δx|` per lag, per component and per native cadence, plus the turning-angle,
speed and vertical-velocity histograms. Twelve minutes over both archives: histograms only,
no per-segment decomposition. `--discipline`, `--out`, `--limit`.

### `scripts/reporting/measure_edge_effect.py`
Computes the ensemble MSD twice on the same flights, once over all samples and once over
interior ones only, and writes `thesis/generated/edge_effect.tex`. A pass rather than a
reduction, but it takes `--limit` and is run on a subsample, since the effect is a property
of the segment ends that every flight has.

---

## Reductions

### `scripts/reporting/audit_msd_report.py`
`--audit-dir` → `audit.tex`, `msd_curve.csv`.

### `scripts/reporting/generate_msd_figure.py`
Streams the fix table itself rather than reading an array, so it is a pass in cost.
Writes `msd.pdf`, `msd.tex`, `msd_curve.csv`.

### `scripts/reporting/generate_transport_figure.py`
`--audit-dir`, `--allow-partial` → `transport.pdf`, `transport.tex`.

### `scripts/reporting/generate_shape_figure.py`
`--audit-dir`, `--allow-partial` → `shape.pdf`, `shape.tex`. Not instant like the other
reductions: the Clauset–Shalizi–Newman cut-off scans every distinct run length as a candidate
and measures a KS distance on the tail at each, which on the paragliders' run collection is
about fifteen minutes.

### `scripts/reporting/generate_propagator_figure.py`
`--audit-dir`, `--allow-partial` → `propagator.pdf`, `propagator.tex`.

### `scripts/reporting/generate_prelim_figure.py`
`--audit-dir` → `prelim.tex`, `prelim_map.pdf`, `prelim_ensemble.pdf`, `prelim_strata.pdf`.
Reads the audit arrays rather than the fix table, which is what makes a stratified MSD a row
selection rather than another traversal.

### `scripts/reporting/generate_dataset_stats.py`
Reads `flights_meta.parquet` and the catalogue. → `dataset_stats.tex`,
`dataset_seasons.pdf`.

### `scripts/reporting/generate_pipeline_census.py`
Reads `flights_meta.parquet`. → `pipeline_census.tex`.

### `scripts/reporting/generate_census_stats.py`
Reads the cached raw-archive scan, never rescans. → `census.tex`.

### `scripts/reporting/generate_stats.py`
Reads the committed `data/*/seasons_index.csv` snapshots. → `stats.tex`.

### `scripts/reporting/generate_preproc_figure.py`
→ `preproc_diagnostics.pdf`, `fixlevel_diagnostics.pdf`, `gap_diagnostics.pdf`,
`sampling_intervals.pdf`.

### `scripts/reporting/generate_altitude_noise_figure.py`
→ `altitude_noise.pdf`.

---

## Tools that are not part of the regeneration

### `scripts/reporting/check_generated_macros.py`
Reads both sides of the macro contract and reports the difference in a second, with no build.
A macro quoted and never written is a fatal LaTeX error inside `\SI{}`, diagnosed from a
symptom that names the wrong line, so this runs before the build. It also reports macro names
LaTeX cannot accept, and typed numbers in the body that a generated macro already carries.

### `scripts/reporting/show_dataset.py`
Prints the shape, the dtypes and the first rows of every artefact on the data disk.
`docs/guide/data-on-disk.md` is written from its output; re-run it after a pipeline run and
paste the blocks back. `--discipline`.

### `scripts/reporting/write_ssd_readme.py`
Writes a README at the root of the data disk describing what is on it, so the disk explains
itself when it is not plugged into this repository. `--root`.

### `scripts/reporting/build_basemap.py`
Builds the committed `data/basemap.json` the take-off maps are drawn on, from Natural Earth.
Run once; the output is versioned so the figures need no network.

### `scripts/reporting/estimate_savgol_timescales.py`
Estimates the Savitzky–Golay smoothing timescales from the ENU power spectra. The measurement
behind the window choice in `configs/preprocessing.yaml`.

### `scripts/reporting/refresh_seasons_index.py`
Re-copies the canonical `seasons_index.csv` from the SSD into `data/`. Run by the pre-commit
hook.

### `scripts/reporting/generate_timeline.py`
Generates the git-history timeline for the private logbook. Run by the pre-commit hook.

### `scripts/build_docs.sh`
`stats`, `timeline`, `thesis`, `logbook`, `all`, `clean`. Uses
`latexmk -halt-on-error`, so a LaTeX error fails the build rather than producing a PDF with a
hole in it.
