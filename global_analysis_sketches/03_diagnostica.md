# 3 — Diagnostica, validazione, output

> Parte 3 di 3. Contiene i test che decidono se i risultati della parte 2 sono difendibili, e
> il formato in cui vanno prodotti.

---

## 3.1 Il confound principale: eterogeneità

> Una sovrapposizione di processi diffusivi **normali** con tempi di persistenza diversi
> produce un MSD d'ensemble che sembra una legge di potenza superdiffusiva su tutto
> l'intervallo dei $\tau_p$, e piega su $t^1$ solo dopo. Nessuna anomalia vera.

**È il modo più probabile in cui il risultato può essere sbagliato**, più della fisica e più
degli errori numerici. E i tuoi dati sono strutturalmente eterogenei: piloti diversi, siti
diversi, giornate diverse, vele diverse.

### 3.1.1 Perché funziona l'inganno

Con una distribuzione $g(\tau_p)$ di tempi di persistenza,

$$\langle x^2(t)\rangle = \int d\tau_p\, g(\tau_p)\, \frac{2v^2\tau_p^2}{1}\left[\frac{t}{\tau_p} - 1 + e^{-t/\tau_p}\right]$$

Ogni componente è balistica sotto il suo $\tau_p$ e diffusiva sopra. La sovrapposizione
interpola dolcemente tra $t^2$ e $t^1$, e su un range finito la curva è indistinguibile da una
potenza con $1<\nu<2$. **Se $g$ è a coda pesante, la legge di potenza è addirittura esatta.**

### 3.1.2 Protocollo

1. Stima $\nu$ **per volo singolo**, dove $T_f \ge 3$ h (statistica sufficiente).
2. Stima $\nu$ per **sottoinsiemi omogenei**: stesso sito, stessa classe di giornata, stesso
   pilota, stesso tipo di volo.
3. Confronta con l'ensemble completo.

