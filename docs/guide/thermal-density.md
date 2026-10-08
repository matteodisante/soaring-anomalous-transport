# Thermal density: ore per km²

Il tab **Thermal density** del viewer mostra il tempo cumulativo trascorso nella
fase `climb` per unità di superficie orizzontale. Usa tutti gli intervalli
**disponibili nei prodotti di segmentazione preparati**, tutte le quote e le due
discipline. Non applica i filtri temporali del tab Thermal planes.

## Costruzione, passo per passo

1. **Selezione dei segmenti.** Si prendono coppie consecutive di posizioni
   appartenenti alla stessa fase `climb`, senza collegare voli diversi, cambi di
   fase, segmenti di preprocessing distinti o buchi temporali. Un punto isolato
   non ha durata e non contribuisce.
2. **Proiezione orizzontale.** Le posizioni sono espresse in Lambert-93
   (EPSG:2154), in metri. Si conserva la durata di ogni tratto, indipendentemente
   dalla sua quota o dal dislivello percorso. Non si generano intersezioni con
   piani e non si introducono fasce verticali di 10 m.
3. **Ripartizione del tempo.** La mappa ha pixel di **50 × 50 m**. Tra gli estremi
   di ogni tratto si assume moto lineare in posizione e tempo. Il tratto viene
   tagliato ai confini dei pixel; ciascun pixel riceve esattamente la frazione
   della durata trascorsa al suo interno. Anche un tratto fermo in proiezione
   orizzontale contribuisce per tutta la sua durata.
4. **Somma.** Si sommano queste durate per tutti i voli, tutte le date disponibili
   e tutte le quote. Se un volo entra nel pixel mentre è già in termica, si conta
   il suo tempo **dall'ingresso all'uscita**. Non serve che la termica inizi lì.
5. **Normalizzazione.** Si convertono i secondi in ore e si divide per l'area
   del pixel in km². L'area è quella della griglia metrica della proiezione.

Per un pixel B:

```text
D(B) = [somma dei secondi trascorsi in climb dentro B] / [3600 × area(B) in km²]
```

Equivalentemente, il numeratore è la somma, sui segmenti, dell'integrale nel tempo
dell'indicatore «la posizione orizzontale è dentro B». Il tempo entra una sola
volta: non si moltiplica la durata di un thermal per il numero di quote attraversate.

**Esempio:** 36 secondi complessivi in un pixel di 50 × 50 m corrispondono a
0,01 ore / 0,0025 km² = **4 ore/km²**. Dieci piloti che vi trascorrono ciascuno
36 secondi producono 40 ore/km², anche se stanno usando la stessa termica fisica.

Questa è una misura di **tempo di volo osservato in termica per superficie**.
Non è una probabilità di incontrare una termica, il numero di termiche fisiche,
la loro durata atmosferica o una media annuale. Frequentazione dei piloti,
scelta delle rotte e durata dei climb influenzano il risultato. Un pixel
trasparente può essere inesplorato oppure esplorato senza climb osservati.

## Popolazioni delle mappe

- **Regions:** Alps, Pyrenees, Massif Central, Channel Coast e
  Champagne-Lorraine. Sono ritagli della griglia nazionale Vilpellet di
  [Routes](route-comparison.md), allineati ai suoi pixel da 50 m: ogni pixel
  conserva esattamente i suoi secondi. La griglia nazionale legge i fix nativi
  di `fixes.parquet`, le run `climb` salvate in
  `segmentation/vilpellet/phase_segments.parquet` e le origini geografiche in
  `flights_meta.parquet`. Si collegano solo fix consecutivi della stessa run,
  con passo positivo non superiore a 1,5 volte il passo mediano del segmento:
  i buchi di registrazione non contribuiscono.
- **Cells:** le stesse dodici celle da 5 × 5 km selezionate per Thermal planes.
  Si riusano gli archi continui Vilpellet, con tempi UTC, di
  `thermal-planes.sqlite3`. Non si usano i punti di intersezione già campionati
  per quota.

La segmentazione HMM non è più mostrata.

Nelle regioni contribuiscono tutti i segmenti che attraversano il riquadro,
**anche se il decollo è fuori dalla regione**. È un cambiamento rispetto alla
precedente mappa di conteggi, che filtrava per decollo. La cornice metrica comprende
il box geografico della regione e il margine circostante, senza sovrapporre il
contorno del box. Il totale nel titolo è riferito a tutta la cornice e rimane
invariato durante lo zoom. Le cornici regionali si sovrappongono: non sommare i
loro totali per stimare un totale nazionale.

## Zoom, colori e sfondi

La rotella e gli strumenti della toolbar consentono zoom e pan. A scala regionale
il viewer aggrega blocchi di pixel adiacenti: **somma i secondi e divide per
l'area complessiva**, conservando le ore totali. Zoomando ritorna ai pixel
originali di 50 m. I 50 m sono una risoluzione spaziale scelta per la mappa,
non una suddivisione in quota e non una garanzia di accuratezza delle traiettorie.

Una sola scala logaritmica viene usata per tutte le zone e i metodi, da
0,01 ore/km² al massimo della griglia di 50 m dell'intero prodotto. Lo zoom non
cambia questi estremi; cambia l'area su cui il valore è mediato. I valori
positivi sotto 0,01 usano il colore minimo; zero rimane trasparente. L'opacità
di sfondo e densità è regolabile separatamente.

