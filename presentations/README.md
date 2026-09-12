# Presentazioni dei capitoli 2 e 3

Queste presentazioni raccontano la tesi revisionata il 13 settembre 2026, con
cleaning 2.3.0 e risultati del run completo `20260912T133040Z-073601cb`, con
PCA regionale calcolata a 10, 100, 1000 e 10.000 s e documentata nella revisione
`regional-pca-lags-2026-09-12`. L'estensione
`regional-variations-2026-09-12` aggiunge differenze seconde e terze regionali,
covarianze direzionali, distribuzioni e controlli della popolazione.
`grouped-tamsd-2026-09-12` aggiunge la TAMSD per regione e quota iniziale,
con un controllo che mantiene gli stessi segmenti a tutti i lag.
`environment-axis-integration-2026-09-12` integra gli assi ETOPO dei rilievi
e il riferimento ERA5 per il vento costiero. La revisione
`channel-wind-flight-altitude-2026-09-13` valuta il vento alla quota media
delle finestre della PCA, con orari annuali e controlli stagionali separati.
Sono capitoli da discutere con i supervisors, senza durata prestabilita.
Le domande scientifiche accompagnano i risultati; i confronti tra versioni
precedenti della pipeline non fanno parte delle slide.

| Documento | Slide | Versione con note |
|---|---:|---|
| [Capitolo 2](chapter2.pdf) | 58 | [PDF con note](chapter2-notes.pdf) |
| [Capitolo 3](chapter3.pdf) | 101 | [PDF con note](chapter3-notes.pdf) |

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
della PCA, alle nuove differenze regionali e alla TAMSD raggruppata; gli altri risultati sono invariati. I quattro report
completi sono conservati in `data/*.json.gz`: compressione senza perdita, nessun
sottocampionamento o troncamento del report. I manifest delle figure distinguono
copie, ritagli vettoriali e ridisegno degli array già calcolati.

Per compilare i quattro PDF dagli input inclusi, senza leggere l'SSD:

```bash
python3 presentations/build.py all --notes
```

Per rigenerare gli asset dal manoscritto revisionato nella stessa checkout:

```bash
uv run --no-project --with pypdf python presentations/prepare_assets.py --pca-update revisions/regional-pca-lags-2026-09-12 --variation-update revisions/regional-variations-2026-09-12 --tamsd-update revisions/grouped-tamsd-2026-09-12 --environment-update revisions/environment-axis-integration-2026-09-12 --wind-altitude-update revisions/channel-wind-flight-altitude-2026-09-13
uv run --no-project --with pypdf python presentations/crop_chapter_panels.py
.venv/bin/python presentations/render_figures.py
.venv/bin/python presentations/render_chapter3_panels.py
uv run --no-project --with pypdf --with numpy --with matplotlib python presentations/render_variation_panels.py
uv run --no-project --with pypdf python presentations/render_tamsd_panels.py
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

La TAMSD raggruppata precede la struttura direzionale. Usa le curve native dei
segmenti, con lag di riferimento richiesto pari a 1049 s; non è la griglia
esatta della PCA. Plains, Hills, Low mountains e High mountains sono fasce
della quota GNSS iniziale della traiettoria pulita, non classi di rilievo misurato.
Le curve disponibili e quelle con segmenti fissi mostrano quanto la selezione
dei voli contribuisca all'ampiezza e alla crescita apparente. I conteggi e
l'incrocio regione–quota accompagnano le interpretazioni.

Il collegamento `soaring-viewer://open` nella slide dell'esempio reale richiede
il launcher macOS locale già previsto dal progetto; `install_viewer_link.py`
lo registra. Il grafico incorporato resta disponibile per la discussione offline.

Le otto slide ambientali confrontano i rilievi con la PCA a 10.000 s e il vento
con l'asse costiero. I Pirenei mostrano un forte allineamento; nelle Alpi rimane
uno scarto di circa 18°. Per la costa si misura una quota media di 1006 m sulle
2013 finestre della PCA, da 1680 voli. Il vento ERA5 viene interpolato a questa
quota usando le altezze dei livelli atmosferici di ogni ora. Gli assi annuali
sono 15.8° per tutte le ore e 17.9° per le 09–17 UTC, contro 30.2° della PCA:
scarti di 14.4° e 12.3°. La selezione aprile–settembre resta un controllo
separato, con scarti di 14.2° e 9.6°.

Il confronto annuale in quota è meno allineato di quello al suolo, ma cambia
meno con la stagione. Le slide discutono il ruolo della quota, i limiti del
riferimento GNSS, il supporto comune per la sensibilità verticale e il bisogno
di vento appaiato alle condizioni reali dei voli. La media del vento e la
covarianza centrata sono statistiche diverse: la somiglianza degli assi non
identifica una causa. Tutti i dati usati sono conservati nel progetto e su SSD:
32.22 MB compressi per i livelli atmosferici, oltre ai 6.33 MB dei dati al suolo.
