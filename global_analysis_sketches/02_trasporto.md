# 2 — Osservabili di trasporto

> Parte 2 di 3. Tutto qui dentro opera su $\Delta\mathbf{r}_c$ (incrementi centrati,
> parte 1 §1.4.4), su run contigui validi, sulla griglia di lag di §1.3.

---

## 2.1 MSD

### 2.1.1 Perché

È il punto di ingresso: fissa $\nu$, la velocità RMS e il tempo di crossover $\tau_c$. Ma da
solo **non discrimina nulla** — tre meccanismi diversi producono la stessa forma. Serve a
fissare i numeri che le osservabili successive devono riprodurre.

### 2.1.2 Definizione

$$\text{MSD}(\Delta) = \big\langle |\Delta\mathbf{r}_c(t;\Delta)|^2 \big\rangle_{t,\,\text{voli}}$$

### 2.1.3 Algoritmo — FFT

Il calcolo diretto è $O(N^2)$ per volo. Con $N\sim10^4$ e migliaia di voli è proibitivo.
L'identità

$$\text{MSD}(m) = \underbrace{\frac{1}{N-m}\sum_{k}\big(|\mathbf{r}_k|^2+|\mathbf{r}_{k+m}|^2\big)}_{S_1(m)} - 2\underbrace{\frac{1}{N-m}\sum_k \mathbf{r}_k\cdot\mathbf{r}_{k+m}}_{S_2(m)}$$

riduce tutto a $O(N\log N)$: $S_2$ è un'autocorrelazione (Wiener–Khinchin), $S_1$ una somma
cumulativa.

```python
def _autocorr_fft(x: np.ndarray) -> np.ndarray:
    N = len(x)
    F = np.fft.fft(x, n=2*N)
    res = np.fft.ifft(F * F.conjugate())[:N].real
    return res / (N - np.arange(N))

def msd_fft(r: np.ndarray) -> np.ndarray:
    """r: (N, 2) posizioni centrate. Ritorna MSD per m = 0..N-1."""
    N = len(r)
    D = np.square(r).sum(axis=1)
    D = np.append(D, 0.0)
    S2 = sum(_autocorr_fft(r[:, i]) for i in range(r.shape[1]))
    Q = 2 * D.sum()
    S1 = np.empty(N)
    for m in range(N):
        Q -= D[m-1] + D[N-m]
        S1[m] = Q / (N - m)
    return S1 - 2 * S2
```

Verifica: `msd_fft(r)[0]` deve essere `0.0` a meno dell'errore macchina. È il primo unit test.

⚠️ L'FFT vale **solo per $q=2$**. Per gli altri momenti (§2.2) serve il calcolo diretto con
stride.

### 2.1.4 Aggregazione tra voli — scelta esplicita

Due schemi, risultati diversi:

| Schema | Formula | Quando |
|---|---|---|
| **pooled** | media su tutti gli incrementi | i voli lunghi dominano |
| **per-flight** | media dei MSD per volo, peso uguale | ogni volo pesa 1 |

**Usa `per-flight` come default.** Il pooling pesa i voli per $T_f$: un singolo volo di 8 ore
in condizioni eccezionali può fissare l'esponente d'ensemble. E la stratificazione di §3.4
richiede comunque il MSD per volo.

```python
def ensemble_msd(per_flight: dict[str, np.ndarray], lags: np.ndarray) -> np.ndarray:
    M = np.vstack([m[lags] for m in per_flight.values()])
    return np.nanmean(M, axis=0)
```

⚠️ Nel per-flight, un volo contribuisce a un lag solo se $T_f \ge 10\Delta$. Altrimenti `nan`.
Registra `n_flights(lag)` accanto a `n_eff(lag)`: il primo cala con $\Delta$ e spiega gli
allargamenti dell'errore.

### 2.1.5 Cosa estrarre

**$v_{\rm rms}$ dall'intercetta balistica.** Fit di $\text{MSD}=v^2\Delta^2$ sui lag
$\Delta \le 5$ s. Confronto obbligatorio con $\sqrt{\langle v_x^2+v_y^2\rangle}$ (gate di
parte 1 §1.2.2).

**$\tau_c$ dall'incrocio.** Fit di due rette in log-log (balistico forzato a pendenza 2, ramo
anomalo libero) e intersezione analitica:

