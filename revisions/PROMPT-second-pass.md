# Protocollo di revisione da PDF annotato con Skim

> Questo file era il prompt del secondo giro (agosto 2026), che è stato eseguito per intero.
> Lo tengo come **ricetta riutilizzabile** per il giro successivo, aggiornata con quello che
> si è imparato facendolo.

---

## 1. Estrazione (il passo che non va improvvisato)

Skim tiene le note negli **extended attributes**, non dentro il PDF, e il suo export
testuale (`skimnotes get -format text`) perde **sia il colore sia il testo evidenziato** —
cioè le due cose su cui si regge tutto il lavoro.

La catena che funziona è in [`extract_annotations.py`](extract_annotations.py):

```
skimpdf embed        note dagli xattr → annotazioni PDF vere
  → pypdf            /C (colore), /Contents (nota), /QuadPoints (posizione)
  → pdftotext -bbox  testo marcato, per intersezione dei box
  → synctex edit     ancora file:riga nei sorgenti LaTeX
```

```bash
python3 revisions/extract_annotations.py \
    revisions/main_revision_<N>.pdf \
    revisions/<N>_annotations.json revisions/<N>_annotations.md \
    --tex-root=thesis/main.tex
```

**Le ancore SyncTeX valgono solo finché la build è byte-identica al PDF annotato.** Lo
script controlla lo sha256 e le omette altrimenti — quindi vanno estratte *prima* di
toccare qualsiasi cosa, e da lì in poi si ri-localizza con `grep` sul testo marcato.
Rigenerare il digest a lavoro finito produce (correttamente) un digest senza ancore.

Requisiti: Skim installato (`/Applications/Skim.app/Contents/SharedSupport/{skimpdf,skimnotes}`),
`python3` con `pypdf`, poppler (`pdftotext`), TeX Live (`latexmk`, `synctex`).

## 2. Legenda dei colori

Il colore dà la natura dell'intervento, **la nota è sempre l'autorità**.

| colore | significato | azione |
|---|---|---|
| verde | il passo va bene | togli `\rev{}`/`\flow{}`: quel testo diventa nero |
| giallo | forma, riferimenti, punteggiatura | applica |
| arancione | obiezione di sostanza: poco chiaro, da riscrivere, numero da verificare | riscrivi/verifica |
| rosso Highlight | correzione di contenuto, o un task esplicito | applica |
| rosso StrikeOut | testo da cancellare | cancella |
| viola | dubbio metodologico aperto | rispondi in tesi e nel PDF risposte |

Attenzione: **il verde non è sempre un "ok" secco.** Nel secondo giro una nota verde
([180]) conteneva un'osservazione sostanziale. Vanno lette tutte.

## 3. Regole di lavoro

1. Leggi il digest `.md` **dalla prima all'ultima riga** prima di editare. Niente campioni.
2. Modifica solo `thesis/` (più `src/` e `scripts/` quando una nota chiede un cambio di
   codice). **Mai** toccare il PDF annotato.
3. Non committare. Mai il trailer `Co-Authored-By`.
4. Mai numeri di censimento a mano: estendi `generate_census_stats.py` ed emetti una macro.
5. Il testo nuovo si marca `\rev{}` (blu) se nasce da una nota, `\flow{}` (arancione) se è
   solo scorrevolezza. Blocchi lunghi: ambienti `revblock` / `flowblock`.
6. I float **non** ereditano il colore del blocco: dentro `figure`/`table` ri-metti
   `\ifrevmode\color{revblue}\fi`. E `\path{}` si rompe dentro `\caption`: lì usa `\texttt{}`.
7. Il contratto di cleaning vive in tre posti che devono restare allineati:
   `sections/03-dataset.tex`, `appendices/impl/C2-dataset.tex`,
   `docs/guide/preprocessing-pipeline.md`.

## 4. Verifiche finali (automatizzabili, e da fare)

Queste hanno pescato errori veri nel secondo giro — non sono cerimoniali.

- **Cancellature**: per ogni StrikeOut, normalizza il testo (via i comandi LaTeX, minuscole,
  solo alfanumerici) e verifica che **non** compaia più nei sorgenti. *Ha trovato un'annotazione
  che avevo letto come verde e che invece era una cancellatura.*
- **Copertura**: il registro deve contenere tutti gli id da 1 a N, senza buchi e senza celle
  vuote. Verificalo con uno script, non a occhio.
- **Domande**: ogni nota con `?` deve risultare o "chiarito in tesi" o nel PDF risposte.
- **Build**: `latexmk -pdf` con `exit 0`, zero `Overfull \hbox`, zero riferimenti irrisolti.
  Se si aggiungono note vere a una tabella con colonne `l`, va cambiata in `p{}` — altrimenti
  sfora in silenzio.
- **Test**: `pytest` verde, se si è toccato `src/`.

## 5. Output attesi

| file | contenuto |
|---|---|
| `thesis/REVISION-log-<N>.md` | una riga per annotazione, tutte, con l'esito reale |
| `thesis/REVISION-TODO.md` | ciò che resta aperto, raggruppato per cosa lo sblocca |
| `revisions/answers-<N>.pdf` | risposte alle domande non risolvibili in tesi |

## 6. Cose che si scoprono solo facendolo

- Le note possono contenere **task in due passi** che vietano di editare prima
  dell'approvazione ("do not edit anything before I approve Step 1"). Vanno rispettate:
  si produce il report e ci si ferma.
- Le fonti non sono tutte uguali. Il **FAI Sporting Code** è pubblico e scaricabile; una
  **norma EN** è un documento venduto dagli enti nazionali (AFNOR, DIN, BSI) a qualche
  centinaio di euro, e non si può citare il testo autoritativo. Ripiego accettabile: il
  *final draft* diffuso pubblicamente da CEN, dichiarando lo scarto.
- Quando una nota dice "sono sicuro di questo numero?", la risposta utile è quasi sempre
  *da dove viene* il numero, non una rassicurazione.
- **Attenzione agli heredoc in bash**: `<<PY` non quotato fa espandere i backtick del
  contenuto, che in un testo pieno di `` `codice` `` significa eseguire frammenti a caso.
  Usa sempre `<<'PY'` e passa i parametri via variabili d'ambiente.
