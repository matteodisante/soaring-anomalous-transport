# Richieste della revisione e criteri di chiusura

Rassegna della chat, aggiornata l'11 settembre 2026. Questo registro distingue il
lavoro richiesto ora dal programma dei capitoli successivi. «Implementato» descrive
una modifica presente nei sorgenti, non certifica che la relativa figura sia già
stata rigenerata o che l'interpretazione empirica sia conclusa. Le verifiche scientifiche
e numeriche sono documentate negli audit dei capitoli e nell'audit di correttezza.

## Stato corrente

Cleaning, rebuild, revisione del manoscritto e riconciliazione con il run SSD sono
completati. La cascata corretta coincide con la rigenerazione dai metadati SSD,
l'inventario del disco è aggiornato e il PDF finale comprende 101 pagine. Sono passati
824 test e 258 controlli aggiuntivi sui risultati. Il
[verbale conclusivo](manuscript-review-2026-09-11/completion.json) registra le identità
verificate. I gruppi di modifiche sono descritti nel
[piano dei commit](commit-plan-2026-09-11.md); l'esecuzione è documentata dalla storia Git.
Le annotazioni umane, i test di reiezione calibrati e i capitoli successivi restano
attività scientifiche future, dichiarate come tali nella tesi e nella roadmap.

## Priorità e procedura

| Richiesta | Stato e condizione di chiusura |
|---|---|
| Controllo profondo prima del nuovo cleaning | Audit, correzioni e lettura finale eseguiti; controlli sui risultati aggiornati registrati nel verbale conclusivo. |
| Rirun del cleaning con i criteri attuali, SSD ricollegato | Completato: 156.305 voli para e 6.093 hang conservati. Log SSD `derived-audit/cleaning/20260910-v2.2.0/cleaning.log`. |
| Rigenerare tutte le analisi e figure dopo il cleaning | **38/38 stadi completati.** Risultati interpretati e PDF revisionato; manifesti riconciliati e cascata verificata sui metadati SSD. |
| Usare la CPU secondo l'ultima indicazione | Otto worker, thread numerici interni limitati a uno; ultima richiesta di massima potenza sostituisce quella precedente di riduzione. |
| Spiegare i lanci e non fare ricalcoli senza motivo | Ogni stadio ha comando, log e manifest; le interruzioni per modifiche ai sorgenti non sono run completi. |
| Completare prima 2, 3 e 4, poi confronto solo/gruppo | Sequenza registrata nella roadmap; i capitoli futuri non sono presentati come già svolti. |
| Add e commit finali di tutte le modifiche, separati per logica | Otto gruppi logici, con diff, provenienza e descrizione separati; esecuzione documentata nella storia Git, nessun push. |

## Introduzione, struttura e scrittura

| Richiesta | Intervento / verifica restante |
|---|---|
| Introduzione su domande fisiche, motivazione, struttura e metodi | Riscritta e riletta nel PDF. |
| Capitoli leggibili come lavoro scientifico, non ricettario | Riorganizzazione e revisione della prosa, con controllo della continuità e riduzione delle frasi telegrafiche. |
| Più matematica dove serve, schemi e grafici informativi | Aggiunti e controllati stimatori, ipotesi, teoria HMM, schemi e richiami. |
| Riepilogo alla fine di ogni capitolo | Presente nei quattro capitoli e aggiornato ai risultati del nuovo archivio. |
| Fonti reali, pertinenti e citate nel punto corretto | Inventario aggiornato a 44 voci, 33 citate nel manoscritto compilato. Verificati i nuovi riferimenti a Efron, Fritsch–Butland e Taylor; recuperato Kapos; limiti di accesso dichiarati nell'audit. |
| Appendici corrette e utili | Conservate stime spettrali e geodesia; revisionate. Rimossa l'appendice sul CTRW subdiffusivo e l'ergodicità. |
| Eliminare la parte separata sui dettagli implementativi e ogni rinvio | Rimossa dal manoscritto e dai percorsi ritirati; ricerca finale nei file correnti senza rinvii residui. |

## Capitolo 2: dati e cleaning

