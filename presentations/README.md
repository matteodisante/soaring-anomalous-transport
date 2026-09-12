# Presentazioni dei capitoli 2 e 3

Queste presentazioni raccontano la tesi revisionata il 12 settembre 2026, con
cleaning 2.3.0 e risultati del run completo `20260912T133040Z-073601cb`, con
PCA regionale calcolata a 10, 100, 1000 e 10.000 s e documentata nella revisione
`regional-pca-lags-2026-09-12`. L'estensione
`regional-variations-2026-09-12` aggiunge differenze seconde e terze regionali,
covarianze direzionali, distribuzioni e controlli della popolazione.
Sono capitoli da discutere con i supervisors, senza durata prestabilita.
Le domande scientifiche accompagnano i risultati; i confronti tra versioni
precedenti della pipeline non fanno parte delle slide.

| Documento | Slide | Versione con note |
|---|---:|---|
| [Capitolo 2](chapter2.pdf) | 58 | [PDF con note](chapter2-notes.pdf) |
| [Capitolo 3](chapter3.pdf) | 85 | [PDF con note](chapter3-notes.pdf) |

L'[indice](outline.md) riporta l'ordine e le pagine. I PDF con note affiancano
alla slide le spiegazioni su stimatore, popolazione, limiti e interpretazione.

Il capitolo 2 segue acquisizione, campi IGC, scelta della quota, PSD su blocchi
validi, decisioni sui fix, trimming, coordinate, segmentazione dei gap, smoothing
e popolazione trattenuta. Le domande riguardano disponibilità dei canali,
possibili salti di quota, sensibilità alle soglie e validazione indipendente.
La durata nel grafico preliminare comprende i gap tra primo e ultimo fix;
la lunghezza del percorso somma soltanto i tratti osservati.

Il capitolo 3 segue crescita e supporto, quantili e controlli della popolazione,
rescaling marginale e congiunto, struttura direzionale e ambiente, durata ed
equipaggiamento, modelli e memoria. Il campione completo eleggibile contiene
155085 parapendii e 6060 deltaplani. Il controllo a voli e origini comuni contiene
14360 e 563 voli: misura la stessa popolazione a tutti i lag e non sostituisce
l'analisi dell'archivio completo.

L'ipotesi che equipaggiamento e scelte dei piloti moderino i vincoli di vento e
orografia viene presentata insieme alle sue criticità: rapporto tra momenti
uguale a uno non basta per l'isotropia, le classi non misurano l'esperienza,
l'ordinamento pirenaico si inverte, la costa comprende rilievi locali e i gruppi
non sono appaiati per condizioni. La discussione propone confronti discriminanti;
non attribuisce causalmente le differenze a vento o abilità.

## Provenienza e ricostruzione

La preparazione richiede prima una revisione completata della tesi. Il
[source manifest](source-manifest.json) registra hash di tesi, sorgenti numerici,
input e cleaning. Il registro collega il run completo all'aggiornamento mirato
della PCA e alle nuove differenze regionali; gli altri risultati sono invariati. I tre report
completi sono conservati in `data/*.json.gz`: compressione senza perdita, nessun
sottocampionamento o troncamento del report. I manifest delle figure distinguono
copie, ritagli vettoriali e ridisegno degli array già calcolati.

Per compilare i quattro PDF dagli input inclusi, senza leggere l'SSD:

```bash
python3 presentations/build.py all --notes
```

Per rigenerare gli asset dal manoscritto revisionato nella stessa checkout:

```bash
uv run --no-project --with pypdf python presentations/prepare_assets.py --pca-update revisions/regional-pca-lags-2026-09-12 --variation-update revisions/regional-variations-2026-09-12
uv run --no-project --with pypdf python presentations/crop_chapter_panels.py
.venv/bin/python presentations/render_figures.py
.venv/bin/python presentations/render_chapter3_panels.py
uv run --no-project --with pypdf --with numpy --with matplotlib python presentations/render_variation_panels.py
.venv/bin/python presentations/render_supervisor_gate.py
.venv/bin/python presentations/render_supervisor_maps.py --run revisions/vertical-gap-split-2026-09-11/recovery-runs/20260912T133040Z-073601cb --out presentations/assets
python3 presentations/build.py all --notes
```

Solo il ridisegno delle mappe legge metadati del run e dei voli sull'SSD.
Non viene rilanciato il cleaning, il bootstrap o alcun fit del capitolo 3.
Il [registro di validazione](validation.json) identifica gli output verificati.

Il rapporto regionale completo è conservato in
`data/ch3_regional_variations.json.gz`. I pannelli sulle differenze seconde
distinguono origini disponibili, origini condivise tra ordini e origini comuni
fino a 1000 s. La standardizzazione per durata, periodo, attrezzatura e task è un
controllo descrittivo; le bande simultanee si riferiscono al confronto con
origini comuni prima di tale standardizzazione. Le differenze regionali non
identificano il vento e non forniscono un Hurst validato.

Il collegamento `soaring-viewer://open` nella slide dell'esempio reale richiede
il launcher macOS locale già previsto dal progetto; `install_viewer_link.py`
lo registra. Il grafico incorporato resta disponibile per la discussione offline.