```python
def crossover(lags, msd, ball_max=5.0, anom_min=60.0, anom_max=None):
    b = lags <= ball_max
    v2 = np.exp(np.mean(np.log(msd[b]) - 2*np.log(lags[b])))   # MSD = v2 * lag^2
    a = (lags >= anom_min) & (lags <= (anom_max or lags.max()))
    nu, logA = np.polyfit(np.log(lags[a]), np.log(msd[a]), 1)
    tau_c = np.exp((logA - np.log(v2)) / (2 - nu))
    return np.sqrt(v2), nu, tau_c
```

**$\nu$ su almeno tre finestre di fit.** Es. $[60,600]$, $[120,1200]$, $[300,\Delta_{\max}]$ s.
Se $\nu$ si muove di più dell'errore bootstrap, **non è asintotico** e va riportato come
esponente effettivo su un range dichiarato.

### 2.1.6 Test di ampiezza — vincolo, non fit

Se il ramo anomalo è $A\,\Delta^{3-\alpha}$, l'analisi dimensionale impone
$A = C\,v^2 t_0^{\alpha-1}$ con $C=O(1)$ e $t_0$ il cutoff inferiore dei tempi di volo. Quindi

$$\tau_c \simeq t_0$$

**Perché è potente.** $t_0$ sarà misurato indipendentemente dopo la segmentazione, dalle
durate delle transizioni. La coincidenza (entro un fattore ~3) è un vincolo quantitativo sul
modello Lévy walk, non un parametro libero. Se $\tau_c$ cade molto sopra la transizione più
breve osservata, il crossover è fissato da persistenza direzionale e l'interpretazione cambia.

Registra `tau_c` in `msd_summary.parquet`. È una delle righe della tabella di consistenza
(parte 3 §3.6).

---

## 2.2 Spettro dei momenti — *il test principale*

### 2.2.1 Perché

Discrimina Lévy walk da processo gaussiano correlato con **una sola figura**, e in modo
visivo invece che tramite un fit delicato. Se dovessi eseguire una sola osservabile
pre-segmentazione, è questa.

$$\big\langle|\Delta\mathbf{r}_c(\Delta)|^q\big\rangle \sim \Delta^{\,q\nu(q)}$$

| Forma di $q\nu(q)$ | Processo |
|---|---|
| **bilineare**, ginocchio a $q_c$ | Lévy walk (*strong anomalous diffusion*) |
| **lineare** per l'origine, $q\nu = qH$ | gaussiano correlato (fBm) |

Per Lévy walk con $1<\alpha<2$:

$$q\nu(q) = \begin{cases} q/\alpha & q<\alpha\\ q+1-\alpha & q>\alpha\end{cases}$$

Il ginocchio è a $q_c=\alpha$. **Tre stime indipendenti di $\alpha$**: pendenza sinistra,
pendenza destra, posizione del ginocchio — più il vincolo $\alpha = 3-\nu$ da §2.1.

### 2.2.2 Implementazione

```python
Q_GRID = np.array([0.25,0.5,0.75,1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0])

def moment_spectrum(r_c: np.ndarray, lags: np.ndarray, q_grid=Q_GRID):
    """r_c: (N,2). Stride = lag → incrementi non sovrapposti."""
    out = np.full((len(lags), len(q_grid)), np.nan)
    tails = np.full((len(lags), len(q_grid)), np.nan)
    for i, m in enumerate(lags):
        d = r_c[m:] - r_c[:-m]
        s = np.hypot(d[:, 0], d[:, 1])[::m]          # decorrelazione
        if len(s) < 20:
            continue
        for j, q in enumerate(q_grid):
            w = s ** q
            out[i, j] = w.mean()
            k = max(1, int(0.01 * len(w)))
            tails[i, j] = np.sort(w)[-k:].sum() / w.sum()
    return out, tails
```

