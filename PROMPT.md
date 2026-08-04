# Prompt — repo cleanup, code reorganisation, and Chapter 3: the un-segmented analysis

Paste everything below the line as a single prompt. Delete this file when the work is done.

---

## 0. What this is

Six pieces of work, in one pass, on a repository whose pre-processing pipeline and first
transport measurement are finished and committed.

1. Delete what the repo no longer needs.
2. Reorganise the analysis code for the twenty observables about to land in it.
3. Build the dataset statistics properly: what was discarded and why, and what survived,
   per year and per stratum.
4. Split the planning chapter: Chapter 3 becomes **the analysis that needs no
   segmentation**, Chapter 4 becomes segmentation and everything downstream, deferred.
5. Implement **every observable that can be measured on the un-segmented dataset**,
   following `global_analysis_sketches/`.
6. Write Chapter 3 against what those measurements return.

Task 5 is the bulk. Tasks 1–3 are the ground it stands on and are cheap. Do not start 5
before 3 is done: several of its observables are statements about a stratum, and a stratum
is not defined until the survivor statistics are.

## 1. Standing rules

**Numbers.** No number is ever hard-coded in the thesis. Every quantity reaches the text
through a generated macro emitted by a script under `scripts/reporting/`, and
`scripts/reporting/check_generated_macros.py` must pass. The repo already implements
exactly what `03_diagnostica.md` §3.7.2 asks for — **use the existing `\Stat*` contract, do
not invent a parallel `values.tex`.**

**The three-place contract.** Anything about the pipeline stays aligned across
`thesis/sections/03-dataset.tex`, `thesis/appendices/impl/C2-dataset.tex` and
`docs/guide/preprocessing-pipeline.md`. The analysis-side equivalent is
`thesis/sections/04-next-steps.tex` ↔ `thesis/appendices/impl/C3-next-steps.tex` ↔
`docs/reference.md`.

**Review markup.** New text uses `\rev{...}` (blue) and `\flow{...}` (orange);
`revblock`/`flowblock` for anything spanning a paragraph — `\textcolor` is not `\long`, so
a bare `\rev{}` across a blank line is a build error. Floats do not inherit the block
colour. `\path{}` breaks inside `\caption`; use `\texttt{}` or `\protect\path{}`.

**Voice.** MSc Physics-of-Complex-Systems register, quantitative, not AI-flavoured. Banned:
narrativized or question headings, aphorism set-ups, meta-commentary, sustained metaphors,
antithesis density, em-dash chains. Nominal headings, plain connectives, assert and move
on. Captions 90–130 words. Rationale belongs in Appendix C, numbers in the body.

**Figures are read from the PDF.** Check every new figure by rendering the PDF
(`pdftoppm -png -r 110 -singlefile f.pdf out`), never a `savefig` PNG. `hexbin` renders
clipped in the PDF backend on Matplotlib 3.11 — use `pcolormesh`.

**Running things.** Env vars are not set in the shell; pass them inline.
`scripts/regenerate.sh` runs the nine-step chain in the only correct order and refuses to
start while `preprocess.py` is alive. `ModuleNotFoundError: soaring` → `chflags -R nohidden
.venv`. `timeout` does not exist on this machine; use `curl --max-time`.

**Tests.** `pytest` must pass. New observables need the synthetic tests of §3.7.3 below.
Do not commit unless asked; this repo never uses a `Co-Authored-By` trailer.

## 2. Where things stand

- The pipeline is built, run and committed: **155 788** paraglider and **6 132** hang-glider
  flights retained, in `fixes`/`segments`/`flights_meta` on the SSD. `verify_dataset.py`
  passes and `check_reproducible.py` reproduces 500/500 sampled flights.
- Both MSD estimators exist in `src/soaring/analysis/transport.py`, with an audit
  (`scripts/reporting/audit_msd*.py`, `\StatAudit*`).
