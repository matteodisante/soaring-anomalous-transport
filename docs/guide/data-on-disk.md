# Data on the SSD

Raw flight recordings and large processed tables live on the external SSD. The
repository keeps small season summaries, map geometry, numerical reports and annotation
packs. The disk's root `README.md` is generated from its actual directory entries,
file sizes and Parquet metadata by `scripts/reporting/tools/write_ssd_readme.py`.
It is refreshed by the combined rebuild. This page describes the schema and conventions;
it does not preserve obsolete example counts from an earlier cleaning run.

## Roots and identity

| Discipline | Default root | Environment override | Stored `source` |
|---|---|---|---|
| Paragliders | `/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc` | `SOARING_PARA_DATA_ROOT` | `paraglider` |
| Hang gliders | `/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc` | `SOARING_DELTA_DATA_ROOT` | `hangglider` |

Defaults come from `configs/para_download.yaml` and `configs/delta_download.yaml`.
A flight is identified by `(source, flight_id)`, not by `flight_id` across disciplines.
A segment adds `segment_id`; a fix adds elapsed time `t`.

```text
<data_root>/
  raw/igc/<season>/             original IGC tracks
  raw/raw_xml/                 original season XML exports
  catalog/                     catalogue and season index
  derived/
    fixes.parquet
    flights_meta.parquet
    segments.parquet
    suspect_intervals.parquet
    run_manifest.json
    segmentation/              fitted models and phase products
    ...                        raw diagnostic caches
  logs/                        acquisition logs
```

The shared `derived-audit/` directory sits alongside the two discipline roots. Its
`runs/<run-id>/arrays/` files are inputs to report generators. Each run also carries
logs and `manifest.json`; older standalone arrays must not be mixed with a new run.
After an SSD interruption, a validated recovery may keep its manifest, logs and
some backing arrays on the internal disk. The September 2026 recovery is recorded
under `revisions/vertical-gap-split-2026-09-11/recovery-runs/`; its manifests identify
the exact parent stages and every reused path. This recovery directory is not
interchangeable with either the SSD's general audit directory or another run's arrays.

## The four cleaned tables

| Table | Row represents | Role |
|---|---|---|
| `fixes.parquet` | A grid time in a retained segment | Position, derivatives and quality flags |
| `flights_meta.parquet` | An attempted flight, retained or rejected | Decisions, counters, origin and processing parameters |
| `segments.parquet` | A segment considered for retention | Segment coverage, disposition and boundaries |
| `suspect_intervals.parquet` | A flagged slow/flat interval | Intervals reserved for a future sensitivity analysis |

A rejected flight remains in `flights_meta`. A rejected segment remains in `segments`
when the pipeline reached that stage. Stages not reached leave their metadata null.
A missing table is not evidence that its count is zero: all four are required, including
an empty `suspect_intervals` table.

### `fixes.parquet`: 19 columns

| Columns | Meaning and units |
|---|---|
| `source`, `flight_id`, `segment_id` | Flight and segment identity |
| `t` | Seconds from the trimmed flight origin; retained across segment boundaries |
| `E`, `N` | Smoothed local east and north position, metres |
| `z` | Smoothed adopted GNSS altitude, metres; not re-zeroed |
| `v_E`, `v_N`, `v_z` | First derivatives, m/s |
| `a_E`, `a_N`, `a_z` | Second derivatives, m/s² |
| `interpolated` | No surviving horizontal fix within half a native interval of this grid time |
| `z_reconstructed` | Interpolated grid time or a nearest surviving fix with missing altitude |
| `z_derivative_reconstructed` | The vertical polynomial fit uses at least one altitude marked reconstructed |
| `edge` | Off-centre polynomial evaluation near a segment end |
| `hampel_flagged` | Nearest-fix diagnostic position flag; it does not itself delete a fix |
| `alt_invalidated` | Nearest-fix altitude invalidation during cleaning |

The ten time/kinematic columns are stored as float32. A uniform grid is defined within
each segment at that flight's estimated native interval; it is not one common cadence
for the whole archive. Do not compare fix-to-fix turns between cadences as though their
time separations were equal.

`E,N` use the first trimmed fix as the coordinate origin before smoothing. Smoothing
can move that first retained value slightly away from zero. `z` keeps the numerical
recorder altitude. Recorder geoid/ellipsoid conventions have not been harmonised;
absolute altitude is therefore not a common geodetic datum established by this pipeline.

### Flight and segment metadata

`FlightRecord` in `soaring.analysis.preproc.pipeline` defines the per-flight fields.
Values are nullable when a flight stopped before reaching the relevant stage; counter
names identify different operations and must not be summed as disjoint removed fixes.

