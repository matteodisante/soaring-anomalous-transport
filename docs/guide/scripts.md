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

That three-way split is about run cost, not about location. Physically, `scripts/reporting/`
splits instead by the thesis chapter each script feeds — `ch2_dataset/` for Chapter 2, "The
dataset", and `ch3_global_transport/` for Chapter 3, "Global transport" — plus `checks/` and
`tools/` for what is not chapter-specific. A pass and the reduction that reads what it wrote
therefore sit side by side in the same chapter folder (`measure_msd.py` and
`generate_msd_figure.py` are both under `ch3_global_transport/`), not in a `passes/` or
`reductions/` folder of their own: that distinction lives on this page, in the section
headings below, rather than in the filesystem. Chapter 4, "Flight phases", has no folder yet
because it has no script yet — it is a plan, not a result.

`scripts/regenerate.sh` runs all eighteen in the one order that is correct, and its header
explains why the order is a constraint rather than a convenience. Every script that touches the
archive needs both roots exported, whichever discipline it is asked for, because the generated
`.tex` files carry both and a partial one breaks the build:

```bash
export SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc
export SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc
scripts/regenerate.sh              # everything, then the thesis build
scripts/regenerate.sh --no-build   # everything, stopping before latexmk
PY=python3 scripts/regenerate.sh   # override the interpreter (default .venv/bin/python)
```

It refuses to start while `scripts/preprocess.py` is still running — a `pgrep` guard, because
measuring a table that is still being written gives numbers that are wrong and look fine.

## Reaching one discipline of two

Every generator refuses to write when it reaches one archive and not the other. A truncated
`.tex` makes the thesis fail to build on the absent discipline's macros; a truncated *figure*
fails silently, losing a curve while the build succeeds. `--allow-partial` is the escape
hatch where a one-discipline run is meant.

The refusal names its cause, and separates an unconfigured `data_root` from an unmounted
disk and from a missing pass, because the three have different fixes. The first of those
used to be the commonest: `configs/para_download.yaml` shipped a placeholder while
`configs/delta_download.yaml` carried a real path, so a run without
`SOARING_PARA_DATA_ROOT` reached one archive and not the other and looked normal doing it.
Both configs now carry a real path, and the environment variable still overrides either.

`--help` is safe on every script, including the ten with no argument parser: it prints
what the script does and exits without touching the archive.

---

## Where the intermediate arrays go

Not into the repository — they are analysis products rather than thesis products,
reproducible from the SSD by re-running the pass, and large enough that versioning them
would be wrong. `regenerate.sh` uses

```
AUDIT_DIR=${AUDIT_DIR:-${TMPDIR:-/tmp}/soaring-audit}
```

and every pass takes `--out`, every reduction `--audit-dir`. The default is a temp
directory a reboot clears, which is fine for a one-shot run but throws away hours of
traversal for nothing: **point `AUDIT_DIR` at a path on the data disk instead** —
`/Volumes/SSD_DISANTE/derived-audit` on the author's machine — so that a change to a fit
range, a bootstrap count or a figure's styling costs only the reduction that reads the
cached array, not the pass that wrote it.

| file | written by | paragliders | hang gliders | what sets the size |
|---|---|---|---|---|
| `msd_<slug>.npz` | `measure_msd.py` | 216.8 MB | 7.86 MB | MSD/TAMSD curves (pooled, east, north, cohorts) and their per-flight/per-segment bootstrap samples |
| `audit_positions_<slug>.npz` | `audit_msd.py` | 73.72 MB | 2.67 MB | one row per flight, one column per lag |
| `audit_flights_<slug>.parquet` | `audit_msd.py` | 14.39 MB | 0.61 MB | one row per flight |
| `variations_<slug>.npz` | `measure_variations.py` | 117 MB | 4.7 MB | one curve per flight per filter order, plus east/north at orders 1-2 |
| `variation_flights_<slug>.parquet` | `measure_variations.py` | 3.25 MB | 0.22 MB | one row per flight |
| `shape_<slug>.npz` | `measure_shape.py` | 5 KB | 5 KB | moment spectrum and one autocorrelation, averaged over flights |
| `propagator_<slug>.npz` | `measure_propagator.py` | 0.45 MB | 0.15 MB | histograms per lag per component |

`<slug>` is `para` or `hang`. The sizes are measured on the current archive rather than
estimated, and the last column is what they scale with, so a number that has gone stale is
recognisable as one. The set comes to a few hundred MB, which is why it lives outside the
repository — but on the persistent disk, not a directory that disappears on its own.

---

## Pipeline

