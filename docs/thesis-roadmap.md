# Direzione della tesi — revisione del 10 settembre 2026

Questa nota registra il programma concordato con Matteo. Non certifica risultati ancora
da ottenere e non sostituisce GitHub Issues per le attività di implementazione.

## Domanda scientifica

Quale processo stocastico, compatibile con il bilancio energetico e con la dinamica del
volo veleggiato, riproduce insieme il trasporto globale e le statistiche delle sue fasi?
Un fit dell'MSD, da solo, non identifica il processo. I modelli devono essere confrontati
sulle medesime osservabili, con lo stesso campionamento, cleaning, durata e selezione dei
dati. Si escludono ipotesi precise, non intere famiglie sulla base di un solo grafico.

## Ordine del lavoro

1. **Capitolo 2, dati:** verificare cleaning e disponibilità locale del witness
   barometrico; distinguere flag, cancellazione e split; illustrare i difetti e i limiti
   dei controlli con formule, schemi ed esempi reali.
2. **Capitolo 3, osservabili globali:** rendere centrale il confronto tra modelli.
   Studiare 10–10.000 s con conteggi e sensibilità alla scala; MSD entro volo,
   differenze seconde come controllo del drift costante, quantili e loro rapporti,
   momenti, gaussianità centrata, memoria a più risoluzioni temporali, geometria
   open/closed e anisotropia per regione. La media sincronizzata al decollo rimane
   solo descrittiva. Togliere l'interpretazione in termini di ergodicità.
3. **Capitolo 4, segmentazione:** allineare tutte le figure al decoder corrente;
   definire emissioni, transizioni, durata e assunzioni; mostrare esempi leggibili e
   diagnostiche quantitative. Preparare annotazioni manuali, separando calibrazione
   e valutazione su voli distinti. Stabilità e plausibilità non equivalgono ad accuratezza.
4. **Nuovo capitolo, osservabili condizionate alla fase:** descrivere transizione,
   ricerca e salita con durata, spostamento, lunghezza percorsa, velocità, variazione
   di quota, curvatura, propagatori, memoria e correlazioni tra episodi. Conservare
   anche le finestre che attraversano una transizione: la sola somma delle finestre
   interne alle fasi non ricostruisce le osservabili globali.
5. **Confronto solo/gruppo:** prossima priorità operativa dopo la stabilizzazione di
   3 e 4, introducendo prima le osservabili di fase indispensabili. Un gruppo significa
   compresenza spazio-temporale compatibile con visibilità e scambio d'informazione;
   non coincide con una competizione. Definire soglie di distanza, dislivello, tempo
   e, se disponibile, linea di vista; distinguere leader/seguaci, ingresso/uscita dal
   gruppo e copertura incompleta degli altri piloti. Confrontare osservabili globali e
   di fase controllando sito, giorno, meteo, ala, abilità e compito. Vicinanza non prova
   interazione e assenza di altri log non prova solitudine.
6. **Modello stocastico e Monte Carlo:** usare vincoli globali e condizionati per
   costruire e confrontare modelli meccanistici. Stimare parametri su un insieme,
   verificare su voli o giornate separati. Simulare l'intero protocollo osservativo e
   verificare congiuntamente tutte le osservabili, senza aggiustare ciascuna a parte.
7. **Termiche e percorso ottimale:** stimare distribuzione spaziale 2D e struttura
   di correlazione delle termiche tenendo conto dello sforzo di esplorazione e della
   selezione dei piloti. Una mappa dei punti di salita è una mappa di termiche visitate,
   non automaticamente della loro disponibilità. Confrontare modelli analitici e
   simulazioni; formulare obiettivi distinti (tempo minimo A→B, circuito chiuso,
   massima distanza con risorse fissate). Procedere da un ambiente senza vento a uno
   con vento, poi eventualmente a vincoli orografici, con riserva energetica e quota
   esplicite. Una densità marginale 2D da sola non specifica un paesaggio di termiche.

## Vento, orografia e processo intrinseco

Mantenere due oggetti distinti e confrontabili: dinamica osservata al suolo, condizionata
all'ambiente, e possibile modello di riferimento senza forzanti esterne. La relazione
cinematica è `v_ground = v_air + wind`. Senza misura indipendente dell'aria, la velocità
media del volo non identifica il vento. L'orografia modifica anche la velocità e le
decisioni; il vento modifica anche la posizione. La PCA ruota gli assi e annulla una
covarianza contemporanea: non toglie vento, memoria temporale o anisotropia. Il whitening
uniforma la covarianza a una scala ma cambia la metrica fisica e non produce isotropia
delle leggi congiunte. Un dataset reso isotropo artificialmente è un controllo, non una
misura del volo in assenza di vento e montagne.

## Criteri per la versione semi-definitiva di 3 e 4

- Ogni risultato rinvia a dati, versione del preprocessing/decoder, pesi e supporto.
- Ogni esponente dichiara intervallo, unità statistica e carattere effettivo/asintotico.
- Le figure principali rispondono a una domanda e restano leggibili a dimensione pagina.
- Nessuna equivalenza tra momenti quasi lineari e autosimilarità esatta, tra assenza di
  evidenza e indipendenza, o tra likelihood/posterior del segmentatore e accuratezza.
- La validazione manuale resta un requisito prima di chiamare il segmentatore validato.
- Non scrivere ora i capitoli futuri come se fossero risultati già ottenuti.
