# Direzione indicativa dei rilievi e PCA dei voli

La [mappa PDF](terrain-versus-flight-axes.pdf) confronta un asse dei rilievi,
ricavato da dati geografici indipendenti, con la PCA dei parapendii a 10.000 s.
È una stima geografica indicativa: non è una ricostruzione precisa delle creste.

| Regione | Asse dei rilievi | Asse dei voli a 10.000 s | Differenza tra assi |
|---|---:|---:|---:|
| Alpi | circa 48° | circa 65° | circa 18° |
| Pirenei | circa 170° | circa 170° | meno di 1° |

Gli angoli partono da est e crescono in senso antiorario: 0° è est–ovest,
90° è nord–sud. Sono assi senza verso, quindi definiti modulo 180°.

## Come è stata ottenuta la direzione

1. Fonte: [NOAA NCEI, ETOPO 2022](https://www.ncei.noaa.gov/products/etopo-global-relief-model),
   [DOI 10.25921/fd45-gt74](https://doi.org/10.25921/fd45-gt74).
   Il [servizio ERDDAP](https://coastwatch.pfeg.noaa.gov/erddap/griddap/ETOPO_2022_v1_15s.html)
   fornisce quote su una griglia di 15 secondi d'arco. Per questa stima si prende
   una cella ogni quattro in entrambe le direzioni: circa 1–2 km tra celle.
2. Si usano esattamente i box del capitolo: Alpi, longitudine 5.4–10.0° e
   latitudine 43.8–46.6°; Pirenei, longitudine −1.9–3.3° e latitudine 42.0–43.5°.
3. Si selezionano le celle con quota almeno 1000 m. Questa è una definizione
   operativa del territorio montuoso, scelta senza ottimizzare l'accordo con i voli.
4. Si convertono i centri delle celle in coordinate metriche est/nord WGS84,
   tangenti al centro del box, ponendo la quota a zero nella sola proiezione.
   Si calcola la covarianza spaziale dei centri, pesata approssimativamente per
   l'area delle celle con `cos(latitudine)`. Tutte le celle selezionate hanno lo
   stesso peso per unità di area: l'altitudine non aggiunge un ulteriore peso.
5. L'autovettore principale dà l'asse di allungamento medio di quella superficie.
   Nella mappa la linea nera mostra tale asse; quella rosa tratteggiata mostra
   soltanto l'orientamento della PCA dei voli, traslato nello stesso centro per
   facilitare il confronto. Lunghezza e posizione delle linee non rappresentano
   un percorso, una cresta o l'ampiezza degli spostamenti.

Un controllo rapido cambia soltanto la soglia di quota:

| Soglia | Alpi | Pirenei |
|---|---:|---:|
| 500 m | 42.1° | 175.4° |
| 1000 m | 47.6° | 170.5° |
| 1500 m | 47.9° | 169.7° |

Questi intervalli di sensibilità **non sono intervalli di confidenza**. Suggeriscono
un'indicazione complessiva di circa 42–48° per il rilievo alpino in questo box e
170–175° per quello pirenaico. Le cifre decimali permettono di riprodurre il
calcolo; non misurano la precisione della direzione fisica della catena.

## Interpretazione e limiti

Nei Pirenei gli assi sono molto vicini: questo è coerente con spostamenti allungati
lungo la catena. Nelle Alpi la direzione è dello stesso settore nordest–sudovest,
ma i voli sono più orientati verso nord rispetto all'asse medio dei rilievi.
Nessuno dei due confronti dimostra un effetto causale dell'orografia: vento,
itinerari e selezione dei voli possono contribuire.

La forma e il taglio del box, la curvatura alpina, gli altopiani e la soglia di quota
influenzano l'asse. Inoltre i box selezionano il **decollo**: i voli che entrano nella
PCA possono uscire dal box. Il DEM usa un unico piano tangente regionale, mentre
gli incrementi dei voli sono espressi nei rispettivi piani tangenti di decollo.
Il confronto è quindi regionale e indicativo, adatto allo scopo richiesto.

## Riproduzione e provenienza

```bash
.venv/bin/python revisions/terrain-axis-2026-09-12/estimate_axes.py
```

I due piccoli file NetCDF scaricati sono inclusi; non servono Google Maps, nuovi
voli o una nuova pulizia. `terrain-axis.json` conserva URL, hash SHA-256, box,
metodo, risultati, sensibilità e identificazione dei risultati PCA usati.
La verifica usa soltanto operazioni geometriche; non sono stati ricalcolati i voli.
Questa analisi aggiuntiva è consegnata qui separatamente dal PDF della tesi e
dalle presentazioni già revisionati nella correzione dei ritardi PCA.
