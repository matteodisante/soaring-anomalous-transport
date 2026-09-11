# Audit di correttezza e stato dei risultati — 10 settembre 2026

Il cleaning completo è terminato sui file IGC originali con la definizione
2.2.0, dopo il superamento di 329 test mirati su preprocessing, canali, verifica
e riproducibilità. Il lancio usa otto worker e priorità normale, secondo l'ultima
richiesta dell'autore. I thread interni delle librerie numeriche sono limitati a
uno per worker per evitare moltiplicazioni del parallelismo.

Log persistente: `/Volumes/SSD_DISANTE/derived-audit/cleaning/20260910-v2.2.0/cleaning.log`.
**Aggiornamento dell'11 settembre: cleaning e tutti i 38 stadi del rebuild completati.**
Conservati 156.305/186.052 parapendii e 6.093/6.716 deltaplani. I controlli integrali
sulle tabelle sono passati; 250 voli per disciplina sono stati ricalcolati dai file
raw con risultati concordanti alla precisione float32 e flag coincidenti.
La [lettura dei risultati freschi](fresh-results-review-2026-09-11.md) riporta
l'interpretazione attuale. La suite locale conclusiva passa 824 test. La revisione
del PDF e la riconciliazione finale con i manifesti sull'SSD sono concluse dopo
il ricollegamento. Il [verbale conclusivo](manuscript-review-2026-09-11/completion.json)
registra PDF, sorgenti, prodotti e controlli finali.

Le sezioni seguenti conservano la cronologia dei controlli, compresi i loro conteggi
intermedi. Gli stati di avanzamento storici non sostituiscono l'aggiornamento qui sopra.

## Correzioni documentate

- [Capitolo 2](audit-ch2-2026-09-10.md): disponibilità locale del barometro,
  riferimento delle quote GNSS, geometria ENU, supporto ricostruito delle derivate,
  filtro Savitzky–Golay, rumore nell'MSD, selezione dei campioni PSD e verificatore.
- [Capitolo 3](audit-ch3-2026-09-10.md): pesi degli stimatori, formule e ipotesi di
  scala, cancellazione numerica nell'MSD, covarianza/PCA, VACF, spettro dei momenti,
  limiti delle deduzioni sui modelli. I confronti restano descrittivi: non sono
  esclusioni statistiche calibrate di tutte le varianti di un processo.
- [Capitolo 4](audit-ch4-2026-09-10.md): decoder effettivo, supporto delle feature,
  arresto e convergenza del fit, aggiornamento delle covarianze, provenienza dei
  pacchetti di annotazione. Le predizioni non sostituiscono etichette indipendenti.
- [Bibliografia](../docs/guide/bibliography.md): metadati, fonti primarie accessibili
  e inventario locale. Le fonti originali non ottenute sono dichiarate tali.

## Disegni per le equazioni 2.6 e 2.7

Due schemi vettoriali, scritti direttamente nel sorgente LaTeX del capitolo 2,
mostrano la selezione dei midpoint, l'ordinamento dei moduli e la mediana, poi
le due finestre sovrapposte e la condizione AND sul fix. Gli esempi sono sintetici.
La formula operativa ora comprende il fallback sotto cinque passi disponibili.
Il secondo schema mostra esplicitamente che due mediane elevate possono censurare
una quota anche quando entrambi gli incrementi adiacenti sono piccoli: è un test
dell'intorno, non una dimostrazione di errore del singolo fix.

Nel codice, mediana e conteggio ora escludono lo stesso insieme di valori non
finiti: prima `rolling.count()` poteva contare gli infiniti che la mediana ignorava.
I due test mirati su questo caso e sull'esempio delle finestre sovrapposte sono
passati (`/tmp/median-diagrams-tests.log`, 2 test).

Rettificate anche affermazioni residue su selezione dei voli: un plateau della
frazione trattenuta non dimostra assenza di distorsione; poca escursione verticale
non esclude il volo veleggiato; durata registrata e intervallo temporale totale
sono quantità distinte; il limite di raggiungibilità include 50 m di tolleranza
prima di proiezione e smoothing. L'analisi di sensibilità sugli intervalli sospetti
è prevista, ma non è presentata come già eseguita.

