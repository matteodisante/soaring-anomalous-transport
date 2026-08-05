# Audit of Chapter 3 — correctness, method, and what the physics can be

## 1. Is the chapter correct?

**No.** Nine statements are false as written, and four more are true only under an assumption the chapter does not state. The exponents themselves mostly survive; what fails is a set of sentences that describe the *shape* of curves the chapter has already computed and stored, and a set of inferences that treat one curve as three.

The defects, ordered by how much they cost.

---

**D1. `04-global-transport.tex:448-449` — "the local slope of $V_2$ declines gently across the fitted range and does not turn."**

It turns twice, inside the fitted range, and I verified this from your own `variations_*.npz`:

| | 60 s | max | min | 1958 s | swing |
|---|---|---|---|---|---|
| para $V_2$ | 2.124 | **2.164** @138 s | **1.902** @613 s | 1.971 | 0.262 |
| hang $V_2$ | 2.182 | **2.195** @84 s | **1.750** @519 s | 2.070 | 0.445 |
| para $V_1$ | 1.850 | — | — | 1.642 | monotone |

It is not a smoothing artefact of `local_slope`: the raw residuals of the straight-line fit carry the same three-phase structure (para $-0.040 \to +0.038 \to -0.029$, amplitude 0.078 dex, against the 0.0027 dex per-lag noise the chapter itself quotes). It is not a coverage artefact either — I refitted on the balanced flight set (every flight finite at all 22 lags, $n=145\,097$ para / 5856 hang) and the shape is unchanged (swing 0.269 / 0.461). Your own breakpoint machinery reports the same thing from the other side, selecting a break at 267 s.

*Fix:* the comparison with the ensemble MSD is still favourable and should be made correctly — $V_2$'s swing is 0.26 against the ensemble curve's 0.91 for paragliders, and it is a **dip** where the ensemble curve is an **arch**, i.e. the opposite sign. For hang gliders the factor is only 3.2 (0.445 against 1.43), so "has no counterpart" must become "is three times smaller and of opposite sign".

---

**D2. `04-global-transport.tex:1112-1117` — "Both are flat across that window: end to end the parameter moves by $+0.02$ and $-0.02$ … and neither shows a maximum at intermediate lags."**

Read straight off `shape_para.npz` / `shape_hang.npz` with your own formula $m_4/(2m_2^2)-1$:

```
para  60:+0.011  92:+0.042  141:+0.065  215:+0.076  266:+0.077  407:+0.066
      623:+0.039  953:+0.013  1179:+0.008  1459:+0.011  1805:+0.027
hang  60:+0.148  114:+0.207  174:+0.232  266:+0.228  407:+0.203  623:+0.160
```

Paragliders rise monotonically over eight consecutive lags to seven times the endpoint value and fall monotonically over seven more. Hang gliders peak at 174 s. The $\pm 0.02$ "drift" is the end-to-end **chord of an arch** — precisely the error the chapter diagnoses at l. 206 ("an exponent fitted across that crossover is a straight line through a bend") and at l. 112 ("The arrangement of the residuals is an arch").

*Fix:* delete "flat" and "neither shows a maximum at intermediate lags." This is not a loss — an interior maximum at 170–320 s in both disciplines is a **positive, model-selecting** measurement, and it is the single most useful new number in the chapter (see §5, §6). It also removes a load-bearing step: the flatness is used at l. 1150 and in the verdict at l. 1370 to present the propagator shape as a fixed property of the process.

---

**D3. `04-global-transport.tex:1214-1216` — "the measured tail is a power law of $\gamma=0.61$ for paragliders and $0.57$ for hang gliders."** *(new; I found this one)*

It is not a power law over that window. The local logarithmic slope of the stored `vacf` array runs monotonically:

```
para  60s:0.30  114:0.42  174:0.53  266:0.63  407:0.71  623:0.77  953:0.82  1179:0.84
hang  60s:0.34  141:0.58  215:0.66  266:0.66  407:0.56  623:0.51  953:0.58  1179:0.62
```

The paraglider $\gamma$ changes by a factor of 2.8 across the 15 lags it is fitted over; the residuals of the single power law form an arch of amplitude 0.106 dex. The quoted 0.61 is a chord across a bend — the same defect as D1 and D2, on a third curve.

The *shape* of the bend is exactly what the estimator's own documented bias produces. I ran exact fBm (your `fractional_brownian`) through your `velocity_autocorrelation` at the archive's record length, where the true $\gamma$ is constant by construction:

```
H=0.85, n=8600, true gamma 0.30 -> fitted 1.176; local gamma 0.55 (60s) rising to 7.4 (1179s)
H=0.85, n=40000, true gamma 0.30 -> fitted 0.535; local gamma 0.40 rising to 0.58
H=0.95, n=8600, true gamma 0.10 -> fitted 0.890; local gamma 0.38 rising to 3.6
```

Mean removal in-sample steepens the tail *progressively with lag*, which is what the module docstring says it does. So the archive's rising local $\gamma$ is consistent with a **constant** true $\gamma$ well below 0.61, and the least-biased reading is the local slope at the floor of the grid: 0.30 (para) / 0.34 (hang). An independent route — the record-length ladder on a fixed population of 802 segments longer than 16 000 s, with the uncentred row as the control — lands on the same number: $\gamma \to 0.29$, flat in $T$ where the centred estimate runs 1.63 → 0.37.

