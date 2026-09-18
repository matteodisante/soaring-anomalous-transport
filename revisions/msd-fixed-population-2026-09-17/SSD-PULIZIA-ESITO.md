# Pulizia SSD — esito del 17 settembre 2026

Pulizia completata su autorizzazione dell'utente, subordinata alla conservazione
integrale del viewer. Rimossi **12.854 GiB allocati**; spazio libero alla
verifica finale: **35.747 GiB**. Le misure del preventivo sono precedenti:
lo spazio libero è cambiato anche prima della cancellazione.

## Rimossi

- 146 file: incrementi `vectors-*`, indici `owners-*`, `scaling-values-*`, vecchie
  curve MSD e cache generali di variazioni, propagatori, forma e campione storico.
- 146 file AppleDouble associati (`._*`).
- 248 collegamenti locali diretti ai file ritirati, di cui 124 principali.

Ogni percorso eliminato ha dimensioni, data e SHA-256 registrati nei manifest
`SSD-PULIZIA-ESECUZIONE.json` e `SSD-PULIZIA-SUPPLEMENTO.json`. Nessuna directory
è stata cancellata in blocco. I processi aperti sono stati controllati prima
di ciascuna rimozione.

## Conservati

Raw IGC e cataloghi; dati puliti, metadati, trimming e segmentazione; modelli HMM
e configurazioni Vilpellet; tutti i database e le immagini del viewer; input e
diagnostiche del capitolo 2. Restano anche coordinate e indici dei segmenti,
audit cinematici, input ambientali e riepiloghi necessari per PCA e anisotropia.
I 1199 file protetti rimanenti hanno identità, dimensioni e mtime invariati.

`derived-audit` conserva dati condivisi con capitolo 2 e PCA/anisotropia,
riproducibilità e risultati storici: non va eliminato in blocco. Il vecchio
campione del run del 10 settembre conserva anche il suo materiale PCA; i
riepiloghi misti restano integri. Figure, tabelle e PDF della tesi e di
`esperimenti` non sono stati eliminati o rigenerati durante questa pulizia.

## Verifica del viewer

- 117 test passati prima e 117 dopo: selettore e filtri, mappe, navigazione,
  grafici, segmentazioni, termiche, confronto giornaliero e controlli Qt.
- Dati reali: 8 voli delle due discipline; raw, pulizia e risultati di entrambe
  le segmentazioni identici prima/dopo, inclusi casi senza fasi classificate.
- Cataloghi, menu dei filtri e punti della mappa identici prima/dopo.
- GUI Qt con dati reali: coordinate geografiche/ENU, 2D/3D, HMM/Vilpellet,
  confronto affiancato, sole termiche, zoom/reset ed esportazione PDF.
- Tutte le 12 celle termiche, entrambe le segmentazioni e le fasce orarie
  giornaliere: risultati identici prima/dopo. Verificate 39 immagini di sfondo.
- Database termico integro, nessun prodotto mancante; SHA-256 dell'intero
  database identico prima/dopo.
- Le verifiche reali bloccano esplicitamente l'apertura delle cache candidate:
  nessuna funzione verificata ne ha richiesto la lettura. Il codice del viewer
  non è stato modificato. Le finestre Qt sono state esercitate fuori schermo.

I risultati completi sono in `viewer-before.json`, `viewer-after.json` e
`SSD-PULIZIA-VERIFICA.json`. Il confronto integrale dei due JSON è identico.

## PCA e analisi precedenti

La PCA è stata ricalcolata dalle coordinate conservate **anche dopo la
cancellazione**, su 155085 parapendii e 6060 deltaplani. Tutti i 23 risultati
regione–lag coincidono con il riferimento entro tolleranza relativa/assoluta
1e-12. Passati anche 12 test PCA/isotropia.

Comando indipendente dalle cache eliminate:

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/generate_regional_pca.py \
  --audit-dir /Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1/arrays \
  --output-dir output/regional-pca
```

La modalità generale `generate_revision_diagnostics.py --reuse` non può riaprire
le vecchie cache di trasporto rimosse: per quelle analisi servirà ricalcolarle.
Il comando PCA dedicato, il viewer e la compilazione dei documenti esistenti
restano indipendenti da tali cache. I manifest storici descrivono le esecuzioni
originarie e non vengono riscritti come se i file fossero ancora presenti.
