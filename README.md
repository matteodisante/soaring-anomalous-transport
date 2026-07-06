# soaring-anomalous-transport

Code for the master's thesis **_anomalous transport in soaring flights_**.

Thesis monorepo. Currently contains the **acquisition of** `.igc` **flight data** from the
**Coupe Fédérale de Distance (CFD)** of the [FFVL](https://www.ffvl.fr), covering two glider
types via the package `soaring.acquisition.ffvl`:

| Source | Glider | CLI | Env var |
|--------|--------|-----|---------|
| [parapente.ffvl.fr](https://parapente.ffvl.fr/cfd/liste) | Paragliders | `soaring-para` | `SOARING_PARA_DATA_ROOT` |
| [delta.ffvl.fr](https://delta.ffvl.fr/cfd/liste) | Hang gliders | `soaring-delta` | `SOARING_DELTA_DATA_ROOT` |

Analyses and simulations will be added as further sub-packages of `soaring`.

📖 **Documentation:** <https://matteodisante.github.io/soaring-anomalous-transport/>

## Quick start

```bash
uv sync --all-extras                          # environment + dependencies

# --- Paragliders (parapente.ffvl.fr, seasons 1999–2025) ---
export SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc
uv run soaring-para fetch-xml --seasons 1999  # archive the XMLs
uv run soaring-para download  --seasons 1999  # download .igc files (resumable)
uv run soaring-para build-catalog             # catalog.csv + seasons_index.csv
uv run soaring-para status                    # per-season summary
uv run soaring-para verify                    # integrity check of .igc files

# --- Hang gliders (delta.ffvl.fr, seasons 2001–2025) ---
export SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc
uv run soaring-delta fetch-xml --seasons all
uv run soaring-delta download  --seasons all
uv run soaring-delta build-catalog
uv run soaring-delta status
```

`--seasons` accepts `all`, a single year (`2014`), a range (`2010-2015`), or a list (`2010,2012`).

## Where the data goes

Raw data is **not** stored in the repo; it lives in `data_root` on the external SSD, and
nothing is ever kept locally instead. Each source has its own directory, grouped by
maturity -- `raw/` (untouched acquisition output), `catalog/` (tables derived from it),
`derived/` (further analysis byproducts, e.g. the pre-processing scan cache); future
cleaned/filtered data and analysis results will follow the same pattern:

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
│   │   └── track_scan.parquet        # pre-processing scan cache (duration, path length, …)
│   └── logs/
└── hang_gliders/delta_cfd_igc/
    ├── raw/
    │   ├── raw_xml/2001.xml …
    │   └── igc/2001-2002/….igc
    ├── catalog/
    │   ├── catalog.csv
    │   └── seasons_index.csv
    ├── derived/
    │   └── track_scan.parquet
    └── logs/
```

`.igc` filename scheme: **`{date}_{flightID}.igc`**. The `flightID` opens the flight page
directly (paragliders: `https://parapente.ffvl.fr/cfd/liste/vol/{flightID}`; hang gliders:
`https://delta.ffvl.fr/cfd/liste/vol/{flightID}`), so any file can be traced back without a
lookup dictionary (details: [From the .igc file to the flight](docs/guide/igc-to-flight.md)).

## Documentation

Guides + API Reference (auto-generated from docstrings) are published at
**<https://matteodisante.github.io/soaring-anomalous-transport/>**.

To preview locally:

```bash
uv run mkdocs serve   # http://127.0.0.1:8000
```

## Thesis document

[`thesis/`](thesis/) is the LaTeX **state-of-the-work document** (set up as a master's
thesis): acquisition method, dataset description, statistics, and next steps. Its
quantitative parts (`thesis/generated/`) are auto-generated from the per-discipline
season indices in [`data/`](data/); the compiled `thesis/main.pdf` is kept in the repo.

```bash
scripts/build_docs.sh thesis   # regenerate stats + compile thesis/main.pdf
```

A pre-commit hook keeps the stats and the PDF in sync on every commit — enable it once
with `git config core.hooksPath .githooks`. The narrative prose is updated on demand.
A private working **logbook** (`logbook/`, git-ignored) tracks the chronology and the
reasoning; it is never published.

License: MIT.
