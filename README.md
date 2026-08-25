# soaring-anomalous-transport

[![Tests](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml/badge.svg)](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml)
[![docs](https://img.shields.io/badge/docs-online-brightgreen)](https://matteodisante.github.io/soaring-anomalous-transport/)
[![python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Master's thesis on **anomalous transport in soaring flights**, and the code that produced
every number in it. Both live here, in one repository, on purpose: no measurement in the
document is typed by hand, so the text and the code that backs it cannot drift apart
without the build failing.

**Work in progress.** Three chapters are measured and written; the fourth is a plan.

📄 [`thesis/main.pdf`](thesis/main.pdf) · 📖 [Documentation](https://matteodisante.github.io/soaring-anomalous-transport/) · 📓 [`logbook/logbook.pdf`](logbook/logbook.pdf)

## Where the thesis is

| | Chapter | State |
|---|---|---|
| 1 | Introduction | written |
| 2 | The dataset | **measured and written** — acquisition from the FFVL CFD, and the seven-stage pre-processing pipeline that turns roughly 190 000 raw `.igc` tracklogs into the analysis ensemble |
| 3 | Global transport | **measured and written** — everything the un-segmented ensemble can be asked, and the class of transport it fixes |
| 4 | Flight phases | **a plan, not a result** — segmentation into climb / glide / search, and the modelling it would enable. None of it is implemented |

Appendices 2.A–2.B (PSD, geodesy), 3.A (CTRW), and an implementation appendix per chapter.
A numerical simulation of a transport model is the next sub-package and does not exist yet.

## What the measurements say so far

Over one window of about 1.5 decades, measured within a retained segment by an estimator
that annihilates a polynomial trend rather than estimating one, cross-country soaring is:

- **super-diffusive**, at an exponent the two disciplines agree on within uncertainty —
  which is not guaranteed, since paragliders and hang gliders differ in speed and glide ratio;
- **monofractal** — the moment spectrum is straight, with no Lévy knee, so it is **not the
  Lévy walk this thesis was framed around**;
- **not Gaussian** either, but through a *between-flight amplitude spread* rather than a
  heavy tail within any one record: against a matched Gaussian null both disciplines sit
  below it;
- **directionally persistent**, with a non-integrable velocity memory — which is what
  reconciles a fast-decaying autocorrelation with correlated increments;
- **never isotropic**, in amplitude and in exponent alike, so the two horizontal components
  are analysed separately and never pooled.

Three cautions belong beside those, because the code makes them explicit and a figure does not:

- **The ensemble MSD about take-off is a crossover, not a power law.** Its shape is set by
  the geometry of the launch site — displacement from take-off bends where the population
  leaves its launch area. The reported exponent comes from the within-segment filtered
  variation instead; the ensemble curve is kept as the measurement of that contamination.
- **Scaling inside the window is approximate.** The exponent moves when the fitted range is
  halved by more than the sampling error, and the fit carries a budget for one exponent,
  not for a count of regimes.
- **Correlations between flight legs are untested, not established.** They cannot be tested
  before the segmentation exists, and nothing here says that a glide points at the next
  thermal.

Four further measurements were tried and **withdrawn**, each for a stated reason rather
than because it disagreed. The chapter says which and why; that record is part of the result.

## What is in the repository

```text
thesis/       the LaTeX thesis, and thesis/generated/ — every measured number, as macros
src/soaring/  the installable package: acquisition, pre-processing, estimators
  acquisition/ffvl/     .igc download and cataloguing from the two CFD sites
  analysis/preproc/     the seven-stage cleaning pipeline, one module per stage
  analysis/observables/ the transport estimators, and the synthetic nulls they are validated against
  analysis/stats/       the clustered bootstrap
  reporting/            what the reporting scripts share: the disciplines, the macro contract
scripts/      the command-line entry points that drive the package
  reporting/            the passes (stream the archive) and the reductions (write .tex and .pdf)
docs/         the published documentation (MkDocs + mkdocstrings)
configs/      every threshold, external to the code: acquisition and pre-processing YAML
data/         the only versioned data: two per-season summary CSVs and a basemap
tests/        512 tests, mirroring src/ module for module
logbook/      a working logbook: the chronology and the reasoning, with a generated timeline
revisions/    the annotated PDFs and answers from the two review passes
global_analysis_sketches/  the July 2026 specification the analysis was built from
```

**The flight archive is not in the repository.** It lives on an external SSD, organised by
maturity (`raw/`, `catalog/`, `derived/`), and comes to 1.36 × 10⁹ cleaned fixes and 43 GB
of Parquet for paragliders alone. What is versioned here is the two small `seasons_index.csv`
snapshots and the basemap, so the figures need neither the network nor the disk.

## The contract between the code and the thesis

This is the one thing to understand before changing anything, and the only part not
documented better elsewhere.

**No measured number is typed into the thesis.** Every one is a `\newcommand` written by a
script into `thesis/generated/` and quoted by name: the thesis says `\StatVarParaAlphaOrderTwo`, never the digits it
stands for. Four mechanisms keep that honest:

- **`scripts/regenerate.sh`** re-measures everything in the one order that is correct, and
  its header says why the order is a constraint rather than a convenience. It refuses to
  start while `preprocess.py` is still writing, and refuses again if a previous run died
  half-way and left the derived tables describing two different runs.
- **`soaring.reporting.write_macros`** refuses to write a macro name LaTeX cannot parse. A
  name with a digit in it defines a *shorter* macro taking arguments, which fails the build
  from a definition nothing even quotes.
- **`soaring.reporting.guards`** refuses two silent half-results: a file written for one
  discipline of two (the thesis then fails on the absent one's macros, or a figure quietly
  loses a curve), and a `--help` that a script without an argument parser would otherwise
  treat as an instruction to start a pass over the archive.
- **`scripts/reporting/check_generated_macros.py`** reads both sides of the contract in a
  second and with no build: every macro the thesis quotes must exist, and a typed number
  that a generated macro already carries is reported as the same failure in the other
  direction.
- **A pre-commit hook** (`git config core.hooksPath .githooks`) keeps the cheap, deterministic
  parts in sync on every commit — the season snapshots, the headline statistics, the logbook
  timeline, and the two PDFs.

The corollary for anyone editing: **change a threshold in `configs/`, not in the code, and
re-run the generator that owns the number** — [Where each number comes from](https://matteodisante.github.io/soaring-anomalous-transport/guide/provenance/)
maps every macro back to the script that wrote it, and is itself generated so it cannot go stale.

## Documentation

Installing, acquiring the data, the pre-processing pipeline stage by stage, what is on the
data disk column by column, the transport estimators, and the provenance of every number
are all at **<https://matteodisante.github.io/soaring-anomalous-transport/>** — and are
deliberately not repeated here.

Two pages are the entry points: [The pre-processing pipeline](https://matteodisante.github.io/soaring-anomalous-transport/guide/preprocessing-pipeline/)
for Chapter 2, and [The global-transport measurement](https://matteodisante.github.io/soaring-anomalous-transport/guide/global-transport/)
for Chapter 3.

```bash
uv sync                             # environment
uv run pytest                       # the test suite
uv run --extra docs mkdocs serve    # the documentation, at 127.0.0.1:8000
```

License: MIT.
