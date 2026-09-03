# soaring-anomalous-transport

[![Tests](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml/badge.svg)](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml)
[![docs](https://img.shields.io/badge/docs-online-brightgreen)](https://matteodisante.github.io/soaring-anomalous-transport/)
[![python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

This is my master's thesis on anomalous transport in soaring flights, together with all
the code that produced every number in it. They live in one repository on purpose: no
measurement is ever typed into the thesis by hand. Every number is written by a script,
and if a script and the thesis disagree, the build fails instead of quietly going stale.

**Work in progress.** Three chapters are measured and written; the fourth is a plan.

📄 [`thesis/main.pdf`](thesis/main.pdf) · 📖 [Documentation](https://matteodisante.github.io/soaring-anomalous-transport/)

## Where the thesis is

| | Chapter | State |
|---|---|---|
| 1 | Introduction | written |
| 2 | The dataset | **measured and written.** Acquisition from the FFVL CFD, and the seven-stage pre-processing pipeline that turns roughly 190 000 raw `.igc` tracklogs into the analysis ensemble. |
| 3 | Global transport | **measured and written.** Everything the un-segmented ensemble can be asked, and the class of transport it fixes. |
| 4 | Flight phases | **a plan so far.** Segmentation into climb, glide and search, and the modelling it would enable; none of it is built yet. |

Appendices 2.A–2.B (PSD, geodesy), 3.A (CTRW), and an implementation appendix per chapter.

## What the measurements say so far

These hold over a window of about 1.5 decades in lag, measured within a retained flight
segment by an estimator that filters out a polynomial trend rather than fitting one:

- Cross-country soaring is super-diffusive, at an exponent the two disciplines agree on
  within uncertainty. That agreement isn't automatic: paragliders and hang gliders fly at
  different speeds and glide ratios.
- The moment spectrum is straight, with no Lévy knee: monofractal, not the scaling collapse
  a Lévy walk would produce.
- It isn't Gaussian either, but not because of heavy tails within a single flight. The
  non-Gaussianity comes from how much the amplitude varies between flights: measured
  against a matched Gaussian null, both disciplines sit below it.
- The velocity memory decays too slowly to integrate, which is how a fast-decaying
  autocorrelation can still coexist with correlated increments: the motion is
  directionally persistent.
- Amplitude and exponent are both anisotropic, so the two horizontal components are
  always analysed separately and never pooled.

Three things to keep in mind, because the code accounts for them and a figure on its own
would not:

- Near take-off, the ensemble MSD is a crossover, not the transport exponent. Its shape
  comes from the geometry of the launch site: displacement bends where the population
  disperses away from it. The reported exponent instead comes from the within-segment
  filtered variation; the ensemble curve is kept in the thesis as a measurement of that
  crossover, not as the estimate.
- The scaling law only holds approximately over the fitted window. The exponent shifts
  when the fitted range is halved by more than the sampling error would predict, and the
  fit is built to return one exponent, not to detect how many regimes are really there.
- Whether flight legs are correlated with each other is still open. Testing that needs a
  segmentation into legs, which doesn't exist yet. Nothing here shows, for instance, that
  a glide tends to point at the next thermal.

## What is in the repository

```text
thesis/       the LaTeX source; thesis/generated/ holds every measured number, as macros
src/soaring/  the installable package: acquisition, pre-processing, estimators
  acquisition/ffvl/     .igc download and cataloguing from the two CFD sites
  analysis/preproc/     the seven-stage cleaning pipeline, one module per stage
  analysis/observables/ the transport estimators, and the synthetic nulls they are validated against
  analysis/figures/     plotting code shared by more than one script, kept apart from the estimators
  analysis/stats/       the clustered bootstrap
  reporting/            what the reporting scripts share: the disciplines, the macro contract
scripts/      the command-line entry points that drive the package
  reporting/            grouped by which thesis chapter each script feeds:
                        ch2_dataset/, ch3_global_transport/, plus checks/ and tools/
docs/         the published documentation (MkDocs + mkdocstrings)
configs/      every threshold, kept out of the code: acquisition and pre-processing YAML
data/         the only versioned data: two per-season summary CSVs and a basemap
tests/        557 tests, mirroring src/ module for module
logbook/      a working logbook: the chronology and the reasoning, with a generated timeline
revisions/    the annotated PDFs and answers from the two review passes
global_analysis_sketches/  the July 2026 specification the analysis was built from
```

**The flight archive itself is not in the repository.** It lives on an external SSD,
organised by maturity (`raw/`, `catalog/`, `derived/`): 1.36 × 10⁹ cleaned fixes and 43 GB
of Parquet for paragliders alone. What is versioned here is small on purpose: the two
`seasons_index.csv` snapshots and the basemap, just enough that the figures don't need the
network or the disk to rebuild.

## Documentation

Installing, acquiring the data, the pre-processing pipeline stage by stage, what is on the
data disk column by column, the transport estimators, how no number is ever typed by hand
into the thesis, and the provenance of every one of them are all at
[the documentation site](https://matteodisante.github.io/soaring-anomalous-transport/).
On purpose, none of that is repeated here.

Two pages are the entry points: [The pre-processing pipeline](https://matteodisante.github.io/soaring-anomalous-transport/guide/preprocessing-pipeline/)
for Chapter 2, and [The global-transport measurement](https://matteodisante.github.io/soaring-anomalous-transport/guide/global-transport/)
for Chapter 3.

```bash
uv sync                             # environment
uv run pytest                       # the test suite
uv run --extra docs mkdocs serve    # the documentation, at 127.0.0.1:8000
```

License: MIT.
