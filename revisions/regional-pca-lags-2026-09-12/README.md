# Exact regional PCA lags

Figure 3.15, the regional reference table and Chapter 3 supervisor slides 52–54
use exactly **10, 100, 1000 and 10,000 s**. Every supported lag has a coloured
ellipse, eigenvalue-ratio marker, axis annotation and contributing-flight count.
The table's reference is 1000 s. Other diagnostics keep their own lag grids.

The preceding full-archive run is `20260912T133040Z-073601cb`, with cleaning
2.3.0. This follow-up changes only regional PCA. Its immutable record is
[`numerical-update.json`](numerical-update.json), and its compact results are
[`regional-pca.json`](regional-pca.json). The complete current Chapter 3 overview
report is retained losslessly in `ch3_revision.json.gz`; the preceding complete
reports and run manifests remain in the September 11 revision directory.

## Calculation and checks

`update_pca.py` verifies SHA-256 identities of both full-archive coordinate stores
and their flight indexes, then streams all 155,085 eligible paraglider and 6,060
hang-glider flights. Within each launch box it pools nonoverlapping, within-segment
increments with equal origin weight. Each flight's centred scatter is merged into
the regional covariance without keeping the pooled vectors in memory. There is no
flight subsampling, no gap crossing and no repeated cleaning or bootstrap.

The focused update took 38.5 seconds, including source/input checks and outputs;
the covariance calculations took 21.4 seconds for paragliders and 0.5 seconds for
hang gliders on this Mac. These are observations from this run, not a benchmark
guarantee. Results at the two shared lags, 10 and 10,000 s, agree with the preceding
calculation within floating-point tolerance. All non-PCA values in the full report
and the other 74 generated inputs were verified unchanged.

The 33 targeted tests passed, covering direct pooled covariance, exact lags,
segment boundaries, changing support, duplicate flights, four-lag rendering,
full-archive cache/support behaviour and the shared colour palette. Static
provenance resolves 95 generated files and 1113 macros without problems. Strict
documentation compilation also passed.

| Paraglider region | Flights at 1000 s | Ratio at 1000 s | Flights at 10,000 s | Ratio at 10,000 s |
|---|---:|---:|---:|---:|
| Alps | 90,737 | 2.13 | 46,336 | 2.54 |
| Pyrenees | 12,242 | 2.19 | 4,331 | 7.25 |
| Channel Coast | 4,890 | 1.92 | 1,680 | 2.19 |

The falling support matters: differences across lags can include population
selection. The eight-flight minimum is only a display rule. The ellipses describe
centred covariance, not rotational invariance of the entire joint distribution.

## Documents and reproducibility

`review_update.py` verifies the original cleaning definition and source-table
identities, all inherited and updated products, the bounded source changes and
the compiled thesis. [`manuscript-review.json`](manuscript-review.json) identifies
the reviewed 116-page PDF and its exact source files. An error-message line was
wrapped after the focused run: `executed-reporter.py.gz` retains the executed
bytes, and the review verifies equality of the complete Python AST. Independent
viewer changes are included in the reviewed checkout hash but do not enter the
focused PCA calculation.

The thesis was completed before freezing the presentation inputs:

```bash
.venv/bin/python revisions/regional-pca-lags-2026-09-12/review_update.py
uv run --no-project --with pypdf python presentations/prepare_assets.py --pca-update revisions/regional-pca-lags-2026-09-12
.venv/bin/python presentations/render_chapter3_panels.py
.venv/bin/python presentations/render_figures.py
python3 presentations/build.py all --notes
uv run --no-project --with pypdf python presentations/validate.py
```

The immutable focused runner refuses to overwrite a completed record and requires
the preceding baseline outputs. It is not needed to compile the delivered files.
For a future complete numerical rebuild, the canonical Chapter 3 reporter calls
the same exact-lag covariance and figure functions directly. Old development-sample
caches without coordinates require regeneration; full-archive coordinate caches
retain the unchanged measurement contract.

The thesis figure and adjacent table, all three updated slides and their note
pages were visually inspected. Counts and legends remain readable without
covering the ellipses. `audit_delivery.py` verifies the committed source, inherited
and updated results, thesis PDF and complete presentation files against these
records. It performs no remote operation.
