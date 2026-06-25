# soaring-anomalous-transport

Code for the master's thesis **_anomalous transport in soaring flights_**.

Thesis monorepo: currently contains the **acquisition of** `.igc` **flight data** from the
**Coupe Fédérale de Distance (CFD)** of the [FFVL](https://parapente.ffvl.fr/cfd/liste).
Data analyses and numerical simulations will be added in the future as further
sub-packages of `soaring`.

## What it does, in brief

For each season (1999-2000 → 2025-2026) it downloads the CFD XML export, extracts the
metadata for **~203,000 flights** (~186,000 with a GPS track), and downloads the `.igc`
files, organising them by season on an external HDD. It also builds a **CSV catalog** that
links each flight to its file and its URLs.

## Quick start

```bash
# 1. environment (see Guide → Installation)
uv sync --all-extras

# 2. set the HDD destination in configs/ffvl_download.yaml (data_root)

# 3. archive the XMLs, download a test season, build the catalog
uv run soaring-ffvl fetch-xml --seasons 1999
uv run soaring-ffvl download  --seasons 1999
uv run soaring-ffvl build-catalog
uv run soaring-ffvl status
```

## How it is organised

- **Code** (this repo): installable package `soaring`, under
  `soaring.acquisition.ffvl` (see [API Reference](reference.md)).
- **Raw data** (on the HDD, `data_root`): never in the repo.

```text
<data_root>/
├── raw_xml/1999.xml …            # archived XML exports (provenance)
├── igc/1999-2000/…igc            # tracks, one directory per season
├── catalog.csv                   # 1 row/flight: metadata + local_path
└── seasons_index.csv             # 1 row/season: links + counts
```

Continue with the **[Guide](guide/installation.md)** or consult the **[API Reference](reference.md)**.
