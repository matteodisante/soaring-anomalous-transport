# Scaling dei quantili e delle distribuzioni: verifica del §3.3.2

Analisi dell’11 settembre 2026 sullo snapshot di pulizia **2.2.0**, run completato `20260910T221820Z-05d36ab4`. Il ricalcolo della pulizia 2.3.0 era in corso: questa analisi non ne dichiara il completamento. Nessuna tabella sorgente in scrittura è stata letta.

La tesi aggiornata contiene i risultati nel §3.3.2 e le distribuzioni al quadrato nell’appendice 3.A. La figura 3.6 distingue i quattro controlli con colori e tratti diversi.

## Risultato

Sull’intervallo 10–10.000 s le distribuzioni empiriche di |ΔE|, |ΔN| e R non seguono una singola forma riscalata. I quattro quantili hanno pendenze differenti; anche normalizzando ogni distribuzione per la propria mediana rimangono differenze di forma. Questo risultato riguarda il campione e l’intervallo osservati, non una classificazione definitiva del processo stocastico.

| Disciplina | Quantità | H25 | H50 | H75 | H90 | H comune candidato |
|---|---|---:|---:|---:|---:|---:|
| Parapendio | \|ΔE\| | 0.950 | 0.924 | 0.879 | 0.866 | 0.905 |
| Parapendio | \|ΔN\| | 0.992 | 0.945 | 0.901 | 0.897 | 0.934 |
| Parapendio | R | 0.979 | 0.893 | 0.887 | 0.892 | 0.912 |
| Deltaplano | \|ΔE\| | 0.962 | 0.915 | 0.857 | 0.850 | 0.896 |
| Deltaplano | \|ΔN\| | 0.968 | 0.954 | 0.872 | 0.869 | 0.916 |
| Deltaplano | R | 0.995 | 0.888 | 0.851 | 0.864 | 0.900 |

Il candidato comune è il fit a pendenza comune e intercetta distinta per quantile, con uguali pesi per lag e quantile nel piano logaritmico. È la media delle quattro pendenze. Non è un H universale, né un valore ottimizzato visivamente per fare collassare gli istogrammi. Il rapporto temporale usa τ₀ = 1000 s.

Per Y = |ΔE|, |ΔN| o R, la trasformazione S = Y² dà esattamente Qp(S) = Qp(Y)² e βp = 2Hp. La densità riscalata usa a·pY(a u) per Y e a²·pS(a² v) per S. Il raggio R è già positivo: absolute_R è ridondante. R non è la differenza tra distanze dall’origine né la lunghezza della traiettoria percorsa.

## Forma e direzione

| Disciplina | Quantità | D con H comune | D dopo normalizzazione per mediana |
|---|---|---:|---:|
| paragliders | Est | 0.188 | 0.163 |
| paragliders | Nord | 0.203 | 0.193 |
| paragliders | Raggio | 0.284 | 0.213 |
| hang gliders | Est | 0.230 | 0.205 |
| hang gliders | Nord | 0.238 | 0.207 |
| hang gliders | Raggio | 0.354 | 0.215 |

D è il massimo della distanza sup tra ECDF pesate per tutte le coppie dei sei lag mostrati (10, 80, 320, 1070, 2960, 10000 s). Usa tutte le osservazioni, senza binning, troncamenti di coda o p-value KS per campioni indipendenti. La trasformazione al quadrato lascia invariata questa distanza.

Nel parapendio le quattro differenze H_N,p − H_E,p sono positive e gli intervalli puntuali del bootstrap per volo escludono zero. Nel deltaplano questo avviene solo alla mediana. Intervalli che comprendono zero non dimostrano uguaglianza. La pendenza della mediana radiale è inferiore a entrambe le pendenze delle mediane componenti: si tratta di ranghi di distribuzioni diverse, per cui non esiste un obbligo di interpolazione fra i due valori.

Per ogni quantità H90 − H25 è negativo in entrambe le discipline. Per R vale circa −0.087 nel parapendio e −0.132 nel deltaplano. Tuttavia H90 > H75 per R: non c’è una discesa monotona attraverso tutti i quantili. Anche i rapporti Q90/Q25 sono non monotoni nel lag. La variazione di forma è più informativa di una semplice etichetta di “restringimento”.

