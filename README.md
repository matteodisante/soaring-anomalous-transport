# soaring-anomalous-transport

[![python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![Tests](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml/badge.svg)](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/matteodisante/soaring-anomalous-transport/branch/main/graph/badge.svg)](https://codecov.io/gh/matteodisante/soaring-anomalous-transport)
[![docs](https://img.shields.io/badge/docs-online-brightgreen)](https://matteodisante.github.io/soaring-anomalous-transport/)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Code for the master's thesis **_anomalous transport in soaring flights_**.

The repository holds three subsystems, in the order the data moves through them.

**Acquisition** (`soaring.acquisition.ffvl`) — `.igc` tracks from the **Coupe Fédérale de
Distance (CFD)** of the [FFVL](https://federation.ffvl.fr), for two glider types:

| Source | Glider | CLI | Env var |
|--------|--------|-----|---------|
| [parapente.ffvl.fr](https://parapente.ffvl.fr/cfd/liste) | Paragliders | `soaring-para` | `SOARING_PARA_DATA_ROOT` |
| [delta.ffvl.fr](https://delta.ffvl.fr/cfd/liste) | Hang gliders | `soaring-delta` | `SOARING_DELTA_DATA_ROOT` |

**Pre-processing** (`soaring.analysis.preproc`) — the seven-stage cleaning pipeline:
altitude-channel choice, cleaning, trimming, flight-level filtering, projection to a local
ENU frame, resampling, and Savitzky–Golay smoothing. It turns the raw archive into four
Parquet tables per discipline. See [the pipeline guide](docs/guide/preprocessing-pipeline.md).

**Analysis** (`soaring.analysis.observables`, `soaring.analysis.stats`) — the transport
estimators: mean-square displacement and its time-averaged counterpart, filtered variations,
the moment spectrum, persistence runs, the increment propagator, regime detection, synthetic
null processes, and the clustered bootstrap.

📖 **Documentation:** <https://matteodisante.github.io/soaring-anomalous-transport/>

## Quick start

Python 3.12 or newer.

```bash
uv sync                                        # environment + dependencies
```

### 1. Acquire

```bash
# --- Paragliders (parapente.ffvl.fr, seasons 1999–2025) ---
export SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc
uv run soaring-para fetch-xml --seasons 1999  # archive the XMLs
uv run soaring-para download  --seasons 1999  # download .igc files (resumable)
uv run soaring-para build-catalog             # catalog.csv + seasons_index.csv
uv run soaring-para status                    # per-season summary
uv run soaring-para verify                    # integrity check of .igc files
uv run soaring-para clean                     # remove '._*' sidecars (macOS/exFAT)

# --- Hang gliders (delta.ffvl.fr, seasons 2001–2025) ---
export SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc
uv run soaring-delta fetch-xml --seasons all
uv run soaring-delta download  --seasons all
uv run soaring-delta build-catalog
uv run soaring-delta status
```

`--seasons` accepts `all`, a single year (`2014`), a range (`2010-2015`), or a list (`2010,2012`).

### 2. Pre-process

```bash
uv run python scripts/preprocess.py            # --discipline, --jobs, --limit, --seed
uv run python scripts/verify_dataset.py        # invariants the thesis claims for the tables
uv run python scripts/check_reproducible.py    # re-runs a seeded sample through the pipeline
```

### 3. Regenerate the analysis

```bash
scripts/regenerate.sh                          # 16 steps: passes, reductions, macros, figures
```

The order is a constraint rather than a convenience, and the script's header says why.
[The scripts guide](docs/guide/scripts.md) explains what each one reads and writes, and why
the expensive streaming passes are kept separate from the cheap reductions.

## Where the data goes

The flight archive is **not** in the repo; it lives in `data_root` on the external SSD. What
the repository does keep is in [`data/`](data/): the two per-season summary CSVs and the
basemap the take-off maps are drawn on, so the figures need no network and no disk.

Each source has its own directory, grouped by maturity — `raw/` (untouched acquisition
output), `catalog/` (tables derived from it), `derived/` (the analysis dataset):

```text
/Volumes/SSD_DISANTE/
├── paragliders/ffvl_cfd_igc/
│   ├── raw/
│   │   ├── raw_xml/1999.xml …        # archived XML exports (provenance)
│   │   └── igc/1999-2000/….igc       # tracks, one subdirectory per season
│   ├── catalog/
│   │   ├── catalog.csv               # 1 row/flight: metadata + local_path
│   │   └── seasons_index.csv
│   ├── derived/
│   │   ├── fixes.parquet             # 1,363,998,292 rows, 43.4 GB — the cleaned fixes
│   │   ├── segments.parquet          #   281,777 rows — contiguous stretches within a flight
│   │   ├── flights_meta.parquet      #   186,052 rows — one per flight, post-filter
│   │   ├── suspect_intervals.parquet #       859 rows — slow-and-flat stints, left open
│   │   └── track_scan.parquet        #   186,025 rows — pre-processing scan cache
│   └── logs/
└── hang_gliders/delta_cfd_igc/       # same layout: 34,525,108 fixes, 13,222 segments,
    …                                 # 6716 flights, 12 suspect intervals
```

Row counts measured from the Parquet footers on the current archive.

`.igc` filename scheme: **`{date}_{flightID}.igc`**. The `flightID` opens the flight page
directly (paragliders: `https://parapente.ffvl.fr/cfd/liste/vol/{flightID}`; hang gliders:
`https://delta.ffvl.fr/cfd/liste/vol/{flightID}`), so any file can be traced back without a
lookup dictionary (details: [From the .igc file to the flight](docs/guide/igc-to-flight.md)).

A description of every table, column and dtype is in
[what is on the data disk](docs/guide/data-on-disk.md), and `write_ssd_readme.py` puts a copy
at the root of the disk so it explains itself when it is not plugged into this repository.

## Documentation

Guides + API Reference (auto-generated from docstrings) are published at
**<https://matteodisante.github.io/soaring-anomalous-transport/>**.

MkDocs is an optional extra rather than a default dependency, so preview it with:

```bash
uv run --extra docs mkdocs serve   # http://127.0.0.1:8000
```

## Thesis document

[`thesis/`](thesis/) is the LaTeX thesis: acquisition method, dataset description, global
transport, and next steps. Every number it quotes is a generated macro rather than a typed
one — `thesis/generated/` holds fourteen `.tex` files, of which `stats.tex` and the two
season tables descend from the snapshots in [`data/`](data/) and the other eleven from the
processed tables on the SSD, by way of `scripts/regenerate.sh`. The compiled
`thesis/main.pdf` is kept in the repo.

```bash
scripts/regenerate.sh            # re-measure everything, then rebuild
scripts/build_docs.sh thesis     # recompile only, from the macros already generated
```

`scripts/reporting/check_generated_macros.py` reads both sides of that contract in a second
and with no build, which matters because a macro quoted and never written is a fatal LaTeX
error diagnosed from a symptom that names the wrong line.

A pre-commit hook keeps the stats and the PDF in sync on every commit — enable it once
with `git config core.hooksPath .githooks`. A working **logbook** (`logbook/`) tracks the
chronology and the reasoning; its timeline is auto-generated from the git history by the
same pre-commit hook.

License: MIT.
