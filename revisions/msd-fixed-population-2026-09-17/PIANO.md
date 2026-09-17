# Capitolo 3: piano di implementazione concordato e precisazioni scientifiche

Aggiornato il 17 settembre 2026. Questo file consolida la conversazione e sostituisce
le proposte precedenti su origini comuni, soglia 0.5 e confronti estesi di cadenza.
La chat resta la fonte delle richieste; questo documento è il riferimento operativo.
Stato: implementazione autorizzata. Il 17 settembre l’utente richiede anche il fit
log--log globale 10--10000 s, risultati elaborati su SSD per ridisegno immediato e
commit del lavoro. I numeri dei vecchi risultati restano provvisori.

## 1. Consegna e stile

- Scrivere il nuovo capitolo 3 nella tesi (`main.tex` / `main.pdf`), rispettando
  la separazione attuale fra tesi e volume `esperimenti`.
- Conservare in rosso i passaggi originali di `esperimenti` recuperati nella tesi,
  con rimando alla nuova sezione. La nuova versione resta nel colore normale.
  Usare etichette/riferimenti distinti per evitare collisioni fra i documenti.
- Non trasferire automaticamente ogni sezione di `esperimenti`.
- Stile inglese da paper di fisica: asciutto, matematico, motivazioni concrete,
  definizioni leggibili. La sequenza deve collegare domanda, osservabile, misura
  e interpretazione. Evitare ripetizioni e contrapposizioni retoriche inutili.
- Esplicitare perché ogni analisi risponde a una domanda fisica. La motivazione
  può precedere o seguire la figura secondo il ragionamento.
- Mantenere separati parapendii e deltaplani. Lo studio circuito × quota oggi
  disponibile è sui parapendii; non trasferirne conclusioni ai deltaplani senza dati.
- Preservare le modifiche concorrenti. Rileggere i file correnti prima di editarli.

## 2. Struttura narrativa e figure

1. **Mean-square displacement**: definizione equal flight; ensemble riferito
   all'origine dopo trimming e TAMSD; supporto; scelta della popolazione fissa;
   immediato confronto delle coorti per mostrare l'effetto della selezione.
2. **Transport by circuit type and initial altitude**: due pannelli, open e
   closed, ciascuno suddiviso nelle quattro fasce di quota. Numeri e percentuali
   dei gruppi, ampiezze e pendenze, significato della miscela complessiva.
3. **Anisotropy and principal directions**: solo segnaposto. Nessuna nuova
   implementazione PCA/anisotropia in questa fase.
4. **Scaling of displacement distributions**: sottosezioni su quantili,
   rapporto Q25/Q90, spettro dei momenti, eccesso di kurtosi, sintesi sullo scaling.

Ogni figura deve distinguere i valori effettivamente calcolati (marcatori) dalle
linee che li collegano. Griglie identiche quando si confrontano pendenze.

## 3. Tempi, cadenza e interpolazione

- La MSD descrittiva conserva i lag 1, 2, ..., 10 s già presenti nei dati salvati,
  proseguendo ai lag maggiori con passo circa logaritmico. Verificare il supporto
  nativo e i lag effettivi: non attribuire una misura a un lag non risolto.
- M(0)=0; lo zero non si disegna su un asse logaritmico.
- Il blocco principale controllato copre 10--10000 s. Usare i 31 lag della
  griglia attuale di scaling, aggiungendo 100 e 1000 s esatti: 33 lag complessivi.
  Esportare sempre la lista effettiva e l'intervallo di ogni fit.
- Per il blocco principale usare coordinate su griglia comune di 10 s,
  entro ciascun segmento, con cadenza nativa non superiore a 10 s. Interpolazione
  lineare per i tempi non coincidenti con un fix della traiettoria pulita.
  Mai attraversare gap o extrapolare. Questo permette confronti agli stessi lag
  e riduce il costo. Non equivale a una media su blocchi di 10 s.
- Esempio da capire e descrivere brevemente: con cadenza nativa 8 s il valore
  a 10 s si interpola fra 8 e 16 s; scegliere 10 s non crea un'osservazione diretta.
- I lag sotto 10 s della figura generale usano soltanto dati con risoluzione
  sufficiente. Dichiararlo brevemente. Non ricampionare l'intero archivio a 1 s.
