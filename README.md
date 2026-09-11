# soaring-anomalous-transport

[![Tests](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml/badge.svg)](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml)
[![docs](https://img.shields.io/badge/docs-online-blue)](https://matteodisante.github.io/soaring-anomalous-transport/)

The thesis and Python code for studying transport in paraglider and hang-glider flights.
The workflow starts from FFVL IGC recordings, cleans trajectories, measures their
transport statistics and segments flight into transition, search and climb.

[Read the thesis](thesis/main.pdf) · [Documentation](https://matteodisante.github.io/soaring-anomalous-transport/) · [Research roadmap](https://matteodisante.github.io/soaring-anomalous-transport/thesis-roadmap/)

## Manuscript and scientific scope

| Chapter | Question |
|---|---|
| 1. Introduction | Which physical questions motivate the data analysis, segmentation and later modelling? |
| 2. Dataset | Which recorder measurements can be used, how are defects handled, and what population survives cleaning? |
| 3. Global transport | What do displacements, quantiles, directional structure and velocity memory require of a stochastic model? |
| 4. Flight phases | How are transition, search and climb inferred, and what evidence is needed to validate those labels? |

Two appendices specify the spectral estimates and the geodetic coordinate transformation.
The roadmap records later work on phase-conditioned observables, solo/group flight,
stochastic modelling and simulation, and thermal landscapes with route optimisation.

Chapter 3 distinguishes full-archive summaries from a reproducible diagnostic subset
measured over 10–10,000 s. Quantile and moment weights, changing coverage and model
assumptions are explicit. Regional principal axes do not identify wind. Beginners (EN A/B)
and experts (EN C/D/CCC) are equipment-based experience proxies used consistently in
anisotropy and duration comparisons; the catalogue does not measure individual skill.
The model comparisons constrain particular
predictions; formal process rejection needs calibrated finite-record simulations.
Independent manual labels remain necessary before claiming segmentation accuracy.

The cleaning and all 38 rebuild stages completed for run
`20260910T221820Z-05d36ab4`: 156,305 paraglider and 6,093 hang-glider flights were
retained. The [fresh-results review](revisions/fresh-results-review-2026-09-11.md)
records the empirical interpretation. The 101-page PDF of that run was checked and reconciled
with the SSD run, including the corrected rejection cascade. The manuscript figures were
restyled afterwards, which moved the build to 102 pages. Validation includes
824 passing tests, 258 additional algebraic/support checks on saved results, and
agreement of the annotation pack with both mounted archives.
The [completion record](revisions/manuscript-review-2026-09-11/completion.json)
identifies the reviewed sources, outputs and PDF; the
[request checklist](revisions/request-checklist-2026-09-11.md) records the scope.

The computational rebuild and one manuscript-review pass are complete. Making
Chapters 3 and 4 semi-final still requires quantitative model comparisons and
segmentation validation.
The current HMM remains a model requiring independent phase validation. Its selected
restart has a negative final likelihood increment, and its coverage and posterior
probabilities are not classification accuracy. These limits and the absence of
calibrated stochastic-model rejection tests are stated in the manuscript.

## Rebuild after changing cleaning

Install the environment with `uv sync` and mount both archives. Then run:

```bash
uv run python scripts/rebuild_thesis.py --clean --jobs 8 --full-speed
```

This command uses up to eight workers at normal scheduling priority. Native numerical
libraries use one thread per worker to avoid nested oversubscription. Omit `--full-speed`
and use `--jobs 1` for a low-priority run. `--dry-run` prints the commands without writing.

The driver cleans both complete archives, verifies the tables, independently reprocesses
a sample, recomputes analyses and figures, refits and applies segmentation, prepares a
new annotation pack, updates the SSD inventory and builds the PDF. The order is defined
in [configs/rebuild.yaml](configs/rebuild.yaml). It takes multiple passes over the SSD.
A standalone `scripts/preprocess.py` run performs cleaning only; after it completes,
run the driver without `--clean` to regenerate all downstream results.

Every rebuild has a separate directory under `derived-audit/runs/` on the SSD, containing
logs, arrays and a manifest with source and dataset identities. Failed or stale stages
stop the workflow. A complete manifest with a matching PDF hash identifies a completed
build. See [the rebuild guide](https://matteodisante.github.io/soaring-anomalous-transport/guide/rebuilding/) for recovery and provenance limits.

## Repository layout

| Path | Contents |
|---|---|
| `src/soaring/acquisition/ffvl/` | Download and catalogue code, including XML export handling |
| `src/soaring/analysis/preproc/` | Cleaning, trimming, coordinate conversion, resampling and smoothing |
| `src/soaring/analysis/observables/` | Displacement, scaling, distribution and persistence estimators |
| `src/soaring/analysis/segmentation/` | Features, Gaussian HMM fitting, decoding and evaluation |
| `src/soaring/analysis/stats/` | Cluster resampling and statistical diagnostics |
| `src/soaring/reporting/` | Shared paths, numerical macros, provenance and figure style |
| `scripts/` | Command-line workflows; reporting is grouped by chapter |
| `configs/` | Acquisition paths, cleaning rules, segmentation settings and rebuild order |
| `thesis/` | LaTeX sources, bibliography, generated figures and numerical fragments |
| `annotations/phase_labeling/` | Annotation instructions and packs with source provenance; preserve human labels |
| `data/` | Small season summaries and map geometry; no flight trajectories |
| `docs/` | Methods, data schemas, workflow documentation and research roadmap |
| `tests/` | Numerical, synthetic-process and workflow checks |
| `revisions/` | Review notes and audit records |

The flight archive lives on the external SSD. Its generated `README.md` inventories the
actual files; [the data guide](https://matteodisante.github.io/soaring-anomalous-transport/guide/data-on-disk/) explains the schemas.
Do not load the full fix table into memory: use `soaring.analysis.derived.stream_flights`.

Earlier working material is preserved separately from the current methods:
`segmentation_chat.txt` is a preliminary discussion, `distinzione_e_detrending_parapendio.tex`
explores hypotheses about terrain and wind, and `riguardo-gnss-vs-baro-wise-bumblebee.md`
records an earlier cleaning proposal. Their proposed thresholds, inferences and workflows
must not be read as the current implementation. The chapter sources and method guides
above describe the reviewed definitions.

## Working on the project

```bash
uv sync
uv run pytest
uv run --extra docs mkdocs serve
```

The [pipeline guide](https://matteodisante.github.io/soaring-anomalous-transport/guide/preprocessing-pipeline/),
[transport guide](https://matteodisante.github.io/soaring-anomalous-transport/guide/global-transport/) and
[segmentation guide](https://matteodisante.github.io/soaring-anomalous-transport/guide/flight-phase-segmentation/) connect the methods to code.
[Figure conventions](https://matteodisante.github.io/soaring-anomalous-transport/guide/figures/) define colours and printed dimensions.
[Generated provenance](https://matteodisante.github.io/soaring-anomalous-transport/guide/provenance/) maps manuscript inputs to their producers;
[the bibliography audit](https://matteodisante.github.io/soaring-anomalous-transport/guide/bibliography/) records source verification and its limits.

The roadmap requires no action. The current [manual annotation pack](annotations/phase_labeling/20260910T221820Z-05d36ab4/README.md) is ready; follow
[the annotation instructions](annotations/phase_labeling/README.md).
Keep the final test split separate from model tuning.

License: [MIT](LICENSE).