I fit su 60–1970 s e 210–1970 s danno H comuni circa 0.95–0.98. Sono finestre di sensibilità con gli stessi voli e origini, non regimi identificati automaticamente. Non è stato affermato un collasso esatto su queste finestre più strette.

Circling, ritorni, rotte, planate e condizioni ambientali sono meccanismi possibili. I dati presentati non ne separano i contributi causali e non dimostrano multifrattalità, isotropia o un particolare modello di moto. La dipendenza est–nord non è isolata: anche le marginali mostrano variazione di forma.

## Campione, incertezza e riproducibilità

Gli stessi 107 segmenti di parapendio e 56 di deltaplano, tutti lunghi almeno 20.000 s, contribuiscono rispettivamente 157.493 e 82.774 origini a ogni lag. Ciascun volo ha lo stesso peso totale, distribuito sulle sue origini. È un sottoinsieme esplorativo di segmenti lunghi, non un campione rappresentativo dell’intero archivio.

Il bootstrap ricampiona interi voli 400 volte (seed 20260911), conservando le stesse molteplicità per ogni lag e componente. Ogni replica ricalcola i quantili della miscela pesata e i fit: non si mediano quantili di singoli voli. Gli intervalli al 95% sono puntuali e condizionati all’indipendenza fra voli; non modellano condizioni condivise nello stesso luogo e giorno.

La cache contiene tutti gli incrementi consecutivi a 10 s. La ricostruzione per somma cumulativa verifica la lunghezza completa e riproduce i quantili del controllo originale entro rtol=1e-9, atol=1e-6 m. Cache, contratto di misura, voli, segmenti, origini, fit, contrasti bootstrap, istogrammi, masse a zero e distanze sono documentati in `thesis/generated/ch3_self_similarity.json`.

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py \
  --saved-snapshot /Volumes/SSD_DISANTE/derived-audit/runs/20260910T221820Z-05d36ab4/arrays/ch3_revision_sample.pkl
```

Il normale stadio `transport_subset` rigenera automaticamente questi prodotti sui dati del nuovo rebuild. Il manifest del run precedente non è stato modificato. La compilazione locale della tesi non equivale a una nuova certificazione dell’archivio.

## Cosa c’era nella vecchia tesi

La revisione Git `6e6566f` contiene `scripts/reporting/generate_propagator_figure.py` e `measure_propagator.py`. Si misuravano già quattro quantili, separatamente per est, nord e modulo, e si sovrapponevano densità riscalate. Il fit principale era 60–2000 s, suddiviso per cadenza nativa. Quindi i vecchi H non sono direttamente confrontabili con il fit attuale 10–10.000 s.

Il vecchio accumulatore usa istogrammi fra 1 e 100.000 m, escludendo massa fuori intervallo. `hurst_bootstrap_error` ricampiona blocchi di quantili e fitta la loro media; il suo stesso docstring chiarisce che ciò non ricalcola i quantili della distribuzione pooled. I vecchi errori molto piccoli non sono stati trasferiti al nuovo stimatore. Nella versione immediatamente precedente di questo capitolo i dodici H e i controlli per tutte le componenti erano già nel JSON; mancavano la presentazione completa, i collassi controllati e i contrasti di incertezza.

Come riferimento metodologico è stato consultato [Coeurjolly, Hurst exponent estimation of locally self-similar Gaussian processes using sample quantiles](https://arxiv.org/abs/math/0506290). I suoi risultati di consistenza richiedono ipotesi specifiche su processi gaussiani: non sono stati usati come giustificazione degli intervalli o delle ipotesi sui voli.

## Verifiche

- 58 test mirati passati: oracoli di scaling e trasformazione quadratica, ricampionamento della miscela, dipendenza tra componenti, controlli esistenti, palette, macro e provenienza.
- Ruff passato sui nuovi moduli e test; `git diff --check` passato.
- Tutte le macro citate hanno un produttore; la verifica della provenienza ha riportato zero problemi.
- Tesi compilata con latexmk e pagine nuove ispezionate visivamente. Nel log resta l’avviso preesistente sul duplicato di destinazione `page.1` del frontespizio; non risultano riferimenti indefiniti o overfull box.

Log conservati in questa cartella. Le modifiche preesistenti alla pulizia e al capitolo 2 sono state preservate.