*Consequence, which is larger than the sentence:* the implied floor $2-\gamma$ is not 1.39/1.43 but **≈1.70**, and $\alpha_1=1.75$ then clears it by 0.05 rather than 0.36. The Green–Kubo comparison stops being a comfortable one-sided pass and becomes a near-equality — which is *better* physics (see §4) but is not what the chapter claims. And the para/hang contrast $0.61$ vs $0.57$ must be withdrawn: kept-segment medians are 8302 s vs 9906 s, and at the ladder's $-0.29$ per doubling that predicts $-0.053$ against the observed $-0.04$. The contrast is record length.

*Fix:* report $\gamma$ as a local slope against lag with the fBm bias control beside it, quote the value at the floor of the grid, withdraw the discipline difference, and raise the quoted floor to ≈1.70.

---

**D4. `04-global-transport.tex:461` — "the second-order variation does not see it at all."**

False as a statement about the estimator. $V_2(\Delta) = 4S(\Delta) - S(2\Delta)$ exactly, so $V_2$ is a fixed linear combination of $V_1$ at two lags and sees everything $V_1$ sees. I verified the identity on your archive: $4V_1(\Delta)-V_1(2\Delta)$ reproduces the measured $V_2$ to 0.003 in exponent (para) and 0.009 (hang), using no $V_2$ data at all. The correct statement is that the combination *annihilates the per-flight course* (which enters $S$ as $+|v|^2\Delta^2$), not that it fails to see it.

The chapter's own next sentences are correct and should carry the paragraph: the order-1 task gap grows with the ceiling ($+0.110 \to +0.155 \to +0.231$ as the fit ceiling goes 2000 → 4000 → 12 000 s) while the order-2 gap does not ($-0.103 \to -0.105 \to -0.113$). That discriminating test is empirically right.

---

**D5. `04-global-transport.tex:374`, "Orders two and three agree" paragraph — "the agreement between $\alpha_2$ and $\alpha_3$ is the statement that nothing polynomial is left for a higher difference to find."**

Circular. $15V_1(\Delta)-6V_1(2\Delta)+V_1(3\Delta)$ reproduces the measured $V_3$ to 0.012 in exponent on both archives. The agreement between orders 2 and 3 is forced by an algebraic identity between one curve and itself; it is not evidence about the trajectory. The paragraph loses its evidential content and should say what it actually is — a closure check on the implementation, like the $\alpha_1 \leftrightarrow \alpha_{\rm TA}$ paragraph.

---

**D6. `04-global-transport.tex:499-501` — "$\alpha_2=2.02$ is $2H$ with $H=1.009$, at the upper boundary of the self-similar family and marginally past it"; Table 3.3 row 3 and the bracket at l. 875.**

To first order in the curvature,
$$\alpha_2 = \alpha_1 - \frac{2^{\alpha_1}\ln 2}{4-2^{\alpha_1}}\,\frac{d\alpha_1}{d\ln\Delta},$$
and I reproduce the measured $\alpha_2$ from $\alpha_1$ and its log-derivative to 0.006 (para) and 0.017 (hang). The bracket is 3.53 where this archive sits. The measured $d\alpha_1/d\log\Delta$ is $-0.165$/decade, so the entire $+0.26$ excess of $\alpha_2$ over $\alpha_1$ *is* the amplified curvature of $V_1$. Under the chapter's own closed form $V_2=S(\Delta)(4-2^{2H})$, $2H\ge 2$ gives a negative mean square: 1.009 is not a value $H$ can take, so it cannot be an endpoint of a bracket.

The excess is also not irreducible — it tracks the declared course. $\alpha_2$ by declared type (para, 60–2000 s): out-and-return + quadrilateral 2.076, triangle 2.059, Dist 3 pts 1.953, Dist 2 pts 1.953, **free distance (Dist libre + Dist 1 pt, $n=1540$) 1.901 ± 0.007**, i.e. $H = 0.951$, below unity, self-consistent with its own $\alpha_1=1.865$, and bracketing the quantile $H=0.901$ the way Table 3.3 wants.

*Fix:* either quote the course-free row as the second-moment upper jaw ($H=0.95$), or state that the pooled 1.009 exceeds the family boundary by an amount attributable to the 56 % closed tasks and to the amplified log-derivative. Quote $d\alpha_1/d\log\Delta$ and the amplification (3.53 / 2.97) beside $\alpha_2$. Note the span across declared types is 0.175 in $\alpha_2$, larger than the $\pm 0.10$ Table 3.2 enters for the task cut, because that entry averages the two bent-but-open classes in with the free one.

*What is not wrong:* "the trajectory is rough at every lag" survives. A locally ballistic $V_1$ at this curvature would give $V_2/V_1(60\,\text{s})=0.069$; the measured ratio is 0.424 / 0.497, which needs a short-lag slope of 1.87.

---

**D7. `04-global-transport.tex:1364` — verdict, "Every moment scales with that one exponent", following $\alpha_2 = 2.02$.**

