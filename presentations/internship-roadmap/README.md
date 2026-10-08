# Internship and thesis research directions

Presentazione Beamer in inglese per discutere con i supervisors il piano
ottobre 2026–febbraio 2027. **12 slide principali e 2 appendici**, circa
12–15 minuti. Sorgente e asset sono autonomi rispetto al resto delle presentazioni.

- [Slide PDF](internship-roadmap.pdf)
- [PDF con note a fianco](internship-roadmap-notes.pdf)
- [Sorgente LaTeX](internship-roadmap.tex)

## Contenuto

1. Titolo.
2. Percorsi di ricerca e dipendenze, con download/preprocessing già completati.
3. HMM con osservazioni continue, vincolo di campionamento e copertura.
4. Caratterizzazione stocastica oltre MSD ed esponente efficace.
5. MSD empiriche di transition, search e climb.
6. Modello gliding/waiting e memoria angolare.
7. Definizione e confronto solo/group flight.
8. Quantità identificabili dalle osservazioni di salite e limiti delle mappe.
9. Possibile studio di controllo ottimo stocastico.
10. Calendario con le finestre richieste, pausa e buffer.
11. Sviluppo parallelo del tool grafico.
12. Priorità e momenti di discussione.

Le appendici precisano i denominatori della copertura e il legame tra
autocorrelazione della velocità e crescita della MSD.

## Compilazione

Occorrono Python 3 e una distribuzione LaTeX con `pdflatex`, Beamer, TikZ,
Palatino e i pacchetti indicati nel preambolo. Non serve accedere all'SSD per
compilare le slide: dati numerici e figura sono inclusi.

```bash
python3 presentations/internship-roadmap/build.py
```

Lo script esegue due passaggi per ogni PDF, usa una directory temporanea e
segnala riferimenti indefiniti, caratteri mancanti o box in eccesso.

## Provenienza e interpretazione

**Campionamento e copertura.** La verifica legge il codice originale
`flight_phase_inference_minimal.py.txt` nel pacchetto di Jérémie Vilpellet,
la configurazione locale e le tabelle `phase_coverage.parquet` del 16 settembre
2026. Il codice originale usa finestre e angoli per fix. Il port locale
richiede un passo medio strettamente inferiore a 1,2 s, almeno 3.600 fix per volo
e almeno 30 per segmento. Questi vincoli riguardano l'implementazione corrente,
non gli HMM in generale. L'articolo seleziona dati con frequenza di almeno 1 Hz.

I tempi esclusi, 30,1% e 70,9%, hanno come denominatore la somma delle durate
dei segmenti puliti nei due archivi di copertura. Escludono i gap. Includono
tutti i criteri di ammissibilità, non soltanto la cadenza. I voli con almeno
un segmento classificato sono rispettivamente il 66,9% e il 27,4%. Il solo
criterio di cadenza mantiene il 70,7% e il 29,2% del tempo supportato.

Il report [coverage-audit.json](coverage-audit.json) conserva conteggi,
denominatori e hash delle due tabelle. Per rigenerarlo con l'SSD montato:

```bash
.venv/bin/python presentations/internship-roadmap/audit_coverage.py
```

Il calcolo misura la cadenza direttamente, perché un'esclusione registrata per
volo corto può nascondere un ulteriore problema di cadenza. Il tempo classificato
usa l'intero segmento pulito, evitando di perdere un intervallo a ogni cambio
di fase. Le percentuali descrivono l'esportazione archiviata e non certificano
l'accuratezza delle etichette.

**Curve empiriche.** `assets/empirical-phase-msd.pdf` riproduce in vettoriale
la Figura 3, pagina 4, di [Vilpellet, Darmon e Benzaquen,
arXiv:2601.01293v1](https://arxiv.org/pdf/2601.01293v1).
Il ritaglio della pagina PDF è `[54, 58, 562, 214]` punti dall'angolo in alto
a sinistra. Tutti e tre i pannelli, le curve e la legenda sono conservati.
È una coorte empirica esterna, non un nuovo calcolo sull'archivio locale.
Le figure per fase del precedente modello di Pisa sono simulazioni, quindi
non sono state utilizzate come evidenza empirica.

**Stato dei lavori.** Esiste già un prototipo Gaussian HMM e sono presenti
analisi preliminari oltre MSD/H. Le slide descrivono il lavoro futuro come
validazione, consolidamento ed estensione, senza presentarli come assenti.
Fonti locali: `docs/guide/flight-phase-segmentation.md`,
`docs/guide/vilpellet-segmentation.md`, `docs/guide/group-flights.md`,
`docs/guide/thermal-density.md` e capitoli della tesi.

**Controllo ottimo.** [Almgren e Tourin,
DOI 10.1002/oca.2122](https://doi.org/10.1002/oca.2122),
*Optimal Control Applications and Methods* 36, 475–495 (2015),
pubblicato online nel 2014. [Record del manoscritto degli autori](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2399214).
La proposta è esplorativa. Il lavoro di approfondimento dell'articolo e la
fattibilità del problema con scelta della rotta nel piano restano da svolgere.
Le mappe di salite osservate sono condizionate dal campionamento dei piloti.
Una densità spaziale marginale da sola non definisce il processo atmosferico
necessario a un problema di controllo.

**Date.** Sono mantenute tutte le finestre indicate. Il 30 novembre è condiviso
fra modello e solo/group. Il 7 febbraio è condiviso fra controllo e buffer.
Il periodo solo/group è di 24 giorni di calendario, quindi poco più di tre
settimane. Il buffer resta disponibile per imprevisti o approfondimenti.
