# Lettura dei risultati del nuovo cleaning

Run a valle: `20260910T221820Z-05d36ab4`, cleaning `2.2.0`.
Questo documento registra la lettura dei prodotti completati. Il rebuild ha concluso
tutti i 38 stadi; la successiva revisione del manoscritto e del PDF è conclusa e
riconciliata con i manifesti sull'SSD. Le conclusioni descrittive non sono test di
reiezione calibrati né una validazione delle etichette di fase.

## Durata ed equipaggiamento

Il controllo usa 154.984 voli para e 6.059 hang con almeno un segmento ammissibile
(almeno otto fix, cadenza nativa non superiore a 10 s). I segmenti sono aggregati entro
volo con pesi proporzionali alle origini ammissibili; i voli contribuiscono con peso
uguale. Non è lo stesso stimatore della media a pesi uguali per segmento in Figura 3.1.

Le pendenze su 10–10.000 s sono 1,728 per A/B e 1,788 per C/D/CCC. Nel confronto delle
otto celle durata × equipaggiamento, l'intervallo comune è 10–1.695 s: includere la
classe di durata minima di un'ora limita la parte comune a non oltre 1.800 s. È un
confronto secondario esplicito, non un cambiamento dell'intervallo principale.

| Proxy | Tutte le durate | Almeno 4 h | Voli con almeno 4 h |
|---|---:|---:|---:|
| Beginners, A/B | 1,755 | 1,806 | 7.426 |
| Experts, C/D/CCC | 1,803 | 1,836 | 27.842 |

Le classi sono proxy di esperienza richiesti dall'autore, non misure individuali
indipendenti dell'abilità. La quota C/D/CCC tra le due classi note passa da 63,5% a
78,9% nei voli di almeno quattro ore. Questi voli non appartengono tutti agli experts.
A 576 s il rapporto MSD(≥4 h)/MSD(tutte) scende da 1,301 a 1,248 fissando le
proporzioni delle due classi; a 1.695 s passa da 1,415 a 1,349. La composizione spiega
parte del contrasto sotto questa standardizzazione, ma non lo elimina. La convergenza
verso uno vicino a 7.200 s risente della scomparsa dei voli più brevi dal riferimento.
Il risultato aggiornato non giustifica l'indipendenza dalla durata totale.

## Quantili e popolazione fissa

Il controllo più restrittivo conserva 107 voli para e 56 hang, con gli stessi pesi e
le stesse origini a tutti i lag. Le pendenze radiali 25%/90% sono 0,979/0,892 per para
e 0,995/0,864 per hang. Non c'è un ordinamento strettamente decrescente di tutti i
quantili: in entrambi i casi la pendenza al 90% supera quella al 75%.

La sola differenza delle pendenze non descrive bene la forma delle curve. A pesi e
origini fissi Q90/Q25 sale inizialmente, raggiunge il massimo a 80 s, diminuisce fino a
circa 2.000–2.400 s e poi risale. Per para vale circa 1,94 a 10 s, 4,48 al massimo e
3,03 a 10.000 s; per hang 2,23, 5,89 e 2,65. La pendenza OLS negativa del logaritmo
del rapporto non implica quindi un restringimento monotono, né un valore finale
inferiore all'iniziale. L'identità tra differenza delle pendenze e pendenza del rapporto
richiede la stessa matrice del fit, qui verificata.

Cambiare dalla popolazione disponibile a quella lunga fissa cambia anche la domanda
scientifica. Gli effetti di selezione della popolazione lunga non vengono eliminati
fissando pesi e origini; viene eliminata la loro variazione con il lag entro quel
campione. Non si ottengono repliche indipendenti dai molti incrementi sovrapposti.

## Anisotropia regionale

Nei Pirenei il rapporto non centrato est/nord della posizione raggiunge circa cinque
ai tempi lunghi. La direzione prevalente è compatibile con la geometria del massiccio,
ma non separa contributi di vento, percorso e condizioni selezionate. La PCA centrata
sul sottoinsieme fornisce a 1.070 s un asse di 155,3° rispetto a est e un rapporto degli
autovalori 2,20 (61 voli). A 10.000 s restano solo 20 voli in quel confronto.

Nelle Alpi le curve degli experts sono più vicine a uno per posizione e velocità
nell'intervallo visualizzato. Nei Pirenei l'ordinamento cambia con il tempo: il minore
sbilanciamento iniziale degli experts non persiste su tutta la curva. Non è quindi
sostenibile una superiorità uniforme nel superare i vincoli orografici.

## Memoria e forma

A separazione 600 s le correlazioni medie para sono 0,144, 0,198 e 0,272 per velocità
mediate rispettivamente su 10, 60 e 300 s; hang: 0,130, 0,186 e 0,265. Sono stime
positive senza calibrazione dell'incertezza a quel lag. Le curve log–log sono curve,
non una prova di decadimento a potenza su tutto l'intervallo; quelle hang diventano
negative a separazioni lunghe. I valori negativi sono conservati nei pannelli lineari.

L'eccesso di Mardia varia da −2,12 a 3,74 per para e da −1,60 a 7,45 per hang;
rispetta il vincolo empirico −4 per covarianza bidimensionale nonsingolare stimata con
denominatore n. Né un valore positivo identifica una coda a potenza né zero dimostra
la gaussianità. Il confronto con modelli omogenei riguarda questa popolazione pooled.

## Passi verticali isolati

