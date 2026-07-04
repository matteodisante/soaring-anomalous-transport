# Pre-processing pipeline — implementation blueprint

!!! warning "Status: design blueprint (transient)"
    This page is the **engineering contract** for building the IGC → clean-dataset
    pipeline: the exact steps, schemas, config keys and storage. It is deliberately
    *transitional*. Once the pipeline is implemented it **retires** into the code (the
    single source of truth) plus the auto-generated [API Reference](../reference.md) and a
    short usage guide — it is **not** maintained as a second copy forever.

    The **why** (justification, method, hyperparameter reasoning) lives in the thesis,
    chapter *Next steps*, §4.1 — not here. The **numbers** (all thresholds) live in
    `configs/preprocessing.yaml` (loaded via `load_preproc_config`) — not here. This page
    never restates either; it links to them. That is how we avoid a thesis/doc that drift.

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
| Raw IGC tracks | `<data_root>/igc/` per source (SSD) | `source ∈ {paraglider, hangglider, sailplane}`; on-disk dirs are `paragliders/`, `hang_gliders/` (values ≠ dir names by design) |
| Raw catalog | `data/<discipline>/catalog.csv` | pandas + CSV, 23 columns (`soaring.acquisition.ffvl.catalog.CATALOG_COLUMNS`), regenerable via `build-catalog` |

The catalog is **metadata only** and can be wrong (see [Catalog quirks](#catalog-quirks));
it is a coarse pre-filter and provenance source, never the basis of a scientific cut.

## Pipeline steps

Order and rationale: thesis §4.1. Steps (i)–(iv) act on **raw geographic** coordinates
(great-circle speeds); (v) converts to the metric ENU frame; (vi)–(vii) are metric.

| # | Step | Acts on | Produces | Code home | Thesis |
|---|---|---|---|---|---|
| 0 | Ingest catalogs, add `source`, coarse pre-filter (no track ⇒ skip) | catalog | candidate flight list | `acquisition.ffvl.catalog` | §3 |
| 1 | Parse IGC `B`/`H` records | `.igc` | fixes `[t,lat,lon,valid,baro_alt,gnss_alt]` | `analysis.igc.parse_igc` | §3, §4.1 |
| i | Choose altitude channel per flight | fixes | `alt_source ∈ {baro,gnss}` + chosen `alt` | *(to build)* | §4.1.1 |
| ii | Fix-level cleaning (dynamics plausibility) | raw geo | cleaned fixes | `FixLevelThresholds` ← YAML | §4.1.2 |
| iii | Trim ground phases (`v_xy` sustained) | raw geo | airborne segment | `TrimmingThresholds` ← YAML | §4.1.3 |
| iv | Flight-level filtering (duration + path length) | parsed tracks | keep/drop + reason | `FlightLevelThresholds` ← YAML, `scan_tracks` | §4.1.4 |
| v | Geographic → ECEF → ENU (origin = take-off) | geo | `E,N,U` | *(to build; formula in thesis)* | §4.1.5 |
| vi | Enforce uniform `Δt` within flight | ENU | uniform series or exclusion | *(to build)* | §4.1.6 |
| vii | Savitzky–Golay smooth + differentiate | ENU | pos/vel/acc | *(to build; `scipy.signal.savgol_filter`)* | §4.1.7 |
| viii | Write `fixes` + `flights_meta` | all | Parquet | *(to build)* | — |

Key mechanics that reconcile the blueprint with the repo:

- **Altitude channel (i).** The parser returns *both* channels; the pipeline picks one per
  flight (`alt_source`), never splices. Barometric where present; whole-channel-absent
  flights fall back to unfiltered GNSS. The `A`/`V` flag is subsumed by the
  missing-altitude check on the chosen channel. (Thesis §4.1.1.)
- **ENU (v).** Origin at the take-off fix; `E,N` zeroed there; **`U` is not re-zeroed**
  (absolute barometric altitude retained; the take-off height `U_origin` is stored in
  `flights_meta`). (Thesis §4.1.5, Notation.)
- **Flight-level cuts (iv).** Duration ≥ 40 min and flown **path length** ≥ 30 km, both
  computed from the track. Path length = sum of great-circle steps (not extent/displacement);
  30 km is a *minimal* cut (a real XC flies far more). A minimum-fix-count cut is dropped as
  redundant with the duration cut. (Thesis §4.1.4.)
- **Uniform Δt (vi).** Native `Δt` per flight (no common cadence). Uniform ⇒ use as is;
  mildly irregular ⇒ resample onto the native grid across small gaps; badly sampled ⇒
  **exclude**. Thresholds `max_gap_factor`, `max_missing_fraction` (in the YAML).
- **Savitzky–Golay (vii).** Two hyperparameters: `window_length` (odd) and `polyorder`.
  Set by the noise-matched procedure of thesis §4.1.7 (PSD knee `f_c` → smoothing scale
  `τ_c` → `window = odd(τ_c/Δt)` per flight; `polyorder` fixed at 3; horizontal and
  vertical treated separately). `deriv=0,1,2` and `delta=Δt` are not tuning knobs.

## Output schema

### `fixes` (one row per fix)

Partitioned Parquet by `(source, flight_id)`, zstd. Only filter *outputs* are stored;
everything else is lazy.

| column | dtype | note |
|---|---|---|
| `source` | categorical | `paraglider` / `hangglider` / `sailplane` |
| `flight_id` | int32 | key is `(source, flight_id)` — see [flight_id](#catalog-quirks) |
| `t` | float32 | s; `t=0` at first airborne fix |
| `E`, `N` | float32 | ENU, smoothed (`deriv=0`); `E=N=0` at take-off |
| `U` | float32 | ENU up, smoothed; **not** re-zeroed |
| `v_E`, `v_N`, `v_U` | float32 | velocity (`deriv=1`) |
| `a_E`, `a_N`, `a_U` | float32 | acceleration (`deriv=2`) |

Lazy (never stored), e.g. `v_tot=√(v_E²+v_N²+v_U²)`, `θ_xy=atan2(v_N,v_E)`,
`ω=(v_E a_N − v_N a_E)/(v_E²+v_N²)`, `z_abs=U+U_origin`.

### `flights_meta` (one row per flight)

Single Parquet. Identity + provenance (`source`, `flight_id`, `global_flight_id?`,
`pipeline_version`, `config_hash`, `processed_at`); cleaned catalog fields (§7 recodes);
georeference (`lat0`, `lon0`, `U_origin`); timing (`t_signal_*`, `duration_signal_s`,
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

- The Savitzky–Golay `τ_c` (horizontal/vertical) and the sampling `max_*` values are
  **placeholders** in `configs/preprocessing.yaml` → finalize from the real PSD study on
  `E,N,U`. (`polyorder`, the filtering and trimming cuts are set.)
- Actual `flight_id` cross-source intersection check → confirms the `(source, flight_id)` key.
- Sailplane catalog schema → document as above once the source is in hand.
