# SSD: significato dei 124 array collegati

**Stato aggiornato:** pulizia autorizzata dall'utente a condizione di preservare
il viewer ed eseguita il 17 settembre 2026. Vedere `SSD-PULIZIA-ESITO.md` e i
manifest `SSD-PULIZIA-ESECUZIONE.json` / `SSD-PULIZIA-SUPPLEMENTO.json`.
I 124 array di incrementi/proprietari e i relativi link locali sono stati ritirati.
La PCA ha ora un comando indipendente verificato sulle coordinate conservate.

Il testo seguente conserva l'audit **precedente alla cancellazione**; i riferimenti
a file ancora presenti o a una pulizia futura descrivono quello stato storico.

## Che cosa è collegato

Il recupero locale `../vertical-gap-split-2026-09-11/recovery-runs/20260912T104500Z-5cfc4e8c/arrays/`
contiene link simbolici verso file del run SSD `20260911T213634Z-7b7367f1`.
Un link è un riferimento al file SSD, non una seconda copia dei suoi dati.
Sono stati verificati 124 link principali e l'esistenza dei rispettivi file:

| File | Numero | Dimensione logica | Contenuto |
|---|---:|---:|---|
| `vectors-*.bin` | 62 | 8.380 GiB | Incrementi E/N: 31 lag per due discipline |
| `owners-*.bin` | 62 | 2.095 GiB | Indice del volo proprietario di ciascun incremento |
| totale | 124 | 10.475 GiB | Cache delle analisi di trasporto |

Il fatto che il run generale sia fallito non rende inutili gli stadi già terminati.
L'errore storico è una disconnessione SSD durante `transport_full`.

## A cosa servono effettivamente

`src/soaring/analysis/observables/archive_diagnostics.py:load_measurement`
apre queste matrici per lag insieme ai riepiloghi numerici. Il reporter
`scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py`
usa quel caricatore nella modalità `--reuse` per gli studi di trasporto:
quantili e controlli di popolazione, forme delle distribuzioni, momenti,
diagnostiche direzionali e relativi prodotti. La compilazione LaTeX, invece,
legge le figure e tabelle già generate e non apre queste matrici.

Gli incrementi sono differenze di coordinate calcolate da `_flight_measure`;
gli owner sono assegnati da `measure_archive`. Non sono nuove osservazioni
irripetibili. Si possono ricostruire da coordinate, identità dei segmenti,
griglia dei lag e codice originale. `positions.bin`, `flights.json`,
`measurement.pkl` e `counts.json` sono presenti come file regolari, non symlink,
per entrambe le discipline nel recupero locale. Non è stato eseguito qui
un ricalcolo completo né un nuovo confronto byte per byte di tutti gli array.

Quindi questi 10.475 GiB preservano soprattutto il lavoro computazionale e la
possibilità di riaprire subito le vecchie analisi. Eliminandoli senza aggiornare
il caricatore, `--reuse` fallirebbe; tenere soltanto i PDF non conserverebbe quella
possibilità di ricalcolo. Un futuro caricamento dai riepiloghi può ridurre alcune
dipendenze, ma deve essere implementato e verificato prima del ritiro dei file.

## Capitolo 2 e dati condivisi

La ricerca dei consumatori nei reporter del capitolo 2 non ha trovato letture
dirette dei 124 `vectors/owners`. Quel capitolo dipende però da altri dati nello
stesso archivio e in parte nella stessa cartella di audit. In particolare il
reporter preliminare usa `audit_flights_*.parquet` e `audit_positions_*.npz`;
il resto della catena documenta grezzi, pulizia, trimming, metadati e cache di
diagnostica. Una cancellazione dell'intera cartella può rimuovere anche tali input.

Vincolo prioritario dell'utente: preservare il lavoro del capitolo 2, inclusa la
possibilità di rigenerarlo; conservare possibilmente anche i dati che alimentano
le figure del volume esperimenti. Non eliminare grezzi, cataloghi, traiettorie
pulite, metadati, cache uniche, fonti, risultati numerici e provenienza di quel
capitolo per recuperare spazio da questa analisi.

## Ordine della pulizia futura

**Aggiornamento successivo del 17 settembre:** l'utente sta valutando di ritirare
tutti gli intermedi SSD degli esperimenti salvo PCA/anisotropia. Resta il vincolo
di preservare capitolo 2, raw, pulizia e segmentazione. Il codice PCA corrente
(`regional_pca.py`) usa direttamente coordinate e metadati, senza vectors/owners;
è il caricatore generale `load_measurement` che ne impone oggi l'apertura.
La separazione di questi caricamenti permetterebbe di rimuovere tali matrici
conservando la rigenerazione dei risultati direzionali.

Il preventivo attuale `SSD-PULIZIA-PREVENTIVO.json` censisce 142 candidati:
12.613 GiB allocati. Spazio libero rilevato: 25.327 GiB; dopo il ritiro dei
candidati, circa 37.939 GiB a parità delle altre scritture. I file NON sono stati
cancellati. Le diagnostiche capitolo 2, le coordinate PCA, gli audit cinemativi,
la segmentazione e gli input ambientali sono fuori da questa lista.

L'elenco seguente descriveva la proposta precedente di pulizia progressiva;
il nuovo intento estende il ritiro anche agli esperimenti non trasferiti,
preservandone nel repository risultati finali, codice e provenienza.

1. Riconfermare le copie reali identiche, precedentemente censite per circa
   4.24 GiB, e le dipendenze prima di eliminare una delle copie. Un link non conta
   come copia indipendente. Conservare un registro dei percorsi sostitutivi.
2. Dopo ciascuna sezione nuova validata, individuare intermedi esclusivamente
   superati. Controllare anche le sezioni di esperimenti che non verranno trasferite.
3. Per le grandi matrici di incrementi, preservare gli input e il percorso di
   riproduzione; preferire il riuso o la rigenerazione per lag agli accumuli di
   molte copie persistenti. Ritirarle solo quando i consumatori rimasti sono
   coperti da una soluzione verificata.
4. Conservare i manifest storici anche se i relativi intermedi vengono ritirati.

Riferimenti dell'audit precedente: `ssd-space-review.md`,
`ssd-duplicate-verification.json`, `ssd-protected-live-arrays.json` nella revisione
`vertical-gap-split-2026-09-11`. Sono evidenze datate da aggiornare prima di cancellare,
non un'autorizzazione a cancellare intere directory.
