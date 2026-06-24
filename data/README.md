# data/

Qui sta **solo** un piccolo artefatto versionabile:

- `seasons_index.csv` — una riga per stagione con i link (lista + export XML) e i conteggi
  (voli totali, con traccia, scaricati). Generato/aggiornato da `soaring-ffvl build-catalog`
  e copiato qui come riferimento rapido.

I **dati grezzi** (file `.igc`, XML archiviati, catalogo completo) **non** stanno nel repo:
vivono in `data_root` sull'HDD esterno (vedi `configs/ffvl_download.yaml`). Sono ~65 GB e
sono esclusi via `.gitignore`.
