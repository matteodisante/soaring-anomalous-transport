# Capitolo 3 — implementazione completata il 18 settembre 2026

Codice, misure, figure e testo sono completi. Il nuovo capitolo 3 è in
`thesis/sections/04-fixed-transport.tex`, incluso in `thesis/main.pdf`.
Il documento `esperimenti.pdf` mantiene in rosso i passaggi originali trasferiti;
PCA e anisotropia restano nel volume sperimentale e hanno un segnaposto nella tesi.
L'introduzione e lo schema della tesi ora includono il capitolo 3.

## Misure e risultati principali

- Coorti principali: 46.273 parapendii, 46.367 segmenti, 25.682 gruppi sito–giorno;
  2.326 deltaplani, 2.327 segmenti, 1.768 gruppi.
- Stessi voli e segmenti su 33 lag da 10 a 10.000 s, durata del segmento almeno
  12.500 s. Origini ordinarie sovrapposte, peso totale uguale per volo.
- Quantili esatti della distribuzione pesata; momenti delle componenti assolute e
  del raggio; eccesso di kurtosi delle componenti con segno. Un unico bootstrap
  accoppiato di 1.000 repliche, intervalli puntuali 5–95%.
- Fit OLS globale: H = 0,882 [0,881, 0,883] per parapendii;
  H = 0,852 [0,849, 0,855] per deltaplani. Sono anche presenti pendenze locali,
  fit per decade e residui dei fit, sempre sulla stessa coorte principale.
- Le coorti più ampie danno MSD inferiori: a 1.000 s, rapporto con la principale
  0,781 per parapendii e 0,731 per deltaplani. La composizione open/closed cambia.
- Open: H maggiore in Plains/Hills che nelle fasce montane; closed: H inferiore
  a open in tutte le fasce, ma non compatibile fra tutte le fasce di quota.
- I rapporti dei quantili sono non monotoni e la kurtosi varia con il lag.
  Il risultato non sostiene un'unica famiglia di scala su tutte e tre le decadi.
- La nuova curva dall'origine ha il minimo iniziale di pendenza a 110 s nei
  parapendii e 320 s nei deltaplani; recupera verso H=1 intorno a 600–700 s.
  L'interpretazione ricerca più salita rimane una stima qualitativa dopo il trimming.

## Dati e riproduzione

Run SSD: `/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917`.
Occupazione: circa 663 MiB allocati (circa 638 MiB di contenuti), senza array
temporanei di incrementi residui.
Le coordinate già protette per la PCA sono riutilizzate senza modificarle.
Tutte sono state ricostruite dai dati puliti e confrontate: differenza massima zero,
per 155.085 parapendii e 6.060 deltaplani e tutti i loro segmenti ammissibili.

Il solo `report.json` consente il ridisegno: circa 6 secondi per dieci figure e
relative tabelle/frammenti numerici. Una copia è versionata in `thesis/generated/`.
Comandi: `docs/guide/chapter3-fixed-transport.md`.
`RELEASE.json` contiene SHA-256 dei risultati e del codice; gli audit di input
riportano provenienza e identità dei file sorgente.

## Verifiche

- 55 test mirati di trasporto/scaling passati, inclusi dieci nuovi test sulle
  identità statistiche, sui gap e sull'inversione esatta della CDF pesata.
- 117 test del viewer passati. Nessun cambiamento a raw, pulizia o segmentazione.
- Identità MSD/momento radiale q=2 verificate su ogni replica e lag; identità
  fra pendenza del rapporto e differenza degli esponenti dei quantili verificata.
- Nessun riferimento indefinito, overflow di impaginazione o destinazione PDF
  duplicata nella compilazione dei due volumi. Pagine nuove controllate visivamente.
- La sorgente del capitolo 2 è identica allo stato trovato all'inizio del lavoro.
  Il checkpoint iniziale delle modifiche preesistenti rimane locale.

I commit della tesi conservano lo stato corrente dei sorgenti e degli input del
volume sperimentale, compresa la separazione dei due volumi già presente all'inizio.
Le modifiche di codice preesistenti estranee alla nuova pipeline restano nel workspace.

## Riproduzione da soli file committati

Verificato il commit `653a88e` in una directory isolata estratta da Git.
I dieci nuovi test passano anche lì. Il ridisegno offline dal solo rapporto
versionato riproduce byte per byte tutte le figure e i frammenti numerici
(4,7 secondi). Entrambi i PDF compilano senza riferimenti mancanti, overflow
o destinazioni duplicate. Nessuna dipendenza dalle modifiche di codice
preesistenti lasciate nel workspace.
