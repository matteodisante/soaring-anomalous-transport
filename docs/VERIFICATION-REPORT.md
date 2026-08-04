# Verification report

The pass specified by `PROMPT-VERIFY.md`, run after the implementation tasks of `PROMPT.md`.
Organised by that document's sections. **Confirmed** means checked here, by running
something; **suspected** means argued and not checked. The two are never mixed.

Eighteen findings. Fifteen are fixed, two are reported and not fixed, one is a limitation of
this pass rather than of the work. Three of the fixes were themselves wrong when first made
and are recorded as such in §6a.

---

## Summary of findings

| # | What | Severity | Status |
|---|------|----------|--------|
| 1 | The thesis called the process "a correlated Gaussian motion"; it is not Gaussian | claim stronger than evidence | fixed |
| 2 | The velocity autocorrelation and the exponent looked mutually contradictory and nothing addressed it | unanswered objection | fixed |
| 3 | `transport.pdf` — the figure of the chapter's central measurement — was generated and included nowhere | missing content | fixed |
| 4 | `green_kubo_msd` was dead code, and the module docstring cited it as the module's reason to exist | dead code / false claim | fixed |
| 5 | `data-on-disk.md` documented 17 columns where the file has 18, and contradicted itself | stale documentation | fixed |
| 6 | The logbook's Next-steps listed as unbuilt three observables that are built | drift | fixed |
| 7 | Sec. 3.1 catalogued nine observables; the chapter measures four, with no statement of which | implied promise | fixed |
| 8 | Two measured numbers typed by hand where a generated macro already carried them | contract breach | fixed |
| 9 | A 535-word paragraph running a page and a half; two more above 450 | density | fixed |
| 10 | `smooth_crossover` overflowed on its way to the minimum | latent | fixed |
| 11 | ~16 further archive measurements in the body are typed rather than generated | contract breach | reported |
| 12 | Three catalogued observables remain unmeasured | scope | reported |
| 13 | The abstract described the document as a plan; Chapter 3 contains measurements | understatement | fixed |
| 14 | The introduction pointed the modelling decision at the wrong chapter, and promised measurements the body does not make | wrong reference | fixed |
| 15 | The first-passage exponent, tried here as a cross-check, moves by 0.5 across the available radii | negative result | reported |
| 16 | Fig. 3.3's caption lettered four panels; the figure has six, and (c) named the wrong one | wrong caption | fixed |
| 17 | Chapter 3 never put its exponent beside the published one it cites in Chapter 4 | missing comparison | fixed |
| 18 | One narrow table column was justified where its neighbours were ragged, causing 17 of 27 underfull boxes | typesetting | fixed |

---

## 1. Verification of the numbers

### 1.1 Every quoted number traces to a generator — **confirmed**

Every `\Stat*`/`\Preproc*` macro the thesis quotes is written by a generator: 0 quoted and
never written, once the paraglider shape pass landed. Macro names are all valid control
sequences. Each quoted number was read in its sentence against what its generator computes.

### 1.2 Independent recomputation of the headline exponent — **confirmed, with a caveat that
mattered**

The paraglider $\alpha_2$ was recomputed from `fixes.parquet` by a route sharing no code with
the published one: `pyarrow` row-group reads instead of `stream_flights`, an explicit
`np.convolve` instead of `filtered_variation`, a `scipy.stats.linregress` instead of the
library fitter. On 13 k flights it returns **2.0276** against the library's **2.0276** on the
same subset and the published **2.02 ± 0.10** on the whole archive.

The two curves agreed **bitwise**, which is too well. The order-2 kernel $[1,-2,1]$ is
symmetric, so `np.convolve` performs the same three products in the same order: that step was
not independently verified by this route at all, and the agreement was an artefact of the
check rather than evidence about the code.

