# The global-transport measurement

What is measured on the retained ensemble *without* segmenting a flight into its phases:
seven estimator modules under `soaring.analysis.observables/`, the clustered bootstrap in
`soaring.analysis.stats`, five streaming passes over the fix table and six reductions that
turn their output into the figures and macros of the thesis chapter **Global transport**.

This page is the map of that code, in the same sense that
[the pipeline guide](preprocessing-pipeline.md) is the map of the pre-processing code.
Two things deliberately live elsewhere:

- **The reasoning** — why an estimator was chosen, why a measurement was withdrawn — is in
  the thesis, chapter *Global transport* (`ch:global`), with the implementation detail in
  appendix `impl:global`.
- **The numbers** — every exponent and every count — are generated macros in
  `thesis/generated/`, listed by owner in
  [Where each number comes from](provenance.md).

On any disagreement the thesis is normative and this page is the one to correct.

!!! note "File names are one ahead of chapter numbers"
    `sections/02-data-acquisition.tex` is `\input` inside `03-dataset.tex` as its opening
    section, so the printed chapters are one behind the filenames.

    | file | printed as |
    |---|---|
    | `sections/03-dataset.tex` | Chapter 2, *The dataset* |
    | `sections/04-global-transport.tex` | **Chapter 3, *Global transport*** — this page |
    | `sections/05-flight-phases.tex` | Chapter 4, *Flight phases* |

## What this establishes, and what it cannot

Without segmentation the ensemble answers questions about a **class** of transport: how far
a wing gets in a given time, how that growth is distributed across the increment
distribution, how long the motion remembers its heading, and how many distinct scaling
regimes the answer needs. It cannot answer which flight behaviour produces any of it —
every quantity here mixes climbing, gliding and searching into one number. That separation
is Chapter 4 and does not exist yet.

Two constraints from the preliminary characterisation (`sec:prelim`) hold throughout the
code, not just the prose:

1. **The horizontal components are anisotropic.** The ratio of their mean squares never
   touches unity, so the two marginals are measured separately and a pooled
   one-dimensional marginal never substitutes for the two-dimensional propagator.
2. **The discipline is heterogeneous.** Wing class and orographic group are relevant
   strata; season is not. Every exponent is reported by stratum as well as pooled, and the
   two disciplines are never pooled into each other.

Both are enforced by the estimators taking a component axis and by the reductions
stratifying, rather than by a convention anyone has to remember.

## The observable inventory

One row per section of the chapter. The **pass** streams `fixes.parquet` and writes an
intermediate array; the **reduction** reads that array and writes the macros and the
figure. Steps are the numbered steps of `scripts/regenerate.sh`.

| chapter section | estimator module | pass | reduction | macros |
|---|---|---|---|---|
| `sec:obs-global` — displacement from take-off | `observables.transport` | `audit_msd.py` (5) | `audit_msd_report.py` (6), `generate_msd_figure.py` (3) | `\StatMsd*`, `\StatAudit*` |
| `sec:variations` — the filtered variation | `observables.variations` | `measure_variations.py` (9) | `generate_transport_figure.py` (10) | `\StatVar*` |
| `sec:transport-measure` — the uncertainty on the exponent | `stats.bootstrap`, `observables.regimes` | — (reads step 9) | `generate_transport_figure.py` (10) | `\StatVar*` |
| `sec:transport-propagator` — the exponent from the quantiles | `observables.propagator` | `measure_propagator.py` (13) | `generate_propagator_figure.py` (13) | `\StatProp*` |
| `sec:transport-axisroutes` — the exponent, split by component | `observables.transport`, `observables.variations` | — (reads steps 3, 9) | `generate_msd_figure.py` (3), `generate_transport_figure.py` (10) | `\StatMsd*`, `\StatMsdTa*`, `\StatVar*` |
| `sec:transport-shape` — not a Lévy walk | `observables.moments` | `measure_shape.py` (11) | `generate_shape_figure.py` (12) | `\StatShape*` |
| `sec:transport-gaussian` — the propagator is not Gaussian | `observables.moments` | `measure_shape.py` (11) | `generate_shape_figure.py` (12) | `\StatShape*` |
| `sec:transport-memory` — the memory of the heading | `observables.persistence` | `measure_shape.py` (11), `measure_circling.py` (15) | `generate_shape_figure.py` (12) | `\StatShape*`, `\StatCircling*` |
| `sec:transport-kinematics` — speed and vertical velocity | `observables.propagator` (`KinematicAccumulator`) | `measure_propagator.py` (13) | `generate_propagator_figure.py` (13) | `\StatKin*` |
| — the edge-sample effect | `observables.transport` | `measure_edge_effect.py` (14) | same script | `\StatEdge*` |