| Richiesta | Intervento / verifica restante |
|---|---|
| GNSS lock e barometro disponibili allo stesso fix | Witness locale con supporto barometrico completo; non scartare globalmente ogni fix privo di barometro. Distinguere disponibilità e prova dello stato del ricevitore. |
| Validità scientifica dell'intera catena | Controllati timestamp, canali mancanti, frozen lock, Hampel, gate, split, resampling e smoothing; audit e test specifici. |
| Soglia verticale circa 10 m/s nel cambio di pendenza | Soglia a 10 m/s; distribuzione fresca e didascalia verificate. Il cambio di pendenza resta una motivazione operativa, non la misura di un limite fisico. |
| Spiegare il test della mediana e formule 2.6–2.7 con disegni | Schema delle finestre, mediana e logica AND, incluso controesempio; Numerazione 2.6–2.7 e disegni verificati nel PDF. |
| Illustrare i tre difetti/Hampel anche nei dati reali | Schemi ed esempi reali rigenerati dal cleaning corrente e controllati nel PDF; gli esempi illustrano decisioni, senza riferimento umano indipendente. |
| Alleggerire uniform sampling | Sezione riscritta, con limite dei gap, interpolanti e flag espliciti; grafici della cadenza e dei gap ricollocati per evitare pagine isolate. |
| Pipeline summary subito dopo 2.7 | Collocata in 2.8, subito dopo 2.7. La cascata include il gate GNSS ed è stata verificata direttamente sui metadati SSD. |
| Preliminary characterization alla fine del capitolo, anisotropia nel 3 | Riorganizzazione implementata. |
| Figura 2.2: valutare asse x lineare | Assi x lineari nelle distribuzioni dei limiti; code leggibili su y logaritmico. |
| Documentare esattamente l'effetto dello smoothing e i flag | Corrette formule, supporti e schema; test del comportamento. Le correzioni solo documentali successive al cleaning sono provate da equivalenza AST e manifest originali conservati. |

## Capitolo 3: osservabili e modelli

| Richiesta | Intervento / verifica restante |
|---|---|
| Launch/ensemble MSD riportata senza studio interpretativo | Mantenuta descrittiva, con eterogeneità per sito, stagione e anno; nessuna assunzione di repliche della stessa legge. |
| Utilità della filtered variation ed esponente H senza drift | Differenze seconde, cancellazione esatta della velocità costante e ipotesi per ricavare H esplicitate; non identificare drift e vento. |
| Fit principale 10–10.000 s | Implementato, con supporto effettivo dichiarato. Confronti secondari più brevi identificati esplicitamente. |
| Più attenzione open-loop / closed-loop | Diagnostiche e schema geometrico interpretati: l'ordinamento open/closed cambia fra differenza prima e seconda; nessuna decomposizione causale del drift. |
| Ridurre la sezione pesante sull'incertezza | Integrati limiti operativi e conteggi nei metodi; evitare sezioni prive di una domanda scientifica. |
| Quantili: apparato matematico, interesse, autosimilarità e significato delle pendenze | CDF empirica, quantili, esponenti e rapporti definiti; schemi di forma e selezione. |
| Possibile cambio dei voli o dei pesi tra quantili/lag | Quattro controlli: pool disponibile, voli fissi, pesi uguali per volo, origini e pesi fissi; test con controesempio balistico e CDF pesata. **Interpretazione aggiornata:** il contrasto fra quartile inferiore e 90% persiste, ma non c'è ordinamento monotono di tutti gli esponenti. |
| Discesa di H con il quantile: disegni e significato pratico | Rapporti studiati con popolazione, pesi e origini fissi. Il rapporto prima sale, poi scende e risale; la differenza delle pendenze OLS non implica un andamento monotono. |
| Radiale che non riscala, correlazione E/N e PCA | Spiegati struttura congiunta, invarianza del raggio per rotazione e limiti di PCA/whitening. |
| Anisotropia per regione, Pirenei est–ovest | Figure kinematics rigenerate e controllate; Pirenei con forte preferenza est–ovest. Nelle Alpi experts più bilanciati, nei Pirenei ordinamento variabile nel tempo. Nessuna attribuzione univoca a vento o abilità. |
| Beginners/experts e anisotropia | Due proxy comuni: A/B e C/D/CCC. Confronti entro regione; differenze non attribuite automaticamente alla sola abilità. |
| Vento contro orografia; PCA regionale | Relazione velocità al suolo/aria/vento e limiti di identificazione; entrambe le forzanti possono agire su posizione e velocità. |
| Spettro dei momenti del Lévy walk | Riportate le due branche del benchmark superdiffusivo e le ipotesi; evitare esclusioni di varianti non testate. |
| Eliminare tail control e sezioni shape/heading se inutili | Percorsi legacy ritirati; diagnostiche informative integrate nella discussione dei modelli. |
| Autocovarianza su tempi più lunghi e log–log | Velocità mediate a 10/60/300 s; pannelli positivi log–log e pannelli con segno conservato. Non trasformare valori negativi in positivi. |
| Significato del parametro non gaussiano | Eccesso di Mardia centrato con covarianza completa; distinguere gaussianità omogenea da miscele condizionate. |
| Escludere modelli poco adatti con osservabili informative | Predizioni di Browniano, Browniano con drift, fBm, memoria esponenziale e Lévy walk confrontate. Reiezione formale richiede calibrazione finita; non dichiararla senza test. |
| Eliminare ergodicità; durata con conteggi e deduzioni severe | Sezione rimossa; confronto TAMSD per durata con numerosità e limiti. Nessuna indipendenza dedotta dalla sola somiglianza delle curve. |
| Durata × beginners/experts, pendenze e composizione | MSD entro ciascuno dei due gruppi, otto celle, miscela osservata e composizione fissa. **Risultati interpretati:** experts con crescita descrittiva maggiore, differenze di durata anche entro classe; la composizione spiega solo parte del contrasto. |