- **The audit's verdict, which the sketches independently predict.** The ensemble MSD about
  take-off is not a power law: residual 15.2 % / 31.2 % rms against 3.8 % / 3.6 % for the
  time average, local slope running 1.31→2.21 and going super-ballistic where the
  population leaves its launch area (median departure 1911 s). `01_fondamenta.md` §1.4 says
  why in advance: *"una deriva residua aggiunge |v_d|²Δ² al MSD, rende tutto balistico a lag
  lunghi, gonfia ν, e trasla la PDF invece di riscalarla"*. The disease is diagnosed; §1.4.4
  prescribes the cure and Task E must apply it.
- Section 2.8 exists (`sec:prelim`) with three figures and `\StatPrelim*`. It reports two
  results that constrain everything below: the ensemble is anisotropic, and the strata
  differ by wing class (40 % typical) and orographic group (62 %) but not by season (12 %).

**Two things already in the thesis that the sketches contradict. Resolve both explicitly.**

1. **Isotropy.** Sec. 2.8 measures `⟨E²⟩/⟨N²⟩`. `01_fondamenta.md` §1.5.1 argues that ratio
   is the wrong test under heavy tails — dominated by a few outliers, "non misura nulla di
   stabile" — and prescribes the **angular distribution of centred increments** with
   circular order parameters `a_n` against a Rayleigh threshold built on `N_eff`, not `N`.
   Implement §1.5 properly, keep the variance ratio only if it still says something, and
   rewrite Sec. 2.8's isotropy paragraph around whichever survives.
2. **Heterogeneity.** `03_diagnostica.md` §3.1 calls it *"il modo più probabile in cui il
   risultato può essere sbagliato"* — a superposition of ordinary diffusions with different
   persistence times imitates a power law exactly. Sec. 2.8 already shows the strata differ.
   The per-flight-versus-ensemble test of §3.1.2 is therefore not optional.

## 3. `global_analysis_sketches/` — the specification for Task E

Three documents, ~1340 lines, in Italian. Treat them as the specification and this prompt
as the ordering. Read all three before writing code.

- `01_fondamenta.md` — data schema, `dt` and filtering, lag grid and `N_eff`, wind from
  the sliding-window hodograph, the three drifts, **centred increments**, isotropy.
- `02_trasporto.md` — MSD by FFT; **the moment spectrum, which it calls the main test**;
  PDF scaling and collapse; VACF, velocity PSD, heading correlation; geometric persistence
  times and the **inspection bias**; block and shuffle tests.
- `03_diagnostica.md` — the heterogeneity confound; the vertical channel as a
  segmentability diagnostic; bootstrap over flights; the **15-row consistency table**; what
  remains precluded; output schema and the global execution order with four blocking gates.

**Where the sketches and the repo disagree, the repo wins on facts and the sketches win on
method.** Their data schema (`tracks.parquet`, `flights.parquet`) predates the pipeline —
the real schema is `fixes`/`segments`/`flights_meta`, documented in
`docs/guide/data-on-disk.md`. Their proposed `src/io/`, `src/observables/`… layout is a
suggestion; adopt its *separation of concerns* inside `src/soaring/` (Task B) rather than
its literal paths, and do not disturb `acquisition/`.

**ERA5 (§1.4.2) is a cross-check against reanalysis data this repo does not have.** Do not
add a network dependency for it. Implement the hodograph wind, state that the ERA5 gate
(GATE B) is unmet and why, and treat it as future work.

---

## Task A — delete what the repo no longer needs

Survey everything and remove what has no reader. Candidates, each to be confirmed rather
than assumed:

- `docs/IMPLEMENTATION-BRIEF.md` — a handoff for work now finished; it says itself it is
  disposable.
- `docs/PROMPT-msd-audit.md` and this file — prompts, executed.
- `global_analysis_sketches/*.pdf` — 18 MB of renderings of the 60 KB Markdown beside them.
  Keep the `.md`, drop the PDFs, and say in `docs/` where the sketches came from.
- `revisions/` — 4.4 MB of July review-pass material. **Check `thesis/REVISION-TODO.md`
  first**: if it still has open items pointing into that directory, keep what they need and
  drop the rest. Never touch `main_revision.pdf`.
- Anything in `docs/guide/` superseded by `data-on-disk.md` or the pipeline guide — check
  `igc-to-flight.md` in particular for overlap.
