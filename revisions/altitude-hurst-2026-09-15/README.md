# Altitude-band TA-MSD and effective scaling uncertainty

The thesis already contains the altitude comparison in section 3.4, figure 3.18
(printed page 75 in the current build). This extension adds uncertainty for the
fitted scaling exponents and standalone figures. It does not modify the thesis
or the completed parent measurement.

## Figures and data

- [TA-MSD curves with effective exponents](../../output/pdf/altitude_msd_hurst.pdf):
  both disciplines, available segments and fixed long segments. Legends give
  H_eff and its marginal 95% interval for the requested 100-1000 s range.
- [Lag-range and population sensitivity](../../output/pdf/altitude_hurst_sensitivity.pdf):
  all three fitted decades, both controls, and contributing flight counts.
- `altitude_hurst_estimates.csv`: all 48 fits, intervals, bootstrap standard
  errors, actual fitted limits, flight/cluster support, and validity status.
- `altitude_tamsd_curves.csv`: full curves, pointwise intervals and support.
- `report.json`: complete numerical record, estimator contract and source hashes.
- `figure-manifest.json`: current renderer and final PDF hashes.

The groups use the cleaned trajectory's initial GNSS altitude `alt0`:
Plains below 300 m, Hills from 300 to below 800 m, Low mountains from 800 to
below 1500 m, and High mountains at least 1500 m. They pool all eligible
regions and do not classify instantaneous altitude or measured terrain relief.

## Estimator and interpretation

Within each flight, pool segment TA-MSDs using their admissible displacement
origin counts; then give each contributing flight equal weight. No displacement
crosses a segment boundary. The fixed control retains the same segments
supporting the requested 10000 s maximum at every lag. This selects long
continuous records; origins and within-flight segment weights still vary.

Fit `log M(tau) = a + alpha log(tau)` by unweighted OLS on the requested native
lag grid and define **H_eff = alpha / 2**. The main range 100-1000 s uses actual
requested lags 107-931 s. The other two ranges use 10-95 s and 1049-10000 s.
These are range-dependent moment exponents; they do not establish self-similarity,
stationary increments, fractional Brownian motion or an intrinsic Hurst parameter.

Resample whole site-day clusters 2000 times within each altitude band, preserving
all flights in each selected cluster. Each draw is shared across all lags and
both controls. Recompute each mean and refit on the same observed lag mask.
The 2.5th and 97.5th percentiles of the resulting H_eff draws form the interval.
The sample standard deviation of those draws is also stored as bootstrap SE.
Base seed is 20260915, incremented by the altitude-band index.

Require at least eight flights per selected lag, three fitted lags, twenty
contributing clusters at every fitted lag and 90% complete finite replicates
for an interval. All 48 fits satisfy these rules and have 2000 finite draws.
These operational thresholds do not prove nominal frequentist coverage.

This procedure retains the observed dependence within a site-day and across
lags. It assumes independent resampling units; repeated pilots or weather
shared across site-days can create dependence that it does not capture.
The intervals are marginal, conditional on the estimator, population and fit
window. They exclude cleaning, altitude-label, model and fit-window uncertainty.
They are not simultaneous intervals or tests of differences between bands.
Testing band differences would require common draws over their union of clusters.

The ordinary regression residual standard error is not the sampling error of
H_eff: different TA-MSD lags share trajectory information. Fitting the two
pointwise ribbon edges also fails to recover their joint sampling distribution.
For the correlation issue see [Zhang et al. (2018)](https://arxiv.org/abs/1805.06295);
their process-specific asymptotic estimator is not applied here. The whole-cluster
resampling principle and independence assumptions are discussed by
[Cameron and Miller (2015)](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015.pdf).

## Main results: available segments, requested 100-1000 s

| Initial-altitude group | Paragliders H_eff [95% CI] | Hang gliders H_eff [95% CI] |
|---|---|---|
| Plains | 0.9308 [0.9294, 0.9322] | 0.8846 [0.8747, 0.8937] |
| Hills | 0.9046 [0.9031, 0.9061] | 0.8741 [0.8659, 0.8820] |
| Low mountains | 0.8690 [0.8682, 0.8697] | 0.8531 [0.8509, 0.8554] |
| High mountains | 0.8711 [0.8703, 0.8720] | 0.8347 [0.8311, 0.8382] |

The small statistical intervals should be read alongside the much larger
sensitivity to the population and lag range. For example, at 1000-10000 s,
paraglider Plains/Hills change from H_eff = 1.094/1.104 on available segments
to 0.984/0.966 on fixed long segments. The apparent above-quadratic growth in
the available means does not persist in the same way under fixed membership.
The geographical composition also differs strongly between altitude groups;
these contrasts do not identify a causal altitude effect.

## Provenance and checks

Inputs are the SHA-256 identified local native-segment arrays and the immutable
`revisions/grouped-tamsd-2026-09-12/report.json.gz` flight membership. Reconstruction
checks every altitude-band/control/lag mean and flight count, native support,
fixed flight identities and all inherited descriptive slopes. The SSD was
connected during the work: all four catalog/flight-metadata files match the
parent SHA-256 identities (`ssd-verification.json`).

`measurement-source.py.txt` preserves the exact reporting script whose hash is
in the numerical report. Subsequent renderer-only changes corrected panel titles,
legend spacing and caption layout and clarified the actual lag/segment support;
the numerical code and report are unchanged. The final renderer hash is in
`figure-manifest.json`.

Validation: 30 tests passed across the new scaling tests, existing grouped TA-MSD
tests and palette tests; Ruff lint and format checks passed. Both final PDFs were
rendered with Poppler and visually inspected for labels, overlap and clipping.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
MPLCONFIGDIR=/tmp/soaring-altitude-mpl XDG_CACHE_HOME=/tmp/soaring-altitude-cache \
.venv/bin/python scripts/reporting/ch3_global_transport/generate_altitude_hurst.py \
  --record-dir /tmp/new-altitude-hurst-run --resamples 2000 --fit-range 100 1000
```

Default inputs point to the preserved local arrays and parent report, so an SSD
is not required to reproduce this extension. Override `--audit-dir` and
`--parent` for identical copies elsewhere. Use `--out` to choose another figure
directory. To redraw without recalculation:

```bash
MPLCONFIGDIR=/tmp/soaring-altitude-mpl XDG_CACHE_HOME=/tmp/soaring-altitude-cache \
.venv/bin/python scripts/reporting/ch3_global_transport/generate_altitude_hurst.py \
  --record-dir revisions/altitude-hurst-2026-09-15 --render-only
```
