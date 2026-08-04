# 1 — Fondamenta: dati, lag, deriva, isotropia

> Parte 1 di 3. Prerequisiti di ogni osservabile successiva. **Nulla in `02_trasporto.md`
> è interpretabile se questa parte non è chiusa.**

---

## 1.1 Schema dati

### 1.1.1 Tabella traiettorie — `tracks.parquet`

Una riga per campione temporale, partizionata per `flight_id`.

| Colonna | dtype | Unità | Definizione |
|---|---|---|---|
| `flight_id` | `Utf8` | — | chiave primaria del volo |
| `t` | `Float64` | s | tempo dall'inizio volo, **griglia uniforme** |
| `x`, `y` | `Float64` | m | ENU, origine = primo fix del volo |
| `z` | `Float64` | m | quota GPS o barometrica (dichiarare quale) |
| `vx`, `vy` | `Float64` | m/s | velocità al suolo, da Savitzky–Golay |
| `vz` | `Float64` | m/s | velocità verticale, da Savitzky–Golay |
| `wx`, `wy` | `Float64` | m/s | vento stimato (§1.4), `null` dove non stimabile |
| `valid` | `Boolean` | — | maschera qualità (§1.1.3) |

### 1.1.2 Tabella metadati — `flights.parquet`

Una riga per volo. È la tabella su cui si stratifica (parte 3, §3.4).

| Colonna | dtype | Definizione |
|---|---|---|
| `flight_id` | `Utf8` | chiave |
| `T` | `Float64` | durata utile (s) |
| `n_samples` | `Int32` | campioni validi |
| `date` | `Date` | data |
| `site` | `Utf8` | sito di decollo (cluster geografico) |
| `pilot_id` | `Utf8` | pilota, anonimizzato |
| `is_competition` | `Boolean` | volo di gara vs libero |
| `wind_mean` | `Float64` | modulo del vento medio (m/s) |
| `wind_dir` | `Float64` | direzione media del vento (rad) |
| `drift_net` | `Float64` | \|r(T)−r(0)\|/T (m/s) |
| `frac_wind_valid` | `Float64` | frazione di finestre odografo valide |

### 1.1.3 Maschera di validità

`valid = False` se una qualunque delle condizioni:

