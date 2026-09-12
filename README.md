# soaring-anomalous-transport

[![Tests](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml/badge.svg)](https://github.com/matteodisante/soaring-anomalous-transport/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/matteodisante/soaring-anomalous-transport/branch/main/graph/badge.svg)](https://codecov.io/gh/matteodisante/soaring-anomalous-transport)
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

Three appendices specify the spectral estimates, the geodetic coordinate transformation
and the relation between absolute and squared displacement distributions.
The roadmap records later work on phase-conditioned observables, solo/group flight,
stochastic modelling and simulation, and thermal landscapes with route optimisation.

Chapter 3 now computes the 10–10,000 s diagnostics from all eligible cleaned
flights and segments. The complete rerun and reviewed 116-page thesis are finished. Signed joint displacement
laws complement the absolute component and radial distributions. Quantile and moment weights, changing coverage and model
assumptions are explicit. Regional principal axes do not identify wind. Beginners (EN A/B)
and experts (EN C/D/CCC) are equipment-based experience proxies used consistently in
anisotropy and duration comparisons; the catalogue does not measure individual skill.
The model comparisons constrain particular
predictions; formal process rejection needs calibrated finite-record simulations.
Independent manual labels remain necessary before claiming segmentation accuracy.

Pipeline 2.3.0 applies the temporal gap bound to missing altitude and splits the full
trajectory at long vertical holes. Both complete archives were rebuilt: 156406
paraglider and 6094 hang-glider flights were retained. The full common-grid Chapter 3
diagnostics use 155085 and 6060 eligible flights; fixed long-flight controls use
14360 and 563. All 39 downstream stages and the final manuscript review completed.
See the [execution and review record](revisions/vertical-gap-split-2026-09-11/README.md)
for source identities, recovery evidence and remaining scientific limitations.

The numerical rebuild does not by itself validate HMM phase labels or formally
reject a stochastic transport model. The fresh phase outputs were reviewed;
independent phase labels and calibrated model comparisons remain necessary.
The [request checklist](revisions/request-checklist-2026-09-11.md) distinguishes
these research questions from the current delivery.

[Supervisor chapter decks](presentations/README.md) cover both complete chapters,
including the current joint laws and the interpretation and criticisms of the
regional equipment comparison. They were assembled after the thesis review.

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

The roadmap requires no action. The current [manual annotation pack](annotations/phase_labeling/20260912T133040Z-073601cb/README.md) is ready; follow
[the annotation instructions](annotations/phase_labeling/README.md).
Keep the final test split separate from model tuning.

License: [MIT](LICENSE).