## Capitolo 4: segmentazione

| Richiesta | Intervento / verifica restante |
|---|---|
| Teoria HMM prima dell'applicazione | Modello generativo, indipendenze, emissioni Gaussiane, forward/backward, posteriori, Viterbi ed EM esplicitati. |
| Matematica e assunzioni coerenti con codice | Controllati preprocessing feature, standardizzazione, aggiornamenti, marginalizzazione della coerenza, transizioni del decoder e condizioni di arresto. |
| Tutti gli indicatori definiti quantitativamente | Coerenza, parametri di emissione, likelihood, posteriori, copertura, precisione/recall/F1 e ablation definiti; schema della coerenza. |
| Serie temporali leggibili, meno minuti | Finestre di otto minuti controllate nel PDF; ridotte a 9 pt le etichette degli assi che si toccavano. Tracciati e fasi invariati. |
| Figure 4.4, 4.5, 4.6 e successive aggiornate | Figure legate al nuovo modello/decoder, con riproduzione dei percorsi verificata. Revisione visiva effettuata e registrata sul manifest SSD. |
| Evidenza quantitativa e grafica del funzionamento | Diagnostiche di plausibilità, copertura, stabilità e ablation; nessuna confusione tra posteriori e accuratezza misurata. |
| Preparare eventuale labeling manuale | Nuovo pacchetto `20260910T221820Z-05d36ab4` pronto: 40 voli, 4/8/8 train/validation/test per disciplina. Checksum locali e identità degli archivi montati controllati; istruzioni aggiornate; l'annotazione resta un'azione umana futura. |

## Figure, repository e consegna

| Richiesta | Intervento / verifica restante |
|---|---|
| Stile professionale simile alla vecchia figura 3.6 | Recuperato il riferimento; palette condivisa, assi sobri e dimensioni di stampa controllate. Passata visiva su tutto il PDF, con correzioni di clipping, etichette e collocazione dei float. |
| Colori coerenti per discipline, esperienza, fasi e regioni | Palette semantiche centralizzate; beginners blu ed experts terracotta in tutti i confronti. |
| Tesi e codice perfettamente allineati | Test con oracoli espliciti, audit delle definizioni e tracciabilità dei prodotti; confronto finale risultati/testo. Nessuna promessa di infallibilità matematica. |
| Documentazione repo accurata, README utile | Guide, README e istruzioni del pacchetto aggiornati allo stato effettivo; build MkDocs strict passato. Chiusura SSD registrata; commit descritti nel piano e nella storia Git. |
| README SSD fedele all'organizzazione reale | Generatore di inventario integrato nel rebuild; aggiornamento finale e rilettura eseguiti sull'SSD ricollegato. |
| Eliminare file inutili con cautela | Rimossi percorsi/report ritirati; non eliminare note o file personali di provenienza incerta. Diff e provenienza controllati per il raggruppamento dei commit. |
| Spiegare roadmap e pacchetto di annotazione | Roadmap = piano condiviso, non input da eseguire. Pacchetto = annotazioni manuali quando richieste, con istruzioni e percorso del run corrente nella consegna. |
| PDF finale e riepilogo delle verifiche | **Chiuso.** PDF compilato, controllato e registrato contro il manifest SSD; identità dei prodotti e del pacchetto verificate. |

## Programma esplicitamente successivo

La richiesta di completare i compiti non anticipa i capitoli che l'autore ha chiesto
di sviluppare più avanti. La roadmap conserva: osservabili per le tre fasi e finestre
di transizione; confronto solo/gruppo con visibilità e leader/seguaci; costruzione di
un modello stocastico fisico e simulazioni Monte Carlo confrontate con dati globali e
condizionati; distribuzione spaziale delle termiche e ottimizzazione di itinerari aperti
o chiusi, prima senza vento, poi con vento ed eventualmente vincoli orografici.