- Non eseguire il confronto supplementare griglia 1 s contro griglia 10 s.
- Contare, per disciplina e popolazione: N_grid, N_exact (tempi coincidenti con
  fix puliti), N_interp = N_grid-N_exact, e N_interp/N_grid. Dare anche il numero
  di fix di partenza se utile, senza confonderlo con il denominatore sulla griglia.
  La frazione attesa piccola va misurata, non assunta. La coincidenza si verifica
  sui timestamp, includendo la fase della griglia, non solo sulla cadenza dichiarata.
- Distinguere questa nuova interpolazione da quella già compiuta nella pulizia:
  un fix esistente nella traiettoria pulita non è necessariamente una lettura grezza.
  Usare i flag disponibili per documentare separatamente tale provenienza.
- Prima di riusare cache native, verificare la compatibilità con la nuova soglia
  0.8: le curve vecchie troncate a T/2 non contengono tutti i lag ora richiesti.

## 4. Stimatore equal flight e popolazione

Per il volo f, n_f(tau) conta gli incrementi entro i segmenti selezionati.
R_fi(tau) è la loro lunghezza orizzontale.

\[
m_f(\tau)=\frac1{n_f(\tau)}\sum_iR_{fi}(\tau)^2,
\qquad M_2(\tau)=\frac1N\sum_fm_f(\tau).
\]

Il volo è l'unità che si intende rappresentare: ognuno ha peso totale 1/N.
Non definire formalmente equal segment ed equal window nel nuovo capitolo.
La media temporale usa la convenzione ordinaria entro ciascun segmento; basta
definirne formula e discretizzazione, senza una discussione ripetuta sulle origini.
Le origini non sono fissate fra lag. Non conservarne solo l'intersezione.

Per la coorte principale imporre tau_max <= 0.8 T_s. Con tau_max=10000 s,
ogni segmento selezionato dura almeno 12500 s sulla griglia effettivamente usata.
Un volo entra se possiede almeno un segmento ammissibile. Usare solo i segmenti
ammissibili a tutti i lag, mantenendo identità dei voli e dei segmenti fisse.
Esempio breve da includere: in un volo con segmenti di 14000 e 3000 s, la coorte
principale usa solo il primo anche al lag di 10 s. Non allineare fasi fisiche di
voli diversi e non cambiare il trimming.

La soglia 0.8 conserva un margine di origini al lag massimo e ammette più voli
della soglia precedente. Nessun confronto con 0.5. Le finestre sovrapposte non
sono osservazioni indipendenti.

Salvare gli ID di voli e segmenti, i criteri di ammissione e le griglie. Questo
manifest unico è condiviso da MSD controllata, quantili, momenti e kurtosi.
La coorte non cambia se si restringe il solo intervallo di fit.

## 5. MSD generale, ensemble e interpretazione iniziale

- Figura generale: ensemble all'origine conservata dopo il trimming della fase
  di decollo, e TAMSD equal flight. Verificare che coordinate e clock del calcolo
  corrispondano davvero a quell'origine; non rietichettare una convenzione diversa.
- Ensemble: disegnare media, mediana e fascia empirica fra 5° e 95° percentile
  degli spostamenti quadratici dei voli. È dispersione fra voli, non una banda
  di confidenza sulla media. Distinguere questo uso dei percentili dalle bande
  bootstrap delle altre figure.
- Tabella di supporto per disciplina e stimatore a 10, 100, 1000, 10000 s e
  all'ultimo lag/tempo mostrato, indicando anche il valore di quest'ultimo.
- Chiamarla media empirica d'ensemble dell'archivio. Condizioni eterogenee non
  invalidano matematicamente una media d'ensemble: possono definire una miscela.
  Non presentarla come ensemble di un unico processo omogeneo a condizioni fissate.
  La disponibilità variabile col tempo può cambiare anche la miscela rappresentata.
  Un numero di campioni variabile da solo non prova un bias: conta se la selezione
  della durata è informativa rispetto agli spostamenti.
- Verificare sui nuovi risultati il tratto iniziale circa balistico di 10--20 s
  e il successivo minimo di pendenza locale indicato dall'utente intorno a 600 s.
  Precisare se diminuisce la MSD stessa o la sua pendenza: non confonderle.