### `scripts/preprocess.py`
Runs the seven-stage pipeline over an archive and writes `fixes.parquet`,
`segments.parquet`, `flights_meta.parquet` and `suspect_intervals.parquet` into
`<data_root>/derived/`. `--discipline`, `--jobs`, `--limit`, `--seed`.

### `scripts/verify_dataset.py`
Checks the written tables against the invariants Chapter 2 claims for them, and writes
`thesis/generated/verify.tex`. A full traversal. Step 1 of `regenerate.sh`, because a failure
here invalidates everything downstream. It rewrites `verify.tex` wholesale, so an unreachable
data root would delete the other discipline's macros rather than leave them alone, so it
refuses to write unless both roots are exported — the rule that now holds for every
generator (above).

### `scripts/check_reproducible.py`
Draws a seeded sample of retained flights, finds their raw IGC files, runs them through
`run_flight` as it stands now, and compares the result with the stored rows column by column.
`--sample` (default 250 per discipline), `--seed`. Answers a different question from
`verify_dataset.py`: not whether the tables satisfy the invariants, but whether they are the
tables *this code* would write.

---

## Passes

Each streams `fixes.parquet` and writes an array to `--out`.

### `scripts/reporting/ch3_global_transport/measure_msd.py`
The ensemble and time-averaged MSD, their east-only and north-only twins
(`sec:transport-axisroutes`), and the fixed-duration cohorts, all from one traversal — plus
the per-flight (ensemble) or per-segment (time-averaged) samples each of those needs for
its bootstrap, since a naive least-squares error understates the truth by about fivefold.
`--discipline`, `--out`.

### `scripts/reporting/ch3_global_transport/audit_msd.py`
Keeps each flight's position at every lag, rather than the average over flights, so the audit
can ask whether the averaged curve's shape survives a fixed cadence, a fixed duration and the
removal of the common heading — questions the averaged curve cannot be asked afterwards.
`--discipline`, `--out`.

### `scripts/reporting/ch3_global_transport/measure_variations.py`
One filtered-variation curve per flight per filter order, with the flight's cadence, wing
class, season and declared task alongside. Every stratification in Chapter 3 is then a row
selection on that table. `--discipline`, `--out`.

### `scripts/reporting/ch3_global_transport/measure_shape.py`
The observables that need the increments themselves: the moment spectrum and the velocity
autocorrelation. `--discipline`, `--out`.

### `scripts/reporting/ch3_global_transport/measure_propagator.py`
Histograms of `|Δx|` per lag, per component and per native cadence, plus the turning-angle,
speed and vertical-velocity histograms. The cheap traversal: histograms only, with no
per-segment decomposition. `--discipline`, `--out`, `--limit`.

### `scripts/reporting/ch3_global_transport/measure_circling.py`
Averages the velocity autocorrelation at **native cadence** over 1 Hz segments and writes
`thesis/generated/circling.tex`. It exists because `measure_shape.py` evaluates every integer
lag and then keeps only its geometric grid, whose floor is 60 s — and the circling period is
about 21 s, so the whole feature sits below the first lag that pass retains. Restricted to
1 Hz because a lag in samples is a lag in seconds only there. `--limit` (default 25000
flights per discipline), and the sample size reaches the thesis as a macro.

### `scripts/reporting/ch3_global_transport/measure_edge_effect.py`
Computes the ensemble MSD twice on the same flights, once over all samples and once over
interior ones only, and writes `thesis/generated/edge_effect.tex`. A pass rather than a
reduction, but it takes `--limit` and is run on a subsample, since the effect is a property
of the segment ends that every flight has.

---

## Reductions

### `scripts/reporting/ch3_global_transport/audit_msd_report.py`
`--audit-dir` → `audit.tex`, `msd_curve.csv`.

### `scripts/reporting/ch3_global_transport/generate_msd_figure.py`
`--audit-dir`, `--allow-partial` → `msd.pdf`, `msd.tex`, `msd_curve.csv`. Reads what
`measure_msd.py` wrote, so it is a reduction in cost like every other one here, not the
pass its name might suggest. `--redraw` goes one step cheaper still, re-rendering the
figure and the macros from the committed `msd_curve.csv` alone, without even reading
`--audit-dir`: use it for a change that is about the drawing rather than the measurement.

### `scripts/reporting/ch3_global_transport/generate_transport_figure.py`
`--audit-dir`, `--allow-partial` → `transport.pdf`, `transport.tex`.

### `scripts/reporting/ch3_global_transport/generate_shape_figure.py`
`--audit-dir`, `--allow-partial` → `shape.pdf`, `shape.tex`. Reads the moment spectrum and
the velocity autocorrelation that the shape pass wrote, fits the tail exponent of the
autocorrelation, and builds the matched Gaussian null the non-Gaussianity is read against.

