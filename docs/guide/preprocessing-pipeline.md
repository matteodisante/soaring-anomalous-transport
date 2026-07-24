# Pre-processing pipeline — implementation blueprint

!!! warning "Status: design blueprint (transient)"
    This page is the **engineering contract** for building the IGC → clean-dataset
    pipeline: the exact steps, schemas, config keys and storage. It is deliberately
    *transitional*. Once the pipeline is implemented it **retires** into the code (the
    single source of truth) plus the auto-generated [API Reference](../reference.md) and a
    short usage guide — it is **not** maintained as a second copy forever.

    The **why** (justification, method, hyperparameter reasoning) lives in the thesis,
    chapter *The dataset*, section *Trajectory pre-processing* (`sec:preproc`) — not here.
    The **numbers** (all thresholds) live in
    `configs/preprocessing.yaml` (loaded via `load_preproc_config`) — not here. This page
    links to both; where it repeats a headline threshold for readability, the YAML stays
    authoritative. That is how we avoid a thesis/doc that drift.

    **During implementation, follow this page** for steps, schemas, keys and storage;
    open the thesis only when the *behaviour* is ambiguous. On any conflict, the thesis
    is normative and this page must be corrected — the two are kept aligned by the same
    design audits that produced them.

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
| i | Choose altitude channel per flight | fixes | `alt_source ∈ {baro,gnss}` + chosen `alt` | *(to build)* | `sec:altchannel` |
| ii | Fix-level cleaning: absolute bounds + robust local test + structural rules | raw geo | cleaned fixes | `FixLevelThresholds` ← YAML; `fix_level_distributions` | `sec:fixlevel` |
| iii | Trim outer ground phases (`v_xy` sustained); interior-ground guard planned (near-zero `v_xy` ≥ `T_ground` **and** flat baro → excise & split) | raw geo | airborne segment | `TrimmingThresholds` ← YAML | `sec:trimming` |
| iv | Flight-level filtering (duration + path length) | parsed tracks | keep/drop + reason | `FlightLevelThresholds` ← YAML, `scan_tracks` | `sec:flightfilter` |
| v | Geographic → ECEF → ENU (origin = first fix of the trimmed track) | geo | `E,N,U` | *(to build; formula in thesis)* | `sec:enu` |
| vi | Enforce uniform `Δt` within flight | ENU | uniform series or exclusion | *(to build)* | `sec:uniform` |
| vii | Savitzky–Golay smooth + differentiate | ENU | pos/vel/acc | *(to build; `scipy.signal.savgol_filter`)* | `sec:savgol` |
| viii | Write `fixes` + `flights_meta` | all | Parquet | *(to build)* | — |

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
  flights); **altitude activity** ≥ 75 m on the adopted channel (vehicle
  logs, dead sensors). Path length = sum of great-circle steps (not extent/displacement).
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

## Reporting-stage scan cache (not the production `fixes`/`flights_meta` tables)

Ahead of the real pipeline, the thesis-figure scripts already run a full-dataset scan
(`soaring.analysis.preprocessing.scan_tracks`, driven by `track_stats` per flight) to
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
`baro_present_frac` is consumed by the altitude-noise figure's fallback-rate panel (thesis
`sec:altchannel`), which prefers this cache (`altitude_noise.baro_presence_from_scan`) over its own
separate scan when it exists, turning a sampled estimate into an exact census at no extra
parsing cost. The speed/altitude fields are per-flight *maxima*, so they only say which
*flights* a fix-level bound would touch; the fix-level figure (step ii) instead uses genuine
**per-fix** distributions (`fix_level_distributions`, a seeded sample), because what
justifies a fix-level cut is the fraction of *fixes* it removes, not of flights it touches.

## Output schema

### `fixes` (one row per fix)

Partitioned Parquet by `(source, flight_id)`, zstd. Only filter *outputs* are stored;
everything else is lazy.

| column | dtype | note |
|---|---|---|
| `source` | categorical | `paraglider` / `hangglider` / `sailplane` |
| `flight_id` | int32 | key is `(source, flight_id)` — see [flight_id](#catalog-quirks) |
| `segment_id` | int16 | 0-based within the flight; a split at a long gap / excised run increments it (thesis `sec:uniform`) |
| `interpolated` | bool | grid point reconstructed at resampling, not measured |
| `t` | float32 | s; `t=0` at first airborne fix of the **parent flight** (segments keep the parent clock) |
| `E`, `N` | float32 | ENU, smoothed (`deriv=0`); `E=N=0` at the first fix of the trimmed track |
| `z` | float32 | adopted altitude channel at its measured value, smoothed; never re-zeroed (thesis `sec:enu`) |
| `v_E`, `v_N`, `v_z` | float32 | velocity (`deriv=1`) |
| `a_E`, `a_N`, `a_z` | float32 | acceleration (`deriv=2`) |

Lazy (never stored), e.g. `v_tot=√(v_E²+v_N²+v_z²)`, `θ_xy=atan2(v_N,v_E)`,
`ω=(v_E a_N − v_N a_E)/(v_E²+v_N²)`. (`z` is already absolute; no `U_origin` offset exists.)

### `segments` (one row per segment)

Single Parquet. Key `(source, flight_id, segment_id)`: `t_start`, `t_end`, `n_fix`,
`frac_interpolated`, and the boundary-censoring flags for phases truncated at either end
(thesis `sec:uniform`). Per-flight aggregates stay in `flights_meta`.

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