- Interpretazione fisica da sviluppare: ricerca di ascendenza e prima salita
  limitano l'avanzamento orizzontale; la successiva ripresa della pendenza è
  compatibile con il ritorno al gliding. In questa lettura il minimo vicino a
  600 s fornisce una stima grossolana del tempo tipico necessario per completare
  ricerca e prima salita dopo l'origine conservata. Presentare questa stima
  euristica con il suo argomento fisico, distinguendola dalla durata misurata
  direttamente con le etichette di fase e dalla media statistica delle durate.
  Non fissare il valore a 600 s se il nuovo calcolo colloca altrove il minimo.
- Media sopra mediana: contributo rilevante dei grandi spostamenti alla media.
  Percentili puntuali bassi non tracciano una stessa sottopopolazione nel tempo:
  non inferire dalle sole bande la pendenza individuale dei voli di rango basso.
  La separazione dei voli dopo il tratto iniziale può essere descritta se osservata.

## 6. Effetto della selezione, subito dopo la popolazione fissa

Confrontare tre coorti annidate con identiche regole salvo il lag massimo:

| Coorte | Lag massimo | Durata minima segmento con criterio 0.8 |
|---|---:|---:|
| breve | 100 s | 125 s |
| intermedia | 1000 s | 1250 s |
| principale | 10000 s | 12500 s |

I requisiti già imposti dalla pulizia rimangono applicati. La coorte breve
contiene i segmenti lunghi e ne aggiunge di corti; aggiunge sia nuovi voli sia,
possibilmente, altri segmenti di voli già inclusi nella coorte principale.
Mostrare MSD, rapporti, conteggi e pendenze sugli stessi lag condivisi. La domanda
è quanto il requisito di supportare grandi lag modifichi l'osservabile a piccoli lag.
Non cucire curve di coorti diverse. Accoppiare il bootstrap perché i campioni
si sovrappongono. Le coorti brevi non sostituiscono quella principale nello scaling.

Motivazione fisica concreta: la selezione può cambiare la proporzione di voli
locali/circuiti e voli di distanza, o di siti e attrezzature; non basta dire che
ogni volo è diverso. Verificare i cambiamenti di composizione disponibili nei dati.

## 7. Open/closed e quota: ampiezza, crescita, composizione

- Solo due pannelli principali: open e closed, ognuno con Plains (<300 m), Hills
  (300--800 m), Low mountains (800--1500 m), High mountains (>=1500 m).
  Le classi derivano dalla quota iniziale GNSS pulita, non dal rilievo attraversato.
- Riportare N_open, N_closed, quote percentuali e non classificabili, sia nella
  popolazione candidata sia nella coorte effettivamente analizzata. Tabella
  per ogni cella circuito × quota con numero di voli e gruppi sito--giorno.
- Stesso criterio di supporto e stessi intervalli di fit in tutti i confronti.
  Se un gruppo è scarsamente supportato, riportarlo senza cambiare di nascosto
  popolazione o fit. Eventuali risultati su intervalli più corti sono aggiuntivi.
- Verificare, senza imporli, i precedenti ordinamenti: open Plains/Hills con H_eff
  maggiore delle fasce montane; closed più vicini fra fasce e inferiori a open.
  H_eff=alpha/2 è una pendenza efficace del secondo momento nell'intervallo dichiarato.
- Separare ampiezza (per esempio M_2 a 10000 s) e crescita (alpha/H_eff).
  Quantificare differenze di pendenza con bootstrap accoppiato dei contrasti.
  Bande marginali sovrapposte/non sovrapposte non sostituiscono questo calcolo.
- La media complessiva è una miscela: per una partizione esaustiva,
  M_all(tau)=sum_g (N_g/N) M_g(tau). Includere sconosciuti/fasce mancanti, oppure
  circoscrivere esplicitamente l'identità alla sottopopolazione classificabile.
  Non dire che l'esponente complessivo è la media aritmetica degli esponenti:
  per pendenze locali alpha_all=sum_g [(N_g/N)M_g/M_all] alpha_g.
- Interpretare la geometria closed come possibile vincolo sull'avanzamento alle
  scale paragonabili alla durata del circuito. La classe è dichiarata nel catalogo,
  non una garanzia di chiusura esatta del segmento conservato.
