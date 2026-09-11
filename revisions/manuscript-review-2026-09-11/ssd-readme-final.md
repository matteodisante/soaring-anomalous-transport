# Soaring flight data

External data for `matteodisante/soaring-anomalous-transport`. This inventory is generated from the mounted disk by `scripts/reporting/tools/write_ssd_readme.py`.

Generated 2026-09-11T10:09:12+02:00.

## Disk root

| Entry | Purpose |
|---|---|
| `README.md` | this generated inventory |
| `derived-audit/` | analysis arrays, audit logs and rebuild manifests |
| `hang_gliders/` | hang-glider archive |
| `paragliders/` | paraglider archive |
| `uni_other stuff/` | outside the thesis data workflow; contents not inspected |

Hidden macOS indexing, trash and filesystem directories are omitted.

## Connecting the repository

Default paths are in `configs/para_download.yaml` and `configs/delta_download.yaml`. Environment variables override them when the disk mounts elsewhere:

```bash
export SOARING_PARA_DATA_ROOT='/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc'
export SOARING_DELTA_DATA_ROOT='/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc'
```

Preserve raw downloads, catalogues containing acquisition state, human labels and run records. Cleaned tables can be regenerated from the raw tracks with the recorded code, configuration and dependencies. Diagnostic caches, transport arrays and segmentation need their respective reporting and fitting steps. The complete sequence is `uv run python scripts/rebuild_thesis.py --clean --jobs 8 --full-speed`.

Schema and mathematical conventions: `docs/guide/data-on-disk.md`, `docs/guide/preprocessing-pipeline.md` and `docs/guide/rebuilding.md` in the repository.

## Paragliders

Root: `/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc`.

| Directory | Files | Size | Contents |
|---|---:|---:|---|
| `catalog/` | 2 | 82.8 MiB | catalogue reconstructed from source XML, with acquisition state |
| `derived/` | 19 | 53.8 GiB | cleaned tables, diagnostic caches and fitted segmentation products |
| `logs/` | 2 | 77.8 KiB | acquisition logs |
| `raw/` | 186,079 | 60.6 GiB | downloaded IGC tracks and original season XML; preserve and back up |

The actual raw-data subdirectories are: `raw/igc/`, `raw/raw_xml/`.

Cleaning manifest: **complete**, pipeline **2.2.0**. Run identifier: `1c8597f1-e955-4dd0-b899-81fad898c377`.

### Files directly in `derived/`

| File | Rows | Size | Purpose |
|---|---:|---:|---|
| `.preprocess.lock` | — | 0 B | advisory lock file; its presence alone does not mean a process is running |
| `alt_offset_scan.parquet` | 19,964 | 1018.0 KiB | sampled paired altitude offsets |
| `fixes.parquet` | 1,370,352,162 | 40.4 GiB | retained trajectories on each flight's native-rate grid |
| `fixlevel_scan.parquet` | 508,170,274 | 943.1 MiB | streamed raw diagnostic values |
| `flights_meta.parquet` | 186,052 | 12.8 MiB | every attempted flight, decisions and stage counters |
| `psd_sample.npz` | — | 2.8 MiB | paired-channel raw altitude PSD sample and its selection policy |
| `run_manifest.json` | — | 5.1 KiB | cleaning definition, completion state and identities of all four cleaned tables |
| `savgol_psd_sample.npz` | — | 1.9 MiB | raw horizontal and vertical PSD samples used to discuss smoothing |
| `segments.parquet` | 281,439 | 4.6 MiB | retained and rejected segments, with coverage diagnostics |
| `suspect_intervals.parquet` | 499 | 8.2 KiB | flagged slow/flat intervals; the proposed waiting-time sensitivity analysis is not implemented |
| `track_scan.parquet` | 186,025 | 9.2 MiB | raw per-flight census cache |

### Subdirectories of `derived/`

`segmentation/`

Fitted HMMs, their training provenance, decoded phase products and coverage. These require `segment_flights.py train`, `apply` and `coverage`; cleaning alone does not regenerate them.

| File | Rows | Size |
|---|---:|---:|
| `coverage_summary.json` | — | 695 B |
| `phase_coverage.parquet` | 179,843 | 2.3 MiB |
| `phase_points.parquet` | 171,721,035 | 12.2 GiB |
| `phase_segments.parquet` | 10,197,199 | 141.8 MiB |
| `model/` | — | directory |

## Hang gliders

Root: `/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc`.