⚠️ **Stride `[::m]`.** Per $q=2$ le finestre sovrapposte sono accettabili (l'FFT le usa) perché
il bias è nullo e conta solo la varianza. Per $q>2$ no: un singolo evento estremo compare in
$m$ finestre sovrapposte e viene contato $m$ volte, gonfiando il momento in modo sistematico.
**Lo stride non è un'ottimizzazione, è correttezza.**

### 2.2.3 Il controllo delle code

`tails[i,j]` è la frazione del momento contribuita dall'1% di campioni più grandi.

| Frazione | Interpretazione |
|---|---|
| < 20% | stima affidabile |
| 20–50% | riportare con cautela esplicita |
| > 50% | **non stimabile**: il momento è un singolo evento |

Da plottare accanto a $q\nu(q)$, non da nascondere. Un momento a $q=4$ che è per l'80% un
singolo volo non è un momento, e un referee lo chiederà.

### 2.2.4 Fit del ginocchio

Regressione bilineare con breakpoint libero:

```python
from scipy.optimize import curve_fit

def bilinear(q, qc, s_lo, s_hi):
    return np.where(q < qc, s_lo*q, s_lo*qc + s_hi*(q - qc))

qc, s_lo, s_hi = curve_fit(bilinear, q_grid, q_nu, p0=[1.7, 0.6, 1.0])[0]
```

Attese per Lévy walk: `s_lo ≈ 1/α`, `s_hi ≈ 1`, `qc ≈ α`. Il vincolo `s_hi ≈ 1` è
particolarmente informativo: significa che il fronte è **balistico**.

**Test di preferenza del modello.** Confronta il fit bilineare con quello lineare puro
($q\nu = Hq$) via BIC. Se il lineare vince, sei nel ramo gaussiano correlato del diagramma di
fase e l'interpretazione Lévy walk va abbandonata.

### 2.2.5 Curtosi — versione economica

$$K(\Delta)=\frac{\langle|\Delta\mathbf{r}_c|^4\rangle}{\langle|\Delta\mathbf{r}_c|^2\rangle^2}$$

**Riferimento**: per gaussiano 2D isotropo, $K = 2$ (non 3 — quello è il caso 1D). Errore
frequente.

Crescente con $\Delta$ → code pesanti. Piatta a 2 → gaussiano, l'anomalia viene dalle
correlazioni.

---

## 2.3 Scaling della PDF

### 2.3.1 Perché, e cosa aspettarsi

Il collasso della PDF è la controparte "in forma" dello spettro dei momenti. Il punto
importante è controintuitivo:

> **Il fallimento del collasso è il risultato atteso, non un problema.**

Per un Lévy walk il bulk scala con $\delta=1/\alpha$ (legge stabile) e il fronte balistico con
$\delta=1$: due riscalamenti diversi (bi-scaling / densità infinita). Un collasso singolo
riuscito **esclude** il Lévy walk.

### 2.3.2 Rappresentazione primaria: survival function radiale

$$S(r,\Delta) = P\big(|\Delta\mathbf{r}_c(\Delta)| > r\big)$$

Tre ragioni per preferirla alla densità:

1. **Nessun binning** → nessun rumore da istogramma sulle code, dove i bin sono quasi vuoti.
2. **Nessun Jacobiano da sbagliare** (vedi ⚠️ sotto).
3. **Ben definita senza isotropia** — è una media sulle direzioni; se anisotropo resta
   interpretabile per l'esponente, mentre la forma va letta con cautela.

```python
def survival(s: np.ndarray):
    x = np.sort(s)
    return x, 1.0 - np.arange(1, len(x)+1) / len(x)
```

⚠️ **Jacobiano.** L'istogramma di $|\Delta\mathbf{r}|$ stima $\rho(r) = 2\pi r\,P(\mathbf{r})$,
**non** $P(\mathbf{r})$. Il riferimento gaussiano per $\rho$ è una **Rayleigh**, non una
gaussiana. È un errore silenzioso: la curva "sembra" sbagliata sulle piccole $r$ e si finisce
per attribuirlo alla fisica.

### 2.3.3 Test di scaling per quantili — implementazione raccomandata

Invece di cercare a occhio un collasso, misura l'esponente di scaling **quantile per quantile**:

$$q_p(\Delta) \sim \Delta^{\,\delta(p)}$$

```python
P_GRID = np.array([0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.995])

def quantile_scaling(r_c, lags, p_grid=P_GRID):
    Q = np.full((len(lags), len(p_grid)), np.nan)
    for i, m in enumerate(lags):
        d = r_c[m:] - r_c[:-m]
        s = np.hypot(d[:, 0], d[:, 1])[::m]
        if len(s) >= 50:
            Q[i] = np.quantile(s, p_grid)
    delta = np.array([np.polyfit(np.log(lags[ok]), np.log(Q[ok, j]), 1)[0]
                      for j, ok in enumerate((~np.isnan(Q)).T)])
    return Q, delta
```

**Lettura di $\delta(p)$:**

| Comportamento | Diagnosi |
|---|---|
| $\delta(p)$ **costante** | scaling singolo → collasso riesce |
| $\delta(p)$ **cresce** verso 1 al crescere di $p$ | bi-scaling → **Lévy walk** |
| $\delta \approx 1$ già a $p=0.5$ | deriva residua, torna a parte 1 §1.4 |

**Perché i quantili e non i momenti.** Contengono la stessa informazione ma sono robusti: un
quantile non è mai dominato da un singolo evento, e non richiede il controllo delle code di
§2.2.3. I momenti restano utili per il contatto con la teoria (le formule sono scritte per
momenti); i quantili per decidere.

Attesa per Lévy walk: $\delta(0.5)\approx 1/\alpha$, $\delta(0.99)\to 1$.

### 2.3.4 Collasso esplicito — due figure

**Figura A — bulk.** Plotta $S(r,\Delta)$ vs $r/\Delta^{1/\alpha}$ con $\alpha$ da §2.2.
Deve collassare per $S \gtrsim 0.1$ e **sfaldarsi** sulla coda.

**Figura B — fronte.** Plotta $S(r,\Delta)$ vs $r/\Delta$. Deve collassare per $S \lesssim 0.05$
e sfaldarsi sul bulk.

Due riscalamenti che collassano regioni complementari **è** la firma del Lévy walk. Cerca in
particolare una spalla o un picco a $r \approx v_{\max}\Delta$.

**Metrica quantitativa del collasso** (per non decidere a occhio):

```python
def collapse_cost(curves, mask):
    """curves: lista di (x_scaled, S). Costo = dispersione su griglia comune."""
    grid = np.geomspace(*mask)
    interp = np.vstack([np.interp(grid, x, np.log(S+1e-12)) for x, S in curves])
    return np.nanstd(interp, axis=0).mean()
```

Riporta il costo per Figura A sul bulk e per Figura B sulla coda. Il messaggio è che
**nessun singolo $\delta$ minimizza entrambi**.

### 2.3.5 Stima dell'esponente di coda

Non fittare pendenze su istogrammi log-log: il metodo è biased e non ha errore statistico
definito.

**Hill estimator, con Hill plot.**

```python
def hill(s: np.ndarray, k: int) -> float:
    x = np.sort(s)[::-1]
    return 1.0 / np.mean(np.log(x[:k] / x[k]))
```

Plotta $\hat\alpha(k)$ vs $k$ per $k \in [10, N/10]$. **Cerca un plateau.** Se non c'è, non
c'è una coda a potenza pura, e va detto.

**MLE con cutoff (Clauset–Shalizi–Newman).**

1. per ogni candidato $r_{\min}$ (i valori osservati), $\hat\alpha = 1 + n\big[\sum_i \ln(r_i/r_{\min})\big]^{-1}$;
2. scegli $r_{\min}$ che minimizza la distanza KS tra ECDF e Pareto fittata;
3. p-value via dataset sintetici (≥ 1000): frazione di KS sintetici ≥ KS osservato. $p<0.1$
   → l'ipotesi di legge di potenza è rigettata.

**Confronto con la lognormale, obbligatorio.** Test di Vuong (likelihood ratio normalizzato)
su $r \ge r_{\min}$. Su 1.5 decadi le due sono raramente separabili, e **dichiararlo è più
solido che ignorarlo**. Un referee lo chiederà.

### 2.3.6 Marginali — solo dopo il gate di isotropia

Vale il fatto tecnico: per una distribuzione isotropa 2D con coda $r^{-(2+\mu)}$, la marginale
ha coda $u^{-(1+\mu)}$, **stesso $\mu$**. L'esponente di coda è invariante per proiezione, e
la proiezione di una stabile isotropa è una stabile 1D con lo stesso indice. Per questo la
marginale è uno stimatore legittimo di $\alpha$.

Gerarchia delle minacce:

| # | Problema | Gravità | Azione |
|---|---|---|---|
| 1 | deriva ($a_1\neq0$) | **fatale** — trasla, non riscala | rimuovere (parte 1 §1.4) |
| 2 | nematica ($a_2\neq0$) | gestibile — cambia la scala, non l'esponente | assi principali, due marginali separate |
| 3 | esponente direzione-dipendente | raro | emerge dal confronto delle due marginali |

**Procedura.** Se `isotropic == True` (parte 1 §1.5.6): calcola le marginali su due assi
arbitrari ortogonali come controllo — devono coincidere. Se `False`: ruota agli assi principali
e analizza le due marginali **separatamente**. Se gli esponenti differiscono oltre l'errore
bootstrap, riporta il fatto e non mediare.

---

## 2.4 Correlazioni

### 2.4.1 VACF

$$C_v(\tau) = \big\langle \mathbf{v}_c(t+\tau)\cdot\mathbf{v}_c(t)\big\rangle,\qquad
\mathbf{v}_c = \mathbf{v} - \mathbf{v}_d^{\rm net}$$

Via FFT, per volo, poi media con peso uguale. Normalizza per $C_v(0)$.

| Forma | Diagnosi |
|---|---|
| esponenziale | PRW → diffusione normale asintotica |
| potenza $\tau^{-(\alpha-1)}$ | Lévy walk |

**Consistenza Green–Kubo** — verifica numerica, non decorativa:

$$\text{MSD}(\Delta) = 2\int_0^\Delta (\Delta-\tau)\,C_v(\tau)\,d\tau$$

```python
def msd_from_vacf(tau, Cv, lags):
    return np.array([2*np.trapz((L - tau[tau<=L])*Cv[tau<=L], tau[tau<=L]) for L in lags])
```

Deve riprodurre il MSD di §2.1 entro il 5%. Se no, hai un'inconsistenza tra la serie di
posizioni e quella di velocità (tipicamente: SG applicato anche alle posizioni).

**Le oscillazioni smorzate al periodo di spiralata (~15–20 s) non sono rumore.** Sono il
periodo di virata in termica, estratto senza segmentare. Registralo: serve a calibrare l'HMM e
a verificare la separazione di scale (parte 3 §3.3.2). La parte rilevante per il trasporto è
l'inviluppo a $\tau \gg T_{\rm circ}$.

### 2.4.2 PSD della velocità

Welch, `nperseg = 1024`, finestra di Hann, overlap 50%. Wiener–Khinchin dà
$S_v(f)\sim f^{\alpha-2}$ se $C_v\sim\tau^{-(\alpha-1)}$.

Stessa informazione di §2.4.1, ma statistica d'errore diversa e picco di spiralata risolto
molto meglio. **Controllo, non stima indipendente** — non contarlo due volte nella tabella di
consistenza.

### 2.4.3 Correlazione di heading multi-scala

Heading coarse-grained a scala $\Delta$:

$$\theta_\Delta(t) = \arg\big[\mathbf{r}(t+\Delta)-\mathbf{r}(t)\big],\qquad
C_\Delta(\tau) = \big\langle\cos[\theta_\Delta(t+\tau)-\theta_\Delta(t)]\big\rangle$$

⚠️ **Trappola fondamentale: per $\tau < \Delta$ le finestre si sovrappongono** e
$C_\Delta(\tau)$ è non nulla per costruzione geometrica, non per memoria. Con incrementi
indipendenti la sovrapposizione dà già $C_\Delta(\tau)\approx 1-\tau/\Delta$.

**Vincolo: calcolare solo per $\tau = k\Delta$, $k=1,2,3,\dots$**

```python
def heading_corr(r, m, k_max=40):
    th = np.arctan2(*(r[m:] - r[:-m]).T[::-1])[::m]   # non sovrapposti
    z = np.exp(1j*th)
    return np.array([np.real(np.mean(z[k:] * np.conj(z[:-k]))) for k in range(1, k_max+1)])
```

**Perché serve.** È il sostituto pre-segmentazione di $C(m)$ per ciclo. Scansiona $\Delta$:
sotto il tempo di ciclo domina la spiralata; sopra, converge alla statistica
inter-transizione. Il plateau in $\Delta$ **localizza la scala di separazione** — informazione
diretta per configurare l'HMM.

**Test di markovianità direzionale.** Stima $c_1 = \langle e^{i\phi}\rangle$ dal solo $k=1$ e
verifica se $C_\Delta(k)=\mathrm{Re}(c_1^{\,k})$ predice tutta la curva.

| Esito | Diagnosi |
|---|---|
| decadimento geometrico predetto da $c_1$ | memoria markoviana → esponente invariato |
| decadimento a potenza $k^{-\gamma}$, $\gamma>1$ | memoria effettiva finita, equivalente al caso sopra |
| $\gamma<1$ | **dipendenza a lungo raggio** → contributo $t^{2-\gamma}$ al MSD |

⚠️ Fitta $C_\Delta(k) = c_\infty + A k^{-\gamma}$ con **offset libero**. Un plateau
$c_\infty>0$ è deriva residua, non memoria, e su un range limitato di $k$ è indistinguibile da
una potenza a $\gamma$ piccolo. Se $c_\infty$ non è compatibile con zero, torna a parte 1 §1.4.

---

## 2.5 Tempi di persistenza geometrici

### 2.5.1 Perché

Sostituisce la segmentazione con una **soglia geometrica** invece che con un modello a stati.
Dà direttamente la distribuzione delle lunghezze di run, quindi $\beta$ (e via
$\gamma=\beta-1$ copre anche il ramo memoria). È anche una **diagnostica sulla segmentabilità**:
se il risultato dipende fortemente dalla soglia, non esiste una vera separazione di scale e
l'HMM sarà fragile.

### 2.5.2 ⚠️ Il bias di ispezione — il punto critico

Campionare $T_p(t)$ a ogni istante $t$ **non** dà la distribuzione delle lunghezze di run: dà
la sua versione **length-biased** (paradosso dell'ispezione). Un run lungo è attraversato da
più istanti di partenza, quindi è sovracampionato in proporzione alla sua durata.

Se $P(L>\ell)\sim \ell^{-\beta}$, la versione length-biased ha esponente $\beta-1$.

$$\boxed{\ \text{Stimare }\beta\text{ dal campionamento per istante dà }\beta-1.\ }$$

Su valori tipici ($\beta\approx1.7$) sbaglieresti di un'unità intera, cioè completamente.

**Soluzione: decomposizione in run non sovrapposti**, greedy dall'inizio.

```python
def persistence_runs(r: np.ndarray, s_max: float, min_len: int = 5) -> np.ndarray:
    """Run consecutivi non sovrapposti con sinuosità <= s_max. Ritorna lunghezze (campioni)."""
    step = np.hypot(*np.diff(r, axis=0).T)
    arc = np.concatenate(([0.0], np.cumsum(step)))
    lengths, i, N = [], 0, len(r)
    while i < N - min_len:
        j = i + min_len
        while j < N:
            chord = np.hypot(*(r[j] - r[i]))
            if chord <= 0 or (arc[j] - arc[i]) / chord > s_max:
                break
            j += 1
        lengths.append(j - i)
        i = j
    return np.array(lengths)
```

**Sinuosità** = lunghezza d'arco / corda. Sempre $\ge 1$. Soglie da scansionare:
`s_max ∈ {1.05, 1.15, 1.30}`, corrispondenti grossomodo a coni di semiapertura 18°, 31°, 45°.

⚠️ La condizione **non è monotona** in $j$ (un tratto può rientrare in soglia dopo esserne
uscito). La definizione adottata è **prima violazione**, ed è quella da dichiarare in tesi.
Cambiarla cambia la statistica.

### 2.5.3 Lettura

Fitta $P(T_p > \tau)$ con la procedura CSN di §2.3.5.

**Consistenza attesa**: $\beta \approx \alpha \approx 3-\nu$.

**Scansione della soglia.** Se $\beta$ è stabile su `s_max ∈ {1.05, 1.15, 1.30}` il risultato è
robusto. Se varia di più dell'errore bootstrap, non c'è separazione di scale — risultato
negativo importante da riportare, perché predice che anche l'HMM darà segmentazioni
soglia-dipendenti.

---

## 2.6 Blocchi e shuffle test

### 2.6.1 Costruzione

Taglia ogni volo in blocchi **non sovrapposti** di durata $\Delta_b$ e tratta gli spostamenti
$\{\Delta\mathbf{x}_k\}$ come pseudo-passi.

**Scelta di $\Delta_b$**: $\Delta_b \gtrsim \tau_c$ (da §2.1.5), tipicamente 60–120 s. Sotto
$\tau_c$ i blocchi cadono dentro il regime balistico e non rappresentano passi.

**Ripeti per due o tre $\Delta_b$**: le conclusioni devono essere stabili.

### 2.6.2 I tre shuffle

```python
def surrogate(steps: np.ndarray, mode: str, rng) -> np.ndarray:
    """steps: (K,2) spostamenti di blocco. Ritorna traiettoria surrogata (K+1,2)."""
    if mode == "block":       # permuta i vettori interi
        s = steps[rng.permutation(len(steps))]
    elif mode == "magnitude": # permuta i moduli, conserva le direzioni
        mag = np.hypot(*steps.T); u = steps / mag[:, None]
        s = u * mag[rng.permutation(len(mag))][:, None]
    elif mode == "both":      # permuta moduli e direzioni indipendentemente
        mag = np.hypot(*steps.T); u = steps / mag[:, None]
        s = u[rng.permutation(len(u))] * mag[rng.permutation(len(mag))][:, None]
    return np.vstack(([0, 0], np.cumsum(s, axis=0)))
```

### 2.6.3 Ordine di esecuzione e lettura

**Esegui `both` per primo.** È un controllo di consistenza, non un test:

> Con `both`, il MSD **deve** dare $\nu=1$. Se non lo fa, esiste un accoppiamento
> magnitudine–direzione non fattorizzabile, e la decomposizione diagonale/incrociata del MSD è
> invalida — insieme a tutta l'interpretazione a due contributi.

Solo se `both` passa, esegui gli altri due:

| Shuffle | Distrugge | Se $\nu$ crolla |
|---|---|---|
| `block` | correlazioni a lungo raggio | l'anomalia era nelle **correlazioni** |
| `magnitude` | code pesanti | l'anomalia era nelle **code** |

**Numero di surrogati**: 200. CI dagli 0.025/0.975 quantili della distribuzione di $\nu$.

⚠️ Confronta solo a lag $> \Delta_b$. Sotto $\Delta_b$ la traiettoria surrogata è interpolazione
lineare dentro il blocco e non ha significato.

### 2.6.4 Rapporto max/somma

$$R_K = \frac{\max_k |\Delta\mathbf{x}_k|}{\sum_k |\Delta\mathbf{x}_k|}$$

Diagnostica di coda pesante **quasi non-parametrica**: nessuna stima, nessun cutoff, nessun fit.

| Scaling | Diagnosi |
|---|---|
| $R_K \sim K^{-1}$ | media finita, nessuna dominanza di eventi singoli |
| $R_K \sim K^{1/\alpha-1}$ | firma del *single big jump* |

Da calcolare in funzione di $K$ (numero di blocchi aggregati), mediando su sottoinsiemi
casuali.

**Perché includerlo.** È l'unica osservabile del documento che non dipende da alcuna scelta
di stima, e quindi l'unica non contestabile su basi metodologiche. Ottima come figura di
supporto.

### 2.6.5 $C(k)$ tra blocchi

Analogo di $C(m)$ per ciclo, in indice di blocco. Stessa lettura di §2.4.3 (fit con offset
libero, soglia $\gamma=1$). Ridondante con §2.4.3 ma su un campionamento diverso: se
concordano, la stima di $\gamma$ è solida.

---

## 2.7 Ergodicità e aging

### 2.7.1 TAMSD vs EAMSD

$$\overline{\delta^2(\Delta)} = \frac{1}{T-\Delta}\int_0^{T-\Delta}\big|\mathbf{r}_c(t+\Delta)-\mathbf{r}_c(t)\big|^2\,dt$$

Parametro di rottura di ergodicità:

$$\text{EB}(\Delta) = \frac{\langle(\overline{\delta^2})^2\rangle - \langle\overline{\delta^2}\rangle^2}{\langle\overline{\delta^2}\rangle^2}$$

Per moto browniano ergodico $\text{EB}\to 0$ come $\Delta/T$.

### 2.7.2 ⚠️ Perché questo test è il più fragile del documento

I voli **non sono realizzazioni dello stesso processo**. Giornata, sito, pilota, tipo di volo
sono disordine *quenched*. Una discrepanza EAMSD/TAMSD può riflettere eterogeneità tra voli,
non non-ergodicità del singolo processo — e le due cose sono indistinguibili senza
stratificare.

**Regola: non interpretare §2.7 prima di aver eseguito la stratificazione (parte 3 §3.4).**
Se dopo la stratificazione la discrepanza sparisce, era eterogeneità.

### 2.7.3 Aging

$$\langle|\Delta\mathbf{r}_c(t_a,\Delta)|^2\rangle \quad\text{in funzione del tempo di attesa } t_a$$

⚠️ Nel volo libero esiste **aging fisico reale** — il ciclo diurno della convezione — che non
è aging nel senso del CTRW. Normalizza $t_a$ rispetto alla finestra di volabilità (ora
rispetto a inizio/fine dell'attività termica) prima di interpretare. Altrimenti misuri il
tramonto.