The moment scan is run on order-1 increments and returns $\nu(q) \in [0.847, 0.866]$. "That one exponent" is 0.86, i.e. $\alpha_1/2 = 0.876$, not $H=1.009$. One clause; no conclusion moves.

---

**D8. `04-global-transport.tex:1136` and constraint (v) at l. 1460-1464 — "acts more strongly on the smaller and slower discipline" / "about fourfold more strongly on the smaller, slower wing."**

Two errors compounded.

*(a) The descriptor is inverted.* The discipline carrying $+0.18$ is the hang glider, whose median speed is 15.6 m/s against 9.6 — the chapter itself writes 140 lines later that "the hang-glider median lies above the paraglider ninetieth percentile". The wing carrying the stronger effect is the **faster** one.

*(b) The quantity is not increment shape.* $1+\alpha^{\rm NG}_{\rm pooled} = \mathbb{E}_n[(1+a_f)S_f^2]/\mathbb{E}_n[S_f]^2$ exactly, and `measure_shape.py` accumulates `moment_sum` over every flight before any ratio. A matched null — every flight exactly Gaussian, at the archive's own $n_f$ and $S_f$ — returns a pooled $\alpha^{\rm NG}$ *above* the measured value at every lag in both archives:

```
lag                 60s     100s    178s    300s
para archive      +0.002  +0.036  +0.054  +0.022
para matched null +0.110  +0.127  +0.152  +0.145
hang archive      +0.148  +0.195  +0.210  +0.167
hang matched null +0.233  +0.247  +0.259  +0.269
```

At matched cadence and against a matched Gaussian null the within-flight excess is the **same curve in both disciplines** (null-corrected: para $+0.032 \to +0.155$, hang $+0.047 \to +0.166$ across 60–965 s), while the between-flight amplitude dispersion is not (0.006 vs 0.210 at 60 s). The whole of the fourfold gap is between-flight dispersion. The chapter's calibration references (single homogeneous fBm reading 0.02; Lévy walk 0.55) carry no heterogeneity and are the wrong null for a pooled statistic.

*Fix:* the sentence at l. 1150 ("its propagator is not Gaussian") survives as a statement about the **pooled** propagator, which the chapter explicitly defines as pooled — a Gaussian scale mixture genuinely has excess kurtosis. But the paragraph "The disciplines are not equally non-Gaussian" and constraint (v) must be recast: what Chapter 4 is being handed is a **between-flight variance spread**, not an increment tail, and the ratio to reproduce is $\mathrm{CV}(S_f) = 0.33$ vs $0.48$, not $+0.04$ vs $+0.18$. The Lévy exclusion is untouched.

---

**D9. `04-global-transport.tex:1171-1179` — "A sign change is what a circling wing produces … At the ensemble level the circling does not survive the average … no statistic on the unsegmented trajectory carries it."**

$C$ never changes sign, on or off the grid (minimum over the fine grid $+0.09$ at any cadence), so the literal claim stands. The inference does not, on both halves.

*(a)* The ensemble average of circling wings does not produce a sign change in the first place — radius and phase disperse across flights — so the absence of one is not evidence about circling.

*(b)* The circling **does** survive the average, as a local minimum at half a period and a local maximum at a period, in both disciplines and at every native cadence:

```
hang dt=1 s : C falls to +0.301 at 11 s, recovers to +0.426 at 21 s
hang dt=2 s : min +0.315 @12 s, max +0.451 @22 s
hang dt=5 s : min +0.366 @15 s, max +0.458 @25 s
para dt=1 s : min +0.312 @10 s, max +0.463 @19 s
para dt=3 s : min +0.377 @12 s, max +0.476 @21 s
```

Not a filter artefact: the Savitzky–Golay window is 5 samples at every retained cadence, so it spans 5, 10, 15, 25 and 50 s, and the minimum moves only 11 → 12 → 12 → 15 → 20 s across that tenfold change. It vanishes only at $dt=20$ s, where the 100 s window exceeds the circle period. `velocity_autocorrelation` already returns every integer lag; `measure_shape.py` throws them away at the `grid = np.round(lags_s / step)` line.

*Fix:* the sentence, and the first constraint handed to Chapter 4. A phase decomposition does not have to *produce* an anti-persistence that nothing else shows — the unsegmented ensemble already carries the circling, with a period of 19–22 s, and that is a number Chapter 4 can be held to. It also bears on D3: the "first decade below the grid" is not a monotone decay but a decay to $+0.30$ and a recovery to $+0.43$.

---

**D10. `04-global-transport.tex:1251-1255` — "A positive $C(\tau)$, a tail too slow to be integrable, and increments still correlated at 2000 s are the ensemble consequences of the same forward peak" and "It is also the warrant for the persistent random walk of Sec. `sec:modelling`, which needs the angle distribution as an input rather than as a check."**

I ran the model on its own declared input: signed 5 s turning angles and 5 s step lengths drawn i.i.d. from the measured empirical distributions (6.3 M angles, 1 Hz segments only), 200 records of 8600 s, through your shipped `filtered_variation` and `velocity_autocorrelation`:

```
PRW from the measured marginal : alpha_1 = 1.045, alpha_2 = 1.076, C(60 s) = 0.006
archive                        : alpha_1 = 1.75 , alpha_2 = 2.02 , C(60 s) = 0.37
```