- Discussione dell'orografia: una differenza confermata di pendenza è una
  differenza nella crescita del momento, non solo nell'ampiezza; l'associazione
  con le fasce di quota non isola causalmente orografia, meteo, piloti e attrezzatura.

### Vento: precisazione da inserire brevemente

Se X=Y+u tau con deriva costante u,

\[
\langle|X|^2\rangle=\langle|Y|^2\rangle+
2\tau\,u\cdot\langle Y\rangle+|u|^2\tau^2.
\]

Anche un vento costante può cambiare la pendenza della MSD non centrata, producendo
un contributo balistico. Per la covarianza centrata una stessa traslazione deterministica
si cancella. Derive diverse fra voli possono invece ampliare anche la miscela centrata.
Un campo di vento variabile può cambiare le correlazioni della velocità e lo scaling.
Questa sezione non stima né separa quantitativamente il contributo del vento.

## 8. Una misura empirica comune per quantili e momenti

Per ogni lag, dare a ogni incremento il peso w_fi(tau)=1/[N n_f(tau)].
Il peso totale del volo è sempre 1/N; cambia soltanto la sua ripartizione fra
finestre quando cambia n_f. Stessi incrementi e pesi per tutte le osservabili.

Per una quantità non negativa Y, definire:

\[
\widehat F_{Y,\tau}(y)=\frac1N\sum_f\frac1{n_f(\tau)}
\sum_i\mathbf1\{Y_{fi}(\tau)\le y\},\qquad
Q_{Y,p}(\tau)=\inf\{y:\widehat F_{Y,\tau}(y)\ge p\}.
\]

Spiegare la costruzione: frazione entro ciascun volo, poi media fra voli.
Non fare la media dei quantili individuali. Non aggiungere spiegazioni ovvie sui
nomi dei percentili. Usare l'inversa della ECDF pesata senza interpolare i ranghi.

### Quantili e rapporto

- Studiare Y=|X_E|, |X_N| e R. Le componenti assolute descrivono l'ampiezza per
  direzione e permettono fit logaritmici positivi; R descrive l'ampiezza complessiva.
- Q_p(|X_E|) seleziona una regione vicina a zero dello spostamento con segno,
  non necessariamente al centro della sua distribuzione se c'è deriva. La relazione
  P(|X|<=a)=P(-a<=X<=a) chiarisce il significato; non equivale a Q_p(X).
- Probabilità .25, .50, .75, .90. Curve, esponenti H_p e Q25/Q90.
- Scrivere d log(Q25/Q90)/d log(tau)=H25(tau)-H90(tau); per OLS con stesso
  asse e stessi pesi di fit la pendenza del log-rapporto è la differenza delle
  pendenze. Non trattare rapporto ed esponenti come prove indipendenti.

### Spettro dei momenti

- Scelta di coerenza: calcolare lo spettro per le stesse tre quantità |X_E|,
  |X_N| e R. Riutilizzare gli incrementi già disponibili senza nuove traiettorie
  o array persistenti. R resta il riferimento per la MSD complessiva.
- Ordini q = .25, .5, .75, 1, 1.5, 2, 2.5, 3, 3.5, 4, salvo problemi di
  supporto numerico esplicitamente documentati; nessun ordine negativo.
- Per ogni q, costruire M_q,Y(tau)=sum_f mean_i(Y_fi^q)/N, stimare
  log M_q,Y=a_q+zeta_Y(q) log tau, poi disegnare zeta_Y(q) contro q.
  Confrontare con zeta=qH e, se utile, mostrare zeta/q per leggere le differenze.
- Spiegare che R è la norma, invariante per rotazione, valida anche senza isotropia.
  M_2,R=M_2,E+M_2,N; verificare questa identità e la coincidenza con la MSD.
- Mostrare tutto 10--10000 s e riportare sempre anche il fit OLS log--log
  globale su questo intervallo, con un unico esponente efficace e banda bootstrap.
  Diagnostica delle leggi di potenza prima di interpretare
  lo spettro. Eventuali fit in sottointervalli usano sempre la stessa popolazione
  e gli stessi intervalli per tutte le quantità comparate. Nessuna scelta del fit
  per forzare linearità, curvatura o un ordinamento desiderato.