- Stale scripts under `scripts/reporting/` with no caller in `regenerate.sh`, the docs or
  the thesis.

Report what you delete and why, in one list. If something is ambiguous, leave it and say
so rather than deleting it.

## Task B — reorganise the analysis code

`src/soaring/analysis/` is flat and mixes concerns, and roughly twenty observables are
about to be added to it. Two problems to fix, and a third to judge:

1. **Computation and drawing are in the same modules.** `transport.py` (809 lines) holds
   both estimators, the fit, the bootstrap, the local slope *and* `make_msd_figure`;
   `altitude_noise.py` (613) mixes the Welch machinery with its figure. Separate them.
2. **`preprocessing.py` is 1026 lines of three unrelated things** — config loading, the
   census scan and its cache, and the retention diagnostics. Split it.
3. Judge whether the growing observable set wants its own subpackage. The sketches suggest
   `observables/`, `diagnostics/`, `stats/`, `report/`; `preproc/` already sets the
   precedent that a stage-per-module subpackage works here.

Constraints: every public name that the scripts, the tests or the docs reference keeps
working or is updated at every call site in the same pass; `docs/reference.md` mirrors the
new layout; `pytest` passes unchanged in count; no behaviour changes in this task — a
reorganisation that also fixes a bug hides the bug.

## Task C — the dataset statistics, done properly

The user's request, in full: tables that make clear **which flights were discarded and
why**, and **statistics of the surviving dataset, per year and otherwise**.

`tab:pipecensus` already gives the discard cascade, but it gives only the counts, so the
*impact* of each criterion is left for the reader to compute. Fix that first:

0. **Make the cascade legible as a cascade.** One row per criterion, in the order the
   pipeline applies them, with four columns: how many flights were **still standing** when
   that criterion ran, how many it **removed**, that removal as a **percentage of those
   still standing** (not of the archive), and how many **remain** after it. The reader
   should see at a glance which cut does the work — at present it is buried, and the
   answer is not the obvious one: the resampling sparsity rule removes 21 089 paraglider
   flights, an order of magnitude more than any threshold argued for in the text.

   Put it in `tab:pipecensus`, which is the census table and already reads in pipeline
   order, not in `tab:workingparams`. Those two answer different questions — one is a
   parameter reference, the other is what the parameters cost — and `tab:workingparams` is
   already a multi-page longtable. Cross-reference them instead of merging them.

Then build:

1. **The discard table, per year.** The existing census is archive-wide; the same cascade
   resolved by season answers a question it cannot — whether the pipeline discards
   uniformly over two decades or eats a particular era. Logger technology changed over that
   span, so this is a real risk and not a formality.
2. **Survivor statistics per year**: retained flights, retention rate, median duration,
   median path, median `Δt`, the share at 1 Hz, and the share of flights split into
   segments. One row per season, as a table and as a figure.
3. **Survivor statistics per stratum**: by discipline, by wing class, by orographic group.
   The strata of Sec. 2.8 need their sizes and their basic statistics in one place, because
   every stratified observable in Task E will refer to them.
4. **The cross-tabulation that matters**: discard reason × year, and discard reason ×
   cadence. Sec. 2.8 already reports that the sparsity rule falls unevenly on 2 s and 3 s
   loggers; make that a table rather than a sentence.
5. **A single "what the dataset is" table** for the body: attempted, retained, retained
   fraction, fixes, segments, span in years, per discipline.

All of it through `\Stat*` macros from a script wired into `regenerate.sh`. Where a number
already exists in `\StatPipe*` or `\StatPrelim*`, reuse it instead of recomputing it
differently — two generators disagreeing about the same quantity is the failure the macro
contract exists to prevent.

## Task D — split the planning chapter

Chapter 3 (`thesis/sections/04-next-steps.tex`) currently holds six sections: observables
on the whole trajectory, segmentation, phase-resolved observables, reproducing the
reference results, modelling, tooling.

Restructure:

- **Chapter 3 — the un-segmented analysis.** Everything measurable without phases. This is
  where Task E lands and Task F writes. It stops being a plan and becomes results.