The forward peak is a Brownian object across the entire declared window. It buys $\tau_c = -5/\ln\langle\cos\theta\rangle = 14.3$ s of memory and nothing above it. None of the three named quantities is its consequence, and a distribution that forces a model to fail is not that model's warrant.

What *does* produce them is the correlation **between** successive turning angles, which the marginal cannot see and the chapter never measures. I measured it — autocorrelation of $\cos\theta_i$ at a 5 s stride: 0.640 (5 s), 0.311 (60 s), 0.089 (200 s), and it does not reach zero, sitting at 0.025–0.030 out to 1200 s. Signed angle: 0.714 / 0.329 / 0.125 / 0.062.

*Fix:* delete the warrant sentence; state that what the data show is long-range dependence in the heading, not persistence at a single scale. Report the angle autocorrelation beside the marginal, and the simulated PRW's $\alpha_1 = 1.05$, in the same paragraph. Chapter 4's model must be generalised before it can be fitted, and which generalisation is chosen is itself the physical claim.

---

**D11. `04-global-transport.tex:1198-1202`, Eq. (green-kubo).**

Eq. (vacf) normalises $C(0)=1$ and `velocity_autocorrelation` returns `acf[:max_lag+1]/acf[0]`, so the displayed right-hand side has units of s². Restore the prefactor: $\langle|\Delta\mathbf r|^2\rangle = 2\langle|\delta\mathbf v|^2\rangle\int_0^\Delta(\Delta-\tau)C(\tau)\,d\tau$.

Second: the $C$ you define is the *fluctuation* correlation, so the integral predicts $\langle|\Delta\mathbf r - \mathbf v_d\Delta|^2\rangle$, not $V_1$. $V_1$ exceeds it by a strictly positive ballistic term of 15–32 % (para) and 6–15 % (hang) across the window, so the check at l. 1230-1236 is one-sided on that side too, in the passing direction. Measured directly on 3961 segments longer than 4000 s: plain increment exponent 1.778, course-removed 1.722 — a 0.056 difference, so nothing moves numerically, but the sentence names a statistic the equation does not predict.

Third: "the first decade of the integral lies below the grid" is filed under "Two features of the estimate push $\gamma$ up", where it does not belong — `vacf_tail_exponent` masks to `fit_range=(60,1179)` before the polyfit, so lags below 60 s cannot enter the slope. The conclusion is right but reaches it through the integral, not through $\hat\gamma$: completing $C$ below the grid at its physical ceiling gives an MSD slope of 1.513, and a Lorentzian completion pinned to $C(60)=0.37$ gives 1.577, both above the quoted 1.39.

---

**D12. `04-global-transport.tex:1241` and `propagator.py:366` — "a stride of \SI{5}{\second}".**

`angle_stride: int = 5` and `turning_angles` slices `positions[step::step]`: the stride is five **samples**, and `generate_propagator_figure.py:178` writes the integer 5 into a macro named `...AngleStrideS` typeset inside `\SI{}{\second}`. False for 38 % of hang-glider fixes.

Do **not** convert the stride to seconds. `savgol_window(5.0, dt, 3)` returns 5 samples at every retained cadence, so a five-sample stride is exactly one smoothing window at every cadence and the two successive displacement vectors share no sample — which is what the sentence exists to guarantee. A `round(5/dt)` stride would put both vectors inside one window at $dt\ge5$ s.

*Fix:* relabel. "A stride of five samples — one smoothing window, so 5 s at 1 Hz and 100 s at the coarsest cadence retained." If you instead set the stride per segment to `round(5/dt)`, `\StatKinHangAngleMedianDeg` goes 19 → 16 and `...ForwardPct` 56 → 58; paraglider values are unmoved. The discipline asymmetry stands either way: matched at 1 Hz and a true 5 s stride, 17.1° vs 11.6°.

---

**D13. Two smaller ones.**

`l. 844-846`, "Across them the estimate moves between 0.883 and 0.918. The smoothing scale therefore does not set the estimate." The rows are (cadence, component) pairs; the quoted range mixes the cadence variation the sentence is about with the east–north anisotropy. Cadence-only range within a component is 0.017 (para, both components) and 0.019/0.021 (hang), against 0.035 and 0.070 quoted. The conclusion is *strengthened*; only the clause is loose.