### Eccesso di kurtosi

- Calcolare ai medesimi lag soltanto sulle componenti con segno X_E e X_N:
  K_j(tau)=mu_4,j(tau)/mu_2,j(tau)^2-3. Centraggio alla media complessiva
  pesata della componente a quel lag, non centraggio separato di ogni volo.
- Motivazione: confronto delle distribuzioni marginali degli incrementi con una
  gaussiana, per cui K=0. |X_j| non è gaussiano anche se X_j lo è; lo stesso
  problema rende improprio usare zero come riferimento gaussiano per il raggio.
- K diverso da zero, se la stima è affidabile, esclude la gaussianità di quella
  marginale. K=0 non la dimostra. Due marginali gaussiane non dimostrano una legge
  congiunta gaussiana né un processo gaussiano. La miscela di voli con medie e
  varianze diverse può produrre eccesso anche con leggi condizionate gaussiane.
- K costante con lag è compatibile con una famiglia di scala; non è richiesto K=0
  per la self-similarity. Alta sensibilità del quarto momento agli eventi rari.

### Interpretazione dello scaling

Distinguere l'evidenza per una famiglia di distribuzioni a un lag dalla self-similarity
del processo, che vincola anche distribuzioni congiunte a più tempi. Pochi quantili
e momenti non determinano una legge completa. L'applicazione agli incrementi mediati
su origini diverse richiede attenzione alla stazionarietà: il campione fisso non
la impone. Esprimere il risultato fisico osservato con precisione, senza trasformare
ogni conclusione in una lista di cautele. Conservare i test temporali non trasferiti
nel volume esperimenti; non introdurre ora una nuova campagna di test.

## 9. Bootstrap e significato delle fasce

- Bande centrali fra 5° e 95° percentile delle repliche: livello nominale 90%.
  Puntuali per lag, distinte dallo scatter dei voli nella figura ensemble.
- Cluster = stesso sito di decollo e stessa data. Non è richiesta indipendenza
  fra voli nello stesso cluster, né fra finestre dello stesso volo.
- Estrarre G cluster con reinserimento, mantenendo tutti i loro voli. Ogni copia
  di volo mantiene pari peso; non dare pari peso alle medie dei cluster.
- Usare gli stessi conteggi di estrazione attraverso lag, osservabili, coorti
  annidate e gruppi confrontati. Ricalcolare quantili, rapporti, kurtosi e fit.
- B=1000 repliche iniziali con seme registrato. Non rileggere traiettorie per
  replica: usare riepiloghi/per-flight ECDF o riduzioni ordinate compatte. Quantili
  esatti pesati, evitando medie di quantili come scorciatoia.
- Esporre formula/algoritmo una volta alla prima banda. Interpretazione frequentista:
  sotto le ipotesi, la procedura ha copertura approssimata 90% per il parametro a
  ciascun lag in ripetuti campioni; non significa 90% dei voli o probabilità 90%
  assegnata al valore vero già fissato.
- Valutazione contenuta dell'adeguatezza: N, G, numero di siti e date, distribuzione
  delle dimensioni dei gruppi; distanza dal sito più vicino attivo nello stesso
  giorno e intervallo dalla data osservata precedente nello stesso sito, dove definiti.
  Riportare mediane/intervalli e le frazioni di gruppi privi di confronti.
  Descrivono separazione geografica/temporale, non provano indipendenza meteorologica.
- Verificare gruppi dominanti e chiavi mancanti; conteggiare i singleton introdotti
  per metadati assenti. Le ipotesi includono gruppi sufficientemente numerosi,
  campionamento rappresentativo dello stimando e regolarità/stabilità delle statistiche,
  oltre all'indipendenza approssimata fra cluster. Nessuna mega-analisi aggiuntiva.
- Se G è piccolo o le repliche sono instabili, rendere visibile la limitazione.
  Confrontare direttamente i contrasti di esponente e ampiezza, non solo le bande
  marginali. Non dichiarare indipendenza verificata dalle sole distanze fra siti.

## 10. SSD: pulizia e conservazione

