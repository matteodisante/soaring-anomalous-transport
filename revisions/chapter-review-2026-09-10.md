# Revisione dei capitoli 1–4 — 10 settembre 2026

## Risultato consegnato

Introduzione riscritta intorno a domande fisiche, dati, modelli, simulazioni e struttura.
Capitolo 2 verificato contro il cleaning, con due correzioni del witness barometrico e
illustrazioni analitiche/reali. Capitolo 3 riorganizzato per osservabili discriminanti e
confronti fra ipotesi precise. Capitolo 4 allineato al decoder corrente, con esempi di
8 minuti e protocollo di annotazione indipendente. La direzione successiva è in
`docs/thesis-roadmap.md`; i capitoli futuri non sono stati scritti come risultati.

## Correzioni scientifiche sostanziali

- Nessuna interpretazione dinamica della media sincronizzata al decollo; niente fit nel
  suo grafico introduttivo. Tolta la parte sull'ergodicità, anche l'appendice dal PDF.
- Una differenza seconda cancella esattamente una velocità costante. L'identificazione
  della sua pendenza con 2H richiede ipotesi esplicite. La differenza fra pendenze non
  quantifica un contributo additivo del vento. Un percorso chiuso sopravvive al filtro.
- Sullo stesso campione, l'ordinamento decrescente degli esponenti dei quantili su
  60–2000 s cambia estendendo a 10–10.000 s. Inseriti confronto numerico e disegno
  dell'evoluzione della larghezza relativa. La scelta dell'intervallo cambia la domanda.
- Marginali autosimili non garantiscono autosimilarità congiunta. PCA non cambia il
  modulo e non elimina la memoria; whitening non identifica moto senza vento/orografia.
- Aggiunto spettro teorico del Lévy walk standard, con regime e ipotesi dichiarati.
  Lo spettro quasi lineare non esclude tutte le varianti e non prova monofrattalità esatta.
- Kurtosis di Mardia centrata con covarianza completa; eliminata la falsa identità che
  pretendeva di ricavare la kurtosis entro volo da un null basato solo sulla traccia.
- Autocorrelazione di velocità media su 10, 60, 300 s; Green–Kubo dimensionalmente
  corretto. Nessuna deduzione di non-integrabilità da una finestra finita.
- Coorti di durata con conteggi di voli distinti. Le differenze di ampiezza sono riportate:
  vicinanza grafica non implica indipendenza dalla durata.
- Segmentazione: marginalizzare una Gaussiana 4D non equivale a rifittarne una 3D.
  Separati parametri stimati e prior imposto. Likelihood, copertura e plausibilità non
  sono accuratezza. Le finestre che attraversano fasi servono alla ricostruzione globale.

## Evidenza computazionale

- `thesis/generated/cleaning_witness_audit.json`: confronto legacy 2.0.0/corretto 2.0.1
  su 2.388 candidati; 189 voli modificati, 22.468 fix conservati, nessun cambiamento
  del verdetto di ammissione nel campione sottoposto ad audit, zero errori.
- `thesis/generated/ch3_revision.json`: 877 parapendii e 430 deltaplani, selezione e
  supporto espliciti, misure effettive 10–10.000 s. Campione esplorativo con possibili
  effetti di durata/geografia dovuti alla selezione di row group e segmento più lungo.
- `thesis/generated/segmentation_decoder_audit.json`: ricostruzione delle figure dal
  decoder corrente e confronto con archivio precedente; etichette manuali ancora zero.
- Verifica integrata finale: **403 test superati** su preprocessing, osservabili,
  segmentazione e report/annotazione; lint dei file nuovi/modificati e compilazione PDF.
  Le verifiche di implementazione non costituiscono validazione fisica del modello.

## Requisiti prima della versione quantitativa definitiva

1. Rigenerare le traiettorie dopo le correzioni della disponibilità locale del barometro
   e della conversione zero→mancante prima dell'aggregazione dei timestamp duplicati.
   L'archivio usato nelle figure è lo snapshot precedente: è dichiarato nel testo.
2. Rigenerare osservabili e dati di fase con la stessa nuova versione. L'archivio delle
   etichette conserva ancora il vecchio decoder; gli esempi del capitolo usano quello
   corrente. Non confondere queste due provenienze.
3. Completare annotazioni indipendenti senza consultare predizioni. Pacchetto pronto
   in `annotations/phase_labeling/`; GUI con zoom sincronizzato, selezione dello split e
   snapping corretto anche per griglie non allineate a t=0.
4. Stimare accuratezza, errori di confine, accordo umano e generalizzazione per gruppi;
   calibrare i confronti fra processi con simulazioni finite e protocollo osservativo
   comparabile. L'attuale capitolo formula esclusioni descrittive, non p-value inventati.

Non è stato eseguito un nuovo preprocessing completo dell'archivio né un nuovo export
completo delle fasi; il PDF non presenta questi passaggi come completati.

## Aggiornamento della soglia verticale richiesto sul grafico

Soglia portata da 30 a **10 m/s**, pipeline **2.1.0**. Sul campione diagnostico
GNSS la densità del parapendio supera quella del deltaplano fra i bin [8,9) e
[9,10) m/s; il decadimento diventa progressivamente più lento. È una motivazione
empirica della soglia operativa, non una dimostrazione di massimo fisico.

Su 164.159.011 valori locali finiti, 113.743 superano 10 m/s (0,06929%):
90.211/126.494.460 per il parapendio e 23.532/37.664.551 per il deltaplano.
Le quote derivano dai cache grezzi `fixlevel_scan.parquet`, quantity=2; non
misurano i fix effettivamente invalidati dal cleaning. Il confronto witness
2.0.0/2.0.1 precedente resta riferito alla soglia di 30 m/s.

Rigenerati grafico diagnostico, macro dei parametri ed esempi di cleaning;
**251 test di preprocessing superati**. L'archivio pulito completo e le osservabili
successive devono ancora essere rigenerati includendo anche la nuova soglia.

## Leggibilità della sezione 2.7.6

Riscritta la sezione sul campionamento uniforme, riducendo il corpo a meno della
metà e accorciando entrambe le didascalie diagnostiche. Aggiunto uno schema TikZ
con tre casi: breve buco temporale, interruzione lunga, assenza della sola quota.
La formula del limite sui buchi resta esplicita, con esempi a 1 e 5 secondi.
Dettagli sui flag e sui criteri di ammissione precisati nel capitolo 2.
Eliminate garanzie non dimostrate (errore sempre metrico, impossibilità di perdere
un giro completo, assenza di conseguenze statistiche delle separazioni).
Il cleaning e le soglie non cambiano in questa revisione editoriale.

## Ordine dei capitoli 2 e 3

La sintesi della pipeline segue ora immediatamente la sezione 2.7 sul preprocessing
(è la nuova 2.8). La caratterizzazione preliminare diventa la sezione 2.9 e conclude
il capitolo 2 con statistiche e copertura geografica. La discussione sull'isotropia,
compreso il grafico del rapporto fra momenti secondi est/nord, è trasferita nella
sezione sull'anisotropia del capitolo 3. Riferimenti, raccordi e provenienza aggiornati;
le formule diagnostiche restano distinte da quelle della covarianza centrata/PCA.