- gap di interpolazione > 30 s (fix mancanti nell'IGC originale);
- salto di posizione > 200 m tra campioni consecutivi a 1 Hz (glitch GPS);
- $|v| > 30$ m/s o $|v_z| > 15$ m/s (fuori dominio fisico per parapendio);
- primi/ultimi 120 s del volo (decollo e atterraggio non sono volo libero).

**Perché.** Un singolo glitch GPS produce un incremento gigantesco che, in una statistica a
code pesanti, viene interpretato come un evento estremo genuino e domina i momenti alti. È
il fallimento più comune e più silenzioso di questo tipo di analisi.

**Regola sui segmenti.** Le osservabili a lag si calcolano solo su **run contigui di
`valid=True`**. Non si "cuce" attraverso un gap: un incremento che scavalca un buco di 60 s
non è un incremento a lag $\Delta$.

```python
def contiguous_runs(valid: np.ndarray, min_len: int) -> list[tuple[int,int]]:
    """Indici [start, stop) dei run contigui di True lunghi almeno min_len."""
    d = np.diff(np.concatenate(([0], valid.view(np.int8), [0])))
    starts = np.flatnonzero(d == 1)
    stops  = np.flatnonzero(d == -1)
    return [(s, e) for s, e in zip(starts, stops) if e - s >= min_len]
```

---

## 1.2 Passo di campionamento e filtraggio

### 1.2.1 Scelta di `dt`

Vincolo dominante: risolvere la spiralata in termica, periodo $T_{\rm circ}\approx 15\text{–}20$ s.
Per avere almeno 10 campioni per giro serve

$$dt \le 1.5\ \text{s}$$

**Raccomandazione: `dt = 1.0 s`.** È anche il campionamento nativo della maggior parte dei
logger, quindi l'interpolazione è quasi identità dove i dati sono buoni.

⚠️ Non sovracampionare (`dt < 1 s`). L'interpolazione crea correlazione artificiale a lag
corti, che contamina l'intercetta balistica del MSD.

### 1.2.2 Savitzky–Golay: due serie, non una

Questo è il punto in cui è più facile sabotarsi.

| Serie | Filtro | Uso |
|---|---|---|
| `x, y, z` | **nessuno** (solo interpolazione) | tutte le osservabili di posizione: MSD, momenti, PDF, persistenza |
| `vx, vy, vz` | SG, `window=9`, `polyorder=2`, `deriv=1` | VACF, PSD, odografo, canale verticale |

**Perché.** SG attenua le alte frequenze. Applicato alle posizioni, riduce sistematicamente
la varianza degli incrementi a lag corti: il ramo balistico del MSD si abbassa, $v_{\rm rms}$
stimata dall'intercetta risulta minore della velocità vera, e il ginocchio $\tau_c$ si sposta.
Sulle velocità il filtro serve (la derivazione numerica amplifica il rumore) ed è innocuo,
perché le velocità non entrano nel MSD.

**Test di controllo obbligatorio.** Calcola

$$v_{\rm rms}^{\rm (int)} = \sqrt{\lim_{\Delta\to0}\langle|\Delta\mathbf{r}|^2\rangle/\Delta^2}
\qquad\text{vs}\qquad v_{\rm rms}^{\rm (dir)} = \sqrt{\langle v_x^2+v_y^2\rangle}$$

Devono coincidere entro il 2%. Se $v^{\rm (int)} < v^{\rm (dir)}$ hai filtrato le posizioni.
Se $v^{\rm (int)} > v^{\rm (dir)}$ hai rumore GPS residuo che gonfia gli incrementi corti.

---

## 1.3 Griglia dei lag e sample size

### 1.3.1 Griglia logaritmica

```python
def lag_grid(dt: float, lag_max: float, base: float = 1.2) -> np.ndarray:
    """Lag in numero di campioni, spaziati log, senza duplicati."""
    n_max = int(lag_max / dt)
    lags = np.unique(np.round(base ** np.arange(0, np.log(n_max)/np.log(base) + 1)))
    return lags[(lags >= 1) & (lags <= n_max)].astype(int)
```

`base = 1.2` dà ~38 lag per 3 decadi. Sufficiente per un fit stabile, abbastanza rado da
tenere i costi bassi.

**Perché logaritmica.** In log-log ogni decade deve avere lo stesso peso nel fit. Una griglia
lineare mette il 90% dei punti nell'ultima decade e il fit stima di fatto solo quella.

### 1.3.2 Lag massimo

$$\Delta_{\max} = \frac{T_{\rm mediana}}{10}$$

**Perché $/10$ e non $/2$.** A lag $\Delta$ su un volo di durata $T$ ci sono al più $T/\Delta$
incrementi indipendenti. A $\Delta = T/2$ sono **due**: la stima è dominata dalla varianza e
fortemente biased verso il basso (bias di finestra finita, noto per il TAMSD). A $T/10$ ne hai
dieci per volo, e con migliaia di voli la statistica regge.

### 1.3.3 Sample size effettivo — da riportare ovunque

Con finestre scorrevoli gli incrementi si sovrappongono e **non** sono indipendenti.

$$N_{\rm eff}(\Delta) = \sum_{f\in\text{voli}} \left\lfloor \frac{T_f}{\Delta} \right\rfloor$$

```python
def n_eff(durations: np.ndarray, lag_s: float) -> int:
    return int(np.floor(durations / lag_s).sum())
```

**Uso obbligatorio in tre punti:**

1. barre d'errore (mai $1/\sqrt{N_{\rm campioni}}$, sempre $1/\sqrt{N_{\rm eff}}$);
2. soglia di significatività dei parametri d'ordine circolari (§1.5.3);
3. taglio dei lag: scarta i lag con $N_{\rm eff} < 200$.

**Perché conta tanto.** Con $10^4$ campioni per volo e $\Delta=600$ s hai ~$10^4$ incrementi
sovrapposti ma solo ~17 indipendenti. Usare il primo numero sottostima l'errore di un fattore
25. È il motivo per cui in letteratura si trovano esponenti con barre d'errore incredibilmente
strette e incompatibili tra loro.

---

## 1.4 Deriva e vento

> **Prerequisito assoluto.** Una deriva residua $\mathbf{v}_d$ aggiunge $|\mathbf{v}_d|^2\Delta^2$
> al MSD. Rende tutto balistico a lag lunghi, appiattisce la curtosi, gonfia $\nu$, e **trasla**
> la PDF invece di riscalarla — distruggendo qualunque test di collasso.

### 1.4.1 Vento da odografo a finestra scorrevole

**Idea.** In spiralata a velocità aerodinamica (TAS) costante, la velocità al suolo descrive
un cerchio nel piano $(v_x,v_y)$: **centro = vento**, **raggio = TAS**. Non serve sapere dove
sono le spiralate: si fitta ovunque e si tengono le finestre dove il fit è buono. Le finestre
non-circolari (transizioni) falliscono i criteri e si scartano da sole.

**Parametri.**

| Parametro | Valore | Motivo |
|---|---|---|
| `W` | 60 s | ~3–4 giri; abbastanza per il fit, abbastanza corto perché il vento sia costante |
| `stride` | 10 s | sovracampionamento controllato |
| `min_coverage` | 270° | sotto questa copertura il fit algebrico è fortemente biased |
| `max_resid` | 0.15 | RMS residuo / raggio |
| `tas_range` | (6, 20) m/s | dominio fisico parapendio |

**Fit del cerchio (Kåsa, algebrico, non iterativo).**

```python
def fit_circle_kasa(vx: np.ndarray, vy: np.ndarray):
    """Ritorna (cx, cy, R, rms_resid). Dati centrati per stabilità numerica."""
    mx, my = vx.mean(), vy.mean()
    u, v = vx - mx, vy - my
    Suu, Suv, Svv = (u*u).sum(), (u*v).sum(), (v*v).sum()
    Suuu, Svvv    = (u**3).sum(), (v**3).sum()
    Suvv, Svuu    = (u*v*v).sum(), (v*u*u).sum()
    A = np.array([[Suu, Suv], [Suv, Svv]])
    b = 0.5 * np.array([Suuu + Suvv, Svvv + Svuu])
    try:
        uc, vc = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return None
    R = np.sqrt(uc**2 + vc**2 + (Suu + Svv) / len(u))
    d = np.hypot(u - uc, v - vc)
    return mx + uc, my + vc, R, np.sqrt(np.mean((d - R)**2))
```

⚠️ Il fit di Kåsa è biased su archi parziali (sottostima il raggio). È il motivo per cui
`min_coverage = 270°` non è negoziabile: su archi quasi completi il bias è trascurabile.

**Copertura angolare.** Non il range degli angoli (l'avvolgimento la falsa), ma l'angolo
totale percorso:

```python
def angular_coverage(vx, vy, cx, cy) -> float:
    ang = np.unwrap(np.arctan2(vy - cy, vx - cx))
    return abs(ang[-1] - ang[0])   # rad
```

**Perché l'angolo totale e non il range.** Un pilota che oscilla avanti e indietro copre un
range di 300° senza mai chiudere un giro: il fit è mal condizionato ma il range lo dichiara
valido. L'angolo totale unwrappato distingue una spiralata vera da un'oscillazione.

**Interpolazione tra finestre valide.** Lineare in `t`, con `null` dove il gap tra finestre
valide consecutive supera 300 s.

```python
wind = (df.select("t", "wx", "wy")
          .with_columns(pl.col("wx","wy").interpolate())
          .with_columns(pl.when(gap_len > 300).then(None).otherwise(pl.col("wx")).alias("wx")))
```

### 1.4.2 Controllo incrociato ERA5

Vento a quota/posizione/ora del volo, da reanalisi. Risoluzione grossolana (~30 km, 1 h) ma
**completamente indipendente dai tuoi dati**.

Metrica di confronto: correlazione e bias tra $|\mathbf{w}_{\rm odo}|$ e $|\mathbf{w}_{\rm ERA5}|$,
e differenza angolare mediana. Attesa: correlazione > 0.6, bias di modulo < 2 m/s.

**Perché farlo.** L'odografo può fallire sistematicamente su voli con poche spiralate (voli di
distanza in condizioni forti). ERA5 non ha quel modo di fallimento. Se i due divergono su una
classe di voli, quella classe va trattata a parte.

### 1.4.3 Le tre derive — non confonderle

| Quantità | Definizione | Cosa rappresenta |
|---|---|---|
| $\mathbf{w}(t)$ | centro dell'odografo | moto della massa d'aria |
| $\mathbf{v}_d^{\rm net}$ | $[\mathbf{r}(T)-\mathbf{r}(0)]/T$ | spostamento netto: vento **+** intenzione |
| $\langle\Delta\mathbf{r}(\Delta)\rangle$ | media degli incrementi al lag $\Delta$ | deriva effettiva a quella scala |

### 1.4.4 Incrementi centrati — la definizione operativa

Tutte le osservabili di §2 si calcolano su

$$\boxed{\ \Delta\mathbf{r}_c(t;\Delta) = \big[\mathbf{r}(t+\Delta)-\mathbf{r}(t)\big] - \mathbf{v}_d^{\rm net}\,\Delta\ }$$

con $\mathbf{v}_d^{\rm net}$ **per volo**.

**Perché per volo e non globale.** Ogni volo ha la sua rotta. Sottrarre una deriva media
d'ensemble lascia intatta la deriva del singolo volo, che è quella che conta.

**Perché non lavorare nel frame dell'aria.** Sottrarre $\int\mathbf{w}\,dt$ dà la traiettoria
rispetto alla massa d'aria — corretta per interpretare la *decisione* del pilota, sbagliata per
il *trasporto*, che è uno spostamento fisico nello spazio. Il frame dell'aria serve in §3.4
come stratificazione, non come frame primario.

**Da riportare sempre in coppia.** Ogni esponente va calcolato due volte, con e senza
centratura. La differenza $\nu_{\rm raw} - \nu_c$ è la misura diretta di quanto l'anomalia
apparente fosse deriva, ed è un numero che va in tesi.

---

## 1.5 Isotropia

> Prerequisito per usare le marginali della PDF (parte 2, §2.4). Da riportare **anche** se
> poi lavori solo in radiale, perché quantifica la validità della media angolare.

### 1.5.1 Distribuzione angolare degli incrementi

$$\phi(t;\Delta) = \operatorname{atan2}\big(\Delta r_{c,y},\ \Delta r_{c,x}\big)$$

**Proprietà cruciale: è scale-free.** Non dipende dal modulo degli incrementi. È quindi il
test di isotropia corretto in presenza di code pesanti, dove il rapporto degli autovalori
della matrice di covarianza è dominato da pochi outlier e non misura nulla di stabile.

⚠️ **Ogni incremento pesa 1.** Non pesare per il modulo: reintrodurrebbe la sensibilità alle
code che stiamo evitando.

### 1.5.2 Parametri d'ordine circolari

$$a_n(\Delta) = \frac{1}{N}\sum_j e^{\,i n \phi_j}$$

```python
def circular_moments(phi: np.ndarray, orders=(1, 2, 4)) -> dict:
    return {n: np.exp(1j * n * phi).mean() for n in orders}
```

| Modo | Rileva | Sorgente fisica nel volo libero |
|---|---|---|
| $\lvert a_1\rvert$ | ordine **polare** | deriva residua, rotta netta |
| $\arg a_1$ | direzione | rotta media |
| $\lvert a_2\rvert$ | ordine **nematico** | anisotropia assiale |
| $\tfrac12\arg a_2$ | asse maggiore | orientamento del crinale / linea di convergenza |
| $\lvert a_4\rvert$ | tetratico | in genere trascurabile; se non lo è, sospetta artefatto di griglia |

⚠️ **$a_2$ è il modo che si dimentica.** Voli avanti-e-indietro lungo un crinale, una linea di
convergenza o una gamba di gara producono anisotropia **assiale senza direzione netta**:
$a_1\approx0$ ma $|a_2|$ grande. Verificare solo $a_1$ ti dice "isotropo" quando non lo è
affatto, e la marginale che poi userai sarà sistematicamente sbagliata su un asse.

### 1.5.3 Soglia di significatività

Sotto l'ipotesi nulla di angoli uniformi e indipendenti, $2N|a_n|^2 \sim \chi^2_2$ (test di
Rayleigh). Al 5%:

$$|a_n|_{\rm crit} = \sqrt{\frac{2.996}{N_{\rm eff}}} \approx \frac{1.73}{\sqrt{N_{\rm eff}}}$$

```python
def isotropy_threshold(n_eff: int, level: float = 0.05) -> float:
    return np.sqrt(-np.log(level) / n_eff)
```

⚠️ **$N_{\rm eff}$, non il numero di campioni.** Con finestre scorrevoli il numero di angoli è
enormemente maggiore del numero di angoli indipendenti; usare il primo dichiara significativo
qualunque valore.

### 1.5.4 Dipendenza da scala

Plotta $|a_1|(\Delta)$ e $|a_2|(\Delta)$ con la soglia sovrapposta, su tutta la griglia di lag.

Struttura attesa e sua lettura:

- **lag corti** ($\Delta \lesssim T_{\rm circ}$): $|a_2|$ può essere non nullo per la geometria
  della spiralata; è un artefatto di scala, non anisotropia di trasporto.
- **lag intermedi**: se emerge $|a_1|$, la centratura di §1.4.4 non ha funzionato — controlla.
- **lag lunghi**: qui emergono orografia e rotta. È l'anisotropia che conta per la PDF.

### 1.5.5 Assi principali

Se $|a_2| > $ soglia sul range di lag di interesse:

