# Paraglider altitude scaling, split by declared circuit type

This revision replaces the exponent comparison in thesis Section 3.4.4 with
**paragliders only**, crossing the four initial-GNSS-altitude bands with declared
open and closed circuits. The fit remains **10–10000 s**, using all 59 requested
lags and 2000 site-day bootstrap draws within each circuit–altitude stratum.

| Content | Thesis reference | Printed page | PDF page position |
|---|---|---:|---:|
| Definitions and uncertainty method | Section 3.4.4 | 76 | 80 |
| MSD curves, fitted slopes and intervals | Figure 3.20 | 77 | 81 |
| Estimates, intervals and flight counts | Table 3.9 | 78 | 82 |

## Population and estimates

The verified FFVL catalogue supplies the declared task class: `Dist libre` and
`Dist 1/2/3 pts` are open; triangles, quadrilaterals and out-and-return tasks are
closed. This classification describes the declaration; it does not establish
geometrical closure of each retained trajectory segment.

There are **67003 open** and **87807 closed** eligible flights. The remaining
**275** have other declarations (hike-and-fly categories) and are excluded from
this comparison. All eligible flight IDs have catalogue rows. No hang-glider
arrays are loaded by this calculation.

For the available-segment means, the effective exponent is half the slope of
the unweighted log–log regression. Brackets give marginal 95% bootstrap intervals:

| Initial altitude band | Open circuits | Closed circuits |
|---|---|---|
| Plains, below 300 m | 0.9619 [0.9597, 0.9641] | 0.8363 [0.8258, 0.8448] |
| Hills, 300–<800 m | 0.9522 [0.9500, 0.9544] | 0.8301 [0.8269, 0.8332] |
| Low mountains, 800–<1500 m | 0.8995 [0.8979, 0.9011] | 0.8588 [0.8575, 0.8601] |
| High mountains, at least 1500 m | 0.8955 [0.8942, 0.8967] | 0.8758 [0.8747, 0.8770] |

The figure and table also include the fixed-long-segment control. Closed
circuits in Plains have only **24 flights in 24 site-day clusters** supporting
10000 s; their fixed-population estimate is 0.8933 [0.8761, 0.9054]. Flight
selection therefore matters when interpreting the altitude ordering.

These are effective moment-scaling exponents. The intervals describe sampling
uncertainty under independent site-day clusters; they omit fit-window, model,
cleaning and altitude-label uncertainty. Independently resampled strata give
marginal intervals, not a bootstrap test of open/closed or altitude contrasts.

## Records and verification

- `report.json` contains means, support, cluster counts, membership hashes,
  full-range and decade fits, exclusions, input hashes and executed-source hashes.
- `altitude_hurst_estimates.csv` contains 64 fits: two circuit classes, four
  altitude bands, two population controls and four fitting intervals. Every fit
  has 2000 finite bootstrap draws; all full-range fits use all 59 lags.
- `figures/altitude_msd_hurst.pdf` is byte-identical to the thesis figure.
  `figures/altitude_hurst_sensitivity.pdf` shows the range sensitivity.
- `measurement-source.py.txt` preserves the executed calculation;
  `renderer-source.py.txt` preserves the final table and figure renderer.
- `review_delivery.py` independently joins raw catalogue labels, checks every
  mean/support cell and recomputes the 16 full-range slopes. It verifies input
  identities, the current paraglider cleaning snapshot, table entries, final
  PDF identity and thesis locations. It does not claim a fresh full-byte scan
  of cleaned trajectory tables.
- `manuscript-review.json` records the completed audit. All 103 other generated
  manuscript products match the parent review; the four replaced products and
  prior edited sources are preserved in `before/`.

The 33 numerical and task-classification tests passed, as did Ruff checks. The
142-page PDF compiled without overfull boxes, unresolved references or LaTeX
warnings. Printed pages 76–78 and both standalone figures were rendered and
visually inspected. The provenance index retains its two inherited missing-header
warnings for `ch3_temporal_scaling_bounds.tex` and
`ch3_temporal_scaling_population.tex`; those products are unchanged.

## Reproduce

To redraw the completed result and rebuild the thesis without recomputing:

```bash
MPLCONFIGDIR=/tmp/soaring-altitude-mpl XDG_CACHE_HOME=/tmp/soaring-altitude-cache \
.venv/bin/python scripts/reporting/ch3_global_transport/generate_altitude_hurst.py \
  --record-dir revisions/altitude-hurst-open-closed-2026-09-15 \
  --out revisions/altitude-hurst-open-closed-2026-09-15/figures \
  --thesis-out thesis/generated --render-only
bash scripts/build_docs.sh thesis
```

For a fresh numerical run, use a new record directory with the verified SSD
catalogue mounted (or pass a byte-identical copy through `--catalog`):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
MPLCONFIGDIR=/tmp/soaring-altitude-mpl XDG_CACHE_HOME=/tmp/soaring-altitude-cache \
.venv/bin/python scripts/reporting/ch3_global_transport/generate_altitude_hurst.py \
  --record-dir revisions/altitude-hurst-open-closed-new-run \
  --out revisions/altitude-hurst-open-closed-new-run/figures \
  --fit-range 10 10000 --resamples 2000 --seed 20260915
```

The defaults select the September 12 grouping report and its verified local
paraglider arrays. Completed measurement and review records are immutable;
later changes require a fresh review record.
