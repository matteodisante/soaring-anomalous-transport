# Global transport

Chapter 3 measures transport before phase segmentation: displacement moments and
quantiles, a constant-velocity control, geographical anisotropy and velocity memory.
The revised chapter is `thesis/sections/04-global-transport.tex` (printed Chapter 3).
The scientific programme and sequencing are recorded in [the thesis roadmap](../thesis-roadmap.md).

## Current numerical products

The September 2026 revision uses the complete eligible archive, with explicit
weighting and lag-support conventions:

| Product | Source | Scope |
|---|---|---|
| `msd.pdf` | identified `msd_<slug>.npz` from `measure_msd.py` | descriptive launch average and equal-segment time average |
| `kinematic_isotropy_terrain.pdf` | archive regional kinematics cache | paired uncentred E/N second-moment ratios at 10–10,000 s since launch |
| `kinematic_isotropy_terrain_level.pdf`, `kinematic_isotropy_flat_level.pdf` | same regional kinematics cache | equipment contrasts within mountain/coastal and low-relief launch boxes |
| `ch3_scaling.pdf` | `generate_revision_diagnostics.py` | equal-flight V1/V2, local slopes, open/closed tasks, support |
| `ch3_quantiles.pdf`, `ch3_quantile_control.pdf` | same full eligible archive | quantiles; fixed flight, weight and origin controls |
| `ch3_fixed_quantiles.pdf`, `ch3_fixed_exponents.pdf` | all eligible long flights in that archive | fixed common origins, equal flight weights and paired whole-flight intervals |
| `ch3_absolute_laws_*.pdf`, `ch3_squared_laws_*.pdf` | same fixed long-flight cohort | distributions before and after rescaling; squared-law counterparts |
| `ch3_joint_para.pdf`, `ch3_joint_hang.pdf` | same fixed long-flight cohort | signed East–North distributions on shared bins after one scalar rescaling |
| `ch3_models.pdf` | same full eligible archive | pooled moment spectrum and centred Mardia excess |
| `ch3_velocity_memory.pdf` | same full eligible archive | positive coarse VACF on log–log axes, with signed companion panels |
| `ch3_pca.pdf` | same full eligible archive | centred regional displacement covariance, eigenvalue ratio and axis at exactly 10, 100, 1000 and 10,000 s |
| `ch3_duration.pdf`, `ch3_duration_equipment.pdf`, `ch3_duration_composition.pdf` | full archive identified segment TAMSDs | equal-flight duration cohorts, EN strata and fixed class proportions |
| `duration_equipment.tex`, `_table.tex`, `.json` | same archive duration report | slopes, support, cohort counts and mixture controls |
| `ch3_revision.tex`, `.json` | same full eligible archive | generated values, flight IDs, source metadata, support and code provenance |

The complete rebuild regenerates these products from the current verified cleaning
snapshot. Its manifest records source and table identities. Earlier generated products
must not be treated as current merely because their filenames match. See the
[rebuild guide](rebuilding.md).

Regional PCA evaluates the four decade lags directly from the existing 10-s
coordinates. It does not round them onto the geometric lag grid used for the
other diagnostics. All supported, nonoverlapping origins within each segment
are pooled with equal origin weight; increments cannot cross a segment boundary.
All eligible flights contribute at each lag where they have support. The eight-flight
display minimum is not a precision guarantee, and changing flight support can
contribute to changes in the covariance geometry. The regional table uses 1000 s;
the duration-cohort diagnostic retains its separate reference on its own lag grid.
Every supported PCA lag has an ellipse, ratio marker, axis annotation and flight count.

The focused correction and its data/source identities are recorded in
`revisions/regional-pca-lags-2026-09-12/numerical-update.json`. It recomputes only
regional covariances and preserves the completed cleaning and all other Chapter 3
measurements. The original run manifests remain immutable.

The equipment comparison is `kinematic_isotropy_terrain_level.pdf`: beginners (EN A/B)
and experts (EN C/D/CCC) within each named take-off region. These two groups are
equipment-based experience proxies, not independent measurements of individual
pilot skill or wing performance. Experienced pilots can fly A/B wings, and a
group difference includes equipment effects. Tandem/non-certified and unknown classes
are excluded. All kinematic
curves use observed paired component ratios with pointwise 10–90% site/date bootstrap
bands; 30-flight and 10-cluster display minima do not guarantee precision. Legend
counts give minimum and maximum flight support along the displayed curve. Machine-readable
ratios, coverage and counts of contributing flights with missing cluster keys are saved
in `kinematic_isotropy.json`. Missing site/date keys become singleton groups; those bands
cannot account for shared exposure that the metadata do not identify.