It was verified instead against a closed form derived by hand — for any process with
stationary increments, $V_2 = 4S(\Delta) - S(2\Delta) = S(\Delta)\,(4-2^{2H})$ — which the
implementation matches to 0.2 % at $H=0.5$ and 0.8 % at $H=0.7$. And since the archive sits at
$\alpha_2\simeq2$, i.e. $H\simeq1$, the boundary of the family, the estimator was checked
there specifically: on exact fractional Brownian motion of $H=0.99$ it returns 1.98. Both are
now tests.

*Lesson recorded because it generalises: an "independent implementation" of a symmetric
operation is often the same arithmetic. A closed form is independent; a rewrite may not be.*

### 1.3 Statistical claims — **confirmed**

- The kind of uncertainty is right and is labelled: sampling (day-and-site bootstrap) and
  systematic (range dependence) are reported separately as well as combined, and they differ
  by a factor of fifty.
- The denominator is right: the resampling unit is the day and site, chosen because the
  intraclass correlation was *measured* at four levels (0.00 flight, 0.57 day-and-site, 0.15
  day, 0.29 pilot) rather than assumed.
- The number of independent points is right: 22 lags carry 2.0 effective degrees of freedom,
  and the chapter refuses to count regimes on that budget rather than counting them anyway.
- Precision is defensible: $2.02\pm0.10$ quotes value and uncertainty to the same decimal.
  The bare $\alpha_{\mathrm{TA}}$ figures are bare on purpose, with the reason given.
- Nulls exist and are non-circular. The breakpoint surrogate's noise model is now passed in
  explicitly, and the default carries `circular: True` as a flag.

### 1.4 Reproducibility, end to end — **confirmed for the reductions, partial for the passes**

`check_reproducible.py --sample 250` per discipline: **500 flights recomputed from the raw
IGC through the current pipeline, 500 identical, 0 disagree.** `pytest`: **455 passed**, and
455 again with `-W error::RuntimeWarning` after finding 10.

Every reduction in `regenerate.sh` that can be re-run without a fresh streaming traversal was
re-run and its output compared byte for byte against the committed file: `generate_stats`,
`generate_census_stats`, `generate_pipeline_census`, `generate_dataset_stats`,
`audit_msd_report`, `generate_prelim_figure`, `generate_transport_figure` — **7 of 7
byte-identical.**

The four full traversals (MSD, audit, variations, shape) were not re-run from scratch in this
pass; each is 20–110 minutes over 1.36 × 10⁹ fixes, and the shape traversal *was* re-run,
since its paraglider half was outstanding. What is verified is that every macro descends from
a stored array by a reduction that reproduces exactly, and that the stored arrays descend from
the raw archive by a pipeline that reproduces exactly on a sample of 500.

### 1.5 The provenance of every figure — **confirmed, one finding**

Every generated figure was rendered **from the PDF**, not from a `savefig` PNG, and its
caption checked against its axes. All twelve are now included exactly once; one was not.

> **Finding 3.** `transport.pdf` was included **zero** times. The figure behind Chapter 3's
> central measurement — the filtered variation, the order scan, the closed-against-open task
> split and the fitted range — was generated by `generate_transport_figure.py`, run by
> `regenerate.sh`, and cited by the implementation appendix as `fig:transport`, which was the
> single undefined reference in the document. It is now Figure 3.2. **Fixed.**

---

## 2. Verification of the argument

### 2.1 Claim inventory — **confirmed, one finding**

> **Finding 1.** Sec. 3.5 read a straight moment spectrum as evidence for "a correlated
> Gaussian motion". One exponent for every moment is a statement about how the distribution
> *scales* and carries nothing about its *shape*. The shape was measurable from moments
> already accumulated: $\alpha_2 = \langle|\Delta\mathbf r|^4\rangle/2\langle|\Delta\mathbf
> r|^2\rangle^2 - 1$ is **+0.18** in the median over the fitted range, against **0.01** for an
> exact fractional Brownian motion and **0.56** for a Lévy walk of index 1.5 under the same
> estimator. The increments are heavier-tailed than Gaussian and far lighter than Lévy. The
> Gaussian reading is withdrawn and replaced by the measurement. **Fixed**, and the two
> calibrations are pinned by a test.
>
> Quoted over 60–2000 s rather than the whole grid: beyond it $\alpha_2$ climbs to +0.60,
> but those are the lags where the declared task governs the trajectory and where a fourth
> moment rests on fewest flights. Reading a maximum there would repeat an error this project
> has already made once.