`observables.synthetic` appears in no row because it measures nothing on the archive: it
generates the processes the other seven are validated against (see
[The nulls](#the-nulls-and-what-each-one-rules-out)).

### Which estimator the chapter actually quotes

Not the one it starts from. The headline exponent is $\alpha_2$ from
`variations.filtered_variation` at filter order 2, and the reason is structural rather
than a preference:

- **The ensemble MSD about take-off was withdrawn.** Every flight shares an origin, and a
  residual per-flight course adds $|v_d|^2\Delta^2$ to it, so the curve turns ballistic at
  long lags whatever the motion does. What it yields is a *timescale* — where the
  population leaves its launch area — not an exponent. `audit_msd.py` still runs, because
  measuring the size of that contamination is what licenses withdrawing it — including, per
  component, whether that contamination is itself isotropic (`sec:transport-axisroutes`).
- **The filtered variation never estimates a drift.** A finite difference of order $p$
  annihilates any polynomial of degree $p-1$ identically. The order scan is the useful
  part: $\hat H_1 - \hat H_2$ is how much of the apparent exponent was course, and
  $\hat H_2 = \hat H_3$ certifies nothing polynomial is left.
- **The propagator quantiles are the independent check.** The median absolute increment is
  an order statistic, not a moment, so a heavy tail does not move it; and reading the same
  slope at the 25th, 50th, 75th and 90th percentiles *tests* self-similarity instead of
  assuming it. Nothing else here can.

Everything above the first bullet works on **within-segment increments**, never on
displacement from take-off.

## The lag grids and the fit windows

Stated once here; each is a constant at the top of the script named.

| grid | range | points | set by |
|---|---|---|---|
| MSD / audit | 1 s – 43 200 s | 90, geometric | `audit_msd.py`, `generate_msd_figure.py` |
| filtered variation | 60 s – 20 000 s | 36, geometric | `measure_variations.py` |
| moment spectrum, VACF | 60 s – 8000 s | 24, geometric | `measure_shape.py` |
| propagator histograms | 30 s – 4000 s | 20, geometric | `measure_propagator.py` |
| circling VACF | 1 s – 60 s, every integer lag | 60 | `measure_circling.py` |
| edge effect | 1 s – 600 s | 40, geometric | `measure_edge_effect.py` |

**The fit window is 60–2000 s** — `FIT_RANGE_S` in `generate_transport_figure.py` and
`generate_propagator_figure.py`, `TRANSPORT_RANGE_S` in `generate_shape_figure.py`. Both
ends are physical, not statistical, and neither widens with more data:

- **Below 60 s** the trajectory has been smoothed over a window whose floor is five
  samples and which therefore scales with the logger's cadence, so nothing below it is
  read as motion.
- **Above 2000 s** the declared task governs the displacement — the local slope separates
  closed from open courses — and a soaring day ends, so the upper cutoff follows from the
  system rather than the method.

A quantity sensitive to the far tail is *quoted* over this window and *drawn* beyond it, so
the reader sees what was excluded.

The MSD grid runs far wider than the fit window on purpose: `coverage_limited_range` in
`observables.transport` narrows it per discipline from the number of flights still
contributing at each lag, so a fit is never made on lags carried by a handful of records.

## Why the passes are separate from the reductions

A pass streams `fixes.parquet` end to end. The paraglider table is 1.36 × 10⁹ rows and
43.4 GB, so a pass costs minutes to hours; a reduction reads a few tens of megabytes and
costs seconds. Keeping them apart is what makes a **stratification a row selection rather
than another traversal** — `generate_transport_figure.py` splits by cadence, wing class,
season and declared task without touching the fix table, because `measure_variations.py`
kept one curve per flight per filter order rather than an average over flights.

The same split is why `generate_prelim_figure.py` can produce a stratified MSD from
`audit_msd.py`'s per-flight positions instead of a second 43 GB scan.

Where the intermediate arrays go, what each one holds, and how big it is: see
[The scripts](scripts.md#where-the-intermediate-arrays-go). They are analysis products,
not thesis products — reproducible by re-running the pass, and deliberately outside the
repository.

## The nulls, and what each one rules out

`observables.synthetic` generates trajectories whose transport is known in advance, on a
uniform grid in metres shaped `(n, 2)`, so a synthetic flight reaches an estimator through
exactly the code path a real one takes.

| process | what it tests | pinned by |
|---|---|---|
| `brownian` | the null: an estimator that does not return $\alpha = 1$ here is wrong, and everything else it says is uninterpretable | `test_synthetic.py` |
| `fractional_brownian` | correlated Gaussian motion at a set exponent — the competing hypothesis to a Lévy walk, and the process the detrending bias is measured against | `test_synthetic.py`, `test_variations.py` |
| `levy_walk` | the hypothesis the thesis was framed around: the process whose moment spectrum bends and whose front is ballistic | `test_synthetic.py`, `test_moments.py` |
| `persistent_walk` | the confound: superposed over a spread of persistence times it manufactures a power law out of ordinary diffusion | `test_synthetic.py`, `test_propagator.py`, `test_variations.py` |
| `with_drift` | that a residual course is what turns an ensemble estimator ballistic | `test_variations.py` |

`regimes.spurious_breakpoints` is the same idea one level up: it runs the breakpoint
selection on surrogates built from a single power law plus noise and reports how often it
manufactures a break. Without that number, finding a knee establishes nothing. The noise
model comes from the estimator's *sampling* error — a clustered bootstrap over flights —
and never from the residuals about a straight line, which would be circular whenever the
curve is genuinely bent.

## The uncertainty

`stats.bootstrap` exists because the archive holds 155 788 paraglider flights and nothing
like 155 788 independent measurements of the atmosphere. Two wings launched from one site
on one day flew the same air: the same convective strength, the same wind, the same cloud
base, often the same thermals in the same order.

- **The resampling unit is the cluster, not the flight.** Resampling flights returns an
  error bar one to two orders of magnitude too small — the difference between an exponent
  that discriminates between models and one that does not.
- **Which cluster is a measurement, not a preference.** `intraclass_correlation` reports
  how much of the variance sits between groups at each candidate level — flight, day,
  site, day and site together, pilot, season — and the level to resample at is the coarsest
  one that still carries most of it.
- **A curve of $n$ lags is not $n$ independent points.** Every lag averages the same
  flights. `sampling_covariance` supplies the lag-to-lag covariance, and
  `regimes.effective_dof` converts it into the number of degrees of freedom a fit may
  actually spend — which is what makes "two regimes" a measurement rather than an artefact
  of counting.

Both the clustered and the naive error are emitted (`\StatVar*Err` beside
`\StatVar*ErrNaive`) so the gap between them stays visible in the record rather than being
asserted in the prose.

## What the measurement returns

Read against the code rather than summarised from the chapter, the ensemble over the fit
window is:

- **Super-diffusive**, at an exponent the two disciplines agree on within their
  uncertainties — which is not guaranteed, since they differ in speed and in glide ratio.
- **Monofractal.** The moment spectrum $\nu(q)$ is straight across the range of $q$ read:
  no Lévy knee, so it is **not the Lévy walk this thesis was framed around**.
- **Not Gaussian** either — but the non-Gaussianity is a *between-flight amplitude spread*,
  not a heavy tail within one record. Against a matched Gaussian null both disciplines sit
  *below* it, which is sub-Gaussian per flight. One exponent governing every moment states
  how the increment distribution scales and nothing about its shape.
- **Directionally persistent**, with a velocity memory whose tail is non-integrable — which
  is what reconciles a fast-decaying $C(\tau)$ with correlated increments.
- **Never isotropic**, in amplitude *and* in exponent: $H$ differs between the east and
  north components, on the quantile route and, in the same direction, on the time average
  and both filtered-variation orders (`sec:transport-axisroutes`).

Two cautions the code makes explicit and a reader of the figures might not:

!!! warning "The ensemble MSD is a crossover, not a power law"
    Its shape is set by the geometry of the launch site — displacement from take-off
    crosses over where the population leaves its launch area. The exponent the thesis
    reports comes from the within-segment filtered variation, and the ensemble curve is
    kept as the measurement of that contamination.

!!! warning "Scaling inside the window is approximate"
    $H$ falls from the bulk of the increment distribution to its flank, and the exponent
    moves when the fitted range is halved by more than the sampling error. The window
    carries a budget for one exponent, not for a count of regimes.

## What is deferred to segmentation

Chapter 4 inherits a class of transport and five constraints on how it may be decomposed —
they are stated in `sec:transport-verdict` and are the reason several obvious analyses are
not in this repository yet. The one worth repeating here, because it is the easiest to
assume by accident:

**Correlations between legs are untested, not established.** Whether successive glide
directions, leg lengths, waiting times, or the cross terms between them are correlated can
only be tested once the segmentation exists. Nothing in this code says that a glide points
at the next thermal, and no figure or docstring should be written as though it did.

## Reproducing it

Steps 3–15 of `scripts/regenerate.sh`, which is also the only correct order — its header
says why for each. Both data roots must be exported whichever discipline is asked for,
because the generated `.tex` files carry both and a partial one breaks the build:

```bash
export SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc
export SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc

scripts/regenerate.sh --no-build      # everything, stopping before latexmk
```

To re-run one measurement, run its pass and then its reduction, in that order, with a
shared `--out` / `--audit-dir`:

```bash
AUDIT_DIR=${TMPDIR:-/tmp}/soaring-audit

uv run python scripts/reporting/measure_variations.py --out "$AUDIT_DIR"
uv run python scripts/reporting/generate_transport_figure.py --audit-dir "$AUDIT_DIR"
```

Every generator that reaches one discipline of two **refuses to write** rather than
emitting a half file: a truncated `.tex` makes the thesis fail to build on the macros the
absent discipline owns, and a truncated *figure* fails silently, losing a curve while the
build succeeds. The refusal names the cause — an unset environment variable, an unmounted
disk, a missing pass — because those have different fixes. `--allow-partial` overrides it
when a one-discipline run is what you want.

Both `configs/*_download.yaml` carry a real `data_root`, so a run on the author's machine
needs no environment at all; the variables above override it anywhere else. A config left
on a placeholder is one of the causes the refusal names, since it is indistinguishable from
a mounted disk until it is looked for.

Finally, and before any build:

```bash
uv run python scripts/reporting/check_generated_macros.py
```

Every macro the thesis quotes must exist by then. An undefined one inside `\SI{}` is a
*fatal* LaTeX error diagnosed from a symptom that names the wrong line, which is why the
check runs first and its failure is the useful message. Since the reporting scripts moved
onto `soaring.reporting.write_macros`, a name LaTeX cannot parse is refused at the point
the generator writes it, rather than surviving to this check.
