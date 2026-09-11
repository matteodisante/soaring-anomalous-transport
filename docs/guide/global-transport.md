# Global transport

Chapter 3 measures transport before phase segmentation: displacement moments and
quantiles, a constant-velocity control, geographical anisotropy and velocity memory.
The revised chapter is `thesis/sections/04-global-transport.tex` (printed Chapter 3).
The scientific programme and sequencing are recorded in [the thesis roadmap](../thesis-roadmap.md).

## Current numerical products

The September 2026 revision distinguishes archive estimates from a bounded diagnostic subset:

| Product | Source | Scope |
|---|---|---|
| `msd.pdf` | archive `msd_curve.csv` and `generate_msd_figure.py` | descriptive launch average and equal-segment time average |
| `kinematic_isotropy_terrain.pdf` | archive regional kinematics cache | paired uncentred E/N second-moment ratios at 10–10,000 s since launch |
| `ch3_scaling.pdf` | `generate_revision_diagnostics.py` | equal-flight V1/V2, local slopes, open/closed tasks, support |
| `ch3_quantiles.pdf`, `ch3_quantile_control.pdf` | same fresh subset | quantiles; fixed flight, weight and origin controls |
| `ch3_models.pdf` | same fresh subset | pooled moment spectrum and centred Mardia excess |
| `ch3_velocity_memory.pdf` | same fresh subset | positive coarse VACF on log–log axes, with signed companion panels |
| `ch3_pca.pdf` | same fresh subset | centred regional displacement covariance, eigenvalue ratio and axis |
| `ch3_duration.pdf`, `ch3_duration_equipment.pdf`, `ch3_duration_composition.pdf` | full archive identified segment TAMSDs | equal-flight duration cohorts, EN strata and fixed class proportions |
| `duration_equipment.tex`, `_table.tex`, `.json` | same archive duration report | slopes, support, cohort counts and mixture controls |
| `ch3_revision.tex`, `.json` | same fresh subset | generated values, flight IDs, source metadata, support and code provenance |

The complete rebuild regenerates these products from the current verified cleaning
snapshot. Its manifest records source and table identities. Earlier generated products
must not be treated as current merely because their filenames match. See the
[rebuild guide](rebuilding.md).

The equipment comparison is `kinematic_isotropy_terrain_level.pdf`: beginners (EN A/B)
and experts (EN C/D/CCC) within each named take-off region. These two groups are
operational proxies based on the experience required by the wing, not independent
measurements of individual pilot skill. Experienced pilots can fly A/B wings, and a
group difference includes equipment effects. Tandem/non-certified and unknown classes
are excluded. All kinematic
curves use observed paired component ratios with pointwise 10–90% site/date bootstrap
bands; 30-flight and 10-cluster display minima do not guarantee precision. Legend
counts give minimum and maximum flight support along the displayed curve. Machine-readable
ratios, coverage and counts of contributing flights with missing cluster keys are saved
in `kinematic_isotropy.json`. Missing site/date keys become singleton groups; those bands
cannot account for shared exposure that the metadata do not identify.

## The 10–10,000 second measurement

The new reporter reads 24 seeded paraglider row groups and 12 hang-glider groups,
selecting at most 40 complete flights per group and their longest continuous segments.
It admits native cadence at most 10 s and places positions on a 10 s grid. Row-group
boundary exclusion, caps and longest-segment selection can alter the population. It is
an exploratory subset, not a probability-weighted archive estimate. The manifest records
the exact selection and source metadata.

Fits use actual supported lags from 10 to 10,000 s. The lower end can retain smoothing
influence; the upper end has fewer contributing flights and windows. A fixed cohort of
segments at least 20,000 s long controls changing flight membership for both V1 and V2.
Its duration selection remains a limitation. No calibrated confidence intervals are
claimed for the new subset plots.

## Estimands and interpretation

- **Archive TAMSD:** average every admissible starting fix within a segment, then give
  each admitted segment equal weight; segments with fewer than eight fixes are omitted.
  Several segments from one flight contribute separately.
  Requested lags are rounded to each segment's native grid; exact values may differ by
  half that grid step. The archive count and percentile band concern segments.
- **V1/V2:** average within each selected flight, then equally across flights. V2 is
  exactly invariant to constant velocity. Under finite-variance stationary-increment
  self-similarity with positive variance scale and `0 < H < 1`, it scales as `tau^(2H)`.
  At `H = 1` its prefactor vanishes, leaving no logarithmic slope to fit. A generic smooth
  curved trajectory does not satisfy that interpretation. Differences between fitted exponents are not additive
  drift contributions.
- **Quantiles and moments:** pool non-overlapping plain-increment windows, weighting
  longer segments by their window count. This differs from equal-flight V1. Under a
  common scale family, every quantile exponent agrees and quantile ratios remain fixed.
  The exponent ordering must be checked against the selected fit interval; it is not assumed in advance.
- **Mardia excess:** centre the vectors and use their full covariance. Nonzero excess
  challenges a single Gaussian law but may arise from conditional Gaussian mixtures.
  A trace-based mixture subtraction is not a within-flight kurtosis identity.
- **Archive kinematics:** position, velocity and acceleration curves use raw component
  second moments, not variances: `E[u^2] = Var(u) + E[u]^2`. All use elapsed time since
  launch, not within-flight lag. Differentiation does not separate wind from terrain.
- **Regional PCA:** a rotation does not change radial distances, remove wind or eliminate
  temporal dependence. Equal covariance eigenvalues alone do not establish isotropy.
  Whitening changes the physical metric and is only a diagnostic transformation.