Il contatore `n_alt_level_shift` precede trimming e selezione dei segmenti. Marca un
passo verticale isolato oltre soglia senza ritorno entro il 30% del salto nelle cinque
posizioni successive disponibili al test. Non prova un offset permanente, e può
includere eventi già invalidati da un'altra regola. Tra i voli poi conservati 47.341
para e 1.349 hang hanno un conteggio positivo: non sono conteggi di difetti dimostrati
nei segmenti finali.

Un controllo mirato di otto voli (due conteggi massimi e due esempi positivi con seme
fisso per disciplina) riproduce esattamente i contatori. In tutti gli esempi alcuni
tempi candidati cadono vicino a centri di finestre di feature utilizzabili. Questo
mostra un limite della maschera di qualità, senza provare che ciascun passo sia un
errore o quantificare un effetto sulle etichette. Una sensibilità della segmentazione
all'esclusione di questo supporto rimane necessaria prima di dichiararlo trascurabile.

## Correzione del rapporto delle esclusioni

La lettura finale della tabella di cascata ha rilevato un'omissione nel solo
rapporto: mancava il motivo `no_usable_altitude_channel`, pur presente correttamente
nel cleaning e nel censimento indipendente. Le 697 esclusioni para e 135 hang
omesse lasciavano i totali della tabella diversi dai voli conservati e alteravano
i denominatori delle righe successive.

Il generatore ora include questa decisione nel suo ordine effettivo e rifiuta
motivi non mappati. Due regressioni controllano denominatori e quadratura dei
conteggi. La prima correzione locale è stata ricalcolata dai conteggi esatti del prodotto
`pipeline_census.tex` mentre l'SSD era scollegato. Dopo il ricollegamento, il
generatore è stato rieseguito sui metadati `flights_meta`: l'intero file numerico
coincide byte per byte con la correzione, e la figura stagionale è invariata. Il taglio per assenza di segmenti passa da
11,7% a 11,8% per para e da 3,0% a 3,1% per hang. Non cambiano né il dataset
pulito né le osservabili di trasporto o le fasi.

Il motivo `no_segment_survived` aggrega segmenti troppo corti, troppo incompleti o
non ricostruibili; attribuirlo interamente alla sola soglia di incompletezza sarebbe
scorretto. Il confronto per cadenza usa i voli con cadenza disponibile nei metadati,
non ogni file tentato. Testo e didascalie sono stati corretti di conseguenza.

## Segmentazione aggiornata

Entrambi i percorsi degli esempi di validazione sono riprodotti dal decoder salvato.
Il fit para usa 972 voli, 953.078 osservazioni e 11.604 sequenze; il fit hang usa 874
voli, un milione di osservazioni e 8.784 sequenze. Il restart selezionato per massima
likelihood non soddisfa in nessuna disciplina il criterio di incremento finale
non negativo e inferiore alla tolleranza: gli ultimi incrementi sono −0,223 e −0,253.
La positività degli autovalori della covarianza non risolve questa limitazione.

Le componenti chiamate climb hanno coerenza media vicinissima a uno e deviazioni
standard di circa 0,000089 e 0,000060. La marginalizzazione che elimina la coerenza
è esplicita; non equivale a rifittare un HMM tridimensionale. Nell'esempio hang una
parte della salita resta classificata search, con posteriori divisi tra search e
climb. È un'ambiguità concreta da sottoporre all'annotazione, non una prova di errore
né una classificazione già validata.

Il tempo mantenuto dal cleaning ma privo di fase è 8,28% per para e 5,93% per hang.
I denominatori sono durate, non numeri di fix o percentuali delle sole decisioni.
Il nuovo pacchetto cieco contiene 40 candidati, per disciplina 4 train, 8 validation
e 8 test. Non sono disponibili etichette indipendenti e non è riportata accuratezza.

## Controlli eseguiti e chiusura

Le identità dei conteggi, delle miscele e delle pendenze di durata hanno superato 47
controlli indipendenti sui prodotti salvati. I controlli di quantili, momenti, PCA e
correlazioni ne hanno superati 186; il controllo dei prodotti di segmentazione ne ha
superati 25. La suite locale completa dell'11 settembre passa 824 test, con 24 avvisi
di deprecazione NumPy provenienti da hmmlearn. Le verifiche dei risultati restano
controlli algebrici e di supporto, non una calibrazione statistica.

Le revisioni di prosa, bibliografia e grafica sono riconciliate con il run sull'SSD.
Il PDF finale ha 101 pagine; i sorgenti, tutti i prodotti registrati, le identità dei
due dataset e la provenienza del nuovo pacchetto di annotazione sono stati verificati.
L'inventario README dell'SSD è stato rigenerato e riletto. Le prove sono raccolte in
[`manuscript-review-2026-09-11/completion.json`](manuscript-review-2026-09-11/completion.json).
Non è stato ripetuto inutilmente il cleaning: le correzioni successive riguardano
prosa, grafica, indice documentale e il solo rapporto della cascata, con prove
separate per ciascun intervento.

La rilettura della tabella dei parametri ha inoltre corretto descrizioni troppo
forti delle soglie di ammissione, il test di raggiungibilità applicato a ciascun
fix con tolleranza di 50 m, il conteggio dei passi finiti della mediana e lo span
`(w−1)Δt` della finestra Savitzky–Golay. L'insieme conservato dal cleaning è distinto
dai sottoinsiemi ammissibili per gli estimatori; i segmenti esclusi dall'MSD perché
hanno meno di otto fix non sono presentati come segmenti eliminati dal cleaning.
Le regole di calcolo non sono cambiate in questa rilettura.