A ratio near one describes the balance of two pooled geographic second moments;
it does not establish rotational isotropy or show that individual pilots fly more
isotropically. The site/date bootstrap does not match the equipment groups or remove
weather, task and duration confounding. Regional boxes classify take-off locations,
not terrain or wind exposure along the whole route; the Channel Coast is not a
zero-orography control. Interpret group differences as associations and check for
changes of ordering across regions and elapsed times before proposing a general
pilot-performance explanation.

The low-relief comparison includes Channel Coast, Poitou-Charente and
Champagne-Lorraine. These are latitude/longitude launch boxes, not terrain-model
classifications or samples matched on weather. Use their separate curves to assess
whether a coastal observation generalizes, rather than treating them as equivalent
wind-only environments.

## The 10–10,000 second measurement

The reporter streams the complete cleaned archive, reconstructing flights across
Parquet row-group boundaries. Every retained segment with native cadence at most
10 s and at least two points on the common 10 s grid is admitted. There is no
row-group or flight-count cap, and no longest-segment restriction. This uses all
eligible data; cadence and lag-support exclusions remain explicit. The manifest
records flight IDs, every admitted segment, counts and source identities.

The archive-wide analysis uses all supported flights at each lag. Fixed-population
comparisons are additional controls for changing composition, not a way to make the
archive fit in memory. A short flight contributes at short lags but cannot supply
an unobserved long-lag displacement. The 20,000 s segment criterion also supports
second-order differences at the maximum 10,000 s lag; for ordinary increments it
leaves many common origins. Results conditional on this long-flight cohort are
reported separately from the archive-wide curves.

Coordinates and increment pools are mapped from disk. Bounded process queues use
`--jobs` or `SOARING_MAX_WORKERS` (all available CPUs by default); arrays are reduced one lag at a time. The full
cache is `ch3_revision_full.pkl`, with small summaries and references to the
`ch3-full-para` and `ch3-full-hang` directories, not embedded coordinate arrays.
`--sample` explicitly restores the seeded development subset (24/12 row groups,
at most 40 flights each, longest segment); it must not supply the final full-archive
results. The legacy `--saved-snapshot` command identifies historical sample results.

Fits use actual supported lags from 10 to 10,000 s. The lower end can retain smoothing
influence; the upper end has fewer contributing flights and windows. A fixed cohort of
flights with at least one segment of 20,000 s controls changing flight membership for both V1 and V2.
Its duration selection remains a limitation. Baseline plots are descriptive; paired whole-flight intervals for the fixed
population are conditional on independent flights, as detailed below.

## Estimands and interpretation

- **Archive TAMSD:** average every admissible starting fix within a segment, then give
  each admitted segment equal weight; segments with fewer than eight fixes are omitted.
  Several segments from one flight contribute separately.
  Requested lags are rounded to each segment's native grid; exact values may differ by
  half that grid step. The archive count and percentile band concern segments.
- **V1/V2:** pool admissible origins across all segments within each flight,
  then average equally across flights. Origins never cross a segment boundary. V2 is
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
- **Observed-path closure:** net displacement between first and last retained common-grid
  endpoints divided by the sum of within-segment chord lengths. For a single uninterrupted
  observed path the ratio is at most one. Across separated segments, omitted travel or
  reacquisition offsets can make it larger than one; it is not the closure of a reconstructed
  complete flight. This does not make any increment window cross a gap.
- **Velocity memory:** velocities averaged over 10, 60 and 300 s, centred per segment;
  normalised correlations are averaged over supported segments within each flight,
  then supported flights receive equal weight. Retain signs, require at least
  20 flights and show only separation at least the averaging width and at most
  `h * floor(n_velocity_blocks / 4)`. The mean of normalised correlations differs from
  a normalised covariance pooled over flights.
  A finite observed curve cannot establish non-integrability at infinity.