### `scripts/reporting/ch3_global_transport/generate_propagator_figure.py`
`--audit-dir`, `--allow-partial` → `propagator.pdf`, `propagator.tex`.

### `scripts/reporting/ch2_dataset/generate_prelim_figure.py`
`--audit-dir` → `prelim.tex`, `prelim_map.pdf`, `prelim_ensemble.pdf`, `prelim_isotropy.pdf`,
`strata_compat.pdf`.
Reads the audit arrays rather than the fix table, which is what makes a stratified MSD a row
selection rather than another traversal.

### `scripts/reporting/ch2_dataset/generate_dataset_stats.py`
Reads `flights_meta.parquet` and the catalogue. → `dataset_stats.tex`,
`dataset_seasons.pdf`.

### `scripts/reporting/ch2_dataset/generate_pipeline_census.py`
Reads `flights_meta.parquet`. → `pipeline_census.tex`.

### `scripts/reporting/ch2_dataset/generate_census_stats.py`
Reads the cached raw-archive scan, never rescans. → `census.tex`.

### `scripts/reporting/ch2_dataset/generate_stats.py`
Reads the committed `data/*/seasons_index.csv` snapshots. → `stats.tex`,
`seasons_table_para.tex`, `seasons_table_hang.tex`. Run by the pre-commit hook, as is
`generate_census_stats.py`.

### `scripts/reporting/ch2_dataset/generate_preproc_figure.py`
→ `preproc_diagnostics.pdf`, `fixlevel_diagnostics.pdf`, `gap_diagnostics.pdf`,
`sampling_intervals.pdf`. Filed here for its outputs, but it is not a reduction: it calls
`load_or_scan_tracks`, which scans the raw archive and writes
`<data_root>/derived/track_scan.parquet` (8.5 MB paragliders, 0.4 MB hang gliders). It is the
only producer of that cache, and both `generate_census_stats.py` and
`generate_altitude_noise_figure.py` read it, so it has to run before either of them. Minutes
when the cache is cold.

### `scripts/reporting/ch2_dataset/generate_altitude_noise_figure.py`
→ `altitude_noise.pdf`.

---

## Checks that run before the build

### `scripts/reporting/checks/check_generated_macros.py`
Reads both sides of the macro contract and reports the difference in a second, with no build.
`--quiet` prints only the verdict.
A macro quoted and never written is a fatal LaTeX error inside `\SI{}`, diagnosed from a
symptom that names the wrong line, so this runs before the build. It also reports macro names
LaTeX cannot accept, and typed numbers in the body that a generated macro already carries.

### `scripts/reporting/checks/generate_provenance.py`
Writes `docs/guide/provenance.md`: for every generated file and every macro family, the
script that produced it, the step that runs that script, and the sections that use it.
`--check` writes nothing and fails instead if a generated file carries no `% Generated by`
header, or if that header disagrees with the script whose source declares the output.
The neighbouring question — whether the thesis quotes a macro nothing defines — belongs to
`check_generated_macros.py`, which is why the two run together.

## Tools that are not part of the regeneration

### `scripts/reporting/tools/show_dataset.py`
Prints the shape, the dtypes and the first rows of every artefact on the data disk.
`docs/guide/data-on-disk.md` is written from its output; re-run it after a pipeline run and
paste the blocks back. `--discipline`.

### `scripts/reporting/tools/write_ssd_readme.py`
Writes a README at the root of the data disk describing what is on it, so the disk explains
itself when it is not plugged into this repository. `--root`.

### `scripts/reporting/tools/build_basemap.py`
Builds the committed `data/basemap.json` the take-off maps are drawn on, from Natural Earth.
Run once; the output is versioned so the figures need no network.

### `scripts/reporting/tools/estimate_savgol_timescales.py`
Estimates the Savitzky–Golay smoothing timescales from the ENU power spectra. The measurement
behind the window choice in `configs/preprocessing.yaml`.

### `scripts/reporting/tools/refresh_seasons_index.py`
Re-copies the canonical `seasons_index.csv` from the SSD into `data/`. Run by the pre-commit
hook.

### `scripts/reporting/tools/generate_timeline.py`
Generates the git-history timeline for the private logbook. Run by the pre-commit hook.

### `scripts/build_docs.sh`
`stats`, `timeline`, `thesis`, `logbook`, `all`, `clean`. Uses
`latexmk -halt-on-error`, so a LaTeX error fails the build rather than producing a PDF with a
hole in it.
