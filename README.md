# soaring-anomalous-transport

Code for the master's thesis **_anomalous transport in soaring flights_**.

Thesis monorepo. Currently contains the **acquisition of** `.igc` **flight data** from the
**Coupe Fédérale de Distance (CFD)** of the [FFVL](https://parapente.ffvl.fr/cfd/liste)
(package `soaring.acquisition.ffvl`). Analyses and simulations will be added as further
sub-packages of `soaring`.

📖 **Documentation:** <https://matteodisante.github.io/soaring-anomalous-transport/>

## Quick start

```bash
uv sync --all-extras                          # environment + dependencies
# REQUIRED: point data_root to your mounted external disk (the config ships a placeholder)
export SOARING_FFVL_DATA_ROOT=/Volumes/<YOUR_DISK>/ffvl_cfd_igc
uv run soaring-ffvl fetch-xml --seasons 1999  # archive the XMLs
uv run soaring-ffvl download  --seasons 1999  # download the .igc files (resumable)
uv run soaring-ffvl build-catalog             # catalog.csv + seasons_index.csv
uv run soaring-ffvl status                    # per-season summary
uv run soaring-ffvl verify                    # integrity check of the .igc files
```

`--seasons` accepts `all`, a single year (`2014`), a range (`2010-2015`), or a list (`2010,2012`).

## Where the data goes

The raw data (~65 GB) is **not** stored in the repo but in `data_root`, on the external HDD:

```text
<data_root>/
├── raw_xml/1999.xml …       # archived XML exports (provenance)
├── igc/1999-2000/…igc       # tracks, one subdirectory per season
├── catalog.csv              # 1 row/flight: metadata + local_path
└── seasons_index.csv        # 1 row/season: links + counts
```

`.igc` filename: **`{date}_{flightID}.igc`**. The `flightID` always opens the flight page at
`https://parapente.ffvl.fr/cfd/liste/vol/{flightID}`, so the flight can be traced from the
file without any lookup dictionary (details: [From the .igc file to the flight](docs/guide/igc-to-flight.md)).

## Documentation

Guides + API Reference (auto-generated from docstrings) are published at
**<https://matteodisante.github.io/soaring-anomalous-transport/>**.

To preview locally:

```bash
uv run mkdocs serve   # http://127.0.0.1:8000
```

License: MIT.
