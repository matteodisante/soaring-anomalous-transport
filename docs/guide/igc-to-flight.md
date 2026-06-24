# Dal file `.igc` al volo

Requisito centrale: dato un file `.igc`, risalire a *quale volo* è e ai suoi link. Qui non
serve un dizionario fragile — l'informazione è già nel **nome del file** e negli **XML
archiviati**.

## 1. Il nome del file è auto-descrittivo

Schema: **`{date}_{flightID}.igc`**, es. `2000-00-00_20150770.igc`.

Il `flightID` è la chiave univoca del volo e apre *sempre* la sua pagina:

```text
2000-00-00_20150770.igc   →   flight_id = 20150770
                          →   https://parapente.ffvl.fr/cfd/liste/vol/20150770
```

In codice:

```python
from soaring.acquisition.ffvl.naming import parse_igc_filename
from soaring.acquisition.ffvl.seasons import flight_page_url

date, flight_id = parse_igc_filename("2000-00-00_20150770.igc")
print(flight_page_url(flight_id))   # → .../cfd/liste/vol/20150770
```

## 2. Metadati completi: il catalogo

Per i metadati (pilota, distanza, decollo/atterraggio, durata, …) c'è `catalog.csv`, una
riga per volo, **rigenerabile** in ogni momento dagli XML con `build-catalog`. Include la
colonna `local_path` che collega il volo al file fisico su disco.

```python
import pandas as pd
cat = pd.read_csv("/Volumes/HDD_DISANTE/ffvl_cfd_igc/catalog.csv")

# dal flight_id alla riga completa
row = cat.loc[cat.flight_id == 20150770].iloc[0]
print(row.pilot, row.distance_km, row.takeoff, row.flight_link)

# selezione per l'analisi + path dei file da aprire
voli = cat[(cat.downloaded) & (cat.distance_km > 50)]
for p in voli.local_path:
    ...  # apri il .igc e analizzalo
```

!!! info "Fonte di verità vs derivato"
    La **fonte di verità** è la coppia *[nomi file] + [XML archiviati in `raw_xml/`]*.
    Il `catalog.csv` è un **derivato comodo**: se lo cancelli, lo ricrei con `build-catalog`.

Colonne del catalogo e logica di costruzione: `soaring.acquisition.ffvl.catalog`
(vedi [Reference API](../reference.md)).
