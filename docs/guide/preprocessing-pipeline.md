# Pre-processing pipeline — implementation blueprint

!!! success "Status: built (2026-08-03)"
    Every stage below is implemented under `soaring.analysis.preproc/` (one module per
    stage, chained by `pipeline.run_flight`) and driven over an archive by
    `scripts/preprocess.py`. This page is now a *map* of that code rather than a plan for
    it; where a rule needed a decision the specification left open, the decision is
    recorded in the stage module's docstring and mirrored into the thesis appendix.

!!! note "What this page is for now"
    It stays the map of steps, schemas, config keys and storage — one page to read before
    touching the pipeline — but it is no longer the plan it was written as. It is
    *transitional*: as the API Reference grows it retires into the code plus a short usage
    guide, and it is **not** maintained as a second copy forever.

    The **why** (justification, method, hyperparameter reasoning) lives in the thesis,
    chapter *The dataset*, section *Trajectory pre-processing* (`sec:preproc`) — not here.
    The **numbers** (all thresholds) live in
    `configs/preprocessing.yaml` (loaded via `load_preproc_config`) — not here. This page
    links to both; where it repeats a headline threshold for readability, the YAML stays
    authoritative. That is how we avoid a thesis/doc that drift.

    On any conflict, the thesis is normative and this page must be corrected — and where
    building the code showed the thesis itself to be incomplete, the thesis was corrected
    in the same pass (see *Decisions taken while building*).

## Design principles

1. **Raw is immutable.** Original `.igc` files and the raw catalogs are never modified.
   Every transform writes a new artifact in its own directory.
2. **Config is external.** Every pre-processing threshold / hyperparameter lives in
   `configs/preprocessing.yaml` (documented, grouped by pipeline level), never hard-coded;
   `load_preproc_config` reads it into typed dataclasses. Acquisition config is separate
   (`configs/*_download.yaml`, `soaring.acquisition.ffvl.config`).
3. **Traceability.** Each output row/table carries the pipeline version, the config hash
   and the git commit — stored as Parquet footer key–value metadata, so the dataset
   documents itself.
4. **No redundant storage.** Anything that is pure algebra of stored columns (`v_tot`,
   spherical angles, curvature/`ω`, turn radius, glide ratio, mechanical energy, absolute
   altitude) is computed *lazily* at analysis time — never materialized. Only the outputs
   of a non-trivial parametric step (filtered position/velocity/acceleration) are stored.
5. **Extensible across sources.** `paraglider`, `hangglider` (today) and `sailplane`
   (future) share one `fixes` schema; a new source is a new value of the `source` column,
   never a new column. Missing `flights_meta` fields degrade to `null`, never an error.

## Inputs

| Input | Location | Notes |
|---|---|---|
| Raw IGC tracks | `<data_root>/raw/igc/` per source (SSD) | `source ∈ {paraglider, hangglider, sailplane}`; on-disk dirs are `paragliders/`, `hang_gliders/` (values ≠ dir names by design) |
| Raw catalog | `<data_root>/catalog/catalog.csv` (SSD) | pandas + CSV, 23 columns (`soaring.acquisition.ffvl.catalog.CATALOG_COLUMNS`), regenerable via `build-catalog`; **never stored locally** -- see `Config.catalog_path` |

All raw and derived data lives only on the SSD, under `data_root`, organised by maturity
(`raw/`, `catalog/`, `derived/`, and in future `processed/`, `analysis/` -- see
`soaring.acquisition.ffvl.config.Config`); nothing is duplicated in the local repo `data/`
folder, which holds only the small, versioned `seasons_index.csv` per discipline.

