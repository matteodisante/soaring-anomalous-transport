# Where the three audits got to

Written 2026-08-06. Three audits ran over the repository: the physics of Chapter 3, the code
and its comments, and the documentation. Each finding was recomputed or executed before being
acted on, and several of the audits' own claims did not survive that. This file records what
was applied, what was rejected and why, and what is left.

Everything below refers to commits between `f70d8b3` and `54216a5`.

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

## Left, in the order I would take it

Two high-severity code findings from the audit, **not yet verified by me** and therefore not to be
believed until they are:

1. **`altitude_noise`: a blank barometric field may be counted as present and then crash the PSD
   run.** Reported as high. If true it is a robustness bug rather than a wrong number.
2. **`check_reproducible.py` may report exact agreement when a value turns NaN, and may not compare
   `segment_id`.** If true, the reproducibility check is weaker than the thesis says it is, which
   would matter for Chapter 2's claims.

Then, in descending order: `stream_flights` stitching a non-contiguous flight; `persistence_runs`
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