$$\boxed{\ \text{Se }\ \nu_{\rm volo} < \nu_{\rm ensemble}\ \text{ sistematicamente, l'anomalia è eterogeneità.}\ }$$

```python
def heterogeneity_test(per_flight_nu, ensemble_nu, meta):
    med = np.median(per_flight_nu)
    strat = {k: np.median(v) for k, v in per_flight_nu.groupby(meta["site"])}
    return {"nu_flight_median": med,
            "nu_ensemble": ensemble_nu,
            "gap": ensemble_nu - med,
            "nu_by_site": strat}
```

Un `gap` positivo e maggiore dell'errore bootstrap è il segnale.

### 3.1.3 Variabili di stratificazione

| Variabile | Perché |
|---|---|
| `site` | orografia: disordine *quenched*, non stocastico |
| `date` | condizioni convettive (base nubi, forza, spaziatura termiche) |
| `pilot_id` | abilità e strategia — la sorgente di eterogeneità più forte |
| `is_competition` | **la più importante**, vedi sotto |
| ora del giorno | ciclo convettivo |
| `wind_mean` | forza della deriva |

⚠️ **Gara vs libero.** I voli di gara hanno una **rotta imposta**: la correlazione direzionale
a lungo raggio che misuri riflette il task, non il trasporto. È una correlazione
*deterministica* e *quenched*, non un processo stocastico stazionario, e tutto il formalismo di
$C(m)$ presuppone la stazionarietà.

Confrontare gara vs libero isola la componente comportamentale-deterministica da quella
genuinamente stocastica. **Se $\gamma$ differisce sistematicamente, hai la risposta.** Questa
è una figura da mettere in tesi indipendentemente da come esce.

---

## 3.2 Canale verticale

> Tutte pre-segmentazione. Servono a due cose: caratterizzare il ciclo climb–glide senza
> etichette, e **predire se l'HMM funzionerà**.

### 3.2.1 Bimodalità di $v_z$ — la diagnostica di segmentabilità

**Bimodalità = separabilità.** Se la distribuzione di $v_z$ è unimodale, la segmentazione a
due stati non è supportata dai dati, e va rivista (più stati, feature diverse, o HMM
gerarchico).

```python
from sklearn.mixture import GaussianMixture

def bimodality(vz: np.ndarray) -> dict:
    X = vz.reshape(-1, 1)
    g1, g2 = GaussianMixture(1).fit(X), GaussianMixture(2).fit(X)
    m = np.sort(g2.means_.ravel())
    s = np.sqrt(g2.covariances_.ravel())
    return {"bic_1": g1.bic(X), "bic_2": g2.bic(X),
            "delta_bic": g1.bic(X) - g2.bic(X),
            "separation": (m[1] - m[0]) / np.sqrt((s**2).mean()),
            "weights": np.sort(g2.weights_)}
```

**Soglie**: `delta_bic > 10` (evidenza forte per due componenti) **e** `separation > 2`
(i modi sono risolti, non due gaussiane che si sovrappongono).

Se `separation < 1.5`, aspettati che l'HMM produca segmentazioni instabili e fortemente
dipendenti dall'inizializzazione. È un'informazione che vale la pena avere **prima** di
costruirlo, non dopo.

### 3.2.2 Periodo di ciclo — senza segmentare

PSD di $v_z$ (Welch, `nperseg=512`). Il picco a bassa frequenza dà il **periodo del ciclo
climb–glide**. Da confrontare con il periodo di spiralata (parte 2 §2.4.1).

$$\text{Condizione di validità del modello a cicli:}\qquad T_{\rm ciclo} \gg T_{\rm circ}$$

Se le due scale non sono separate, l'idealizzazione "termica = punto, transizione = volo" non
regge, e il modello a cicli va discusso con cautela nella tesi. Registra il rapporto.

### 3.2.3 Energy height

$$h_e = z + \frac{v^2}{2g}$$

Rimuove gli scambi velocità–quota (pull-up in ingresso termica, accelerazione in uscita) che
altrimenti contaminano $v_z$ con oscillazioni che non sono né salita né discesa.

⚠️ Con la velocità **al suolo** invece della TAS, $h_e$ contiene il vento. Usa
$v_{\rm TAS} = |\mathbf{v} - \mathbf{w}|$ dove il vento è stimato (parte 1 §1.4), e marca il
resto come `null`.

$\dot h_e$ è una feature più pulita di $v_z$ grezzo, sia per la diagnostica qui sia per
l'emissione dell'HMM.

### 3.2.4 Scatter $|\mathbf{v}|$ vs $v_z$

La firma della polare di volo. In transizione $v_z$ è funzione quasi deterministica di
$|\mathbf{v}|$ (più il moto verticale dell'aria); in termica no.

Lo scatter plot pre-segmentazione **mostra già le due popolazioni**. È il controllo visivo più
diretto di ciò che l'HMM dovrà trovare, e costa un plot. Sovrapponi la polare nominale della
vela: la nube inferiore deve seguirla.

---

## 3.3 Osservabili collettive (se hai voli simultanei)

Tutte pre-segmentazione, tutte rilevanti per la parte "strategie collettive" della tesi.

**Criterio di simultaneità**: stessa data, distanza < 20 km, sovrapposizione temporale > 20 min.

| Osservabile | Definizione | Cosa dice |
|---|---|---|
| $g(r)$ | pair correlation function tra piloti allo stesso istante | clustering su termiche **senza identificarle** |
| $n(R)$ | numero di vicini entro $R$ | distribuzione e serie temporale del gregarismo |
| $\langle\mathbf{v}_i\cdot\mathbf{v}_j\rangle(r)$ | correlazione di velocità a coppie | lunghezza di correlazione dell'allineamento |
| $\langle v_{z,i}(t)v_{z,j}(t+\tau)\rangle$ | cross-correlazione ritardata | **chi segue chi**, e con che ritardo |

L'ultima è la più interessante: un picco a $\tau>0$ sistematico per una coppia indica
*following*. Aggregando su tutte le coppie ottieni la distribuzione dei ritardi, che è una
misura diretta del flusso di informazione nello stormo.

⚠️ Normalizza $g(r)$ per la densità attesa da una distribuzione nulla che rispetti i vincoli
geografici (l'orografia concentra i piloti anche senza interazione). Il nullo giusto è
ottenuto **permutando le date** tra voli dello stesso sito, non da una distribuzione uniforme.

---

## 3.4 Statistica

### 3.4.1 Bootstrap sui voli

**Mai sui punti.** Gli incrementi a lag diversi sono fortemente correlati, e le barre d'errore
da OLS in log-log sottostimano di un ordine di grandezza.

```python
def bootstrap_exponent(per_flight_msd, lags, window, B=500, rng=None):
    rng = rng or np.random.default_rng(0)
    ids = list(per_flight_msd)
    m = (lags >= window[0]) & (lags <= window[1])
    out = np.empty(B)
    for b in range(B):
        pick = rng.choice(ids, size=len(ids), replace=True)
        curve = np.nanmean([per_flight_msd[i][lags] for i in pick], axis=0)
        out[b] = np.polyfit(np.log(lags[m]), np.log(curve[m]), 1)[0]
    return out.mean(), np.percentile(out, [2.5, 97.5])
```

`B = 500` è sufficiente per un CI al 95%. Ricampiona **gli ID dei voli**, non gli incrementi.

### 3.4.2 Checklist da allegare a ogni esponente

- [ ] $N_{\rm eff}(\Delta)$ riportato per ogni lag; lag con $N_{\rm eff}<200$ esclusi.
- [ ] Esponente stimato su $\ge 3$ finestre di fit; se si muove più del CI bootstrap,
      riportato come **effettivo su range dichiarato**, non asintotico.
- [ ] $\Delta \le T_{\rm mediana}/10$.
- [ ] **Numero di decadi coperte dal ramo di potenza.** Sotto 1.5 decadi una legge di potenza
      non è distinguibile da un crossover lento — dichiararlo, non nasconderlo.
- [ ] Frazione del momento dal top-1% riportata per ogni $q$.
- [ ] Confronto con la lognormale per ogni stima di coda.
- [ ] Ogni esponente ricalcolato con e senza centratura della deriva; differenza riportata.
- [ ] Ogni conclusione verificata su almeno un sottoinsieme omogeneo (§3.1).

### 3.4.3 Nota di onestà per la tesi

Con voli di poche ore il regime superdiffusivo misurato è quasi certamente
**pre-asintotico** in senso stretto: la finestra temporale accessibile è limitata dal ciclo
convettivo diurno.

Non è un difetto, è una proprietà del sistema — esiste un cutoff fisico naturale. Dichiararlo
esplicitamente e mostrare che l'esponente è stabile **dentro** il range fisicamente
accessibile è più solido che rivendicare un'asintotica che i dati non possono sostenere. Un
referee che trova questa frase nella tesi smette di cercare il problema; uno che non la trova
lo cerca.

---

## 3.5 Tabella di consistenza

Le relazioni che **devono** valere se il modello Lévy walk è corretto. Ogni riga è un test
indipendente; **le violazioni sono il risultato più informativo del documento.**

| # | Relazione | Fonti | Se fallisce |
|---|---|---|---|
| 1 | $\alpha = 3-\nu$ | 2.1.5, 2.2.4 | non sei nel regime $1<\alpha<2$ |
| 2 | $q_c = \alpha$ | 2.2.4 | non è strong anomalous diffusion |
| 3 | pendenza destra $\approx 1$ | 2.2.4 | il fronte non è balistico |
| 4 | $\tau_c \simeq t_0$ | 2.1.6 | crossover da persistenza, non da code |
| 5 | $\delta(0.5) \approx 1/\alpha$ | 2.3.3 | il bulk non è stabile |
| 6 | $\delta(0.99) \to 1$ | 2.3.3 | nessun fronte balistico → Lévy **flight**, non walk |
| 7 | $\beta \approx \alpha$ | 2.5.3 | soglia geometrica e code temporali non coincidono |
| 8 | $C_v \sim \tau^{-(\alpha-1)}$ | 2.4.1 | inconsistenza Green–Kubo |
| 9 | MSD da VACF = MSD diretto (5%) | 2.4.1 | inconsistenza posizioni/velocità |
| 10 | doppio shuffle $\to \nu=1$ | 2.6.3 | accoppiamento magnitudine–direzione |
| 11 | $\nu$ sopravvive al `block` shuffle | 2.6.3 | l'anomalia è nelle correlazioni |
| 12 | $c_\infty$ compatibile con 0 | 2.4.3 | deriva residua |
| 13 | $\nu_{\rm volo} = \nu_{\rm ensemble}$ | 3.1.2 | **eterogeneità, non anomalia** |
| 14 | $T_{\rm ciclo} \gg T_{\rm circ}$ | 3.2.2 | il modello a cicli non è separabile |
| 15 | $\alpha_{\rm pre} = \alpha_{\rm post\text{-}HMM}$ | tutto vs HMM | problema nella segmentazione |

La riga 15 è la ragione d'essere dell'intero documento. Merita una sezione dedicata in tesi:
è il tipo di controllo che un referee cerca e raramente trova.

---

## 3.6 Cosa resta precluso

Da dichiarare esplicitamente per non sovrastimare la portata delle conclusioni:

- $\psi(x,t)$ **accoppiata per passo** — richiede i passi.
- **Test di accoppiamento** $T(\phi\mid t)$: kernel di virata condizionato alla durata del volo
  precedente. Richiede coppie (durata, virata) etichettate. È il test che decide se la
  decomposizione diagonale/incrociata del MSD è legittima.
- Modello a **cicli** con $G_N(\rho)$, e la distinzione crossover vs dominanza asintotica.
- Attribuzione fisica: quale stato di volo genera quale contributo.
- Statistica delle **termiche** come oggetti (forza, raggio, spaziatura).

> **Sintesi.** Pre-segmentazione determini *quale classe di trasporto* hai. La segmentazione
> serve a spiegare *quale meccanismo di volo* la genera. La segmentazione spiega un esponente,
> non lo misura.

---

## 3.7 Output e riproducibilità

### 3.7.1 File di risultati

| File | Grana | Colonne chiave |
|---|---|---|
| `msd.parquet` | (flight_id, lag) | `msd`, `n_eff`, `msd_raw`, `msd_centered` |
| `moments.parquet` | (stratum, lag, q) | `moment`, `tail_frac_1pct`, `n_eff` |
| `quantiles.parquet` | (stratum, lag, p) | `quantile`, `n_eff` |
| `isotropy.parquet` | (stratum, lag) | `a1_abs`, `a2_abs`, `threshold_05`, `isotropic` |
| `vacf.parquet` | (stratum, tau) | `cv`, `cv_norm` |
| `heading_corr.parquet` | (stratum, delta, k) | `c_k`, `n_eff` |
| `persistence.parquet` | (flight_id, s_max) | `run_length_s` (una riga per run) |
| `shuffle.parquet` | (stratum, mode, surrogate) | `nu` |
| `exponents.parquet` | (stratum, observable, window) | `value`, `ci_lo`, `ci_hi`, `n_decades` |

`stratum` è una chiave composita (`site`, `is_competition`, ...) con `"all"` per l'ensemble.

**`exponents.parquet` è la tabella maestra**: ogni numero che finisce in tesi deve avere una
riga qui, con la sua finestra di fit e il suo CI.

### 3.7.2 Emissione verso LaTeX

Fai emettere allo script un file `results/values.tex`:

```python
def emit_tex(exponents: pl.DataFrame, path="results/values.tex"):
    with open(path, "w") as f:
        for row in exponents.filter(pl.col("stratum") == "all").iter_rows(named=True):
            name = row["observable"].title().replace("_", "")
            f.write(f"\\newcommand{{\\{name}}}{{{row['value']:.2f}}}\n")
            f.write(f"\\newcommand{{\\{name}Err}}{{{(row['ci_hi']-row['ci_lo'])/2:.2f}}}\n")
```

e nel testo della tesi usa solo `\NuMsd`, `\AlphaHill`, mai numeri letterali.

**Perché.** Rende **strutturalmente impossibile** che il numero nell'abstract, quello nella
caption e quello nella tabella siano diversi. È la classe di errore più imbarazzante in una
tesi e la più difficile da vedere a occhio.

### 3.7.3 Struttura del repo

```
src/
  io/          schema.py  loader.py
  preprocess/  validity.py  smoothing.py  wind.py        # parte 1
  observables/ msd.py  moments.py  pdf.py  correlations.py
               persistence.py  blocks.py  ergodicity.py  # parte 2
  diagnostics/ isotropy.py  heterogeneity.py  vertical.py
               collective.py                             # parti 1, 3
  stats/       bootstrap.py  tailfit.py  collapse.py
  report/      tables.py  figures.py  emit_tex.py
tests/
results/
```

**Unit test minimi, da scrivere prima delle osservabili:**

1. `msd_fft(r)[0] == 0` entro l'errore macchina.
2. Moto browniano sintetico → $\nu = 1.00 \pm 0.03$, $K(\Delta) \to 2$, $\delta(p)$ costante.
3. Lévy walk sintetico con $\alpha$ noto → recupero di $\alpha$ da §2.2 e §2.3 entro 0.1.
4. Traiettoria con deriva imposta → `a1_abs` sopra soglia, e sotto soglia dopo centratura.
5. Run sintetici con $P(L)$ Pareto nota → `persistence_runs` recupera $\beta$, e il
   campionamento per istante recupera $\beta-1$ (verifica esplicita del bias di ispezione).

Il test 3 e il test 5 sono i più importanti: validano l'intera catena su un caso dove la
risposta è nota.

### 3.7.4 Ordine di esecuzione globale

```
PARTE 1  ─ validità → SG → odografo → ERA5 → v_d_net → lag grid → N_eff → isotropia
             │
             ├─ GATE A: v_rms interpolato = v_rms diretto (2%)
             ├─ GATE B: correlazione odografo/ERA5 > 0.6
             └─ GATE C: a1_abs < soglia dopo centratura
             ▼
PARTE 2  ─ MSD → ν, v_rms, τ_c
             ├─ momenti + code       ─┐
             ├─ quantili + collasso   ├─► discriminazione Lévy walk vs fBm
             ├─ VACF + Green-Kubo    ─┘   (righe 1-9 della tabella)
             ├─ heading corr → γ
             ├─ persistenza → β
             └─ shuffle: `both` PRIMA, poi `block` e `magnitude`
                  └─ GATE D: `both` deve dare ν=1
             ▼
PARTE 3  ─ eterogeneità (stratificazione)   ◄── prerequisito per §2.7
             ├─ verticale → segmentabilità, separazione di scale
             ├─ collettivo (opzionale)
             ├─ bootstrap → exponents.parquet
             └─ tabella di consistenza (15 righe)
             ▼
          values.tex → tesi
```

I **GATE** sono bloccanti. Un gate fallito significa che il problema è a monte, e nessuna
osservabile a valle è interpretabile finché non è risolto.