| Directory | Files | Size | Contents |
|---|---:|---:|---|
| `catalog/` | 2 | 3.5 MiB | catalogue reconstructed from source XML, with acquisition state |
| `derived/` | 19 | 1.9 GiB | cleaned tables, diagnostic caches and fitted segmentation products |
| `logs/` | 2 | 17.6 KiB | acquisition logs |
| `raw/` | 6,741 | 1.6 GiB | downloaded IGC tracks and original season XML; preserve and back up |

The actual raw-data subdirectories are: `raw/igc/`, `raw/raw_xml/`.

Cleaning manifest: **complete**, pipeline **2.2.0**. Run identifier: `5ab9d7ad-dd76-44af-bd5f-7ba97d1865cf`.

### Files directly in `derived/`

| File | Rows | Size | Purpose |
|---|---:|---:|---|
| `.preprocess.lock` | — | 0 B | advisory lock file; its presence alone does not mean a process is running |
| `alt_offset_scan.parquet` | 6,677 | 393.7 KiB | sampled paired altitude offsets |
| `fixes.parquet` | 34,588,180 | 1.1 GiB | retained trajectories on each flight's native-rate grid |
| `fixlevel_scan.parquet` | 150,920,967 | 303.4 MiB | streamed raw diagnostic values |
| `flights_meta.parquet` | 6,716 | 578.9 KiB | every attempted flight, decisions and stage counters |
| `psd_sample.npz` | — | 1.2 MiB | paired-channel raw altitude PSD sample and its selection policy |
| `run_manifest.json` | — | 5.1 KiB | cleaning definition, completion state and identities of all four cleaned tables |
| `savgol_psd_sample.npz` | — | 884.6 KiB | raw horizontal and vertical PSD samples used to discuss smoothing |
| `segments.parquet` | 9,559 | 207.2 KiB | retained and rejected segments, with coverage diagnostics |
| `suspect_intervals.parquet` | 5 | 3.3 KiB | flagged slow/flat intervals; the proposed waiting-time sensitivity analysis is not implemented |
| `track_scan.parquet` | 6,716 | 432.1 KiB | raw per-flight census cache |

### Subdirectories of `derived/`

`segmentation/`

Fitted HMMs, their training provenance, decoded phase products and coverage. These require `segment_flights.py train`, `apply` and `coverage`; cleaning alone does not regenerate them.

| File | Rows | Size |
|---|---:|---:|
| `coverage_summary.json` | — | 676 B |
| `phase_coverage.parquet` | 6,796 | 115.8 KiB |
| `phase_points.parquet` | 7,305,190 | 542.8 MiB |
| `phase_segments.parquet` | 408,172 | 5.7 MiB |
| `model/` | — | directory |

## `derived-audit/`

Intermediate arrays are inputs to figure and table generators. They depend on a specific cleaned archive and must not be mixed across cleaning runs. `runs/<run-id>/` contains fresh `arrays/`, one log per stage and `manifest.json`. A completed manifest records source and table identities, generated-output hashes and the built PDF hash. `cleaning/` holds standalone cleaning logs. Older arrays outside `runs/` are not evidence that the current thesis was rebuilt.

Actual entries:

- `audit_flights_hang.parquet`
- `audit_flights_para.parquet`
- `audit_positions_hang.npz`
- `audit_positions_para.npz`
- `ch3_revision_sample.pkl`
- `cleaning/`
- `msd_hang.npz`
- `msd_para.npz`
- `propagator_hang.npz`
- `propagator_para.npz`
- `runs/`
- `shape_hang.npz`
- `shape_para.npz`
- `variation_flights_hang.parquet`
- `variation_flights_para.parquet`
- `variations_hang.npz`
- `variations_para.npz`

| Rebuild run | State at inventory time |
|---|---|
| `20260910T213521Z-f86216f0` | failed |
| `20260910T214304Z-c85fb6b2` | failed |
| `20260910T220000Z-7bc5c232` | failed |
| `20260910T221405Z-7f7418f8` | failed |
| `20260910T221820Z-05d36ab4` | complete |

## Reading trajectories

Stream `fixes.parquet`; storage row groups can split a flight. This reader restores complete flights:

```python
from soaring.analysis.derived import stream_flights

for flight in stream_flights(root / 'derived' / 'fixes.parquet',
                             ['segment_id', 't', 'E', 'N']):
    ...
```

Time is elapsed from the trimmed flight origin. Segments retain their parent's clock and local east–north frame. Form increments within one retained segment. The quality flags distinguish missing-position interpolation, reconstructed altitude, affected vertical derivatives and filter edges.

Manual annotation packs live in the repository under `annotations/phase_labeling/`, with their source provenance. They are not reproduced by cleaning and human labels must be preserved.

