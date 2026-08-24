# soaring-anomalous-transport

Code for the master's thesis **_anomalous transport in soaring flights_**.

Thesis monorepo. Three things live here, in the order data moves through them.

**Acquisition** (`soaring.acquisition.ffvl`) fetches `.igc` flight data from the **Coupe
Fédérale de Distance (CFD)** of the [FFVL](https://www.ffvl.fr), for both paragliders
(`parapente.ffvl.fr`) and hang gliders (`delta.ffvl.fr`), and builds a catalogue.

**Pre-processing** (`soaring.analysis.preproc`, `soaring.analysis.igc`) turns raw tracklogs
into analysis-ready trajectories: the altitude channel, fix-level cleaning, trimming,
flight-level filtering, the ENU conversion, resampling onto each flight's own cadence, and
Savitzky--Golay smoothing. Seven stages, driven by `scripts/preprocess.py` into four Parquet
tables on the SSD.

**Analysis** (`soaring.analysis.observables`, `soaring.analysis.stats`) holds the transport
estimators — the two mean-squared-displacement averages, the filtered variations, the moment
spectrum, the velocity autocorrelation, the increment propagator, the regime fitting and the
clustered bootstrap — together with the synthetic processes each one is validated against.
Numerical simulation of a transport model is the next sub-package and does not exist yet.

## What it does, in brief

For each season it downloads the CFD XML export, extracts flight metadata, and downloads the
`.igc` GPS tracklogs, organising them on an external SSD. It also builds a **CSV catalog**
linking each flight to its file and its URLs.

| Source | Seasons | Flights | With GPS | CLI |
|--------|---------|---------|----------|-----|
| Paragliders | 1999–2025 | ~203,000 | ~186,000 | `soaring-para` |
| Hang gliders | 2001–2025 | ~9,300 | ~6,750 | `soaring-delta` |

## Quick start

```bash
# 1. environment (see Guide → Installation)
uv sync

# 2. set the destination in the config or via env var (see Guide → Downloading)
export SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc
export SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc

# 3. archive the XMLs, download a test season, build the catalog
uv run soaring-para fetch-xml --seasons 1999
uv run soaring-para download  --seasons 1999
uv run soaring-para build-catalog
uv run soaring-para status
```

## How it is organised

- **Code** (this repo): the installable package `soaring` (see
  [API Reference](reference.md)), and the command-line entry points under `scripts/` that
  drive it (see [The scripts](guide/scripts.md)).
- **Data** (on the SSD, `data_root`): the flight archive is never in the repo. What the
  repository does version is in `data/` -- the two per-season summary CSVs and the basemap
  the take-off maps are drawn on, so the figures need neither network nor disk.
  The layout groups by maturity — `raw/` is untouched acquisition output, `catalog/` the
  tables derived from it, `derived/` everything the pipeline writes. What each file holds,
  column by column, is [What is on the SSD](guide/data-on-disk.md).
- **Intermediate analysis arrays**: neither in the repo nor on the SSD. The streaming passes
  write them to `$TMPDIR/soaring-audit` by default, about 350 MB for both disciplines, and
  they are reproducible by re-running the pass.

```text
/Volumes/SSD_DISANTE/
├── paragliders/ffvl_cfd_igc/
│   ├── raw/
│   │   ├── raw_xml/1999.xml …        # archived XML exports (provenance)
│   │   └── igc/1999-2000/….igc       # tracks, one directory per season
│   ├── catalog/
│   │   ├── catalog.csv               # 1 row/flight: metadata + local_path
│   │   └── seasons_index.csv         # 1 row/season: links + counts
│   ├── derived/
│   │   ├── track_scan.parquet        # raw-archive scan cache (pre-cleaning)
│   │   ├── fixes.parquet             # the processed trajectories
│   │   ├── segments.parquet          # one row per segment, retained or not
│   │   ├── flights_meta.parquet      # one row per flight attempted
│   │   └── suspect_intervals.parquet
│   └── logs/
└── hang_gliders/delta_cfd_igc/
    ├── raw/
    │   ├── raw_xml/2001.xml …
    │   └── igc/2001-2002/….igc
    ├── catalog/
    │   ├── catalog.csv
    │   └── seasons_index.csv
    ├── derived/
    │   ├── track_scan.parquet
    │   ├── fixes.parquet
    │   ├── segments.parquet
    │   ├── flights_meta.parquet
    │   └── suspect_intervals.parquet
    └── logs/
```

## Thesis document

The repository also hosts `thesis/`, a LaTeX *state-of-the-work* document. It is not what
this documentation is about --- these pages describe the code and the data disk --- but two
things about it constrain the code and belong here.

Every number the document quotes comes through a generated macro that a script in
`scripts/reporting/` writes into `thesis/generated/`. Nothing is typed. A macro quoted and
never written is a fatal LaTeX error, so `scripts/reporting/check_generated_macros.py` reads
both sides of that contract in a second and with no build. `regenerate.sh` runs it as step 15,
before the rebuild; `build_docs.sh thesis`, which only recompiles, does not.

`scripts/regenerate.sh` rebuilds everything that descends from the processed dataset, in the
one order that is correct, and the compiled `thesis/main.pdf` is kept in the repository.

Continue with the **[Guide](guide/installation.md)**, the **[API Reference](reference.md)**,
or **[The scripts](guide/scripts.md)** for what each entry point reads and writes.