The catalog is **metadata only** and can be wrong (see [Catalog quirks](#catalog-quirks));
it is a coarse pre-filter and provenance source, never the basis of a scientific cut.

## Pipeline steps

Order and rationale: thesis `sec:preproc`. Steps (i)–(iv) act on **raw geographic**
coordinates (great-circle speeds); (v) converts to the metric ENU frame; (vi)–(vii) are metric.

| # | Step | Acts on | Produces | Code home | Thesis |
|---|---|---|---|---|---|
| 0 | Ingest catalogs, add `source`, coarse pre-filter (no track ⇒ skip) | catalog | candidate flight list | `acquisition.ffvl.catalog` | `sec:catalog` |
| 1 | Parse IGC `B`/`H` records | `.igc` | fixes `[t,lat,lon,valid,baro_alt,gnss_alt]` | `analysis.igc.parse_igc` | `sec:igcformat` |
| i | Choose altitude channel per flight | fixes | `alt_source ∈ {baro,gnss}` + chosen `alt` | `analysis.preproc.altchannel.adopt_alt_channel` | `sec:altchannel` |
| ii | Fix-level cleaning: absolute bounds + robust local test + structural rules | raw geo | cleaned fixes | `analysis.preproc.cleaning.clean_flight` | `sec:fixlevel` |
| iii | Trim outer ground phases (`v_xy` sustained) + interior-ground guard | raw geo | airborne segment | `analysis.preproc.trimming.trim_flight` | `sec:trimming` |
| iv | Flight-level filtering (duration + path + altitude activity) | trimmed track | keep/drop + reason | `analysis.preproc.flightfilter.filter_flight` | `sec:flightfilter` |
| v | Geographic → ECEF → ENU (origin = first fix of the trimmed track) | geo | `E,N,U` | `analysis.preproc.enu.to_local_frame` | `sec:enu` |
| vi | Enforce uniform `Δt` within flight | ENU | uniform series or exclusion | `analysis.preproc.resample.resample_flight` | `sec:uniform` |
| vii | Savitzky–Golay smooth + differentiate | ENU | pos/vel/acc | `analysis.preproc.smoothing.smooth_flight` | `sec:savgol` |
| viii | Write `fixes` + `segments` + `flights_meta` | all | Parquet | `scripts/preprocess.py` (chain: `analysis.preproc.pipeline.run_flight`) | — |

Key mechanics that reconcile the blueprint with the repo:

- **Altitude channel (i).** The parser returns *both* channels; the pipeline picks one per
  flight (`alt_source`), never splices. Barometric where present **and alive**
  (`alt_channel.baro_min_range_m`: a stuck sensor writing a constant value falls back);
  whole-channel-absent flights fall back to unfiltered GNSS. The `A`/`V` flag is subsumed by the
  missing-altitude check on the chosen channel. Individually missing barometric values on
  baro-adopted flights are quantified by the `StatScan*BaroMiss*` census macros
  (`generate_census_stats.py`, July 2026): share of flights affected plus median/max
  missing-fix counts. (Thesis `sec:altchannel`.)
- **ENU (v).** Origin at the **first fix of the trimmed track** (the start of free
  flight — close to, but not, the take-off point on the ground); `E,N` zeroed there. The
  working **vertical is not the rotation's `U`**: the pipeline keeps the adopted altitude
  channel at its measured value, `z(t) = alt(t)`, never re-zeroed (increments are
  offset-invariant; the absolute height stays available). (Thesis `sec:enu`, Notation —
  July 2026 review pass.)
- **Fix-level cleaning (ii).** Three detectors, by how much context each needs (thesis
  `tab:cleaning`). *Absolute bounds* on per-fix `v_xy`, `|v_z|`, barometric altitude
  (`FixLevelThresholds` ←
  YAML): the context-free floor, each placed in the implausible tail of its **per-fix**
  distribution (audited by `make_fixlevel_diagnostics_figure` on a seeded sample,
  `fix_level_distributions`; what matters is the fraction of *fixes* removed, not of flights
  touched). *Robust local-outlier test* (Hampel identifier: median/MAD over a ±`w`-second
  window; flag when residual > max(`k`·σ, `ε_min`), thesis `eq:hampel`): detection and
  **attribution** only — a flag alone never deletes. A horizontal fix is deleted only when
  flagged **and** its implied in-and-out speed breaks the absolute `v_xy` bound
  (impossibility gate); a flagged-but-possible fix is kept, its flag recorded per flight; a
  flagged step that no bounded removal rejoins (position discontinuity, e.g. re-acquisition
  offset) ⇒ **split** at the step, like a long gap.
  Runs per channel, so a vertical spike drops the altitude only (invalidated on the flag
  alone: a dropped altitude is a deferral, restored at (vi), not a deletion). *Structural
  rules*: duplicate timestamp → merge to that second's centroid; non-wrap backward time →
  delete by minimal removal (complement of the longest increasing subsequence, so a
  forward-jumped clock removes itself, not every fix after it; the parser stops clamping
  backward jitter — `parse_igc` keeps only the midnight-rollover unwrap — so the cleaning
  pass sees the defect); frozen-lock run, cut
  only per thesis `eq:frozenlock`: bounding diameter < `ε` **and** witness **and** span ≥
  `τ_freeze`, the witness ranked per altitude source — barometric flight: baro flat **or**
  byte-identical repeats (`V`/zero GNSS alt never overrule a climbing barometer; recorded as
  diagnostics); GNSS-fallback flight: `V` flag / zero GNSS alt **or** byte-identical →
  mark as gap, split at step (vi). **Removal
  semantics:** position/time defect → delete node (gap bridged at vi); altitude defect →
  invalidate the altitude channel only (horizontal position kept). A **flight-level integrity
  gate** drops any flight that cleaning had to rebuild past a small fraction `f`. The keys
  (`w, k, ε_min, ε, δ_z, τ_freeze, f`) live under `fix_level` in the YAML as working
  values, fixed a priori (the routine that applies them is still to build). No inter-fix
  time-gap bound here — gaps handled once at (vi). (Thesis `sec:fixlevel`.)
- **Flight-level cuts (iv).** Duration window 40 min ≤ T ≤ 16 h (the upper bound removes
  loggers left running: 15 census "flights" of 16–166 h); **path length** ≥ 20 km (set in
  the July 2026 review pass; on the census, above 40 min it catches 236 of 184,583
  paraglider and 7 of 6,638 hang-glider flights — `StatScan*{LongEnough,Overlong,ShortPath}*`
  macros from `generate_census_stats.py`,
  thesis `sec:flightfilter`; an earlier 30 km draft removed 5,229 genuine localized
  flights); **altitude activity** ≥ 600 m on the adopted channel (raised from 75 m on
  2026-08-02: 75 m only excluded a dead sensor, 600 m asks for the altitude budget a
  ≥40 min cross-country actually spends. Cheap either way — retained share of barometric
  flights 69.8 % → 68.1 % para, 83.0 % → 81.1 % hang, so both sit on the same plateau.
  Caveat: the census stores only the *barometric* extremes, so this cut cannot yet be
  audited on the GNSS-fallback minority). Path length = sum of great-circle steps (not extent/displacement).
  A minimum-fix-count cut is dropped as redundant with the duration cut.
- **Uniform Δt (vi).** Native `Δt` per flight (no common cadence). Uniform ⇒ use as is;
  mildly irregular ⇒ resample onto the native grid across small gaps (each filled point
  flagged `interpolated`); a gap past
  min(`max_gap_factor`·Δt, max(`max_gap_seconds`, 2·Δt)) (native or opened by an excised frozen-lock
  run, step ii) ⇒ **split** the flight at the gap into independently analysed segments (not
  bridged: interpolating a long hole fabricates motion); segments keep the parent flight's
  origin and clock; a split is bookkeeping, not new files (ENU precedes it, fixes are
  already parent-referred: a `segment_id` column in `fixes` plus a `segments` metadata
  table); the flight-level cuts are **not** re-applied to segments (only the minimal
  segment-duration gate, key `min_segment_duration_s` in the YAML), and phase durations truncated at a
  segment boundary are flagged censored, for the duration fits to exclude; a
  `missing_fraction` too large within a segment ⇒ **drop the segment** (the flight only if
  none survives).
  Grid mechanics (`resample_flight`): anchored on the segment's **own** first fix,
  stepping the flight's native `Δt`, with the span rounded *down* to a whole number of
  steps — so the grid never reaches past the last fix and every point is interpolated
  strictly inside the measured range, never extrapolated. A grid point counts as
  measured when a fix lies within `Δt/2` of it; the fill is per *channel* (PCHIP on
  `E`,`N`; linear on `z`), so an altitude that stage (ii) invalidated is restored even
  where the grid point itself is measured. Carried per-fix flags follow the nearest fix
  and are blanked at reconstructed points, which carry no measurement to describe. The
  bound `g_max` is defined once, in `split_bound_s`, and the diagnostic figure reads it
  from there.
  Thresholds `max_gap_factor`, `max_gap_seconds`, `max_missing_fraction` (in the YAML), audited by
  `make_gap_diagnostics_figure` and quoted by the `StatScan*GapSplit*` census macros. The
  bound is two-scale by design — relative to cadence, capped in seconds (thesis
  `sec:uniform`) — and the cap's working value is swept a posteriori on the split
  fractions (same audit pattern as the cleaning thresholds) before being frozen. This is the *only* gap handling: no other step bounds inter-fix
  time gaps.
- **Savitzky–Golay (vii).** Two hyperparameters: `window_length` (odd) and `polyorder`.
  Set by the noise-matched procedure of thesis `sec:savgol` (PSD knee `f_c` → smoothing scale
  `τ_c` → `window = max(odd(τ_c/Δt), 5)` per flight; runs **per segment**, never across a
  boundary, with `mode='interp'`; `polyorder` fixed at 3; horizontal and
  vertical treated separately, the vertical conditioned on `alt_source` via the two config
  keys `tau_c_vertical_baro_s`/`tau_c_vertical_gnss_s`). `deriv=0,1,2` and `delta=Δt` are
  not tuning knobs.
  Two consequences of the window, made explicit when the stage was built: the first and
  last `w // 2` samples of every segment are evaluated off-centre and are flagged `edge`
  (the per-sample flag `sec:savgol` asks for, so an edge-sensitive observable can be
  recomputed on interior samples only); and a segment with fewer than `w` samples cannot
  be smoothed at all, so it is dropped with reason `shorter_than_smoothing_window`. The
  90 s segment gate of (vi) guarantees the window fits **up to Δt = 22.5 s** — beyond
  that, in the thin slow-logger tail, this drop is what covers the difference. It is
  observed: 1 segment in 307 on a 116-flight raw sample.

## Reporting-stage scan cache (not the production `fixes`/`flights_meta` tables)

Ahead of the real pipeline, the thesis-figure scripts already run a full-dataset scan
(`soaring.analysis.census.scan_tracks`, driven by `track_stats` per flight) to
compute the flight-level filtering, gap and sampling diagnostics (steps iii/iv/vi above).
Since a full paraglider census takes tens of minutes, this scan is **cached** to a flat
Parquet on the SSD, `<data_root>/derived/track_scan.parquet` (`Config.derived_dir` --
never in the repo; `load_or_scan_tracks` reads it if present, else scans and writes it —
no invalidation beyond presence, delete the file to force a refresh). This is a
lightweight *preview* of `flights_meta`, not a substitute for it: same spirit (per-flight
summary, Parquet), far fewer columns, no `alt_source`/provenance/versioning.

The census macros the thesis quotes come from this cache via
`scripts/reporting/generate_census_stats.py`, which emits three families into
`thesis/generated/census.tex`: the scan statistics (`StatScan*`, including the
`BaroMiss` and `GapSplit` groups), the flight-level filtering census
(`StatScan*{LongEnough,Overlong,ShortPath}*`), and — new in the July 2026 pass — the
adopted thresholds themselves re-exported from `configs/preprocessing.yaml` as
`\Preproc*` macros (one per YAML value, converted to the unit the suffix names). The
thesis pipeline-map figure/table (`sec:pipelinemap`, closing the dataset chapter) quotes
the operating point exclusively through `\Preproc*`, so a threshold change re-runs one
script and propagates everywhere without a rescan.

`track_stats` also computes a few per-flight QC fields, free byproducts of the same scan:
`baro_present_frac`, `max_vxy_mps`, `max_vz_mps`, `baro_alt_min_m`, `baro_alt_max_m`.
A flight counts as **barometric** when `baro_present_frac` ≥ `BARO_PRESENT_MIN` = **0.95** (raised from 0.5 on 2026-08-02; defined once in
`soaring.analysis.altitude_noise` and imported by `preprocessing`, so cleaning, census and
PSD cannot drift). The change reclassified 241 paraglider flights and no hang-glider ones
(0.13 % of the archive) — the direct measurement of how bimodal presence is.
`baro_present_frac` is consumed by the altitude-noise figure's fallback-rate panel (thesis
`sec:altchannel`), which prefers this cache (`altitude_noise.baro_presence_from_scan`) over its own
separate scan when it exists, turning a sampled estimate into an exact census at no extra
parsing cost. The speed/altitude fields are per-flight *maxima*, so they only say which
*flights* a fix-level bound would touch; the fix-level figure (step ii) instead uses genuine
**per-fix** distributions (`fix_level_distributions`, a seeded sample), because what
justifies a fix-level cut is the fraction of *fixes* it removes, not of flights it touches.

## Output schema

### `fixes` (one row per fix)

One Parquet per discipline, zstd, written in batches of 400 flights (**a row group is
not a batch** — read it through `soaring.analysis.derived.stream_flights`). Only filter
*outputs* are stored; everything else is lazy. Eighteen columns, in this order — the list
is `pipeline.FIX_TABLE_COLUMNS` and this table is checked against it by
`test_the_documented_fix_schema_matches_the_code`.

| column | dtype | note |
|---|---|---|
| `source` | string | `paraglider` / `hangglider` / `sailplane` |
| `flight_id` | string | key is `(source, flight_id)` — see [flight_id](#catalog-quirks) |
| `segment_id` | int16 | 0-based within the flight; a split at a long gap / excised run increments it (thesis `sec:uniform`) |
| `t` | float32 | s; `t=0` at first airborne fix of the **parent flight** (segments keep the parent clock) |
| `E`, `N` | float32 | ENU, smoothed (`deriv=0`); `E=N=0` at the first fix of the trimmed track |
| `z` | float32 | adopted altitude channel at its measured value, smoothed; never re-zeroed (thesis `sec:enu`) |
| `v_E`, `v_N`, `v_z` | float32 | velocity (`deriv=1`) |
| `a_E`, `a_N`, `a_z` | float32 | acceleration (`deriv=2`) |
| `interpolated` | bool | the **time base** had no fix within half a step, so all three channels were reconstructed at resampling |
| `z_reconstructed` | bool | this grid point's **altitude** did not come from a measured one — either `interpolated`, or the fix it came from carried no altitude. A vertical hole opens no time gap, so it forces no split and `interpolated` stays False: exclude on *this* flag for any vertical analysis |
| `edge` | bool | within a half-window of a segment boundary, where the Savitzky–Golay polynomial is evaluated off-centre and so carries more variance (thesis `sec:savgol`) |
| `hampel_flagged` | bool | the local-outlier test flagged this fix; recorded, never a gate (thesis `sec:fixlevel`) |
| `alt_invalidated` | bool | the **cleaning** removed this altitude, as opposed to the logger never writing one |

Lazy (never stored), e.g. `v_tot=√(v_E²+v_N²+v_z²)`, `θ_xy=atan2(v_N,v_E)`,
`ω=(v_E a_N − v_N a_E)/(v_E²+v_N²)`. (`z` is already absolute; no `U_origin` offset exists.)

### `segments` (one row per segment)

Single Parquet. Key `(source, flight_id, segment_id)`: `t_start`, `t_end`, `n_fix`
(grid points contributed to `fixes`), `n_fix_raw` (measured fixes), `frac_interpolated`,
`frac_z_reconstructed`, and the boundary-censoring flags `censored_start`/`censored_end` for phases truncated at
either end (thesis `sec:uniform`). Per-flight aggregates stay in `flights_meta`.

Two implementation choices, made when stage (vi) was built:

- **Every segment the split produced gets a row**, retained or not, with `kept` (bool)
  and `drop_reason` (null when kept, else `shorter_than_min_segment_duration` /
  `missing_fraction_above_max`). `segment_id` is assigned at split time and stays stable,
  so a gap in the numbering *is* the record of a drop. Same principle as `flights_meta`:
  the reason is recorded, not just the removal — and this is the material the gap-cap
  sweep of `sec:uniform` needs.
- **`censored_*` is True only at a boundary a split created.** The parent flight's own
  first and last boundary truncate the phase in progress too, but they are a different
  thing, and are told apart by these flags being False on the first/last segment.

### `flights_meta` (one row per flight)

Single Parquet. Identity + provenance (`source`, `flight_id`, `global_flight_id?`,
`pipeline_version`, `config_hash`, `processed_at`); cleaned catalog fields (§7 recodes);
georeference (`lat0`, `lon0`, `alt0` — the measured altitude at the origin fix, informational only); timing (`t_signal_*`, `duration_signal_s`,
`duration_flight_s`, `ground_phase_{start,end}_s`); cleaning diagnostics (`n_fix_raw`,
`n_fix_clean`, `frac_interpolated`, `dt_native_s`, `was_resampled`, `alt_source`); filtering
params (`savgol_window_horiz/vert`, `savgol_order`). Fields unavailable for a source stay
`null`.

## Storage & engine

- **`fixes`**: Parquet + **Polars** (lazy / out-of-core) — ~186k flights × ~10⁴ fixes ≈ 10⁹
  rows, too large for pandas-in-RAM; columnar reads + predicate pushdown on
  `(source, flight_id)`. Adds `polars`/`pyarrow` deps.
- **catalog / `flights_meta`**: small — pandas + CSV (catalog, unchanged) / single Parquet.

## Catalog quirks

Handle at ingestion (empirically observed on the real files):

- **`flight_id`**: verify the cross-source intersection *before* merging; FFVL appears to
  share one counter, so the primary key is `(source, flight_id)` — no exceptions.
- **Missing-data sentinels differ**: hang-glider leaves `duration_s`/`speed` blank,
  paraglider writes `0.0` for the same orphan rows → normalize to NaN.
- **Placeholder dates** (`0000-00-00`) → parse defensively (`errors='coerce'`).
- **`dept` is not geolocation** (non-French sentinels `0`, `999`) → use `lat0/lon0` from the
  first fix.
- **`wing_class` is not cross-source comparable** (EN/AFNOR vs FAI classes) → recode
  explicitly; flag `Biplace`/`non homologuée` for exclusion from single-pilot analyses.
- **`pilot`** carries anonymized tokens on some rows → validate the pattern before any
  per-pilot analysis.

## Regenerating everything after a run

`scripts/regenerate.sh` runs, in order:

| # | step | writes | cost |
|---|---|---|---|
| 1 | `verify_dataset.py` | `verify.tex` (`\StatVerify*`) | one full scan |
| 2 | `generate_pipeline_census.py` | `pipeline_census.tex`, `tab:pipecensus` | seconds |
| 3 | `generate_msd_figure.py` | `msd.pdf`, `msd_curve.csv`, `msd.tex` | ~20 min |
| 4 | `generate_census_stats.py` | `census.tex` (`\StatScan*`, `\Preproc*`) | seconds |
| 5 | `audit_msd.py` | per-flight positions at every lag, into `$AUDIT_DIR` | ~20 min |
| 6 | `audit_msd_report.py` | `audit.tex` (`\StatAudit*`) | seconds |
| 7 | `generate_prelim_figure.py` | `prelim_{ensemble,strata}.pdf`, `prelim.tex` | seconds |
| 8 | `generate_dataset_stats.py` | `dataset_stats.tex`, `dataset_seasons.pdf` | seconds |
| 9 | `measure_variations.py` | per-flight filtered variations, into `$AUDIT_DIR` | ~25 min |
| 10 | `generate_transport_figure.py` | `transport.tex`, `transport.pdf` | ~1 min |
| 11 | `check_generated_macros.py` | nothing; fails if a quoted macro is unwritten | instant |
| 12 | `latexmk` | `thesis/main.pdf` | ~1 min |

Steps 9 and 10 are Chapter 3's measurement. Step 9 is the third full traversal of the fix
table; it keeps one filtered-variation curve per flight per filter order, so every
stratification step 10 performs — by cadence, wing class, season and declared task — is a
row selection rather than another 43 GB scan.

Steps 5–7 are the audit and the preliminary characterization. Step 5 is a second streaming
pass that keeps what step 3 averages away — each flight's position at each lag — because
the questions the audit asks (does the curve's shape survive a fixed logger cadence, a
fixed duration, the removal of the common heading?) are different reductions of a
per-flight quantity that no longer exists once the average has been taken. Step 7 reads
step 5's arrays rather than the fix table, which is what makes a stratified MSD a row
selection instead of another 43 GB scan. `$AUDIT_DIR` defaults to `$TMPDIR/soaring-audit`
and holds a few hundred MB per discipline; it is an analysis product, not a thesis one.

It **refuses to start
while `preprocess.py` is alive**, because the driver rewrites `<data_root>/derived/` in
place and writes `flights_meta.parquet` only after its last flight — so a generator run
against a live archive reads a partial fix table beside the *previous* run's metadata and
produces numbers that are wrong and look right. That is not hypothetical; it happened.

The macro contract is checked before the build and not after, because an undefined
generated macro inside a `\SI{}` is a **fatal** LaTeX error, not a warning: siunitx fails
to parse the argument, the braces unbalance, and the build dies with dozens of `Extra }`
errors pointing at lines that are perfectly correct.

## Decisions taken while building (2026-08-03)

Each is a place where the specification did not determine the answer, and each is
mirrored in the thesis appendix (`impl:fixlevel`, `impl:trimming`) in the same pass:

- **The impossibility gate deletes; the Hampel flag does not gate.** The identifier's
  50 % breakdown point is a stated property, and the archive exceeds it: scattered runs of
  null-island `(0,0)` fixes can be more than half a ±20 s window, the median follows them,
  and the corrupt fixes go *unflagged* while the good ones around them are flagged. A rule
  requiring the flag is blind exactly there. Deletion now needs only: unreachable from the
  anchor at the `v_xy` bound, and the block's removal lets the track rejoin. The flag is
  still recorded per fix and counted per flight. (Thesis `sec:fixlevel`, second revblock.)
- **Postcondition: no impossible step inside a segment.** Whatever the scan resolves, any
  surviving step past the `v_xy` bound becomes a segment boundary — it is a transition of
  unknown course, like a long gap. Stated as a property of the output so the invariant
  holds by construction; the number of boundaries it adds is `n_boundaried` in
  `flights_meta`, because a silent repair is a lost diagnosis.
- **A block may run for `hampel_window_s` before it is called a discontinuity.** Reused,
  not invented. It also sets the scale at which excursion and offset part: an offset under
  `v_xy_max · w` ≈ 900 m is removed as an excursion instead of split.
- **Flight-level plausibility bound.** Mean ground speed `path / duration` must stay under
  the discipline's own fix-level `v_xy` bound. Same kind of sanity cut as the 16 h duration
  cap, and it reuses the existing number rather than adding a key. Catches the logs that
  are corrupt beyond repair; one such flight left in would carry the ensemble MSD alone.
- **The ground-flatness test uses a central span, not a full range.** A range is a maximum
  statistic: over zero-mean noise it grows as `2σ√(2 ln n)` — 4.6 m over 60 samples, 7.1 m
  over 3000 — so against a 5 m tolerance the same motionless pilot passed on a short stint
  and failed on a long one, and since an interior stint must last minutes to be considered
  at all, **the guard could not fire on anything**. The p5–p95 span sits at 3.3σ whatever
  the length. Consequence stated openly: on a GNSS-fallback flight the guard *abstains*,
  because the widened tolerance the thesis promises needs a measured channel-noise ratio
  that a first measurement did not reproduce. Abstaining is the safe direction.
- **An unreturned vertical step is counted (`n_alt_level_shift`) but not yet treated.** The
  `|v_z|` rule knew an out-and-back spike and a coherent run; a single step never undone —
  a barometric re-reference — is neither, so it was censored by nothing *and counted by
  nothing*, and the smoothing differentiated it into up to 5117 m/s in the table. 8.3 % of
  paraglider and 6.2 % of hang-glider flights carry one. Detection is not a judgement, so
  it is done; the treatment (split / re-reference / invalidate) each changes a rule the
  thesis argues, so it is left open for the segmentation work that consumes `v_z`.
- **`suspect_intervals.parquet` is written.** The driver returned only three tables, so the
  slow-and-flat stints stage (iii) exists to produce were dropped on the floor and the
  ψ(τ) sensitivity check had no data. Written even when empty, so its absence means "older
  run", not "no flight had one".
- **A hole in the vertical channel is flagged, not split at, and never silent.** `g_max`
  bounds the interval between two *fixes*; it says nothing about an interval where a fix
  exists but carries no altitude — which happens whenever the logger wrote none or the
  cleaning removed one, with the horizontal record intact. No time gap opens, so no split
  is declared and `interpolated` stays False, while `_fill_channel` bridges the hole with
  a straight line of any length. Measured: 500 s of missing altitude gave up to 540 m of
  error, a fabricated `v_z`, `frac_interpolated = 0.00000` and `was_resampled = False`.
  The flight declared itself uniform as recorded. Now: per-fix `z_reconstructed`,
  per-segment `frac_z_reconstructed`, per-flight `z_gap_max_s`. **No split**, because the
  horizontal trajectory is intact and Chapter 3 measures the horizontal — cutting it for a
  vertical defect would discard good data. Vertical analyses exclude on the flag.
- **No rule attributes an impossible step at the *start* of a record — deliberately.**
  The first fix becomes the ENU origin (`sec:enu`), so a corrupt one displaces every
  coordinate; five archive flights sat 4500 km out. But a step is a statement about a
  *pair*, and away from the ends the bounded-removal test settles which end is wrong by
  asking which removal restores the trend — at the first fix there is no trend behind it
  to ask. Two rules were written and both were wrong, opposite ways: firing on the first
  impossible step accuses the earlier end always (an ordinary spike 3 s in deleted the
  good fixes and became the origin); firing on the scan's split looks like evidence but
  the split index is the first fix of the *unrejoinable block*, which is **after** the
  step whenever the corruption outlasts `w` (a 50 s corrupt run 5 s in deleted 5 good
  fixes, kept 50 bad, origin 5039 km out). The discontinuity is left as one; the
  guarantee lives at the flight level, where the reach bound refuses such a record whole.
  That bound never depended on the rule, and the rule would have recovered 2 flights in
  156 017.
- **Flight-level reach bound.** Every fix must satisfy `|r(t)| ≤ v_xy_max · t` — stated
  per fix, the same form `verify_dataset.py` checks on the written table, and not as the
  extent against the whole duration, which would license a fix 100 km out ten seconds in. This is the *displacement* analogue of the
  plausibility bound, and it catches what that one cannot: a flight whose first fix is
  corrupt has no impossible step left to inflate the path, so it passes every other cut and
  simply sits thousands of kilometres from its own origin. Five paraglider flights in run 4
  sat 4500 km out; because the ensemble MSD averages `|r|²`, five records in 156 017 moved
  it by seven orders of magnitude. Costs 0.03 % (para) / 0.05 % (hang) on a 4000-flight
  sample, and reuses the existing number. Re-checked on the written tables by
  `verify_dataset.py` as `|r(t)| ≤ v_xy_max · t` — the one invariant stated in terms of the
  frame and the bound alone, so it holds whatever the pipeline did.
- **No Hampel test on `z`.** `sec:fixlevel` argues it (three reasons); `impl:fixlevel`
  still said the identical test ran on the altitude channel. The body wins, the appendix
  was corrected, and the vertical is cleaned by its absolute bounds alone.
- **Both altitude bounds act on the *adopted* channel**, GNSS included. With no local
  test on `z`, the alternative would leave a GNSS-fallback flight with no vertical cleaner
  at all. The `|v_z|` bound was calibrated on barometric data but expresses an aircraft
  envelope, not an instrument one; its firing rate is recorded per `alt_source`.
- **The `|v_z|` bound marks *isolated* spikes only** — both adjoining steps over the
  bound, opposite signs. A same-sign run is a sustained manoeuvre (a spiral dive), counted
  and left alone: this is `impl:fixlevel` check (5) made operational.
- **The first fix is tested forward.** An anchor-carrying scan never questions its first
  anchor, and that fix becomes the ENU origin — a spike there displaces the whole flight.
  It is deleted on the same two conditions as any other: flagged, and an impossible step
  to its successor. (Found by the MSD: two flights with a 4 km first step dominated the
  short-lag ensemble average.)
- **The interior-ground flatness test bounds the fitted slope too.** Detrending removes a
  steady climb as readily as a pressure drift, so the residual test alone would excise a
  wing thermalling at 1 m/s in still air. The slope bound is `δ_z / τ_freeze`, a rate the
  config already fixes.
- **A segment shorter than the smoothing window is dropped** with reason
  `shorter_than_smoothing_window`. The 90 s segment gate guarantees the window fits only
  up to Δt = 22.5 s.
- **The `segments` table records every segment**, kept or not, with the reason.

## Open items

- ~~The Savitzky–Golay `τ_c` are placeholders~~ **Measured** (2026-07,
  `estimate_savgol_timescales.py`): all three knees at ~0.2 Hz → `τ_c = 5 s`, the typical
  floor being IGC quantization on every channel. Confirm with the sec:savgol validation
  (flat residual spectrum, one-step window stability) on the production ENU series.
- The `alt_channel` liveness bound and the flight-level duration window /
  altitude-activity floor are census-motivated additions (thesis `sec:flightfilter`,
  `sec:altchannel`); audit them on the first production run.
- Duplicate uploads: before pooling, check whether the same physical flight appears twice
  (same pilot and date, near-identical track); the catalog does not guard against it.
- The `sampling` cuts (`max_gap_factor`/`max_gap_seconds`/`max_missing_fraction`) and the
  fix-level **absolute bounds** (thesis `tab:cleaning`) are set and **audited** on the real
  data (`make_gap_diagnostics_figure`,
  thesis `sec:uniform`; `make_fixlevel_diagnostics_figure`, `sec:fixlevel`). Revisit only if a future
  source's distributions place a cut outside its implausible tail. `max_gap_seconds` is a
  **working value** (census impact in the `StatScan*GapSplit*` macros: the cap mostly
  affects the slow-cadence hang-glider half) → freeze it via the a-posteriori sweep of the
  split fractions (same procedure as the cleaning thresholds).
- The fix-level **robust-outlier** (`w, k, ε_min`), **frozen-lock** (`ε, δ_z, τ_freeze`),
  integrity `f`, segment-gate and interior-ground values are **in the YAML as working
  values**, fixed a priori. Primary validation (July 2026 review pass, thesis
  `sec:fixlevel`): audit the per-rule removal fractions over the archive and sweep each
  threshold around its working value (plateau ⇒ keep). Injected defects and the
  downstream-invariance sweep are the deeper, *targeted* follow-up for rules the audit
  leaves in doubt — they bound the false negatives the removal audit cannot see.
- Actual `flight_id` cross-source intersection check → confirms the `(source, flight_id)` key.
- Sailplane catalog schema → document as above once the source is in hand.