Gli sfondi usano gli **stessi layer di Thermal planes**: Plan IGN, BD ORTHO,
Plan IGN con curve di livello ed Esri World Hillshade. Le immagini già salvate
per le celle vengono riutilizzate quando coprono la vista alla risoluzione
necessaria. Negli altri casi viene richiesta la vista attuale in Lambert-93,
alla risoluzione dello schermo, fino a 2048 pixel per lato e 1,25 m/pixel.
Le richieste sono asincrone; dopo zoom o pan si attende una breve pausa prima
di scaricare il nuovo dettaglio. I risultati relativi a viste superate vengono
scartati. I parametri di estensione e dimensione sono quelli del servizio
[WMS Raster IGN](https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/diffusion/wms-raster/).

Le nuove viste regionali richiedono internet. Le viste nella cache e gli sfondi
salvati delle celle funzionano offline. La cache dedicata `density-maps/` è
limitata a **512 MiB**; le risposte meno recentemente usate vengono eliminate.
Non si eliminano gli altri dati dell'SSD. In caso di errore rimane l'eventuale
immagine precedente, con segnalazione nella barra di stato. La copertura IGN
all'estero è parziale; le date delle ortofoto non coincidono con quelle dei voli.

## Preparazione e costi misurati

Il prodotto completo è già preparato sull'SSD. Per rigenerarlo dopo aver
aggiornato archivio o segmentazioni:

```bash
uv run --group viewer python scripts/pipeline/prepare_thermal_density.py
```

Scrive `thermal-duration.npz` e il relativo rapporto JSON accanto a
`thermal-planes.sqlite3`. La fase delle regioni prepara prima, se manca o non è
aggiornata, la griglia nazionale `route-thermal-duration-vilpellet.npz`
(un passaggio su tutti i fix nativi), poi la ritaglia. Il viewer apre soltanto questo prodotto compatto;
**Reload SSD data** non avvia scansioni dell'archivio. Il vecchio
`thermal-regions.npz`, contenente conteggi, non viene interpretato come ore.
La pubblicazione è atomica. Un checkpoint regionale permette di riprendere
con `--only cells` dopo un'interruzione nella fase delle celle; `--only regions`
aggiorna solo le regioni preservando eventuali celle già preparate.
Un benchmark limitato, solo per le celle, richiede
`--only cells --limit-batches N --output /percorso/separato.npz`;
i prodotti incompleti vengono rifiutati dal viewer.

Verifica del **3 ottobre 2026**, con la precedente versione HMM delle regioni,
su questa macchina macOS con 8 GiB di RAM:

| Misura | Risultato |
| --- | ---: |
| Decisioni regionali lette, due discipline | 178.965.099 |
| Archi regionali climb esaminati | 51.663.055 |
| Prodotti volo/cella/metodo letti | 240.726 |
| Mappe salvate | 5 regioni + 12 celle × 2 metodi = 29 |
| Preparazione completa, tempo reale | 430,84 s, circa 7 min 11 s |
| Picco RAM residente del preparatore | 1,57 GB |
| Picco memory footprint riportato da macOS | 2,63 GB |
| File compresso finale | 113,56 MB, circa 108,3 MiB |
| Array sparsi caricati in RAM | 201,50 MB |
| Lettura del file, con cache del sistema calda | 0,44 s |
| Prima aggregazione dell'intera mappa Alps | 292 ms |
| Aggregazione Alps già disponibile | circa 0,94 ms |
| Estrazione di una vista Alps di 5 km, pixel 50 m | circa 0,19 ms |

Questi ultimi tempi misurano la griglia, **escludendo disegno e rete**. Nel
controllo nativo Qt il caricamento con disegno delle cinque regioni ha richiesto
2,03 s; il processo ha raggiunto circa 1,08 GB di RAM residente durante la
navigazione tra mappe e sfondi. Sono misure di questa esecuzione, non limiti
massimi garantiti.

Preparazione Vilpellet del **7 ottobre 2026**, stessa macchina, con
`--only regions`: la griglia nazionale ha letto 1.369.807.970 fix di parapendio e
34.567.535 di deltaplano e ha sommato 389.724.240 + 8.311.492 lati di salita, in
643 s complessivi con un picco di 1,50 GB di RAM residente. Il numero di lati è
esattamente quello dei fix nelle run `climb` meno il numero di run: nessun lato
attraversa due run e nessun passo interno a una run supera la soglia di
continuità. `route-thermal-duration-vilpellet.npz` occupa 137 MB e contiene
105.388 ore (la versione HMM ne conteneva 137.893).

Al controllo restavano circa **28 GiB liberi sull'SSD**. Il prodotto e una cache
piena richiedono complessivamente circa **0,61 GiB aggiuntivi**. Durante la
rigenerazione servono temporaneamente anche il checkpoint regionale e il file
in costruzione; il checkpoint viene rimosso dopo la pubblicazione completa.

Scaricare preventivamente le cinque intere cornici a 1,25 m/pixel implicherebbe
circa **1,25 TB di RGB non compresso per singolo sfondo** (cornici sovrapposte
conteggiate separatamente). Il peso compresso dipenderebbe dall'immagine.
Le richieste per la sola vista rendono superfluo questo download: il costo di
spazio aggiuntivo rimane limitato, con un piccolo e temporaneo margine durante
la scrittura di una nuova risposta.

Dati e tempi dettagliati: [rapporto JSON](../validation/thermal-density-2026-10-03.json).