## Ricostruzione completa e risorse

Il cleaning è terminato tramite `scripts/preprocess.py --jobs 8`.
La ricostruzione a valle usa:

```bash
uv run python scripts/rebuild_thesis.py --jobs 8 --full-speed
```

La [guida](../docs/guide/rebuilding.md) descrive la sequenza: cleaning, controlli,
osservabili, segmentazione, figure, nuovo pacchetto di annotazione e PDF. I passaggi
sono sequenziali. Il profilo corrente usa otto worker a priorità normale, con un
thread per libreria numerica; il profilo predefinito a un worker resta disponibile.
Non occorre ripetere il cleaning già completato se la sua definizione è invariata. Una coda limitata
riduce anche le allocazioni del preprocessing; i diagnostici più grandi leggono
i cache per blocchi.

Manifesti, versioni, impronte dei sorgenti e identità delle tabelle impediscono al
driver di accettare un archivio vecchio o parziale come nuovo. Una figura richiesta
deve essere riscritta dal proprio produttore nel run corrente. L'identità delle
tabelle usa metadati e footer Parquet: non è un checksum di ogni valore del volo.
Il confronto witness precedente rimane un controllo storico alla soglia di 30 m/s.

La roadmap non richiede operazioni da parte dell'autore. Per il labelling conviene
usare il nuovo pacchetto creato dopo il cleaning, conservando gli eventuali giudizi
già raccolti separatamente; il pacchetto precedente non va assunto compatibile.

I rapporti dei capitoli distinguono i test superati dalle verifiche empiriche
ancora necessarie. I test delle modifiche al workflow hanno verificato anche
archivi sintetici, subprocessi e arresto in presenza di prodotti obsoleti; non
costituiscono un'esecuzione dell'intero archivio reale.

## Controlli e revisione successivi

La suite completa più recente ha eseguito 806 test: 805 superati e una discrepanza
nella documentazione dello schema. È stata corretta la guida, riportando tutti i campi
effettivi, e il test interessato è poi passato. I successivi 51 test mirati sulle
nuove analisi durata/classe, i rapporti, il workflow e l’HMM sono tutti passati. I 24 warning
provengono da una deprecazione NumPy nell'attuale hmmlearn; non sono prove di
convergenza né errori di classificazione.

I rapporti direzionali usano supporto finito appaiato. La curva mostra lo stimatore
sul campione osservato; la fascia contiene i percentili bootstrap puntuali. I conti
per cluster consentono lo stesso bootstrap senza ricopiare tutte le traiettorie a
ogni estrazione: il confronto con un ricampionamento esplicito include gruppi di
dimensione diversa e valori mancanti. Le chiavi vuote producono gruppi singoli;
le tuple di metadati non possono collidere per concatenazione di stringhe.

Su indicazione dell'autore, i confronti per vela usano due gruppi: beginners (EN A/B)
ed experts (EN C/D/CCC). Sono proxy dell'esperienza richiesta dalla vela: la
certificazione non misura l'esperienza individuale e un esperto può volare con A/B.
Regione di decollo, vento, percorso, durata e prestazioni della vela possono
confondere il confronto. La stessa mappa è usata nell'anisotropia e nell'MSD per
durata, con otto combinazioni gruppo/durata. Le figure sono progettate alla larghezza stampata, con
palette condivisa, conteggi di supporto e significato delle bande dichiarato.

Sono stati eliminati la parte tecnica separata, l'appendice sul caso subdiffusivo
e il rapporto sui vecchi diagnostici di durata che non era più citato. Le formule
necessarie per stimare l'HMM sono state conservate nel capitolo 4. I rinvii alla
parte rimossa sono stati tolti anche dalle trascrizioni di revisione, conservando
il resto delle annotazioni. Le note e i file personali di provenienza incerta non
sono stati eliminati.

