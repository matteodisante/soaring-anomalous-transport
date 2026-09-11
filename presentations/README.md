# Presentazioni per i supervisori

Due presentazioni LaTeX/Beamer in inglese, preparate l'11 settembre 2026 sui
risultati correnti della tesi. Ciascuna ha **18 slide principali per 20 minuti**:
17 minuti e 40 secondi di esposizione, inclusi i passaggi fra slide, e 2 minuti e
20 secondi per le domande finali proposte. Le slide di riserva sono fuori da
questo tempo. Nel capitolo 2 è previsto anche un minuto per la dimostrazione nel viewer.

| Presentazione | PDF da proiettare | Sorgente | PDF con note a fianco |
|---|---|---|---|
| Capitolo 3: trasporto globale | [chapter3.pdf](chapter3.pdf) | [chapter3.tex](chapter3.tex) | [chapter3-notes.pdf](chapter3-notes.pdf) |
| Capitolo 2: dati e cleaning | [chapter2.pdf](chapter2.pdf) | [chapter2.tex](chapter2.tex) | [chapter2-notes.pdf](chapter2-notes.pdf) |

La [scaletta temporale](timing.md) riporta durata e posizione di ogni slide
principale. Le note nel sorgente contengono cosa spiegare a voce e le cautele
necessarie per interpretare il risultato. Il PDF da proiettare ha collegamenti
alle figure di riserva e alle fonti; i collegamenti sono disattivati nella copia
con note per evitare destinazioni PDF duplicate nella doppia impaginazione.

## Impostazione del colloquio

Il capitolo 3 parte dagli stimatori e arriva al confronto fra processi stocastici.
Quantili a popolazione fissa, geometria dei compiti, anisotropia regionale e
durata × equipaggiamento mostrano perché una pendenza dell'MSD non basta a
identificare un processo. La discussione finale propone di scegliere il bersaglio
fisico del modello, i primi confronti calibrati e le misure che richiedono la
segmentazione. Il Lévy walk standard è presentato come un benchmark ancora da
confrontare su traiettorie finite, senza dichiararne un'esclusione già dimostrata.

Il capitolo 2 segue le decisioni che trasformano i fix in traiettorie misurabili.
Mostra esempi reali, la disponibilità locale del witness, il significato dei due
test di velocità verticale, la ricostruzione e lo smoothing. I problemi aperti
includono i salti di quota candidati, la ricostruzione verticale senza limite di
durata e la sensibilità delle osservabili alle scelte operative.

Lo stile riprende `13_06_26_slides_soaring_ctrw.tex` del 13 giugno 2026 nel progetto
`disante_soaring_ctrw`: Palatino, barra blu acciaio, sigillo di Pisa, pagine
bianche e fascia chiara nel titolo. Il formato è 16:9 per lasciare spazio ai
grafici e alle formule. I colori delle popolazioni seguono la versione corrente
della tesi: blu/terracotta per le discipline, viola/ocra per i due gruppi di
equipaggiamento.

## Il pulsante del viewer

Nella **slide 17 del capitolo 2** il pulsante apre `soaring-viewer://open`.
Il relativo handler macOS è già stato registrato e provato su questo Mac.
La prova ha verificato l'avvio del processo Python tramite URL; non simula un
clic dentro ogni possibile lettore PDF.

Il viewer usa il codice corrente di questo checkout. L'applicazione può aprirsi
senza SSD; i voli reali richiedono l'archivio montato. Per l'esempio della slide,
usare **Browse .igc file…** e aprire:

```text
/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2003-2004/2004-03-27_20030236.igc
```

L'intervallo mostrato è vicino a 4410 s dall'inizio del record grezzo. Il viewer
può ricalcolare il preprocessing del solo volo selezionato; il lanciatore non
rigenera l'archivio. I thread numerici sono limitati a uno durante la demo.

Su un altro Mac o dopo aver spostato il checkout:

```bash
uv sync --group viewer
python3 presentations/setup_viewer_link.py
presentations/launch_viewer.command --check
```

Il lettore PDF può chiedere conferma per aprire un'applicazione esterna. Se non
supporta questo collegamento, fare doppio clic su
[launch_viewer.command](launch_viewer.command), oppure eseguirlo dal terminale.
La figura reale è già nella slide e consente di continuare anche senza demo.
Il log dell'avvio è `presentations/viewer-link.log`, ignorato da Git.

L'app `Soaring Viewer.app` è generata localmente e non è versionata. Il suo
handler accetta soltanto l'URL previsto e non esegue il contenuto dell'URL come
comando. Per rimuovere la registrazione locale:

```bash
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -u 'presentations/Soaring Viewer.app'
```

## Compilazione

La compilazione richiede `latexmk` e una distribuzione TeX con Beamer. Usa gli
asset congelati nella cartella, senza SSD, rete o ricalcoli scientifici:

```bash
python3 presentations/build.py all --notes
```

L'ordine è capitolo 3, poi capitolo 2. Per uno soltanto:

```bash
python3 presentations/build.py 3 --notes
python3 presentations/build.py 2 --notes
```

I PDF di consegna vengono scritti in questa cartella; i file intermedi sono in
`build/`, ignorato da Git. Le note sono scritte nei comandi `\timing` dei sorgenti
e sono incluse solo nel PDF con note.

## Figure, numeri e aggiornamenti

Gli asset sono una copia identificata dei risultati già disponibili nella tesi,
inclusa la revisione grafica presente nel working tree al momento della copia.
`source-manifest.json` registra gli hash degli originali, dei pannelli estratti,
delle definizioni e della configurazione. `figure-manifest.json` identifica le
figure ridisegnate per la proiezione usando esclusivamente array dei report
congelati: nessun nuovo fit o confronto simulato è stato aggiunto.

I pannelli ritagliati conservano i vettori PDF originali. Dove l'asse orizzontale
era condiviso fra righe, il ritaglio include anche le etichette dell'asse
originale corrispondente; i limiti sono gli stessi. Gli schemi disegnati in TikZ
sono identificati come esempi, distinti dalle traiettorie reali.

Per aggiornare le figure da una futura versione della tesi, dopo aver verificato
la coerenza dei nuovi risultati:

```bash
# pypdf serve soltanto per preparare i ritagli, non per compilare i PDF.
uv run --no-project --with pypdf python presentations/prepare_assets.py
.venv/bin/python presentations/render_figures.py
python3 presentations/build.py all --notes
```

Questo rinnova gli asset. **Occorre anche rivedere testo, tabelle sintetiche e
note:** alcune interpretazioni e cifre discusse sono intenzionalmente scritte
nel sorgente della presentazione. Un aggiornamento automatico delle figure non
può garantire che quelle frasi rimangano vere. Il sigillo, copiato dalla
presentazione originale, è già incluso e non richiede il vecchio progetto.

Il controllo di consegna è registrato in [validation.json](validation.json).
La rassegna dello stato scientifico resta nel
[registro delle richieste](../revisions/request-checklist-2026-09-11.md).