```python
theta_major = 0.5 * np.angle(a2)
R = np.array([[np.cos(theta_major),  np.sin(theta_major)],
              [-np.sin(theta_major), np.cos(theta_major)]])
dr_principal = dr_centered @ R.T     # colonna 0 = asse maggiore
```

Le due marginali vanno poi analizzate **separatamente** (parte 2, §2.4), mai mediate.

### 1.5.6 Output della sezione

`isotropy.parquet` — una riga per `(lag, stratum)`:

```
lag_s, n_eff, a1_abs, a1_arg, a2_abs, a2_arg, a4_abs, threshold_05, theta_major
```

**Decisione operativa registrata**: `isotropic = (a1_abs < thr) & (a2_abs < thr)`. Questa
colonna determina se la parte 2 usa la radiale da sola o anche le marginali principali.

---

## 1.6 Ordine di esecuzione

```
tracks.parquet (grezzo)
   │
   ├─ 1.1.3  maschera validità ────────────► valid
   ├─ 1.2.2  SG solo su velocità ──────────► vx, vy, vz
   │            └─ test v_rms int vs dir ── GATE: deve passare
   │
   ├─ 1.4.1  odografo scorrevole ──────────► wx, wy, frac_wind_valid
   ├─ 1.4.2  confronto ERA5 ───────────────► GATE: correlazione > 0.6
   ├─ 1.4.3  v_d_net per volo ─────────────► flights.parquet
   │
   ├─ 1.3.1  griglia lag ──────────────────► lags
   ├─ 1.3.3  N_eff per lag ────────────────► taglio N_eff < 200
   │
   └─ 1.5    isotropia ────────────────────► isotropy.parquet
                └─ decide radiale vs marginali in parte 2
```

I due **GATE** sono bloccanti: se falliscono, il problema è nel preprocessing e nessuna
osservabile di trasporto va calcolata prima di averlo risolto.
