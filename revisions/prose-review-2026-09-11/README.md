Seconda revisione disponibile in [`second-pass/thesis-prose-review.pdf`](second-pass/thesis-prose-review.pdf), copiata anche nel PDF principale. Dettagli e stato del ricalcolo in [`second-pass/README.md`](second-pass/README.md).

# Revisione della prosa dei capitoli 2 e 3

Rivisti `thesis/sections/03-dataset.tex` e `thesis/sections/04-global-transport.tex`: frasi e didascalie più brevi, condizioni matematiche per le regole di pulizia, distinzione fra quantili, collasso e distribuzioni congiunte. Conservati tutti i richiami alle figure, gli input generati, le etichette e le citazioni. Precisati il cambio di fase dove la risposta Savitzky–Golay è negativa e l’indipendenza dal moto necessaria nella decomposizione del rumore dell’MSD.

`thesis-prose-review.pdf` è una copia di lettura e controllo dell’impaginazione: 109 pagine, compilazione riuscita senza warning, riferimenti irrisolti o overfull box. TeXcount misura 18.002 → 12.915 parole di corpo (−28%); includendo titoli e didascalie, 22.549 → 16.715 (−26%). Controllate visivamente sei pagine con formule, distribuzioni e nuove didascalie.

Durante questa revisione era già attivo il ricalcolo completo `20260911T204919Z-a9801d6d`. Il PDF separato usa gli input salvati dello snapshot 2.2.0; non attesta il completamento del ricalcolo né i risultati dell’intero archivio aggiornato. Il titolo del PDF segnala questo stato. La revisione del testo è nei sorgenti principali e sarà inclusa anche nella compilazione del ricalcolo. Il precedente `thesis/main.pdf` è stato conservato.

Due figure congiunte già richiamate dal testo mancavano sul disco. Sono state calcolate solo nella copia isolata, dalla cache immutabile del run completato `20260910T221820Z-05d36ab4`. Verificati hash della cache, identità dei 107 voli di parapendio e 56 di deltaplano, 157.493 e 82.774 origini, tutti i quantili ai sei lag mostrati e la normalizzazione delle masse congiunte. `joint-proof.json` conserva risultati e provenienza; `proof.json` identifica PDF, sorgenti e input della copia di lettura. Nessun prodotto numerico del ricalcolo attivo è stato sostituito.