### 2.2 The chain from raw data to conclusion — **confirmed, in two halves**

Raw → stored is `check_reproducible.py`: 500 flights from `.igc` through `run_flight`,
column by column, exact. Stored → number is §1.2 above: `fixes.parquet` to an exponent by a
second route. The composition covers the chain; it was not traced for one single named flight
end to end, and that is stated rather than implied.

### 2.3 Adversarial reading — **confirmed, one finding**

The sharpest question the document did not answer:

> *Your velocity autocorrelation is below $1/e$ by 60 s. Your exponent says the increments
> stay correlated to 2000 s. Both cannot be true.*

> **Finding 2.** They can, and the chapter never said how. What matters for Green–Kubo is not
> when $C$ becomes small but whether it becomes **integrable**. The tail was never measured.
> It is a power law of $\gamma = 0.57$ (hang gliders) over 60–1179 s — non-integrable, so it
> sustains super-diffusion however small $C$ already is. **Fixed**: the paragraph now carries
> the measurement.
>
> The comparison is **one-sided** and is reported as such. $C$ is estimated per flight with
> that flight's own mean velocity removed, which pulls every lag down by about the record-mean
> of $C$ and so steepens the tail; and the Green–Kubo integral runs from zero while $C$ is
> only estimable above the smoothing scale. Both push $\gamma$ up, so $2-\gamma$ is a **floor**
> on the displacement exponent: 1.43, against a measured $\alpha_1$ of 1.70. The check passes
> in the direction the bound allows. The one-sidedness is itself tested, on an
> Ornstein–Uhlenbeck velocity of known correlation.

Two further questions were asked and already answered by the document: whether the window
sits inside a persistence time (no — a persistent walk of correlation time 3000 s reads 3.02
under this estimator, not 2.02), and whether the exponent is a mixture artefact (no — the
strata spread it by at most 0.06 where they spread the ensemble MSD by 40–62 %).

### 2.4 Internal consistency — **confirmed**

- Numbers appearing twice: 4 generators agree on the flight counts, 2 on each exponent; 0
  divergences.
- Cross-references: 484 checked, 0 use the wrong word for the label kind. (The checker
  initially reported 29; that was a bug in the checker, which compared fixed-width prefixes so
  that `Chapter~\ref{ch:...}` could never match. Corrected before its output was believed.)
- Undefined references: 1 found (`fig:transport`, Finding 3), now 0.

---

## 3. Verification of the writing

### 3.1 Register — **confirmed**

Swept for the banned register. 18 candidate hits, all false positives on inspection: TikZ
`\draw[very thick]`, a quotation from the EN standard, and ordinary uses of "the very same".

### 3.2 Every sentence earns its place — **partial, and stated as such**

Not a complete sentence-by-sentence read of ~3 000 lines. What was done: the whole of
Chapter 3 read closely, which produced Findings 1, 2, 3 and 7; the register sweep across the
document; and the density measurement below. **This is the largest gap in this pass.**

### 3.3 Structure and page density — **confirmed, one finding**

> **Finding 9.** Paragraph lengths measured across the body. The Savitzky–Golay subsection
> ran **535 words in one paragraph** — a page and a half of undivided text covering what the
> filter is, its coefficients, its units, its boundary treatment, whether the boundary samples
> should be excluded, and what grid it sees. Two more above 450 words. Split at the idea
> boundaries: Chapter 2's longest falls to 337 words. Chapter 3 was already at a median of 93.
> **Fixed.**

### 3.4 Typesetting — **confirmed, one finding**

On a full build: **0 overfull boxes**, **0 undefined references**, no float wider than the
text block, checked on rendered pages as well as in the log.