| Fields | Meaning |
|---|---|
| `source`, `flight_id`, `pipeline_version` | Flight identity and cleaning version |
| `drop_stage`, `drop_reason`, `error_detail` | First stopping condition, or null for a retained flight; exception detail when processing failed |
| `gnss_present_frac`, `gnss_range_m` | Raw GNSS altitude availability and range |
| `baro_witness`, `baro_present_frac`, `baro_range_m` | Flight-level barometric availability summary; local witness decisions still require complete local support |
| `n_alt_missing_raw` | Altitudes missing before cleaning |
| `n_fix_raw`, `n_fix_clean` | Fix counts before and after fix-level cleaning |
| `n_merged_duplicates`, `n_removed_backward` | Duplicate-time merges and backward-time deletions |
| `n_removed_spike`, `n_removed_frozen` | Horizontal spike/block and frozen-position deletions |
| `n_alt_out_of_band`, `n_alt_vz_sustained`, `n_alt_vz_spike` | Altitudes censored by the altitude-band, sustained-speed and spike rules |
| `n_flagged_kept`, `n_vz_runs`, `n_alt_level_shift` | Retained Hampel flags, excessive vertical-speed runs and unresolved level shifts |
| `split_jump_max_m`, `n_boundaried`, `integrity_fraction` | Largest forced-boundary jump, boundary count and fix-cleaning integrity fraction |
| `ground_phase_start_s`, `ground_phase_end_s`, `trimmed_fraction` | Ground-trimming endpoints and removed fraction |
| `n_interior_excised`, `n_suspect_stints` | Excised interior-ground fixes and saved shorter suspect intervals |
| `duration_flight_s`, `path_km`, `alt_range_m`, `extent_km` | Flight-level duration, path length, altitude range and horizontal extent before resampling |
| `lat0`, `lon0`, `alt0` | Coordinate origin from the first trimmed fix |
| `dt_native_s`, `g_max_s` | Inferred native interval and gap-splitting bound |
| `n_segments`, `n_segments_kept` | Segments formed and surviving segment-level gates |
| `frac_interpolated`, `frac_z_reconstructed`, `z_gap_max_s` | Time-grid and altitude reconstruction fractions and longest retained run of flagged altitude (not the duration of excluded gaps) |
| `was_resampled` | Whether uniform-grid resampling was applied |
| `savgol_order`, `savgol_window_horiz`, `savgol_window_vert` | Polynomial order and horizontal/vertical smoothing lengths, in fixes |

`duration_flight_s` measures the recorded duration used at the flight-level gate,
excluding gaps and mandatory boundaries. The retained-segment duration measured by a
later transport report can differ after segment rejection. The upper flight-duration
gate uses elapsed span, including gaps. Use the estimator's stated duration convention.

Suspect intervals carry `source`, `flight_id`, `t_start` and `t_end` in the flight clock.
Their proposed waiting-time sensitivity analysis is not currently implemented. They
must not be described as an already measured waiting-time distribution.

## Run state and safe reading

An active or interrupted cleaning leaves `derived/.run_incomplete`. Do not treat the
four tables as a complete archive while it exists. `run_manifest.json` records the
cleaning configuration, source fingerprint, dependency versions and table identities.
These identities use file size, modification time, row count and Parquet-footer hash;
they are not hashes of every trajectory value. The combined workflow additionally
reprocesses a seeded retained-flight sample.

The `.preprocess.lock` file supports advisory locking. Its presence alone does not
mean the lock is held; the operating system tracks that state. See the
[rebuild guide](rebuilding.md) for failure recovery.

Stream trajectories. Parquet row groups can divide a flight:

```python
from soaring.analysis.derived import stream_flights

for flight in stream_flights(root / "derived" / "fixes.parquet",
                             ["segment_id", "t", "E", "N"]):
    for segment_id, segment in flight.groupby("segment_id", sort=False):
        ...  # form time-lagged increments within this segment
```

To inspect current shapes, types and example rows without loading the full table:

```bash
uv run python scripts/reporting/tools/show_dataset.py --discipline "hang gliders"
```

## Diagnostics, segmentation and human labels

Raw caches include `track_scan.parquet`, `fixlevel_scan.parquet`,
`alt_offset_scan.parquet`, `psd_sample.npz` and `savgol_psd_sample.npz` when their
reports have run. Cache presence does not establish freshness. The complete rebuild
rescans raw diagnostics and creates separate transport arrays. PSD cache version 2 uses
paired uninterrupted altitude intervals where both channels are compared.

The `segmentation/` products are written by `segment_flights.py train`, `apply` and
`coverage`. They require their own model/configuration provenance; preprocessing alone
does not update them. Their schemas and missing-feature rules are in the
[segmentation guide](flight-phase-segmentation.md).

Manual labels and packs under `annotations/phase_labeling/` in the repository are
separate research inputs. Preserve them. A new complete rebuild creates a new pack;
it does not overwrite an earlier annotation session or turn model predictions into
human reference labels.

## Vertical support from pipeline 2.3.0

The temporal gap bound also limits separation between consecutive finite altitude
readings. Long vertical holes and missing-altitude endpoints are excluded from the
full trajectory before resampling, even when horizontal fixes exist. The segment table
retains these unsupported intervals as rejected candidates with
`channel_not_reconstructable`; neighbouring supported candidates pass the usual gates.
Their censoring flags, original clock and spatial origin are preserved. Consequently,
`n_segments` includes rejected unsupported intervals as well as supported candidates;
use `n_segments_kept` for the retained count. Rebuild all derived products after this
change; existing raw IGC recordings and human annotations remain unchanged.


`z_gap_max_s` measures runs of the nearest-fix reconstruction **flag on the output
grid**, not the longest interval between finite source readings. With irregular
timestamps, valid readings between grid nodes can support consecutive short bridges
without clearing the flag at an intervening node. A flagged run can therefore exceed
`g_max_s` even though every actual interpolation span respects it. The gap-splitting
rule uses finite source times; the flag-run counter is not a substitute for that check.