- **Chapter 4 — segmentation and what it enables.** Segmentation, phase-resolved
  observables, reproducing Vilpellet et al., modelling and simulation. Still a plan, and
  explicitly labelled as one; it is implemented later.

Keep `sec:tooling` wherever it reads better — probably Chapter 4 or the implementation
appendix. Mirror the split in `thesis/appendices/impl/C3-next-steps.tex` (a new C4 file,
`impl:analysis` renumbered), in `docs/`, and in the logbook's Next-steps section, which a
pre-commit hook checks against the thesis. Fix every cross-reference; the build must have
no undefined references.

Chapter 4's opening should state the relation the sketches state at §3.6: *pre-segmentation
determines which class of transport you have; segmentation explains which flight mechanism
generates it. Segmentation explains an exponent, it does not measure one.* That framing is
what makes the split a thesis argument rather than a filing decision.

## Task E — implement every un-segmented observable

### The objective, which sets the scope of E and F

Chapter 3 must give a **complete characterisation of global transport** on the cleaned but
unsegmented dataset, and extract the maximum information the data can support about the
transport behind the phenomenon. Every method that adds a genuinely distinct viewpoint is
in scope; a longer list of the same viewpoint is not.

The headline question, which the sketches do not address and which the August audit already
shows is live, is **how many dynamical regimes there are and where they change.** The local
slope of the ensemble MSD runs from 1.31 to 2.21 and back, so the answer is already known to
be "more than one". That means:

- the local slope, with its uncertainty, is a primary object and not a diagnostic panel;
- fitting a single exponent to any curve is a hypothesis to be tested, not a default;
- **the number of regimes is itself a fitted quantity**, by segmented regression with model
  selection over the number of breakpoints, and each crossover time is quoted with a
  confidence interval;
- a smooth curve with no regimes is a possible and reportable answer, and the analysis must
  be able to return it rather than manufacture knees.

Several viewpoints are wanted precisely because each is blind in a different place: the MSD
sees the second moment only, the moment spectrum sees the whole spectrum of moments, the
PDF collapse sees the shape, the correlations see the memory, the persistence times see the
geometry, and the surrogates see which of those is load-bearing. Where two methods disagree
about the same exponent, that disagreement is a result and goes in the chapter.

Follow `global_analysis_sketches/` §1–§3, in its own execution order (§3.7.4), respecting
its four gates. The order below is that order; do not reorder it, because each stage's
validity depends on the one above.

### E1 — foundations (`01_fondamenta.md`)

- The validity mask, the sampling step and the two Savitzky–Golay series (§1.1–1.2). Much
  of this already exists in `preproc/`; reuse it, do not reimplement, and reconcile any
  disagreement with `sec:preproc` explicitly.
- **The lag grid and `N_eff`** (§1.3). `N_eff` must be reported with every quantity that
  has an error bar — the sketch is emphatic that using the raw sample count declares
  everything significant. The repo's existing grid is in `transport.log_lag_grid`.
- **Wind from the sliding-window hodograph** (§1.4.1): 60 s windows, 10 s stride, circle
  fit, keep the windows where the fit is good. Non-circular windows fail the criteria and
  drop out by themselves, so no segmentation is needed to find the climbs.
- **The three drifts kept distinct** (§1.4.3) and **centred increments** (§1.4.4) as the
  operative definition every observable in E2 consumes. Centre **per flight**, not by an
  ensemble mean.

#### E1a — the three frames, and whether removing the wind is legitimate at all

This is the question the whole chapter turns on, and it must be answered in the thesis
rather than assumed. Three frames are physically distinct and must never be conflated:

| Frame | Operation | What it measures |
|---|---|---|
| **ground, raw** | none | where the wing actually went. Transport proper. |
| **ground, drift-centred** | subtract `v_d^net · Δ` per flight | the fluctuation about each flight's own mean velocity |
| **air** | subtract `∫w dt`, the hodograph wind | the trajectory relative to the air mass |

**Report the MSD, and every exponent, in the raw and drift-centred frames both.** The
difference is a measurement, not a choice between two candidates for the same number.

The reasoning, which belongs in the body:

*Why centring is necessary.* A population of flights each moving with its own mean velocity
`v_i` contributes `⟨v²⟩Δ²` to the mean square displacement whatever the underlying
stochastic process. The August audit measured that term dominating the ensemble estimator.
Worse, for the PDF work of §2.3 a drift **translates** the distribution instead of rescaling
it, so a collapse test on uncentred data is not merely noisy, it is meaningless.

*Why centring is not free, and this is not in the sketches.* `v_d^net = [r(T) − r(0)]/T`
uses the endpoint, so centring is an **in-sample, acausal detrending**. It forces the mean
centred increment to vanish over the whole flight by construction, which suppresses exactly
the long-lag correlation the analysis is testing for, and biases the centred MSD downward at
lags approaching `T`. **Quantify that bias on synthetic data** — take fractional Brownian
motion with a known exponent, centre it the same way, and measure how the recovered exponent
moves as a function of `Δ/T`. Report the lag range over which centring is safe, and read the
centred curve only there.

*Why the air frame is not the primary frame.* Subtracting the wind gives the trajectory
relative to the air mass, which is the right object for interpreting the pilot's decisions
and the wrong one for transport — transport is physical displacement in space, and a wing
carried fifty kilometres downwind has been transported fifty kilometres. So the air frame
enters as a **diagnostic and a stratification**, never as the frame the exponent is quoted
in. Compute it anyway, because the comparison is informative either way: if the anomaly
survives in the air frame it belongs to the pilot's search strategy, and if it disappears it
was the air carrying the wing. Both outcomes are a result worth a figure.

*How the wind is estimated, stated explicitly in the thesis.* The sliding-window hodograph
of §1.4.1, with its window, stride and acceptance criteria, and with the fraction of the
archive for which a wind estimate is available at all. A wind that is only recoverable
where the wing circles is a wind known on a biased subset of the flight, and that has to be
said.

- **Every exponent computed twice, centred and raw** (§1.4.4). The difference `ν_raw − ν_c`
  is the direct measurement of how much of the apparent anomaly was drift, and it is a
  number that goes in the thesis. Given the audit's finding, expect it to be large.
- **Isotropy per §1.5**, replacing the variance ratio: angular distribution of centred
  increments, circular moments `a_1, a_2, a_4`, Rayleigh threshold on `N_eff`, scale
  dependence, principal axes when `|a_2|` clears the threshold. Record the operative
  decision (`isotropic`) that gates whether E2 uses marginals.

### E2 — transport observables (`02_trasporto.md`)

- **MSD by FFT** (§2.1), aggregation across flights made an explicit choice rather than a
  default (§2.1.4), and the amplitude test as a constraint rather than a fit (§2.1.6).
- **The moment spectrum** (§2.2) — the sketch's main test, and the one figure that
  discriminates a Lévy walk from a correlated Gaussian process visually. Note the stride:
  overlapping windows are acceptable at `q = 2` and **wrong** above it, because one extreme
  event is counted `m` times. Report the tail fraction beside every moment; a `q = 4`
  moment that is 80 % one flight is not a moment.
- **PDF scaling** (§2.3): radial survival function as the primary representation, the
  quantile scaling test, the two collapse figures, the tail exponent by the CSN procedure.
  Marginals only after the isotropy gate.
- **Correlations** (§2.4): VACF with the Green–Kubo cross-check, velocity PSD, multi-scale
  heading correlation.
- **Persistence times** (§2.5) with the **inspection-bias fix**: non-overlapping greedy runs,
  not per-instant sampling, which returns `β − 1` and would be wrong by a whole unit. Scan
  `s_max ∈ {1.05, 1.15, 1.30}` and report whether `β` is stable across it — instability is
  itself an important negative result, because it predicts a threshold-dependent
  segmentation later.
- **Block and shuffle tests** (§2.6), `both` first as GATE D.

### E3 — diagnostics (`03_diagnostica.md`)

- **The heterogeneity protocol** (§3.1.2): `ν` per single flight for flights over three
  hours, `ν` per homogeneous subset, both against the pooled ensemble. A systematically
  lower per-flight `ν` means the anomaly is heterogeneity. Stratify by the variables of
  §3.1.3 — and note that `is_competition` is called the most important of them, since a
  race imposes a route and the long-range directional correlation then reflects the task
  and not the transport. Check what the catalogue actually offers for it.
