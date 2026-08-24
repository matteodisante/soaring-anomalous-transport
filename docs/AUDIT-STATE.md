# Where the three audits got to

Written 2026-08-06. Three audits ran over the repository: the physics of Chapter 3, the code
and its comments, and the documentation. Each finding was recomputed or executed before being
acted on, and several of the audits' own claims did not survive that. This file records what
was applied, what was rejected and why, and what is left.

Everything below refers to commits between `f70d8b3` and `dd3ce11`.

!!! warning "This is a record, not the current state"
    A second pass over the code ran on **2026-08-25**, and this file has to be read against
    what has happened since `dd3ce11`, which is asymmetric:

    - **The code claims mostly still stand.** One module out of 41 under `src/` changed in
      between, so what this file says about estimators and their fixes is still about the
      code that is there.
    - **The thesis claims are void.** `03-dataset.tex` and `04-global-transport.tex` were
      rewritten afterwards — around 4,000 lines of churn — so any argument here about a
      paragraph, a section or a number in the thesis is about text that no longer exists.
      Recheck before believing.

    **Every lead in *Left, in the order I would take it* has now been resolved**, and the
    section is kept for what it says about how such leads should be read. Outcomes:
    `persistence_runs` being quadratic is moot, the estimator having been removed in
    `897c45c`; the IGC parser's bare `int()` and `stream_flights` reassembling a
    non-contiguous flight were both real and are fixed; `preprocess.py` leaving `derived/`
    describing two runs was real and now has a marker the regeneration refuses to run past;
    `velocity_autocorrelation` was right about the function and wrong about the input — an
    explicit `max_lag=0` is silently ignored rather than mismatched, and it is a *negative*
    value that returns arrays of different lengths. That is the file's own prediction, that
    roughly a third of such claims do not survive recomputation, holding for itself.

    The four candidate physics models below have still not been written into the thesis, and
    the condition on them has not changed.

---

## Applied, and why

### Numbers that were printed in the thesis and were wrong

**The kinematic quantiles were half a bin low** (`68385ed`). `_from_histogram` paired
`cumsum(counts)`, which is the mass below each bin's *upper edge*, with the bin *centres*.
Twelve macros moved: the turning-angle medians, three speed percentiles and the vertical decile
band, both disciplines. The band matters beyond a digit — it looked symmetric only because both
ends were displaced equally, and it is skewed upward. Pinned by
`tests/reporting/test_histogram_quantiles.py`, which fails 6 of 7 against the old estimator.

**The turning-angle stride was a sample count typeset as seconds** (`68385ed`). It is
`positions[step::step]`. False wherever the cadence is not 1 Hz: 10.7 % of paraglider fixes and
38.3 % of hang-glider ones. The stride is *right* to be in samples — the smoothing window is
five samples at every retained cadence — so the macro was renamed rather than converted. That
exposed the real problem it was hiding: the two disciplines' medians were being read at
different intervals. `KinematicAccumulator` now keeps a second histogram over 1 Hz segments
only, and the matched comparison is 11.3° against 17.1°, so the discipline difference survives
and loses 27 % of its size.

**The quoted slope swing belonged to a curve the figure does not draw** (`44f5ed5`). Four calls
to `local_slope` passed a half-decade window of 0.25, including the one that draws panel (d);
the one that writes the macros took the 0.15 default. 0.28 quoted against 0.26 drawn.

**The breakpoint null carried the window's noise and the whole grid's correlation** (`c931543`).
Measured with the chapter's own clustering, the lag-to-lag correlation is 0.33 over the full
grid and 0.98 inside the fitted window; the null was built with the second sigma and the first
correlation. A lower correlation whitens the surrogate, a whiter surrogate breaks less often,
and the false-positive rate was understated: 16 %/34 % becomes 59 %/58 %. The direction is safe
— the chapter was already refusing to claim a break — and the corrected numbers say something
the old ones could not: the two disciplines now agree to within a point on archives differing
twenty-five-fold in size, which is direct evidence that the limit is the correlation and the lag
count rather than the amount of data.

**A missing data root silently truncated `verify.tex`** (`644dcf5`). The script rewrites the file
wholesale, so one unreachable root deleted the other discipline's macros and the build then died
on an undefined control sequence naming the wrong line. It also had no argparse, so `--help` ran
a full traversal of a 43 GB table. Both fixed; `--allow-partial` is the escape hatch.

### Comments and docstrings that described something the code does not do (`298481e`)

`filtered_variation` took a `dt` documented as keeping the returned lags in seconds — never read,
and the function returns no lags. Removed rather than documented: a no-op parameter named `dt` in
an estimator whose lags are in samples is the trap that produced the stride defect above.
`moment_spectrum`'s Returns block described the second difference, the one quantity the module
argues must not be used. `bilinear_fit` documented seven of its eight keys and the missing one is
the only one the thesis consumes. The Lévy calibration was quoted twice with different numbers
(1.52 and 1.57); four seeds give 1.563 to 1.653, and neither 1.52 nor the quoted slope 0.96 ever
occurs.

### Documentation (`37e2639`, `191149b`, `15a6318`, `5e8518b`, `522a17a`)

The README described a repository that had stopped existing — acquisition only, with the pipeline,
the observables and the bootstrap all absent, and a quick start that ended at the download.
Rewritten around the three subsystems. Measured and corrected: the Python badge (3.10 against a
`requires-python` of 3.12), the `derived/` tree (one file shown of five), `uv run mkdocs serve`
(fails after a plain `uv sync`), the claim that `thesis/generated/` descends from `data/` (true of
3 files of 14), and the undocumented `clean` subcommand.

