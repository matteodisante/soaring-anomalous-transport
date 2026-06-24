# soaring-anomalous-transport

Codice della tesi magistrale **_anomalous transport in soaring flights_**.

Monorepo della tesi: oggi contiene l'**acquisizione dei dati** di volo `.igc` dalla
**Coupe Fédérale de Distance (CFD)** della [FFVL](https://parapente.ffvl.fr/cfd/liste).
Analisi dati e simulazioni numeriche verranno aggiunte in futuro come ulteriori
sotto-pacchetti di `soaring`.

## Cosa fa, in breve

Per ogni stagione (1999-2000 → 2025-2026) scarica l'export XML della CFD, ne estrae i
metadati di **~203.000 voli** (~186.000 con traccia GPS) e scarica i file `.igc`,
organizzandoli per stagione su un HDD esterno. Costruisce inoltre un **catalogo CSV** che
collega ogni volo al suo file e ai suoi link.

## Quick start

```bash
# 1. ambiente (vedi Guida → Installazione)
uv sync --all-extras

# 2. imposta la destinazione su HDD in configs/ffvl_download.yaml (data_root)

# 3. archivia gli XML, scarica una stagione di prova, costruisci il catalogo
uv run soaring-ffvl fetch-xml --seasons 1999
uv run soaring-ffvl download  --seasons 1999
uv run soaring-ffvl build-catalog
uv run soaring-ffvl status
```

## Come è organizzato

- **Codice** (questa repo): pacchetto installabile `soaring`, sotto
  `soaring.acquisition.ffvl` (vedi [Reference API](reference.md)).
- **Dati grezzi** (sull'HDD, `data_root`): mai nel repo.

```text
<data_root>/
├── raw_xml/1999.xml …            # export XML archiviati (provenienza)
├── igc/1999-2000/…igc            # tracciati, una cartella per stagione
├── catalog.csv                   # 1 riga/volo: metadati + local_path
└── seasons_index.csv             # 1 riga/stagione: link + conteggi
```

Continua con la **[Guida](guide/installation.md)** o consulta la **[Reference API](reference.md)**.