Il 17 settembre l'utente ha autorizzato il ritiro delle cache SSD degli esperimenti,
conservando PCA/anisotropia e subordinando la pulizia al funzionamento completo del
viewer. Restano protetti raw, cataloghi, dati puliti, trimming, segmentazione e
input del capitolo 2. Questa indicazione sostituisce la precedente pulizia graduale
legata al trasferimento delle sezioni nella tesi.

Sono stati rimossi 146 file di cache e 146 metadati AppleDouble: vectors/owners,
scaling-values, vecchie curve MSD e altre cache generali degli esperimenti. Sono
stati rimossi anche i 248 link locali diretti ai file ritirati. Gli originali,
le coordinate e gli indici dei segmenti, gli audit cinematici, gli input ambientali,
i riepiloghi PCA/anisotropia e i prodotti del viewer restano disponibili.
Le coordinate e gli audit condivisi restano sotto `derived-audit`: non cancellare
l'intera cartella né interpretare il fallimento del vecchio run come assenza di
contenuti utili.

`generate_regional_pca.py` ricalcola la PCA dalle sole coordinate, senza aprire
le cache ritirate. La nuova esecuzione è stata confrontata con i risultati
preesistenti per entrambe le discipline. Il comando generale `--reuse` delle
vecchie analisi di trasporto richiederà invece la ricostruzione delle cache.
Le figure e i documenti già generati rimangono nel repository.

Elenco dei file, impronte SHA-256, spazio recuperato e controlli prima/dopo:
`SSD-PULIZIA-ESITO.md`, `SSD-PULIZIA-ESECUZIONE.json`,
`SSD-PULIZIA-SUPPLEMENTO.json`, `viewer-before.json`, `viewer-after.json`.
Il preventivo iniziale è conservato come documento storico.

## 11. Ordine di esecuzione e verifiche

1. Rileggere lo stato concorrente, AGENTS e domain docs; fotografare input e dipendenze.
2. Correggere la modifica preliminare a `self_similarity.py` iniziata prima dello stop:
   il suo helper di origini comuni e soglia 20000 s non è il contratto ora concordato.
   Usare il backup `before/` per isolare le sole modifiche di questa sessione.
3. Implementare contratto unico per coorti, lag, interpolazione e pesi, con controlli
   significativi su gap, composizione e identità della MSD/momento q=2.
4. Generare figura generale, tabella supporto, coorti annidate e tabella interpolazione.
5. Generare circuito × quota, conteggi e contrasti bootstrap. Scrivere i risultati
   in funzione delle nuove stime, senza recuperare automaticamente quelle vecchie.
6. Generare scaling su una popolazione unica: quantili, rapporti, tre spettri e due
   kurtosi. Esportare curve, supporto, fit, repliche ridotte/contrasti e provenienza.
7. Scrivere/integrare il capitolo 3, inserire segnaposto anisotropia, marcare gli
   originali in rosso. Conservare link esterni e numerazione dei due volumi.
8. Test mirati delle identità statistiche, controllo macro e cross-reference;
   compilare entrambi i PDF e renderizzare le pagine modificate per verifica visiva.
9. Pulizia SSD già completata e verificata: mantenere le esclusioni documentate
   nella sezione 10. Progettare i nuovi calcoli con memoria e file temporanei
   limitati, senza ricreare automaticamente tutte le vecchie cache ritirate.

### Verifiche iniziali ancora da eseguire

- Censire voli, segmenti e gruppi sito--giorno delle coorti e delle otto celle
  circuito × quota prima di valutare la precisione ottenibile nei confronti.
- Precisare e registrare gli intervalli dei fit dopo la diagnostica delle curve:
  l'intervallo osservato 10--10000 s non implica una singola legge di potenza.
  Confrontare esponenti soltanto su intervalli comuni alle quantità interessate.
- Misurare su una prova limitata tempi e memoria del calcolo dei quantili pesati
  e del bootstrap, mantenendo il contratto statistico concordato. Si tratta di
  verifica del costo computazionale, senza una nuova analisi di sensibilità
  della cadenza o una modifica della popolazione dei risultati definitivi.

## Riferimenti metodologici

- [NIST: definizione di kurtosi ed eccesso](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35b.htm).
- [Cameron e Miller: dipendenza entro cluster, numero di cluster e bootstrap](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015.pdf).
- [Mura e Mainardi: self-similarity e distribuzioni congiunte](https://arxiv.org/html/0711.0665v1).
