# Commit previsti per la revisione

Suddivisione delle modifiche dopo il completamento del rebuild e della revisione
contro l'SSD. `commit-groups-2026-09-11.json` registra i percorsi assegnati a ogni
gruppo. Questo documento descrive contenuto e motivazione; la storia Git registra
i commit effettivamente creati. Non è previsto un push.

1. **fix(preprocessing): align GNSS cleaning, reconstruction masks and snapshots**
   Criteri GNSS e witness locale, soglia verticale a 10 m/s, test delle mediane,
   trimming, ricostruzione e propagazione dei flag alle derivate. Include la
   registrazione della definizione del cleaning e le regressioni del preprocessing.
2. **fix(dataset): reconcile rejection counts and rebuild recorder diagnostics**
   Diagnostiche appaiate GNSS/barometro, schemi ed esempi di cleaning, stile comune.
   La cascata include il gate altimetrico e controlla che gli esclusi più i conservati
   restituiscano i tentativi; non confonde la perdita di tutti i segmenti con una
   sola causa. Non modifica le traiettorie per correggere il rapporto.
3. **feat(transport): control sampling, geometry and equipment composition**
   MSD numericamente stabile; quantili con popolazione, pesi e origini fissi;
   differenze seconde, momento di Mardia e memoria a più risoluzioni; bootstrap
   appaiato per regione e confronto durata × equipaggiamento. Ritira i produttori
   sostituiti e conserva predizioni di modello con ipotesi esplicite.
4. **fix(segmentation): audit the decoder and prepare blinded phase validation**
   Supporto delle feature, diagnostici di convergenza, marginalizzazione e regole
   del decoder; figure leggibili e pacchetto cieco legato al nuovo archivio.
   La validazione manuale resta distinta dai posteriori e dalle prove numeriche.
5. **feat(workflow): record full rebuilds and explicit manuscript reviews**
   Rebuild ordinato, controllo di sorgenti e prodotti, uso delle risorse, inventario
   SSD e workflow di review. Il pre-commit verifica lo staging senza rigenerare o
   aggiungere file. L'indice di provenienza segue le tabelle generate e distingue
   le famiglie di macro definite da produttori diversi.
6. **docs(thesis): revise the scientific argument and refresh the manuscript**
   Introduzione, capitoli 2–4, matematica, interpretazione dei risultati freschi,
   riepiloghi, bibliografia verificata, appendici pertinenti, figure e PDF. Nessuna
   indipendenza dalla durata o classificazione del processo è proclamata senza
   evidenza; sono dichiarati i limiti attuali del modello di fase.
7. **docs: align repository guides and preserve the scientific review evidence**
   README, guide, roadmap, stato delle richieste e prove delle revisioni documentali,
   grafiche e del rapporto numerico. Conserva la distinzione fra run originale,
   correzioni posteriori e risultati ancora da validare umanamente.
8. **docs(project): preserve guidance and mark working notes as historical**
   Istruzioni di progetto e materiale preesistente dell'autore, con le note
   preliminari separate dalla documentazione normativa. Preserva i collegamenti
   relativi e i contenuti dell'autore; esclude archivio grezzo e PDF delle fonti.

Lo staging segue questa suddivisione e controlla dipendenze, whitespace e provenienza
dei file. L'archivio grezzo e le copie locali delle opere citate restano esclusi.
Il riepilogo di consegna riporta gli hash ottenuti dalla storia Git.
