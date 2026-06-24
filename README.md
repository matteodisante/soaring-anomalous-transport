# soaring-anomalous-transport

Codice della tesi magistrale **_anomalous transport in soaring flights_**.

Monorepo della tesi. Oggi contiene l'**acquisizione dei dati** di volo `.igc` dalla
**Coupe Fédérale de Distance (CFD)** della [FFVL](https://parapente.ffvl.fr/cfd/liste)
(pacchetto `soaring.acquisition.ffvl`). Analisi e simulazioni verranno aggiunte come
ulteriori sotto-pacchetti di `soaring`.

## Quick start

```bash
uv sync --all-extras                          # ambiente + dipendenze
# imposta data_root (HDD esterno) in configs/ffvl_download.yaml
uv run soaring-ffvl fetch-xml --seasons 1999  # archivia gli XML
uv run soaring-ffvl download  --seasons 1999  # scarica i .igc (resumibile)
uv run soaring-ffvl build-catalog             # catalog.csv + seasons_index.csv
uv run soaring-ffvl status                    # riepilogo per stagione
```

`--seasons` accetta `all`, un anno (`2014`), un intervallo (`2010-2015`) o un elenco (`2010,2012`).

## Dove finiscono i dati

I dati grezzi (~65 GB) **non** stanno nel repo ma in `data_root`, sull'HDD esterno:

```text
<data_root>/
├── raw_xml/1999.xml …       # export XML archiviati (provenienza)
├── igc/1999-2000/…igc       # tracciati, una sottocartella per stagione
├── catalog.csv              # 1 riga/volo: metadati + local_path
└── seasons_index.csv        # 1 riga/stagione: link + conteggi
```

Nome file `.igc`: **`{date}_{flightID}.igc`**. Il `flightID` apre sempre la pagina del volo
`https://parapente.ffvl.fr/cfd/liste/vol/{flightID}`, quindi dal file si risale al volo senza
dizionari (dettagli: [Dal file .igc al volo](docs/guide/igc-to-flight.md)).

## Documentazione

Guide + Reference API auto-generata dai docstring:

```bash
uv run mkdocs serve   # http://127.0.0.1:8000
```

## Sviluppo

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run mkdocs build --strict
```

Struttura: `src/soaring/acquisition/ffvl/` (codice), `configs/` (config YAML), `docs/`
(documentazione), `tests/` (test offline su fixture). Licenza: MIT.