- **Duration:** combine all eligible segment TAMSDs within each flight using their
  admissible-origin counts, then give flights equal weight. Legend counts are distinct
  flights. Groups are nested. Their amplitude differences do not justify claiming independence
  from total duration; the figure does not measure an ergodic limit.
  These cohorts use the sum of retained segment spans, excluding gaps. The Chapter 2
  preliminary duration distribution instead uses the elapsed time between the first
  and last retained fixes, including gaps; its plotted path length still sums only
  within-segment steps. These two duration definitions must not be interchanged.

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
uv run python scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py --jobs 8 --audit-dir /Volumes/SSD_DISANTE/derived-audit
uv run python scripts/reporting/ch3_global_transport/generate_scaling_schematics.py
uv run python scripts/reporting/checks/check_generated_macros.py
```

The first command accesses the external source snapshot; use its manifest to reproduce
an exact selection. `--reuse` reuses the selected full or development calculation cache only under the reporter's
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
The quantile reporter compares the available pooled sample with (1) fixed flights
having at least one segment lasting 20,000 s, but pooled windows, (2) the same flights with equal flight
weights, and (3) the same flights and every 10-s starting time eligible at the maximum
10,000-s lag. The last convention keeps the identities, origins and weights unchanged
at every lag. Within a flight, each origin has equal weight; each flight then has the
same total weight. These windows overlap and must not be treated as independent.
Shorter segments of the selected flights also contribute wherever they support the
required stencil. The 20,000 s condition is a flight-selection criterion, not a
rule discarding every shorter segment of those flights.

Quantiles use the inverse weighted empirical CDF, without interpolation. Comparison
slopes use identical positive supported lags across all conventions, coordinates and
percentiles. Counts, fixed-flight indexes into the recorded population, origin counts, actual
fit lags and slopes are recorded in `ch3_revision.json`. The selected long flights
are not representative of shorter flights. Persistence of unequal quantile slopes
after these controls is descriptive shape change in this population; nonstationarity,
finite trajectories and uncertainty still preclude a general model-class rejection.

## East, north and radial distribution scaling

The same Chapter 3 reporter now writes `ch3_self_similarity.json`, the
`ch3_fixed_*` quantile figures, `ch3_absolute_laws_*` and `ch3_squared_laws_*`, and
three generated tables plus quantitative macros. The full rebuild calls this
extension in the `transport_full` stage; no second data selection is made.

The calculation holds the long-flight cohort, all eligible 10-s origins and equal
flight weights fixed over 31 lags from 10 to 10,000 s. It fits the four probability
levels separately for absolute east, absolute north and the horizontal norm. A
common slope per quantity is also fitted with a separate intercept per rank.
It equals the mean of the four slopes on the same log-lag grid, and is only a
candidate rescaling exponent. Sensitivity fits use 60–1970 and 210–1970 s.

Four hundred paired whole-flight resamples recompute the quantiles of each
weighted mixture, retaining the same multiplicity across all coordinates and
lags. Pointwise percentile intervals and paired differences are conditional on
independent flights; shared site/day conditions are not modelled. Overlapping
origins are never treated as independent bootstrap units.

Six lag distributions are shown before and after power rescaling. A second
comparison divides each distribution by its own median to remove any single
scale factor, including a non-power scale. The maximum pairwise weighted-ECDF
separation over those six lags measures remaining shape change. It is not an iid
KS test and carries no nominal KS p-value. Positive histograms retain their full
observed support; zero atoms are recorded separately. Squaring the edges preserves
bin masses; the quantiles square, slopes and their intervals double, and the
corresponding ECDF distances remain unchanged.

To extend a completed saved sample while raw cleaning is running:

```bash
uv run python scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py \
  --saved-snapshot /Volumes/SSD_DISANTE/derived-audit/runs/20260910T221820Z-05d36ab4/arrays/ch3_revision_sample.pkl