`preprocess.py` writes four tables and said three, in four files. The pipeline guide claimed the
Parquet footers carry a config hash and a git commit (they carry `ARROW:schema` and `pandas`),
that `fixes` is read with Polars (not a dependency), and that a threshold is imported by a module
that does not exist. `data-on-disk.md` stated two different shapes for `flights_meta` twenty lines
apart. The published API page marked four pipeline stages "to build" that have run on the whole
archive. `regenerate.sh` enumerated fifteen steps and prints sixteen. The disk README named
`catalog/` as the directory that cannot be regenerated — it is rebuilt by `build-catalog`, while
the 168 MB of season XML that genuinely cannot be replaced had no row at all.

---

## Rejected after checking

**The audit wanted `156017` replaced by `155788` in six places.** Five of them describe an incident
that happened when the archive did hold 156 017 flights. Rewriting them would have falsified the
history rather than corrected it. Only the one in the present tense was changed.

**D1 and D2 of the physics audit were already fixed** by `b9181d0`, which predates the audit's
reading of the file. Their numbers are right; their prescriptions were already in the text
verbatim.

**The physics audit compared a paraglider residual amplitude against the hang-glider noise sigma**
(0.0027 is `\StatVarHangNoiseSigmaDex`; the paraglider value is 0.0005). The thesis quotes both
correctly, each labelled with its discipline, so nothing there needed changing.

**The standardisation in `sampling_covariance` was not the dominant error.** It was reported as the
main defect; inside the fitted window it moves the correlation from 0.973 to 0.979, because sigma
varies by only 3.7× there. The window, not the standardisation, was what mattered. Both were fixed,
but the diagnosis in the audit was the wrong way round.

---

### The two high-severity code findings, since verified and fixed

**A value that turned NaN was reported as exact agreement** (`41408cf`). `check_reproducible.py`
is the guarantee behind Chapter 2's reproducibility claim, and it took its difference with
`np.nanmax`, which *skips* NaNs rather than failing on them. One value of `z` turning NaN in a
four-row frame gave a verdict of 0.0 — identical — and a wholly missing column gave `nan`, which
is not greater than any threshold either. The missing-value pattern is now compared first, in
both directions. Re-run on the archive afterwards: 80 flights, 80 identical, 0 disagreeing, so
the stricter comparison did not turn real data into false alarms.

**A blank barometric channel read as fully present** (`dd3ce11`). `_altitude` returns `nan` for a
blank field, by design; both places that measured presence tested `baro != 0`, and `nan != 0` is
True. A logger writing blanks was therefore reported at 100 % presence, passed the 95 % threshold,
and had its absent altitude adopted. Measured bite: 3 paraglider and 1 hang-glider flight retained
with `alt_source = baro` and a NaN `baro_range_m`. Nothing downstream reports a wrong number,
because the gap filler bridged the range, but the classification rested on a false reading. **The
stored tables predate the fix and still carry those four flights; they change at the next full
pipeline run.**

### D3 — the velocity-memory exponent is quoted as a power law and is not one

**Verified here, fix half-applied.** The chapter says the tail of $C(\tau)$ "is a power law of
$\gamma = 0.61$ and $0.57$" over fifteen lags. Measured on the stored `vacf` with the repo's own
`local_slope` at the window the fit uses, the local exponent runs **0.302 → 0.841** for
paragliders, monotonically, a factor of 2.78, and **0.341 → 0.662 → 0.619** for hang gliders. The
single fit leaves residuals of 0.106 dex (para) and 0.055 dex (hang) — an arch, which is the
chord-across-a-bend error this chapter diagnoses elsewhere.

What does not change is the conclusion, and it comes out stronger: **every local slope is below
one**, in both disciplines, at all fifteen lags. Non-integrability is what Green–Kubo needs, and
it holds pointwise rather than only on the fitted average.

**Applied.** `generate_shape_figure.py` emits `\StatShape*VacfGammaLocalMin/Max/Ratio/BelowOne`
and `...VacfGammaResidualDex` beside the fitted value, and both sentences that called the tail a
power law — the body and the verdict — now give the local range and the pointwise statement
instead. The fitted value is still reported, as a fit rather than as a description.

The audit's own prescription here should **not** be followed: it wanted the Green–Kubo floor
raised from 1.39 to ≈1.70 on the strength of a de-biased γ. That is the wrong direction — a floor
on α needs an *upper* bound on γ — and at 1.70 the hang-glider α₁ of 1.70 would fail its own test.

## Left, in the order I would take it

None of the following has been verified by me. They are the audit's claims, and this repository's
experience is that roughly a third of such claims do not survive recomputation — so treat each as
a lead, not a defect, until it is reproduced. In descending order: `stream_flights` stitching a non-contiguous flight; `persistence_runs`
being quadratic; `velocity_autocorrelation` returning mismatched arrays for an explicit
`max_lag=0`; the IGC parser's bare `int()` on the degrees field; `preprocess.py` able to leave
`derived/` describing two different runs.

The physics audit's four candidate models (fractional heading memory with a superstatistical
amplitude; an advected tracer in a convective boundary layer; a within-flight distribution of
persistence times; a nested-cycle description) have **not** been written into the thesis and should
not be until each falsifying measurement it proposes has been run. Every one of them is a row
selection or a null on arrays already stored.

Also open, unrelated to the audits: the pandas hot-path optimisation (measured 6.9×, not applied,
awaiting a decision), and `git push`, which needs `ssh-add ~/.ssh/id_rsa`.
