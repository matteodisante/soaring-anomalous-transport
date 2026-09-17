# Revisione scientifica e stilistica del capitolo 3

La revisione controlla formule, pesi, bootstrap e interpretazione contro il codice e
le repliche già salvate. Non ricostruisce traiettorie e non estrae nuovi campioni
bootstrap. Il capitolo usa paragrafi più brevi, una tabella per le diagnostiche dei
gruppi e definizioni esplicite per pesi, intervalli, regressioni e self-similarity.

## Risultati e modifiche richieste

- Figura 3.1: eliminato il fit dall'origine dopo trimming. Il fit TA-MSD a popolazione
  disponibile copre 10–30000 s: 48 lag effettivi da 10 a 28440 s. H = 0.86912
  [0.86379, 0.87442] per parapendii e 0.84052 [0.81588, 0.85528] per deltaplani.
  La coda del fit dei deltaplani comprende sette gruppi; 998/1000 repliche hanno
  supporto completo. Questo limite compare nel testo.
- Figura 3.2: colmato solo il vuoto a 20 s. La finestra locale viene estesa ai tre
  lag più vicini in logaritmo (10, 20, 30 s); nessuna MSD interpolata o nuova misura.
  Gli estremi e le pendenze della coorte principale conservano la procedura precedente.
- Figura 3.3: sostituiti i rapporti MSD con H e CI per le tre coorti sulla stessa
  finestra 10–100 s; confronto anche fra le due coorti lunghe su 10–1000 s.
  La tabella riporta differenze accoppiate, usando le stesse repliche.
- C10000 aumenta H di circa 0.017 rispetto alle coorti più ampie. I contrasti sono
  risolti dal bootstrap: non si può affermare assenza di un effetto della selezione.
  C100 e C1000 differiscono meno di 0.0001; la precisione del confronto accoppiato
  risolve anche questa piccolissima differenza per i parapendii, non per i deltaplani.

## Correzioni concettuali

- La formula bootstrap rinormalizza sui voli disponibili a ciascun lag; nella
  coorte fissa l'insieme è costante. Il peso totale per volo è fisso, quello del
  singolo incremento dipende dal numero di origini disponibili.
- Gli intervalli 5–95% sono nominali e puntuali. Il bootstrap conserva la dipendenza
  interna ai gruppi; prossimità fra siti e meteo condiviso possono lasciare dipendenza
  fra gruppi. La numerosità non verifica da sola l'indipendenza.
- Le identità fra derivate locali sono distinte dalle loro stime con regressioni.
  L'identità della pendenza di una miscela è circoscritta alle proporzioni fisse.
- Self-similarity: definizione tramite distribuzioni congiunte; incrementi stazionari
  come ipotesi aggiuntiva per dedurre una legge dipendente solo dal lag. Seguono H
  comune ai quantili, rapporti costanti, spettro qH e kurtosi costante quando esiste.
- L'identità M_q = integrale_0^1 Q_p^q dp spiega perché momenti e fit globali possono
  attenuare variazioni di forma. Lo spettro è quasi lineare, con deviazioni piccole
  ma risolte. Qui i rapporti fra quantili lungo il lag, corroborati dalla kurtosi,
  pesano più della linearità visiva dello spettro.
- Conclusione: un solo modello self-similar con incrementi stazionari non descrive
  adeguatamente la legge aggregata su 10–10000 s. Non sono dimostrate né escluse tutte
  le forme di self-similarity non stazionaria; non si conclude multifrattalità asintotica.
- Il minimo della pendenza dall'origine è un'ipotesi di transizione ricerca/salita–gliding;
  non è identificato con una durata media di fasi segmentate. Un maggiore H della MSD
  non viene chiamato direttamente maggiore persistenza. La deriva uniforme può cambiare
  la pendenza della MSD non centrata.

## Verifiche e conservazione

- 13 test mirati passati, inclusi confronto accoppiato con rumore comune, intervallo
  del fit generale e riparazione della finestra locale. Ruff e formattazione verificati.
- Tutti i risultati già pubblicati della coorte principale, dei quantili, dei momenti,
  della kurtosi e dei gruppi open/closed sono invariati nel rapporto numerico.
- Dieci figure/tabelle estranee ai nuovi confronti sono identiche byte per byte.
- Sorgenti del capitolo 2 e del volume esperimenti preservati; nessuna nuova modifica
  a raw, pulizia, segmentazione, viewer o dati PCA.
- I due volumi compilano senza riferimenti mancanti o box fuori margine. Controllo
  visivo delle pagine del capitolo 3 e delle tre figure modificate.

Il renderer continua a usare il solo `report.json`. Il nuovo rapporto e i prodotti
pronti da ridisegnare sono conservati sia in `thesis/generated/` sia nella directory
SSD della pubblicazione. `RELEASE.json` registra hash e verifiche di questa revisione;
il manifest originale resta in `revisions/ch3-implementation-2026-09-17/`.

Verificato anche il commit `7193433` in una copia isolata estratta da Git:
13 test passati, tutti i 30 prodotti del ridisegno identici byte per byte e compilazione
di entrambi i volumi senza riferimenti mancanti, overflow o destinazioni duplicate.
Il rapporto sullo SSD coincide con quello committato. Log: `clean-reproduction.log`.
