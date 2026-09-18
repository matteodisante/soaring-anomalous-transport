# Altitude-band effective exponents: full 10-10000 s fit

Now integrated into the `esperimenti` volume, section 4.4.4 (page 53),
figure 4.17 (page 55) and table 4.8 (page 54) of the current build. See the
[compiled manuscript review](../altitude-hurst-thesis-2026-09-15/README.md).

User-requested update of the [100-1000 s analysis](../altitude-hurst-2026-09-15/README.md).
The main estimate now fits all **59 requested lags from 10 to 10000 s**, inclusive,
with one unweighted OLS line in log-log space. H_eff is half that line's slope.
It is fitted directly to the full curve, not averaged from the three decade fits.

## Outputs

- [Main curves and full-range fits](figures/altitude_msd_hurst.pdf),
  for both disciplines and available/fixed long-segment controls.
- [Decade sensitivity and flight support](figures/altitude_hurst_sensitivity.pdf).
- `altitude_hurst_estimates.csv`: 16 new full-range fits plus 48 decade fits.
- `altitude_tamsd_curves.csv`: curves, pointwise intervals and flight/site-day support.
- `report.json`, `measurement-source.py.txt`, `figure-manifest.json`: numerical
  results, exact executed reporting source and final PDF/source hashes.

The altitude labels, flight weighting, native-segment support, fixed long-segment
control and bootstrap definition are the same as in the preceding analysis.
Each of the 2000 whole-site-day draws is refitted over all 59 lags; the exponent
interval is the 2.5th-97.5th percentile of those full-range estimates. All 16
full-range fits have 2000 finite replicates and pass the existing support rules.
These remain effective second-moment exponents conditional on this fit range;
curvature and changing flight membership are not included in the bootstrap interval.

## Available-segment results

| Altitude band | Paragliders H_eff [95% CI] | Hang gliders H_eff [95% CI] |
|---|---|---|
| Plains | 0.9579 [0.9554, 0.9603] | 0.9014 [0.8902, 0.9124] |
| Hills | 0.9361 [0.9335, 0.9387] | 0.9083 [0.8988, 0.9168] |
| Low mountains | 0.8750 [0.8739, 0.8761] | 0.8650 [0.8624, 0.8678] |
| High mountains | 0.8831 [0.8822, 0.8841] | 0.8516 [0.8465, 0.8567] |

The fixed long-segment estimates and their intervals are in the lower panels
of the main figure and in the CSV. The original figures and numerical record
remain available at their original paths.

## Validation

The reconstructed means, flight support, pointwise intervals and all 48 decade
fits are identical to the preceding 2000-draw run. All 16 new point estimates
agree with independent NumPy log-log regressions of the parent mean curves;
every full-range fit uses exactly 59 lags with endpoints 10 and 10000 s.
Seventeen numerical tests passed, along with Ruff lint/format checks. Both PDFs
were rendered with Poppler and visually inspected. Final report, renderer and
PDF hashes match the manifest.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
MPLCONFIGDIR=/tmp/soaring-altitude-mpl XDG_CACHE_HOME=/tmp/soaring-altitude-cache \
.venv/bin/python scripts/reporting/ch3_global_transport/generate_altitude_hurst.py \
  --record-dir /tmp/new-altitude-hurst-full-range \
  --out revisions/altitude-hurst-10-10000-2026-09-15/figures \
  --fit-range 10 10000 --resamples 2000
```

The CLI now accepts `--fit-range LOW_S HIGH_S` and defaults to 10-10000 s.
`--render-only` uses the range recorded in the selected report, preserving
the ability to redraw the previous 100-1000 s result.