> **Finding 18.** 27 underfull boxes, and 17 of them came from one column. The tooling table
> in the implementation appendix has three narrow `p{}` columns; the first two carried
> `\raggedright\arraybackslash` and the third did not, making it the only justified narrow
> column in the document — and 5.9 cm cannot justify prose carrying tokens like
> `SOARING_PARA_DATA_ROOT`. **Fixed**, 27 → 10: five `\hbox` in bibliography entries whose
> URLs cannot break, five `\vbox` from float placement.

### 3.4a The exponent against the literature — **confirmed, one finding**

> **Finding 17.** Chapter 4 cites Vilpellet et al. for a global $H\approx0.88$ and Chapter 3
> never set its own number beside it. It reproduces it, on the estimator that matches: the
> plain increment gives $H=0.876$ for paragliders and $0.852$ for hang gliders, the first of
> which rounds to the published figure at the precision that figure is quoted to. The
> second-order variation gives $1.009$ and $0.972$.
>
> The gap is the chapter's own measurement from the other side. The difference between the
> two orders *is* the flown course, and on this archive the course **suppresses**
> displacement rather than inflating it, since most retained flights fly a closed triangle
> that comes home — so a published exponent obtained without removing the course is expected
> to sit below one obtained with it, by about the amount seen. **Fixed**, with $H$ emitted by
> the generator rather than halved in prose: the first draft of the paragraph typed 0.875 and
> 0.850 by hand, which is exactly the breach Finding 8's new check exists to catch.

### 3.5 What belongs where — **confirmed, one finding**

> **Finding 7.** Sec. 3.1 defines nine observables; the chapter measures four. Nothing said
> which, so the list read as a promise. Table 3.1 now states the status of each. Two of the
> unmeasured ones — the return probability $P_0(t)$ and the first-passage time — would each
> give $H$ by a route independent of the second moment, and are named as such rather than
> left in a list. **Fixed** (the statement; not the measurements — see Finding 12).

---

## 4. Verification of the code

### 4.1 Correctness — **confirmed**

- Every estimator is validated against a process whose answer is known, and the generators
  are validated too — which is how the factor-two error in the fractional-Brownian generator
  was caught earlier in this project: it was invisible to every exponent test, since it scaled
  displacement without touching correlation.
- Boundary testing: 18 numerical routines driven with empty input, one sample, all-NaN, a
  single cluster and a degenerate fit. 0 raise. 13 tests added.
- Preconditions the code assumes are now documented where they were not: the mean-subtraction
  bias in `velocity_autocorrelation`, and the one-sidedness it forces downstream.

> **Finding 10.** `smooth_crossover` raised `RuntimeWarning: overflow` on the way to its
> minimum: $10^z$ overflows long before $\log_{10}(1+10^z)$ does, and the optimiser walks
> through that region routinely. The limit is now taken explicitly. **Fixed**; the suite
> passes with runtime warnings as errors.

### 4.2 Comprehensibility — **confirmed**

Module docstrings say why the module exists separately; function docstrings say what is
returned and assumed. One docstring was found stating something false — see Finding 4.

### 4.3 Structure — **confirmed, one finding**

Computation is separated from drawing. No module does three unrelated things. No script
lacks both a caller and documentation: the two that appeared orphaned
(`generate_timeline.py`, `refresh_seasons_index.py`) are run by the pre-commit hook.

> **Finding 4.** `green_kubo_msd` was neither called nor tested, and the module docstring
> named it as the reason the module exists — "computing both and checking they agree is a
> consistency test". The test was never performed, and could not be in that form. Replaced
> by `vacf_tail_exponent`, which does the comparison the data supports; the docstring now
> says why the integral form is unavailable here. **Fixed.**

### 4.4 The tests — **confirmed**

455 tests. Every failure this project has actually had is pinned by one, including the
factor-two generator error, the circular breakpoint null, the inspection bias measuring
residual life, and now the two calibrations that make $\alpha_2$ readable.