`l. 895-900`, "$H$ falls from 0.926 at the lower quartile and the median to 0.872". The four quantile medians are 0.939 / 0.926 / 0.876 / 0.863 (para) and 0.913 / 0.934 / 0.854 / 0.833 (hang) — so q25 and q50 do not coincide, and for hang gliders the lower quartile sits *below* the median, i.e. the four-point curve is not monotone. Quote the four medians. The fitted spread, the calibration comparison and the conclusion are unaffected. (`\StatPropCalibSpread = 0.004` is fine, and is *conservative*: rerun at the archive's per-row increment count, 640 records ≈ $3\times10^6$ increments, the median spread over six replicates is 0.0040. The 0.077/0.098 exceed all 37 calibration draws at any sample size.)

---

**Things I checked that are correct and should not be touched:** the order-1/order-2 task-gap discrimination by ceiling extension (l. 466-479); the identity-based prediction of $\alpha_2$ from $V_1$; the pooled reproduction of every headline macro; the Lévy refusal by the moment spectrum; the anisotropy; the closed/open slope separation growing 0.03 → 1.12; the flight-equal weighting of the fit (`generate_transport_figure.py:253` is exactly "the mean of the per-flight curves", and the window-weighted alternative moves $\alpha_1$ by 0.026, inside the declared 0.062 range dependence); the day-and-site bootstrap; the effective-dof floor.

---

## 2. Is the method sound?

The estimator is the right one and the discipline around it — declared window, both ends set by the system, stratifications, cluster bootstrap, effective dof, withdrawn claims — is better than most of what is published on this kind of data. Four places carry the whole argument, and three of them rest on something unstated.

**(a) The order scan is one measurement, not three.** $V_2$ and $V_3$ are exact linear combinations of $V_1$ at $\{\Delta,2\Delta\}$ and $\{\Delta,2\Delta,3\Delta\}$; I verified both to ≤0.012 in exponent. The chapter's appendix states the closed form (C3 l. 204-206) but the body treats the orders as independent readings — "the scan over orders is a measurement and not a check on one", "orders two and three agree, therefore nothing polynomial is left", "the second-order variation does not see it at all". **Unstated assumption: that the three orders carry independent information.** They do not. What the scan measures is one thing, and it should be named as such: the *curvature of $V_1$*, amplified by a factor $2^{\alpha_1}\ln2/(4-2^{\alpha_1})$ that runs 1.67 at $\alpha_1=1.5$ to 99.6 at $\alpha_1=1.99$. What the combination *does* accomplish, and this is real and worth keeping, is annihilating the per-flight course: on 400 exact-fBm paths at $H=0.85$, a per-flight course of sd 3 m/step drives $\alpha_1$ to 1.845 while $\alpha_2$ stays at 1.674, the truth.

**(b) "$\alpha_2 = 2H$" and "$\alpha_1 \ne \alpha_2$" cannot both be used.** The identification requires exact self-similarity over the window; $\alpha_1\ne\alpha_2$ *is* the statement that the process is not exactly self-similar there. The chapter hedges correctly at l. 520-523 and in the verdict, then enters 1.009 into Table 3.3 as a route to $H$ and uses it as a bracket endpoint. Pick one.

**(c) The heterogeneity argument does not cover the confound the chapter names.** `l. 697-699`: "A mixture of populations with different speeds and different courses is a mixture of trends, and a trend is what the second difference removes." True. But `l. 300` names the confound as "a superposition of ordinary processes with different **persistence times**", and a second difference annihilates a polynomial, not a mixture of stationary correlated walks. The word "superposition" appears once in the chapter and is never returned to. **Unstated assumption: that filtering disposes of the superposition.**

The superposition *is* refused, and by an order of magnitude — but elsewhere. On 3000 persistent walks with $p(\tau)\sim\tau^{-1.57}$ and lognormal per-flight speeds, the moment spectrum's linear departure is 0.0780 with $\nu$ spread 0.160 and `bilinear_fit` **declares a knee**, against the archive's 0.0109/0.0057 and 0.019/0.009; and the pooled non-Gaussian parameter swings by 1.36 across the window ($-0.245$ at 60 s to $+1.118$ at 2762 s) against the archive's arch of 0.07/0.12. Move the refusal there and say so.

*(The stratification evidence does have power, contrary to one line of attack: the random-split null falls monotonically with stratum size — 0.109 at $n=100$, 0.065 at 500, 0.026 at 3000 — and the archive's six wing classes hold $\sim2.6\times10^4$ flights each, where the floor is under 0.03 and the measured 0.06 is real. Also, per-flight median exponents are 1.68/1.72, individually anomalous, so the superposition is excluded at the level of the individual record too — worth saying.)*

**(d) The Green–Kubo comparison establishes nothing as run, and can be made to establish something.** Three problems compound: the floor is derived from a fit to a curve that is not a power law (D3); the floor is in a different frame from the statistic compared to it (D11); and the comparison is one-sided in the passing direction on *both* counts, so it cannot fail. On a persistent walk with a manifestly integrable exponential memory, the detrended $\alpha_1$ clears the floor at every correlation time with no drift at all (1.246 vs $-0.598$; 1.420 vs $+0.429$; 1.595 vs $+0.898$), so the emptiness is not about the course. What excludes an integrable memory is $\gamma<1$ directly, which is measured and one-sided in the safe direction. Attribute it there.

**(e) One thing that is load-bearing and sound.** The quantile route is genuinely independent of the moments and of the origin, and it is robust where it needs to be. Refitting on segments longer than the longest lag — so the contributing population is identical at every lag from 60 to 2000 s — leaves the spread at 0.078 / 0.100 against the published 0.077 / 0.098, third decimal. And 89.5 % / 90.6 % of kept segments already exceed 2000 s, carrying 99.3 % / 99.5 % of flown time, so the population is fixed to begin with. There is no duration–amplitude selection bias: measured directly, $d\log(\text{median}|\Delta x|_{60})/d\log(\text{duration}) = 0.025$ (para) and 0.011 (hang). That result is solid.

**(f) One thing that has no power and is presented as if it does.** The persistence-run threshold scan. A Lévy walk with a *known* power-law leg distribution, observed with 5 m of residual path wiggle, produces a $\beta$ spread of 7.89 (9.43 → 3.08 → 1.55) — larger than the archive's 2.69 and in the same direction; with no jitter the same estimator recovers the truth to 0.07. The stopping rule is first-violation with no length floor, so 92–96 % of runs are shorter than the 60 s floor the chapter imposes everywhere else, and the Hill fit rests on the top 0.13–0.31 %. The index is not even stable to the sample: a 1-in-10 subsample of the same hang flights moves the spread from 2.10 to 1.09. `l. 1051` ("has no scale of its own") and constraint (iii) must be demoted to a description of the decomposition. The moment spectrum carries the Lévy refusal on its own, by an order of magnitude.

---

## 3. The models the data kill

- **Coupled Lévy walk of index ~1.5** (the model the thesis was framed around) — $q\nu(q)$ departs from a line through the origin by 0.0109 / 0.0057 rms against 0.084 for the model on the same grid; $\alpha^{\rm NG}$ is $+0.04/+0.18$ against 0.55.
- **Uncoupled CTRW with a heavy waiting-time tail** — it is subdiffusive; the archive is superdiffusive at every order and by every route.
- **Any single-timescale persistent random walk** (run-and-tumble, OU heading, telegraph process) — the turning-angle autocorrelation falls 0.71 → 0.31 (60 s) → 0.03 (1200 s) with no knee anywhere across 5–1200 s, and $C(\tau)$ has no exponential scale. (Note: *not* killed by $\alpha_2$ — a single-$\tau$ walk at $\tau_c\approx170$–200 s matches $\alpha_2=2.0$ exactly. What it cannot match is $\alpha_3-\alpha_2 = 0.03$, its smallest gap over a $\tau_c$ scan being 0.14 and widening.)
- **The PRW of Sec. `sec:modelling` fed its own declared input** (i.i.d. angles from the measured marginal) — returns $\alpha_1 = 1.045$, $C(60\,\text{s}) = 0.006$.
- **Anything with independent increments** — $C(60\,\text{s}) = +0.37$, positive at every lag, $\alpha_1 = 1.75$.
- **Heavy-tailed increments as the source of the non-Gaussianity** — against a matched Gaussian null at the archive's own $n_f$ and $S_f$, the per-flight increment distribution is Gaussian-compatible at every lag in both archives; the pooled excess is $\mathrm{CV}^2(S_f)$.
- **Any isotropic model** — $H_{\rm east} = 0.890/0.860$ against $H_{\rm north} = 0.908/0.911$, on both components, at every cadence, in both disciplines.
- **Ballistic or locally straight motion** — at the measured curvature a locally ballistic $V_1$ gives $V_2/V_1(60\,\text{s}) = 0.069$; the measured ratio is 0.424 / 0.497.
- **Exact self-similarity over the full window** — quantile spread 0.077 / 0.098 against a matched calibration floor of 0.004, sign-consistent in all 16 archive rows where the calibration's sign is random.

---

## 4. The models that survive, ranked

### 1. Fractional (long-range-dependent) heading memory, $H \approx 0.85$–$0.90$, with a superstatistical between-flight amplitude

**Ingredients.** A heading process whose autocorrelation decays as a power law with no cutoff inside the window; a per-flight velocity scale drawn from a distribution with $\mathrm{CV}(S_f) = 0.33$ (para) / 0.48 (hang); anisotropy built in at the level of the two components; a per-flight net course superposed.

**What it predicts that was measured.** $\alpha_1 = 2H$ (1.75 → $H=0.876$); quantile $H = 0.901/0.885$; published $H\approx0.88$; a straight moment spectrum with $\nu\approx0.86$ and $\nu$ spread 0.019/0.009; $C(\tau)$ positive at every lag with $\gamma = 2-2H \approx 0.25$–$0.30$ — which, corrected for the mean-removal bias (D3), is what the local slope at the floor of the grid actually reads (0.30/0.34); a pooled $\alpha^{\rm NG}$ equal to $\mathrm{CV}^2(S_f)$ with per-flight Gaussianity, which is what the matched-null decomposition finds; and the order gap through the course term alone. Four independent channels — $\alpha_1$, the quantiles, the moment spectrum, and the de-biased $\gamma$ — now land within 0.05 of each other in $H$. That convergence is the chapter's strongest result and it does not currently claim it.

**What it does not address.** The interior maximum of $\alpha^{\rm NG}$ at 170–320 s (D2); the S-shape of $V_2$'s local slope with its interior minimum at 519–613 s (D1); the circling minimum/maximum at 11/21 s (D9); the quantile drift from bulk to flank; why $H_{\rm north} > H_{\rm east}$ in both disciplines.

**The falsifying measurement, from data already on disk.** Exact fBm at $H=0.876$, generated at the archive's own (duration, cadence) pairs and pushed through the identical per-flight-then-pool pipeline, returns $\rho(\Delta) = V_2/(2V_1)$ constant at 0.679 (exact value $2^{2H-1}-1 = 0.684$) and $\alpha_1=\alpha_2=1.75$. The archive's $\rho$ falls 0.787 → 0.474. Add the archive's per-flight speed CV and a per-flight course to the null and re-run. If the fall is not reproduced by course + amplitude dispersion alone, fBm-plus-superstatistics is dead as a complete description and the residue is the physics. This needs only `variations_*.npz` and `synthetic.fractional_brownian`.

### 2. An advected tracer in a convective boundary layer — the memory is the air's, not the pilot's

**Ingredients.** A thermal/street velocity field with its own spatial correlation, sampled by a wing that is largely carried by it; day-to-day variation in convective strength; a mean wind that breaks isotropy.

**What it predicts that was measured.** Non-integrable velocity memory with no distinguished scale. Anisotropy with a *directional* sign — $H_{\rm north} > H_{\rm east}$ in both disciplines, which a pilot-level model has no reason to produce. And, decisively, the structure of the intraclass correlation: **0.57 of the per-flight variance sits between day-and-site clusters, against 0.00 within flight and 0.29 by pilot.** That is the same quantity that D8 shows is producing the entire pooled non-Gaussianity. If flights differ from one another mostly because the *day* differs, then the "non-Gaussian propagator" is superstatistics of the air mass — which is exactly the Brownian-yet-non-Gaussian phenomenology, with the environment supplying the slowly-varying diffusivity.

**What it does not address.** The closed-course saturation (that is the scoring rule, not the air); the phase structure; the 170–320 s scale, unless that is the thermal spacing divided by ground speed — which it plausibly is (200–300 s at 9.6–15.6 m/s is 2–5 km, a reasonable thermal spacing).

**The falsifying measurement, from data already on disk.** Compute $\mathrm{CV}(S_f)$ and the pooled $\alpha^{\rm NG}$ **within** day-and-site clusters and compare to the pooled value. If conditioning on day-and-site collapses the between-flight dispersion, the non-Gaussianity is the air mass and constraint (v) becomes a constraint on the meteorology; if it does not collapse, it is the wing or the pilot and this model is dead. `variation_flights_*.parquet` plus the catalogue already carry the cluster labels.

### 3. A distribution of persistence times, within a flight

**Ingredients.** $p(\tau)$ heavy over at least 5 s to 1200 s, realised *within* each record rather than across records; a modest per-flight speed spread.

**What it predicts that was measured.** $\gamma < 1$; an angle autocorrelation with no knee anywhere on 5–1200 s (measured: 0.640 → 0.311 → 0.089 → 0.030, never zero); $\alpha_1$ between 1.5 and 2; the $\alpha_1<\alpha_2$ ordering via curvature.

**What it does not address.** Why the moment spectrum is straight. This is a sharp constraint and it is what separates this model from the one the chapter's l. 300 warns about: realised *between* flights, the same ingredients give a moment-spectrum departure of 0.078 and a declared knee, an order of magnitude off. The $\tau$-spread has to be within-flight and the speed spread has to be between-flight — an unusual and testable combination. It also does not address the 170–320 s feature or the quantile drift.

**The falsifying measurement, from data already on disk.** The distribution of per-flight $\alpha_2$ against the spread that finite-length fitting noise alone produces on a single-exponent surrogate at the archive's own flight durations. `variations_*.npz` already holds all 155 786 + 6132 per-flight curves; the null costs one call to `fractional_brownian` per flight. If the per-flight exponents are as tight as the surrogate, there is no within-flight $\tau$-distribution to speak of and this collapses into model 1.

### 4. A nested-cycle model: circling ~20 s inside a climb–glide cycle ~250 s inside a task ~1600 s

**Ingredients.** Three explicit timescales, all three now measured: the circling minimum/maximum at 11 and 21 s (D9); an interior feature in both $\alpha^{\rm NG}$ (max at 266/174 s) and $V_2$'s local slope (residual arch peaking at 315 s, interior slope minimum at 519–613 s); and the departure from the launch area at 1725/1530 s.

**What it predicts that was measured.** Everything model 1 cannot: the three interior features, each of which the chapter currently describes as absent or flat.

**What it does not address.** It is not yet a transport model — it has no mechanism and predicts no exponent. It is the description that Chapter 4's segmentation exists to turn into one.

**The falsifying measurement.** Recompute the VACF from native cadence upward per cadence class (one line in `measure_shape.py`) and the $\alpha^{\rm NG}$ and $V_2$ local slope on a balanced flight set. If the 170–320 s feature moves with the *task* stratum rather than staying put, it is the scoring rule; if it moves with wing class or discipline speed, it is the flying; if it stays put across all strata, it is the atmosphere. I have already shown the $V_2$ feature is not a coverage artefact (balanced-set swing 0.269/0.461 against all-flights 0.262/0.445).

---

## 5. What to compute next, ordered by what it settles per unit of work

**1. Plot the local slope of $V_2$ and the local $\gamma$ of $C(\tau)$ against lag, from arrays you already have.** Zero new traversal. It fixes D1 and D3, converts two false sentences into two positive measurements, and hands Chapter 4 a timescale (170–320 s) it can be held to. Add both to Figure 3.2 and Figure 3.4 as inset panels. **This is the highest-value single action in the list.**

**2. Report the non-Gaussian parameter against a matched Gaussian null** carrying the archive's own per-flight $n_f$ and $S_f$, and report the per-flight parameter beside the pooled one. `measure_shape.py` needs one extra accumulator array and no extra traversal. It fixes D8, rewrites constraint (v) into something Chapter 4 can actually test, and turns the "non-Gaussian propagator" claim from a shape statement (unsupported) into a superstatistics statement (well supported, and more interesting).

**3. Recompute the VACF from the native cadence upward, per cadence class.** `velocity_autocorrelation` already returns every integer lag; `measure_shape.py` discards them at the `grid = np.round(lags_s / step)` line. Gives the circling period, 19–22 s, and kills D9. Also gives you the first decade of the Green–Kubo integral, which you currently declare missing.

**4. Measure the turning-angle autocorrelation** $\langle\cos\theta_i\cos\theta_{i+k}\rangle$ over 5–1200 s and report it beside the marginal. This is the actual microscopic memory and the actual input Chapter 4's walker needs; the marginal alone falsifies the model it is offered as a warrant for. One pass over the fix table at 1 Hz segments.

**5. Answer your own open question at l. 729** — the range dependence of $\alpha_2$ inside the open-course population. It is a row selection on stored curves, you say so, and it has now been made: **0.150 (para) and 0.153 (hang), against 0.109 and 0.139 pooled and 0.090 and 0.134 inside the closed population.** The answer is *no*: the scoring rule is not the whole of the systematic, because the open population's exponent moves *more* with the window than the pooled one does. Report it — an honestly negative answer to a question you posed is worth more than the paragraph it replaces.

**6. Quote the free-distance row** (Dist libre + Dist 1 pt, $n=1540$): $\alpha_1 = 1.865$, $\alpha_2 = 1.901$, $H = 0.951$, order gap $+0.036$, and $+0.037$ when durations are matched to 4000–12 000 s. It is the course-free population, it is self-consistent, and it is the honest upper jaw of Table 3.3's bracket. Caveat it: the result does not replicate on hang gliders (gap $+0.070$) and the para $\alpha_2$ runs 1.990 → 1.844 across duration quintiles.

**7. Per-flight $\alpha_2$ distribution against a matched single-exponent surrogate.** Arrays stored. Settles model 3 against model 1, and moves the superposition refusal from an argument to a measurement. Correct the per-flight estimator bias with the surrogate's own bias ($-0.048$ at $H=0.876$) before comparing anything.

**8. One clause in the appendix on the effective span of each order.** Equalising the record read ($p=1$ over 60–2000 s, $p=2$ over 60–1000 s, $p=3$ over 60–667 s) moves $\alpha_2$ by $+0.043/+0.045$ and $\alpha_3$ by $+0.097/+0.140$ — every one inside the intervals you already quote. Worth a sentence, nothing more.

**Not worth doing.** Refitting the persistence-run scan at further thresholds — the statistic has no discriminating power (§2f), and the fix (a 60 s length floor, so the runs live inside your own declared window) is worth trying exactly once and abandoning if it does not stabilise. Any further breakpoint work — you are at the estimator's dof floor and the surrogate false-positive rate settles it. Any revival of first-passage times. And no further exponents: the chapter already has more fitted slopes than it has independent curves, and the marginal value of another one is negative.

**Plots to add:** the two local-slope panels (item 1); $\alpha^{\rm NG}$ with its matched null overlaid (item 2); the VACF from native cadence with the 11/21 s structure visible (item 3). **Plot to remove or demote:** Figure 3.5(e,f), the persistence-run survival curves and $\beta$ scan, which now support a description rather than a refusal.

---

## 6. The single most likely way this chapter is still wrong

**The chapter diagnoses the chord-across-a-bend error correctly for the ensemble MSD, and then commits it three more times on curves it computed itself.**

$V_2$'s local slope swings 0.26 (para) and 0.45 (hang) *inside* the fitted range, with an interior minimum at 519–613 s. $C(\tau)$'s local slope runs 0.30 → 0.84 across the fifteen lags it is fitted over. $\alpha^{\rm NG}$ rises by a factor of seven and falls back, peaking at 266 s and 174 s. Every one of the chapter's three headline scaling numbers — $\alpha_2 = 2.02$, $\gamma = 0.61$, "flat non-Gaussian parameter" — is a straight line fitted through a curve with a feature in the middle of it, and all three features sit in the same decade, roughly 150–600 s.

If that is real, the chapter's architecture is the problem rather than any one of its sentences. "One effective exponent over a declared window, with the curvature booked as range dependence" is a way of not seeing a crossover that is *inside* the window rather than outside it. The chapter has already located and named the scale above the window (departure from the launch area, 1725/1530 s) and it has denied the existence of the scale below it (the circling, 11–21 s, which is there). The scale in the middle is the climb–glide cycle, and it is the one thing Chapter 4 is built to measure. If a segmentation into climbs and glides returns a cycle time of a few hundred seconds, then $\alpha_2 = 2.02$ was never an exponent of a scale-free transport at all — it was the chord across a two-state crossover, and the correct physics is a two-scale one whose exponent is an artefact of where the two ends of the window were placed.

The test is cheap and you can run it before Chapter 4 exists: the features are already in `variations_*.npz` and `shape_*.npz`. Stratify each of the three by declared task, by wing class, and by discipline. A feature that moves with the task is the scoring rule; one that moves with the wing is the flying; one that stays put across every stratum is the atmosphere, and it is the result.