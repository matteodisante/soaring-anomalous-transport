# Section 3.2 confidence-band audit — 21 September 2026

The published bands are correctly calculated **pointwise 90% site–day cluster-bootstrap percentile intervals**. No numerical or plotting error was found. Their narrowness reflects both precision under this resampling model and strong visual compression by logarithmic axes. Their actual population coverage is **not** established: changing the cluster definition materially changes estimated uncertainty.

No manuscript, production code, data cache or published figure was changed by this audit.

## Numerical reconstruction

- Verified SHA-256 fingerprints of all five archived inputs; checked fixed-cohort flight identities against the manifest and published membership table.
- Verified site–day keys against cluster IDs, including the separate treatment of missing keys. Recreated every one of the 1000 original draws exactly: each draws 82,669 archive clusters with replacement.
- Independently recalculated all **35 strata × 1000 replicates × 33 lags**, using direct flight-level weights rather than the production cluster-sum function. Maximum relative discrepancy from saved curves: **1.76e-14** (floating-point roundoff).
- Recalculated all MSD percentiles with `[5, 95]` across the 1000 replicates, excluding the observed row. No extra division by `sqrt(N)`, number of origins, clusters, or bootstrap replicates occurs.
- Independently fitted every replicate with `numpy.linalg.lstsq`, preserving the same draw across lags. Published H estimates and interval endpoints agree within **1e-15**. All **20 conditional paired contrasts** also agree; a separate check verified the **8 circuit-by-altitude fits and 12 additional contrasts** in the main report (32 contrasts in total).
- Verified the exported curve/fit CSVs and all eight circuit-by-altitude point/lower/upper arrays from the separate main report.
- Compared bootstrap MSD standard deviations with an independent first-order cluster-variance calculation: ratios range **0.942–1.026** across groups and lags, consistent with Monte Carlo variation and linearization accuracy.
- Ran the conditional transport, fixed transport and cluster-bootstrap test files: **31 tests passed**.

These checks validate the bootstrap reduction from the saved per-flight MSD cache. They do not repeat the earlier raw-trajectory cleaning and coordinate audit.

## Why the published shading is difficult to see

These are intervals for the **ensemble mean MSD**, not the spread of individual flights. Some curves average tens of thousands of flights. All current conditional PDF files match their saved run; an in-memory check of the actual plotting function verified all 20 conditional shaded polygons against the percentile arrays. The circuit-by-altitude figure uses the same correctly scaled band function and its eight input bands were separately verified.

The conditional axes span seven decades, and the solid lines are 1 point wide. At 100 s the open and closed circuit bands are only **0.183 and 0.109 points** high, respectively: the curve can cover nearly all of the shading. All six relevant source figures were rendered and inspected.

**Full interval width** below means `(upper − lower) / observed MSD × 100`, not a one-sided margin:

| Group | Flights | Site–day groups | Width at 100 s | Width at 10000 s |
|---|---:|---:|---:|---:|
| Open circuits | 17,961 | 12,485 | 1.37% | 4.19% |
| Closed circuits | 28,234 | 16,008 | 0.82% | 3.67% |
| Alps | 32,790 | 16,744 | 0.77% | 3.11% |
| Pyrenees | 2,257 | 1,462 | 2.97% | 16.29% |
| Beginners, Plains | 703 | 582 | 5.15% | 9.55% |

The [relative-scale figure](relative_bands.png) displays exactly the published percentiles, normalized by the observed curve. It changes only the display, not the estimator or intervals.

## Sensitivity to the grouping assumption

Recomputed every stratum and all 32 contrasts using **1000 replicates per configuration and two seeds** (20260921, 20260922). Draws always cover the whole eligible archive before restricting to the fixed cohort/stratum. Observed MSDs and H remain unchanged. No empty replicate occurred. Alternative group definitions:

1. All sites on the same calendar day.
2. All sites in a fixed three-day calendar block, anchored at 2000-01-01 (one boundary offset).
3. The existing thesis diagnostic: 50 km UTM cell × launch-altitude class × month of year, pooling all years. This was reused as a sensitivity scenario; it is not a newly validated independence model.

Ratios below are **bootstrap standard errors of H relative to the published site–day scheme**, with ranges across the two seeds:

| Alternative groups | Open circuits | Closed circuits | Alps | Pyrenees |
|---|---:|---:|---:|---:|
| Calendar day | 1.39 | 1.94–1.96 | 1.76–1.81 | 1.06–1.10 |
| Three calendar days | 1.58–1.61 | 2.05–2.10 | 1.87–1.88 | 1.26–1.29 |
| 50 km × altitude × month | 3.27–3.32 | 3.99–4.08 | 4.35–4.42 | 2.16–2.19 |

For example, the open-circuit H interval is **[0.90884, 0.91096]** under site–day sampling and **[0.90647, 0.91341]** under the spatial/altitude/month grouping with the first seed. Closed circuits change from **[0.85474, 0.85644]** to **[0.85189, 0.85865]**.

The 32 paired contrasts retained the same inclusion/exclusion of zero under all three alternatives and both seeds. This is reassuring for those particular comparisons, but does not validate their nominal coverage or exclude other dependence structures. No multiplicity correction is included. This includes the 12 circuit-by-altitude contrasts published through the separate main report.

**Interpretation:** the published bands are correct for the stated bootstrap, but can be optimistic if distinct site–day groups share weather or other influences. Coarser grouping also changes the dependence model; these alternative intervals are not established “true” intervals or formal bounds. Selection into the archive and causal attribution remain outside this audit. The need for approximately independent clusters is discussed in [Cameron and Miller (2015)](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015.pdf).

## Reproduction and files

From the repository root, with the source SSD mounted:

```bash
VECLIB_MAXIMUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python revisions/conditional-bootstrap-audit-2026-09-21/audit.py
VECLIB_MAXIMUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python revisions/conditional-bootstrap-audit-2026-09-21/sensitivity.py
.venv/bin/python revisions/conditional-bootstrap-audit-2026-09-21/check_task_contrasts.py
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python revisions/conditional-bootstrap-audit-2026-09-21/check_rendering.py
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python revisions/conditional-bootstrap-audit-2026-09-21/plot_relative_bands.py
.venv/bin/python -m pytest -q tests/analysis/observables/test_conditional_transport.py tests/analysis/observables/test_fixed_transport.py tests/analysis/stats/test_bootstrap.py
```

`audit.json` records numerical checks and hashes; `band_widths.csv` includes every group's sizes, H intervals, relative MSD widths and variance diagnostic. `sensitivity.csv` and `sensitivity_contrasts.csv` retain every alternative interval and standard-error ratio. `rendering.json` records PDF hashes, percentile-polygon checks and actual displayed band heights. `verified_replicates.npz` is the compact independent reconstruction, not a replacement for source data.