---

## 5. Verification of the documentation

**Confirmed, one finding.** All 40 `soaring.*` module paths in `docs/` resolve; all 34
scripts named exist.

> **Finding 5.** `data-on-disk.md` pastes the output of `show_dataset.py`, and the pasted
> blocks were a pipeline run behind: `fixes.parquet` shown with 17 columns against 18 on
> disk, `segments.parquet` with 12 against 13, both missing the reconstruction flags. Worst
> of it, `z_reconstructed` was described in the prose immediately beneath the dump that did
> not list it — the page contradicted itself and each half was individually plausible.
> Regenerated rather than patched. **Fixed.**

> **Finding 6.** The logbook's Next-steps listed the moment spectrum, the velocity
> autocorrelation and the inspection-bias-corrected persistence times as work to do; all
> three are built and are the chapter's second measurement. The section preamble also pointed
> at `thesis/sections/04-next-steps`, which the chapter split replaced. **Fixed.** The hook
> that watches this drift was right both times it fired.

---

## 6. Deletion

Deleted: `green_kubo_msd` (Finding 4), `make_altitude_noise_figure` (dead), five
Finder-duplicated test files that were inflating the pass count by 101.

Kept, with the reason: `PROMPT.md` and `PROMPT-VERIFY.md` are analysis plans, which the
instructions say to keep; `global_analysis_sketches/` and `revisions/` are unreproducible
working records.

---

## 6a. Questioning this pass's own corrections

Two of the fixes made here were wrong or incomplete when first made, and both were caught by
re-checking rather than by the original check.

**The paragraph splits broke a `\rev` group.** `\rev` expands to
`\ifrevmode\textcolor{revblue}{#1}\else#1\fi`, and `\textcolor` cannot take an argument
containing `\par`. Splitting a long block *inside* one left an unbalanced argument and the
error *Paragraph ended before \@textcolor was complete*. `pdflatex -interaction=nonstopmode`
still wrote a 114-page PDF, and the checks that had been run on it — overfull boxes,
undefined references, page count — all reported clean. Only counting `^!` in the log found
it. The repository's own build path (`build_docs.sh`, `latexmk -halt-on-error`) would have
caught it; the ad-hoc probe used to check typography while the thesis could not build did
not. Fixed, and every other split in this pass was then checked by balancing `\rev` within
each paragraph: none other was affected.

**The independent recomputation was less independent than it looked.** See §1.2: bitwise
agreement between two "different" implementations was a property of a symmetric kernel, not
evidence about the code. Re-verified against a hand-derived closed form.

**And one finding was a bug in the checker, not in the thesis.** The cross-reference check
first reported 29 references using the wrong word for their label kind; every one was
`Chapter~\ref{ch:...}`, correct, and the checker was comparing fixed-width prefixes so that
`"cha"` could never equal `"ch"`. Fixed before the output was believed. The corrected check
reports 0 of 484.

---

## 7. What was not verified, and why

- **A complete sentence-by-sentence read of the body.** Chapter 3 was read closely; Chapters
  1, 2 and 4 were swept for register and measured for density, not read sentence by sentence.
- **A single named flight traced end to end by hand.** Covered in two halves instead (§2.2).
- **The remaining typed archive numbers.** Finding 11: about sixteen measurements in the body
  are typed rather than generated — the cadence alternation percentages, the effect of
  excluding edge samples, the mean-against-median ratios and the flight counts at the longest
  lags, the closed-against-open separation at 60 s and 12 000 s. Each would need a generator
  to emit it and its pass re-run. A new check reports this class by value from now on
  (`check_generated_macros.py`), which is how the two that *were* fixable were found.
- **Three catalogued observables.** Finding 12: $P_0(t)$, the turning-angle distribution
  and the speed distributions are defined and not measured. (First-passage times were tried
  here and do not serve — §7a. The propagator's scaling collapse is answered through its
  moments.) `PROMPT-VERIFY` says an unbuilt thing is a finding and not a
  task to absorb, so they are reported. Two of them would give $H$ independently of the
  second moment and are the strongest available next check on the headline number.