- **Velocity memory:** velocities averaged over 10, 60 and 300 s, centred per segment;
  normalised segment correlations are equally averaged. Retain signs, require at least
  20 flights and show only separation at least the averaging width and at most
  `h * floor(n_velocity_blocks / 4)`. The mean of normalised correlations differs from
  a normalised covariance pooled over flights.
  A finite observed curve cannot establish non-integrability at infinity.
- **Duration:** combine all eligible segment TAMSDs within each flight using their
  admissible-origin counts, then give flights equal weight. Legend counts are distinct
  flights. Groups are nested. Their amplitude differences do not justify claiming independence
  from total duration; the figure does not measure an ergodic limit.

## Model comparison

The chapter confronts explicit predictions of homogeneous Brownian motion, constant
drift plus Brownian motion, homogeneous fractional Brownian motion, exponential velocity
persistence and the standard unbiased renewal Lévy walk in its superdiffusive regime.
For the latter, with duration-density tail `t^(-1-beta)` and `1<beta<2`, the asymptotic
moment spectrum has branches `q/beta` below `q=beta` and `q+1-beta` above it.
A near-linear empirical spectrum challenges that benchmark, not every Lévy-walk variant.
Candidate-specific finite-record simulations remain necessary for formal rejection.

## Reproduction

```bash
uv run python scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py --audit-dir /Volumes/SSD_DISANTE/derived-audit
uv run python scripts/reporting/ch3_global_transport/generate_scaling_schematics.py
uv run python scripts/reporting/checks/check_generated_macros.py
```

The first command accesses the external source snapshot; use its manifest to reproduce
an exact selection. `--reuse` reuses the subset calculation cache only under the reporter's
source and estimator checks and recalculates summaries and figures. Its versioned
cache now fingerprints fixes, metadata, task inputs, selected sampling parameters,
measurement code, lags, moments and averaging widths. A source or estimator change
requires rerunning without `--reuse`; changes confined to rendering do not. The second command generates
analytical schematics, not synthetic flight-data evidence.

Additional current figures can be redrawn from retained caches with:

```bash
uv run python scripts/reporting/ch3_global_transport/generate_msd_figure.py --redraw
uv run python scripts/reporting/ch3_global_transport/generate_kinematic_isotropy_figure.py --audit-dir /Volumes/SSD_DISANTE/derived-audit --terrain-only
```

These redraws do not update source trajectories or recompute the archive MSD. The legacy
FFT MSD now subtracts the coordinate origin before evaluating squared terms and sets
zero lag exactly to zero; each new archive measurement incorporates this numerical fix.
Its estimator remains an equal-segment average.

The former duplicate variation, shape and propagator reporting paths have been retired.
The current wide-range reporter reads task declarations directly from the catalogue;
it does not require an obsolete observable cache. Reusable estimators and their
regression tests remain in the library. The current decoder provenance is specified
in the [phase guide](flight-phase-segmentation.md).

## Duration and equipment controls

`measure_msd.py` writes a one-to-one `msd_segments_<slug>.parquet` identity table for
the stored segment TAMSD rows. `generate_duration_equipment.py` combines segment
curves with their admissible-origin counts within each flight, then gives contributing
flights equal weight. Eligible segments have at least eight fixes and native cadence
at most 10 s; retained
flight duration sums all cleaned segment spans and excludes acquisition gaps.

All-duration curves cover supported lags from 10 to 10,000 s. Nested 1, 2 and 4 hour
cohorts stop at half their threshold, avoiding the part where the reference population
is forced to become the same by lag eligibility. The two experience proxies are
beginners (EN A/B) and experts (EN C/D/CCC), using the same mapping and colours as
the anisotropy figures. Neither label is an individually measured skill category. Every
curve requires 30 flights per lag, with flight counts beside its legend label.

Unconditional equipment slopes use a common supported range within 10–10,000 s.
The eight group/duration cells use a common range ending no later than 1,800 s;
these secondary slopes cannot be compared as if fitted over the full main interval.
The JSON and TeX report the actual lag endpoints and logarithmic residuals. These are
descriptive fits, without calibrated sampling confidence intervals.

Fixed composition uses the all-duration proportions of the two experience proxies at
every lag and duration threshold. Both adjusted and unadjusted ratios exclude unknown
or other equipment. The comparison can describe a mixture contribution, but cannot
identify pilot skill, weather effects or independence from duration.

## Fixed-population quantiles

All percentiles at a given lag refer to one distribution. They are not classes of
flights, and a flight can change its rank without changing the sampling population.
The quantile reporter compares the available pooled sample with (1) fixed segments
lasting at least 20,000 s but pooled windows, (2) the same flights with equal flight
weights, and (3) the same flights and every 10-s starting time eligible at the maximum
10,000-s lag. The last convention keeps the identities, origins and weights unchanged
at every lag. Within a flight, each origin has equal weight; each flight then has the
same total weight. These windows overlap and must not be treated as independent.

Quantiles use the inverse weighted empirical CDF, without interpolation. Comparison
slopes use identical positive supported lags across all conventions, coordinates and
percentiles. Counts, fixed-flight indexes into the saved sample, origin counts, actual
fit lags and slopes are recorded in `ch3_revision.json`. The selected long flights
are not representative of shorter flights. Persistence of unequal quantile slopes
after these controls is descriptive shape change in this population; nonstationarity,
finite trajectories and uncertainty still preclude a general model-class rejection.
