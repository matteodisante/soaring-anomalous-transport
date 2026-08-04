# Analysis plan — the un-segmented observables

Three working documents, in Italian, written in July 2026 before the pre-processing
pipeline existed. They are the **specification for Chapter 3**: every observable that can
be measured on the dataset without first segmenting a flight into its phases.

| File | Covers |
|---|---|
| `01_fondamenta.md` | data schema, sampling step and filtering, lag grid and `N_eff`, wind from the sliding-window hodograph, the three drifts, centred increments, isotropy |
| `02_trasporto.md` | MSD by FFT, the moment spectrum, PDF scaling and collapse, VACF and heading correlation, geometric persistence times, block and shuffle tests |
| `03_diagnostica.md` | the heterogeneity confound, the vertical channel, bootstrap over flights, the 15-row consistency table, what remains precluded, output schema and execution order |

## How to read them against the code

They were written before the pipeline, so **where they and the repository disagree about
facts, the repository wins; where they disagree about method, they win.**

- Their data schema (`tracks.parquet`, `flights.parquet`) is a proposal. The real schema is
  `fixes` / `segments` / `flights_meta`, documented in `docs/guide/data-on-disk.md`.
- Their proposed `src/io/`, `src/observables/`, … layout is a suggestion about separation of
  concerns, not about paths; the package is `soaring`.
- Their `values.tex` emission (§3.7.2) is the mechanism this repository already implements
  as the `\Stat*` generated-macro contract. Do not build a second one.
- The ERA5 cross-check (§1.4.2, GATE B) needs reanalysis data the repository does not have.
  The hodograph wind is implemented; that gate is recorded as unmet.

## Two places where they correct the thesis

Both were written before the measurement that confirmed them, and both are load-bearing.

**§1.4 — residual drift.** A residual drift adds `|v_d|² Δ²` to the MSD, makes everything
ballistic at long lags, inflates the exponent, and *translates* the PDF instead of rescaling
it, which destroys any collapse test. The MSD audit of August 2026 measured exactly that
signature on the ensemble estimator. §1.4.4 is the prescription: every observable is
computed on centred increments, per flight, and every exponent is reported twice — centred
and raw — so that the difference measures how much of the apparent anomaly was drift.

**§1.5.1 — isotropy.** The per-component variance ratio `⟨E²⟩/⟨N²⟩` is not a sound isotropy
test under heavy tails: it is dominated by a few outliers. The angular distribution of the
increments is scale-free and is the correct test, with circular order parameters against a
Rayleigh threshold built on `N_eff` rather than on the raw sample count.

The renderings that used to sit beside these files were PDF exports of the same Markdown
and were removed; nothing was in them that is not here.
