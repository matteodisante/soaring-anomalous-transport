# Seconda revisione: leggibilità della pagina

Capitoli 2 e 3 ristrutturati nei punti ancora troppo densi: formato IGC, classi, altitudine, pulizia e selezione, geodesia, campionamento, confronti regionali, quantili e memoria della velocità. I confronti numerici ora usano tabelle brevi; le regole di selezione e i limiti matematici sono separati dalla prosa. Paragrafi distanziati di 4 pt nei soli due capitoli; grafici dei quantili e della memoria anticipano la discussione dei risultati.

`thesis-prose-review.pdf` è la copia stabile di questa revisione, riportata anche in `thesis/main.pdf`. Conservato il PDF principale precedente in `previous-main.pdf`. Compilazione riuscita (110 pagine), senza riferimenti irrisolti né overfull box; controllo visivo sulle pagine modificate. Rimangono i precedenti avvisi underfull nel materiale esterno ai due capitoli. Conservati tutti i nomi delle macro numeriche, i richiami alle figure, gli input, le etichette e le citazioni.

La copia usa gli input congelati dello snapshot 2.2.0 della prima revisione, comprese le due figure congiunte documentate in `../joint-proof.json`. Il titolo e il flag locale `StatSnapshotCurrent=0` segnalano che i numeri precedono l'ultima revisione delle regole. Nessun output numerico del ricalcolo è stato sostituito.

Il ricalcolo `20260911T204919Z-a9801d6d` si è fermato al termine di `raw_diagnostics` perché il controllo di provenienza include i sorgenti LaTeX, modificati durante l'esecuzione. Verificato che l'hash delle sorgenti numeriche era invariato. A testo definitivo è stato riavviato lo stesso comando, `scripts/rebuild_thesis.py --jobs 8 --full-speed`, senza ripetere la pulizia. PID, comando e log sono in `rebuild-resume.json` e `rebuild-resumed.log`. Il ricalcolo in background aggiornerà il PDF principale alla propria conclusione; questa copia di revisione rimane disponibile.

`proof.json` identifica sorgenti, input e PDF. Le copie `.tex` e i diff conservano la revisione indipendentemente da successive modifiche.
