# soaring-anomalous-transport

Code for the master's thesis **_anomalous transport in soaring flights_**.

Thesis monorepo: currently contains the **acquisition of** `.igc` **flight data** from the
**Coupe Fédérale de Distance (CFD)** of the [FFVL](https://www.ffvl.fr), covering both
paragliders (`parapente.ffvl.fr`) and hang gliders (`delta.ffvl.fr`).
Data analyses and numerical simulations will be added in the future as further
sub-packages of `soaring`.

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
uv sync --all-extras

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

- **Code** (this repo): installable package `soaring`, under
  `soaring.acquisition.ffvl` (see [API Reference](reference.md)).
- **Raw data** (on the SSD, `data_root`): never in the repo.

```text
/Volumes/SSD_DISANTE/
├── paragliders/ffvl_cfd_igc/
│   ├── raw_xml/1999.xml …            # archived XML exports (provenance)
│   ├── igc/1999-2000/….igc           # tracks, one directory per season
│   ├── catalog.csv                   # 1 row/flight: metadata + local_path
│   └── seasons_index.csv             # 1 row/season: links + counts
└── hang_gliders/delta_cfd_igc/
    ├── raw_xml/2001.xml …
    ├── igc/2001-2002/….igc
    ├── catalog.csv
    └── seasons_index.csv
```

## Thesis document

The repository also hosts `thesis/`, a LaTeX *state-of-the-work* document describing the
acquisition method, the dataset, its statistics, and the next steps. Its statistics are
generated automatically from `data/seasons_index.csv` and the compiled `thesis/main.pdf`
is kept in the repository.

Continue with the **[Guide](guide/installation.md)** or consult the **[API Reference](reference.md)**.
