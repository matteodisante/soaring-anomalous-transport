# Verifica dello spazio SSD — 12 settembre 2026

La richiesta è individuare cosa può essere eliminato. Cancellazioni eseguite: **nessuna**.
L'archivio e il run corrente sono preservati. Dimensioni in GiB (2^30 byte).

Il confronto SHA-256 ha confermato **4,24 GiB di copie identiche** fra SSD e
recupero locale. Insieme alle cache generali, i candidati al recupero sono circa
**4,92 GiB**. Rimuovere una copia SSD lascerebbe quella locale come copia di lavoro;
i percorsi storici andrebbero registrati come ritirati dopo la consegna verificata.

| Voce | Spazio | Valutazione |
|---|---:|---|
| 15 cache direttamente in `derived-audit/` | 0,67 | Cache generali di elaborazioni precedenti, estranee al run corrente. Sono il primo candidato da ritirare. L'elenco preciso è in `ssd-general-cache-candidates.json`. |
| Copie sul disco duplicate nel recupero locale | 4,24 | Identità completa dei byte verificata nuovamente con SHA-256, inclusi i due array ricreati localmente. Conservare la copia locale e registrare il nuovo percorso. |
| Precedente indice della cache del run interrotto | 0,02 | Differisce dall'indice locale aggiornato; non è incluso nei duplicati certificati. |
| Array collegati dal run corrente | 10,47 | Necessari: 124 file sono ancora raggiunti tramite collegamenti simbolici dal recupero locale. Non rimuoverli. |
| Snapshot del precedente run completo | circa 0,61 | Provenienza storica identificata, con il suo campione; non è classificato come spazio inutile. |
| `uni_other stuff/` | 25,71 | Cartella personale, misurata senza esaminarne il contenuto. La sua utilità non è stata valutata. |

La cartella SSD `derived-audit/runs/20260911T213634Z-7b7367f1` risulta fallita
nel manifest, ma contiene gli array riusati dal nuovo run. **Non va cancellata
come se fosse un tentativo abbandonato.** I file non più collegati richiedono
comunque il controllo puntuale sopra descritto, dopo la consegna verificata.

I file grezzi occupano circa **11,86 GiB in più della loro dimensione logica**
per l'allocazione sul filesystem exFAT. Non sono file temporanei rimovibili:
liberare questo spazio richiederebbe cambiare la disposizione o il formato di
archiviazione, con conseguenze per lettura e ricostruzione dei dati. Nessuna
modifica del formato o del disco è proposta durante il run.

I grezzi, i cataloghi, i quattro file del cleaning, le fasi correnti e i manifest
sono dati di lavoro o prove di provenienza. Le cartelle di sistema `.Trashes` e
`.Spotlight-V100` non sono leggibili da questo processo; non è stata stimata la
loro dimensione e non sono state modificate.

I dettagli misurati e i percorsi delle copie sono in `ssd-space-review.json`;
`ssd-duplicate-verification.json` contiene gli hash aggiornati di entrambe le copie.
`ssd-space-raw-inventory.json` distingue dimensione logica e spazio allocato.