```

This mode verifies that the parent run completed, records its identity and the
cache hash, and reconstructs paths from every consecutive 10-s increment in the
cache. Full-path counts are checked and the resulting fixed-population quantiles
must agree with the original controls. It reads no partially written source
tables and does not mark a new archive rebuild complete. The extension's report
stores the source contract, provenance and its own analysis hash; an unchanged
measurement can be redrawn without repeating the bootstrap. Its outputs are a
new analysis of the identified saved snapshot, not outputs of the older run.


## Signed joint distribution and scope of the tests

The absolute East, absolute North and radial laws do not identify the joint law.
Even the signed component laws together with the radius are insufficient: the
uniform laws on `{(1,2),(-1,-2)}` and `{(1,-2),(-1,2)}` share all three but have
different dependence. Covariance and Mardia kurtosis are also summaries, not
identifiers of an arbitrary non-Gaussian law.

`ch3_joint_para.pdf` and `ch3_joint_hang.pdf` display the signed bivariate law at
six lags, on the same fixed long flights and common within-segment origins used
for the quantile controls. Each flight has equal total weight. One candidate
scalar exponent (the mean of the twelve rank slopes) rescales both axes; a common
reference length is the radial median near 1000 s adjusted to 1000 s. Geographic
axes remain fixed; no lag-wise centring, rotation or whitening can hide changes.
The 64-by-64 interior grid spans [-6,6] in these units. Explicit overflow cells
retain the tails in the numerical distribution and in all distances; figures
state the mass outside the displayed square. The full joint masses, means,
covariances and pairwise total-variation distances are in `ch3_self_similarity.json`.

This is a descriptive **binned joint-law** comparison. Distance depends on the
fixed resolution; zero does not identify the continuous joint law, and positive
empirical distance alone is not a calibrated rejection. We attach no iid p-value
to overlapping origins. Whole-flight quantile intervals do not supply a null
calibration for this separate statistic. Finer grids, a multivariate two-sample
statistic with cluster-aware calibration, and joint laws over several times would
be required for stronger inference about an underlying process.

The Cramér–Wold characterization concerns all signed linear projections, not only
two coordinates and a norm: [Fraiman, Moreno and Ransford](https://arxiv.org/abs/2206.13612).
Energy distance is an established full multivariate distribution discrepancy under
finite first moments: [Székely and Rizzo (2013)](https://pages.stat.wisc.edu/~wahba/stat860public/pdf4/Energy/JSPI5102.pdf).
Operator self-similarity permits broader directional scaling than a common scalar
exponent: [Didier and Pipiras (2011)](https://arxiv.org/abs/1102.1822).

## Computational reuse

Archive TAMSD component FFT curves are computed once per segment. Their sum supplies
the radial TAMSD, and duration cohorts reuse the same curve and lag-support mask.
This preserves the estimator up to floating-point arithmetic. The fixed-flight
bootstrap computes cumulative counts at sorted block boundaries, then resolves the
exact weighted empirical quantile inside its block; it does not subsample origins
or average flight quantiles. Chosen distribution arrays are backed by disk in full
mode. The velocity diagnostic averages normalized segment correlations within each
flight and then gives flights equal weight, separately at each supported lag.

The full fixed-population bootstrap currently processes lags serially. The bounded
worker queues used by archive collection and segment FFTs do not make every phase
use every core. The disk-backed design makes the full calculation feasible on the
8 GiB Mac, but the exact bootstrap and empirical-CDF comparisons remain substantial
costs. Performance claims should use the recorded full-run timings, not the smaller
synthetic benchmark or the former development subset.

## Reviewed full-archive results (12 September 2026)

The completed `transport_full` measurement uses 155,085 eligible paraglider and
6,060 eligible hang-glider flights from the cleaned archive of 156,406 and 6,094
retained flights. The additional fixed control contains 14,360 and 563 long
flights, with 21,739,115 and 791,712 common origins. Eligibility and fixed-population
selection are different conditions; the smaller control does not replace the
archive-wide measurement. Exact report identities and independent checks are in
`revisions/vertical-gap-split-2026-09-11/chapter3-results-audit.json`.

North-minus-east rank-slope contrasts are positive at all four ranks in both
disciplines, with paired pointwise 95% whole-flight intervals excluding zero.
These intervals assume independent flights; they are not simultaneous or site/day
cluster intervals. Radial 90th-to-25th percentile ratios first rise, then fall to
post-peak minima at 2,410 s and 1,970 s, then rise again. A negative full-range
slope contrast therefore does not describe monotonic narrowing.

The signed joint laws retain visible evolution after the candidate scalar
rescaling. Their maximum pairwise binned total-variation distances are 0.370 and
0.441; the 10-s versus 10,000-s distances are 0.370 and 0.403. Tail overflow is
zero to numerical precision. These values neither calibrate a rejection test
nor rank the disciplines by the strength of a physical mechanism.

Very small positive histogram bins can have large density heights while carrying
little probability: in every displayed marginal law the mass below 1 mm is less
than 0.003%, including a conservative allowance for a straddling bin and zero
atoms. Such bins do not establish physical displacement resolution. Under the
square transformation, a finite nonzero magnitude-density limit at zero produces
a density proportional to the inverse square root near zero; that shape is a
Jacobian effect, not by itself a heavy upper tail.

For reuse or slide preparation, take the array directory from the identified run's
manifest. The general audit directory can contain historical arrays. A completed
producer, matching input identities and the measurement contract must agree before
results are combined. The legacy `--saved-snapshot` path describes sample caches;
full mode uses its disk-backed stores through `--reuse`.