- **The vertical channel** (§3.2): `v_z` bimodality as the segmentability diagnostic, cycle
  period without segmenting, energy height, the `|v|`-versus-`v_z` scatter. This is what
  tells Chapter 4 whether its segmentation is well posed.
- **Bootstrap over flights** (§3.4.1) and the per-exponent checklist (§3.4.2).
- **The 15-row consistency table** (§3.5) as a generated table in the thesis. Its
  violations are the most informative output of the whole analysis, so report it whole and
  do not quietly drop the rows that fail.
- **What remains precluded** (§3.6), stated explicitly so the conclusions are not
  overclaimed.

### E4 — outputs

Per §3.7.1, one tidy table per observable, keyed by `(stratum, lag, …)`, with
`exponents.parquet` as the master: **every number that reaches the thesis has a row there,
with its fit window and its confidence interval.** Then the `\Stat*` macros are emitted
from that table, so the existing contract and the sketch's §3.7.2 become the same mechanism.

### E5 — the tests that validate the chain

Write these **before** the observables, per §3.7.3:

1. `msd_fft(r)[0] == 0` to machine precision.
2. Synthetic Brownian motion → `ν = 1.00 ± 0.03`, `K(Δ) → 2` (2, not 3 — that is the 1-D
   value), `δ(p)` constant.
3. Synthetic Lévy walk with known `α` → recovered within 0.1 by both §2.2 and §2.3.
4. A trajectory with imposed drift → `a1_abs` above threshold, and below it after centring.
5. Synthetic runs with a known Pareto `P(L)` → `persistence_runs` recovers `β`, and
   per-instant sampling recovers `β − 1`, verifying the inspection bias explicitly.

Tests 3 and 5 are the ones that validate the whole chain on a case where the answer is
known. Treat a failure in either as blocking.

## Task F — write Chapter 3

**Free rein on the structure.** The existing chapter is a list of intended observables
inherited from the planning document, and nothing about its order is load-bearing. Design
the chapter around the argument the measurements actually make, not around the sketches'
section numbering or the old plan's. Discard the current organisation entirely if a better
one exists — it almost certainly does, since a results chapter and a plan chapter have
different shapes.

The shape to aim for is a single line of reasoning with the diagnostics attached where they
bear, rather than a catalogue: establish what has to hold before anything can be measured
(frames, gates, `N_eff`), measure, then spend the rest of the chapter trying to break the
result — heterogeneity, shuffles, strata, the consistency table — and report what survives.
A catalogue of twenty observables in the order they were computed is the failure mode.

Full prose, in the thesis voice, quantitative, every number through a macro. The chapter has
to answer one question — **which class of transport is this** — and be honest about the
answer, including if it is "heterogeneity, not anomaly" (row 13) or "correlated Gaussian,
not Lévy" (the BIC test of §2.2.4).

Two things the sketches ask for explicitly and that belong in the text:

- **The honesty note** (§3.4.3): with flights of a few hours the super-diffusive regime is
  almost certainly pre-asymptotic, bounded by the diurnal convective cycle. That is a
  property of the system rather than a defect. State it, and show the exponent is stable
  *inside* the physically accessible range.
- **The centred-versus-raw pair** for every exponent, as the measurement of how much of the
  apparent anomaly was drift.

Then update Sec. 2.8 for whatever E1 changes about isotropy, and the implementation
appendix throughout.

## Task G — documentation

`docs/guide/` gains a page for the un-segmented analysis: the observables, the gates, the
output tables, and how to reproduce a number from `exponents.parquet`. `docs/reference.md`
follows the Task B layout. The regeneration chain in the pipeline guide grows the new
steps. The logbook gets a dated note and its Next-steps section realigned to the new
chapter split.

## Task H — the thesis as a document

The standard is a doctoral thesis done properly. Content that is right but laid out badly
still reads badly, and a body that explains everything in place stops being readable at
all. Three passes over the whole document, after the content of D and F is settled.