---

## 7a. One check attempted here, and what it returned — **confirmed negative**

The audit arrays keep every flight's position at all 80 lags, so the **first-passage time**
$T(L)$ — the first time the flight is $L$ from take-off — needed no new traversal. It gives
$H$ in the *space* domain, $\langle T(L)\rangle\sim L^{1/H}$, which is independent of any
moment fitted over lags. It looked like the strongest available cross-check on
$\alpha_2$, so it was run.

Naively it returns $\alpha = 2.46$, which is impossible: no process with stationary
increments exceeds 2. The cause is right-censoring — at $L=34\;\mathrm{km}$ only 24 % of
paraglider flights arrive, and the missing three-quarters are the slow ones, so the mean of
the arrivals is biased down and the slope is too shallow. Treating non-arrival as censored
and taking a Kaplan–Meier median instead gives $\alpha = 1.95$ for paragliders and $2.03$
for hang gliders, both inside $2.02\pm0.10$.

**That agreement does not survive its own range check and is therefore not reported as a
confirmation.** Refitting over sub-ranges of radius moves it:

| radii | paragliders | hang gliders |
|---|---|---|
| 0.5–45 km | 1.95 | 2.03 |
| 0.5–8.4 km | 2.03 | 1.86 |
| 6.3–26 km | 1.73 | 2.11 |
| 11–45 km | 1.51 | 1.74 |

A spread of 0.5, five times the uncertainty on the number it was meant to check. Quoting the
full-range value as agreement would be a straight line through a bend — the very error the
chapter identifies in the ensemble MSD and retires that estimator for.

The reason is the same reason. $T(L)$ is measured from take-off, so it shares the ensemble
MSD's origin and inherits its pathology in the space domain: at small $L$ the wing is still
climbing out inside its launch area, and at large $L$ the Kaplan–Meier median extrapolates
past the duration of most flights. The observable is not defective; it is the wrong frame for
this archive, and for exactly the reason Chapter 3 already gives. This is recorded in the
implementation appendix so it is not attempted again from scratch.

---

## 8. The most likely remaining way the thesis is wrong

**The exponent is right about the estimator and wrong about the motion, because the window is
too narrow to distinguish a scaling law from a crossover.**

The measurement lives in 1.5 decades, 60–2000 s. Below it the pipeline has smoothed the
trajectory; above it the declared task takes over, and the closed-against-open separation in
the local slope grows from 0.03 to 1.13 across that boundary. Within the window the local
slope of $V_2$ is not flat: it runs 2.2 → 1.9 → 2.0. The chapter is careful about this — it
calls $\alpha_2$ effective, quotes the range, reports the range dependence as fifty times the
sampling error, and refuses to count regimes on 2.0 effective degrees of freedom. But
"effective exponent over 1.5 decades" and "the transport is characterised by $\alpha=2.02$"
are different statements, and a reader will take the second.

What would rule it out: an independent estimate of $H$ that does not come from a second
moment fitted over lags. **The obvious candidate has now been tried and does not serve.**
The first-passage time is measured in the space domain, but from take-off, so it carries the
launch geometry into the space domain with it and its exponent moves by 0.5 across the
available radii (§7a). It cannot arbitrate a difference of 0.1.

What is left is the observable that avoids both the moment and the origin: the propagator of
the **increments**, $P(\Delta\mathbf r,\Delta)$, and its collapse $t^{H}P \to F(x/t^H)$ read
off histograms rather than moments. The moment spectrum already says all moments scale with
one exponent, which is the collapse in moment form; what a histogram would add is the
low-order and negative-order behaviour, where the bulk of the distribution lives and where a
crossover in shape shows before it shows in the variance. The peak height
$P_0(\Delta)\sim\Delta^{-dH}$ falls straight out of the same histograms. It is one streaming
pass over data already on disk, and it is the measurement this thesis most needs next.