Il README della repo e le guide sono stati riscritti intorno alla struttura
corrente. La guida ai dati non riproduce più vecchie tabelle come se fossero
lo schema attuale. Il generatore dell'inventario SSD include manifesti, cache,
segmentazione e analisi; la scrittura dell'inventario è parte del rebuild.

## Ultime richieste integrate

- Confronto durata–attrezzatura sull’intero archivio con identità dei segmenti,
  pesi per origini ammissibili dentro ciascun volo e uguale peso tra voli. Test
  indipendenti su segmenti di lunghezza diversa e su una miscela di classi costruita
  appositamente verificano che il controllo rimuova una differenza di composizione.
- VACF positiva in log–log e pannelli firmati separati: nessun valore assoluto delle
  correlazioni negative viene presentato come decadimento positivo.
- Teoria HMM prima dell’applicazione; definizioni matematiche e unità di tutti gli
  assi delle serie temporali, formula di standardizzazione, significato dei punteggi
  numerici e disegno della coherence. Nessuno di questi diagnostici è chiamato accuratezza.
- Riepilogo finale per ciascuno dei quattro capitoli.

## Controllo della popolazione per i quantili

Il primo avvio della ricostruzione a valle è stato interrotto volontariamente durante
la verifica iniziale, per integrare l’ulteriore richiesta sui quantili. Il cleaning
completo è invariato. Il controllo a coorte fissa esisteva per le variazioni, ma non
per i quantili; è stato aggiunto distinguendo appartenenza dei voli, pesi dei voli
e origini temporali. Un controesempio con voli tutti balistici dimostra che l’uscita
dei voli brevi veloci può alterare l’esponente del quantile alto; il controllo recupera
H=1 a ogni percentile. I 22 test mirati su questi stimatori sono passati, compreso un controllo della
stabilità numerica della CDF al confine esatto di massa 1/2 con numeri diversi di origini.

Il verificatore sull’intero nuovo archivio ha superato i controlli strutturali e le
tolleranze cinematiche per entrambe le discipline. Una successiva correzione limitata
ai commenti e alle docstring del cleaner è documentata in
[questa prova di equivalenza](cleaner-documentation-2026-09-10/README.md): AST eseguibile
identico, tutte le altre sorgenti byte per byte identiche, tabelle immutate e manifesti
di esecuzione originali conservati. Non è stato eseguito un secondo cleaning per
modificare la documentazione. La ricostruzione a valle riparte con le descrizioni corrette.

## Verifica consolidata dell'11 settembre

L'ultima suite completa passa **812 test**, con 24 avvisi di deprecazione NumPy
provenienti da hmmlearn, in 46,82 s (`/tmp/full-reviewed-suite-20260911.log`). Le
verifiche mirate successive alla divisione beginners/experts passano; l'ultimo
controllo sui diagnostici altimetrici e i due gruppi passa 55 test. La documentazione
compila in modalità strict. La copia temporanea usata esclusivamente per controllare
l'impaginazione compila senza riferimenti indefiniti o contenuti fuori margine: non
è il PDF empirico finale e include dati sintetici dichiarati per i nuovi pannelli.

La rassegna completa delle richieste è in `request-checklist-2026-09-11.md`. Le classi
sono ora A/B e C/D/CCC, con identica mappa in anisotropia e MSD per durata. Sono stati
corretti anche i testi dei diagnostici di offset che descrivevano una vecchia scelta
mista dei canali o attribuivano impropriamente tutto lo scatter entro sito al meteo.
La figura corrispondente descrive ora scatter entro sito e pooled senza tale
attribuzione e mostra l'intero supporto osservato dell'istogramma.

Sono stati consultati altri originali per le citazioni attive, incluso il manoscritto
del capitolo di Kapos reso disponibile da un coautore. Il record bibliografico distingue
lettura del testo, verifica dei soli metadati e limiti di accesso. Il rebuild a valle è
ancora in corso: nessuna nuova conclusione empirica o completamento viene attestato qui.