### H1 — typesetting, and one known defect

**Table 2.5 (`tab:workingparams`) runs off the bottom of its page and overprints the folio.**
It is a plain `tabular` inside a `table` float, taller than the text block, so it overflows
instead of breaking. Convert it to a `longtable` with a repeated header, or split it into
one table per pipeline stage — whichever reads better. Note that `pdflatex` reports no
overfull box for this, so the log is not a sufficient check.

Then sweep the whole document for the same class of problem, by **looking at rendered
pages** and not only at the log:

- every float that exceeds the text block, and every float stranded far from its reference;
- pages left half empty by float placement (page 8 of the current build is one);
- overfull and underfull boxes, orphans and widows, bad hyphenation, tables wider than the
  text block;
- long verbatim or `\path{}` runs breaking the margin;
- consistent float placement policy rather than `[htbp]` everywhere out of habit.

### H2 — page density and the shape of the argument

Immense undivided blocks of text do not help the reader, and this document has them. The
remedy is structural, not cosmetic: more paragraphs with one idea each, headings where the
argument turns, a table or a short list where a sentence is enumerating, and white space
that corresponds to a break in the reasoning rather than to a float landing.

Judge every page on how it reads, not on whether it compiles. A reader should be able to
see the structure of an argument before reading it.

### H3 — voice

Sweep for AI-flavoured register and remove it. The target is scientific prose: clean,
minimal, effective, clear, rigorous, and pleasant to read. Banned, as before and now across
the whole document rather than in the sections recently touched: narrativized or question
headings, aphorism set-ups, meta-commentary about what the text is doing, sustained
metaphors, antithesis density (`X, not Y` in every paragraph), triads, em-dash chains,
throat-clearing openings, and sentences whose work is rhetorical rather than informational.

**Clarity is not what gets cut.** Compactness comes from moving material, not from
compressing explanations. A concept that needs three paragraphs to be understood gets
three paragraphs; a concept that needed three because it was written loosely gets one.

### H4 — what belongs where

The body must be compact and must still contain everything a reader needs to follow the
argument. Everything else moves:

- **implementation detail** — module names, parameter derivations, numerical procedures,
  failure modes, reproduction commands — to Appendix C, which already mirrors the body
  chapter by chapter;
- **self-contained derivations** to their own appendix, following the precedent of the CTRW,
  PSD and geodesy appendices. Create new appendices where a derivation is long enough to
  interrupt the body but is needed for completeness — the moment-spectrum scaling forms and
  the inspection-bias correction are candidates;
- **audit trails and negative results** stay, but as compact statements with their numbers,
  not as narratives of how they were found.

Decide each case by asking what a reader following the argument needs *at that point*. If
the answer is "a pointer", it is a pointer.

### H5 — verification

The document builds with no errors, no undefined references, and no overfull boxes. Every
chapter has been read as rendered pages. Report what you changed and, for the voice pass,
roughly how much text moved out of the body and where it went.

---

## Order

A → B → C → D → E1 → E5 → E2 → E3 → E4 → F → G → H. E5 sits early on purpose: the synthetic
tests are what make E2's numbers believable, and writing them afterwards means trusting a
chain nobody validated. H comes last because it is a pass over finished content — except
the Table 2.5 defect of H1, which is a visible fault and can be fixed as soon as it is
convenient.

Commit as you go, one commit per task or per coherent piece of a task, and push at the end.

The four gates of §3.7.4 are blocking. A failed gate means the problem is upstream and no
downstream observable is interpretable until it is fixed — say so and stop rather than
reporting a number the gate has already invalidated.

## How to report

Per task: what was done, the numbers, and what changed. Distinguish **confirmed** (computed
here) from **plausible** (argued but not computed), and never present the second as the
first. Say explicitly what you could not run and why — an unmet gate, an unavailable
dataset, a runtime too long — rather than skipping it silently. When the honest answer is
that a piece of the analysis does not hold up, that is the useful answer.

Before finishing: `pytest`, `check_generated_macros.py`, `check_reproducible.py`, a full
`regenerate.sh`, a clean thesis build and a clean logbook build. Do not commit.
