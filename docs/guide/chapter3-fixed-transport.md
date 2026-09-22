# Chapter 3: fixed-cohort transport

The current thesis analysis is independent of the historical experiments pipeline.
The numerical contract is in `revisions/msd-fixed-population-2026-09-17/PIANO.md`.
The published run is on SSD:

```
/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917
```

## Change a figure without measuring again

Edit colours, markers or layout in
`scripts/tesi/ch03_fixed_transport/render_ch3_fixed.py`, then run from the repo:

```bash
uv run python scripts/tesi/ch03_fixed_transport/run_ch3_fixed.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 --redraw
cd thesis
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error esperimenti.tex
```

Redraw reads **only `report.json`**, writes vector PDFs and numerical TeX fragments
under `figures/`, and copies them into `thesis/generated/`. It does not read coordinates,
recompute quantiles or rerun the bootstrap. A copy of the report is versioned as
`thesis/generated/ch3_transport_report.json`; it also suffices for an offline redraw
when placed as `report.json` in a separate output directory. The renderer refuses
reports not marked complete.

To update only fits and the general local-slope estimates from the already saved
MSD bootstrap curves, without reading trajectories or drawing a new bootstrap:

```bash
.venv/bin/python scripts/tesi/ch03_fixed_transport/summarize_ch3_fixed.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --refresh-fits-only
```

Then use the redraw command above. This refresh also verifies that the saved MSD
point estimates and bootstrap count agree with the report being extended.

## Reproduce measurements

Use a fresh output directory after changing cleaning, inputs or the statistical
contract. The command below creates a common coordinate store from the cleaned
Parquet archive, verifies it, measures both disciplines, reduces and renders:

```bash
VECLIB_MAXIMUM_THREADS=2 uv run python \
  scripts/tesi/ch03_fixed_transport/run_ch3_fixed.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-NEW
```

For the published run, coordinate collection was avoided by reusing the protected
PCA coordinate store. Every coordinate was then reconstructed from current cleaned
fixes and checked for exact agreement (maximum error: zero). The equivalent command is:

```bash
VECLIB_MAXIMUM_THREADS=2 uv run python \
  scripts/tesi/ch03_fixed_transport/run_ch3_fixed.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --reuse-coordinates /Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1/arrays
```

Completed lag files are reused only after checking their cohort fingerprint and
bootstrap dimensions. Input timestamps and sizes must still match the successful
full coordinate audit. A changed analysis convention requires a fresh run directory;
resume is intended for the same calculation interrupted between lag files.
The historical `scripts/pipeline/rebuild_thesis.py` graph remains available for the experiments
and earlier reports; this dedicated command is the entry point for the new Chapter 3.

Stages can also be run separately:

1. `prepare_ch3_native.py --out RUN --discipline para|hang`: native 1--9 s TA-MSD,
   origin-distance curves, counts of actual/interpolated grid fixes.
2. `audit_ch3_inputs.py --data RUN --coordinates STORE --discipline para|hang`:
   full pointwise coordinate/segment comparison and input fingerprints.
3. `measure_ch3_fixed.py --out RUN --coordinates STORE --discipline para|hang`:
   manifests, common bootstrap, FFT MSD, exact weighted quantiles and moments.
4. `summarize_ch3_fixed.py --data RUN`: validate identities and produce the compact report.
5. `render_ch3_fixed.py --data RUN --publish thesis/generated`: redraw and numerical prose.

`measure_ch3_fixed.py --stage scaling --lags ...` allows disjoint lag lists to run
independently, with the same previously prepared bootstrap. Avoid overlapping lists.
The default single-process run keeps memory bounded; two processes were used to finish
the published paraglider lags. Each process retains at most one scratch increment file.

## Statistical contract

- Main cohort: actual segment grid duration at least 12500 s; fixed segment identities.
  Shorter cohorts admit segments supporting maximum lags 100 or 1000 s under the same
  `tau_max <= 0.8 T` rule. Every valid overlapping within-segment origin is used.
- One total weight per flight; each flight's mass is divided among its origins at that
  lag. The same measure supplies MSD, quantiles, moments and signed-component kurtosis.
- The 33 common lags span 10--10000 s. Quantiles invert the weighted empirical CDF
  exactly. Coarse bins accelerate rank searches; they do not approximate the quantiles.
- Bootstrap: 1000 draws of site--day clusters, seed 20260917. All flights in a drawn
  cluster remain together. Draws are paired across lag, quantity, cohort and task class.
  Percentiles 5 and 95 are nominal 90% **pointwise** intervals. The general empirical
  ensemble instead shows the **across-flight scatter**, with mean and median.
  Descriptive general-curve bands are omitted below 20 contributing groups; tail
  points remain visible and their support is reported.
- All global fits use equal weight per evaluated log-lag. MSD exponent is half the
  fitted slope; quantile exponent is the fitted slope; moment spectrum is zeta(q).
  Three decade fits reuse the main cohort, never reselect it.
  Figure 3.1's descriptive available-population fit uses 10--30000 s (48 evaluated
  lags, ending at 28440 s); its origin-distance panels have no global fit.
  The main fixed-cohort fit remains 10--10000 s.
- Figure 3.3 compares all three cohorts' H on 10--100 s and the two longer cohorts
  on 10--1000 s. Differences use paired bootstrap draws; their intervals distinguish
  a resolved selection effect from overlap of separate confidence intervals.
- Local slopes use a +/-0.25-decade window. Only for the general curves, sparse
  interior windows expand to the three nearest log-lags, with at least two measured
  lags on each side of the centre. This fills the estimate at 20 s using the existing
  MSD values at 10, 20 and 30 s. Endpoints and fixed-cohort slopes are unchanged.
- `R^2 = E^2 + N^2`, agreement with FFT MSD, flight/segment identities and the equality
  of quantile-ratio slope and slope difference are checked before publication.

## Cell, altitude and month-of-year bootstrap

The current requested grouping assigns **each flight by its initial position** to
one fixed 50 x 50 km metric cell, then crosses that cell with its initial-altitude
class and **month of the year, pooling all years**. July 2005 and July 2020 share a
group when cell and altitude class agree. Site names and distances between launch
sites do not enter. Every main-cohort flight remains in the analysis.

The globally defined grid uses WGS84 UTM coordinates within regular six-degree
longitude zones and hemispheres. A cell has key `(EPSG, floor(E/50000), floor(N/50000))`,
origin `(0,0)` and half-open boundaries. Squares are clipped to their zone and
hemisphere. Sizes are in projected metres (small UTM ground-scale distortion),
not degrees or Web Mercator distances. This covers all archived flight origins,
including those outside France; invalid coordinates or positions outside the UTM
latitude domain fail explicitly. See the [PROJ UTM definition](https://proj.org/en/stable/operations/projections/utm.html).

The terrain proxy retains the chapter's initial-altitude thresholds: Plains below
300 m, Hills from 300 to 800 m, Low mountains from 800 to 1500 m, High mountains
from 1500 m upward. It is not a DEM-derived description of the full flight path.

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache VECLIB_MAXIMUM_THREADS=2 \
  .venv/bin/python scripts/tesi/ch03_fixed_transport/check_grid_bootstrap.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --out revisions/bootstrap-reliability-2026-09-18/run-grid \
  --publish thesis/generated
```

The check validates the original cache identities and reconstructs its site-day
bootstrap before changing labels. It compares the MSD at 100, 1000 and 10000 s
and H fitted over 10–10000 s. Each partition has 1000 draws, common to all lags,
with two seeds. Group sampling uses occupied archive groups followed by restriction
to the fixed cohort, preserving the baseline convention and the equal-flight mean.
Missing dates/classes remain singleton archive units; any in the main cohort cause
failure. No flight is dropped to improve group sizes.

Sensitivity configurations use 10, 25 and 50 km cells and translations of half a
cell along either/both axes. **No cell exceeds 50 km per side.** Separate checks
merge 2 or 3 adjacent months with each possible cyclic boundary offset, or pool
altitude classes within the same 50 km cell and calendar month. These alternatives
challenge the baseline assumptions; the baseline always keeps the four classes
and twelve months separate. The figure's denominators are the median baseline SEs
across the two seeds, not the original site-day SEs. Its bars are ranges across
partitions/seeds, not confidence intervals. SE need not increase monotonically
with block size, particularly with uneven, heterogeneous groups.

Portable outputs are `thesis/generated/ch3_transport_grid_bootstrap*`:

- `.json`, `.csv`: complete statistics, percentile intervals, support, configurations
  and provenance. These are a validation run; other chapter bands are not rerun.
- `.pdf`, `_support.tex`, `_values.tex`: figure, composition table and numeric macros.
- `_grid.json`, `_cells.csv`: reusable grid definition and the 477 occupied archive
  cells, with EPSG identifiers and projected bounds. The rule defines the entire
  territory independently of these observed cells; future flights use the same rule.

The separate run directory retains `{para,hang}-membership.parquet` (one row per
eligible flight and its new group), `*-groups.csv`, canonical `*-cluster-draws.npy`
and complete `*-replicates.npz`. Cluster labels are local to each discipline;
cell identities and the geometric grid are shared. Group size-balance indices are
not estimates of the number of independent groups. A larger group or fewer
singletons is not by itself evidence of independence.

Offline redraw needs only `OUT/report.json`:

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python \
  scripts/tesi/ch03_fixed_transport/check_grid_bootstrap.py \
  --out OUT --redraw --publish thesis/generated
```

The earlier all-sites calendar blocking and daily correlograms below remain
reproducible historical diagnostics. Their chronological blocks differ from the
new groups, which pool the same month across years.

## Earlier calendar-block check

The supplementary blocking check reuses `flight-msd.npy`, `flights.parquet`,
`msd.npz`, `cluster-draws.npy`, `cohort-10000.json`, and the published `report.json`.
It checks flight/manifest identities and reconstructs **every baseline replicate**
before changing the resampling unit. It never reads trajectories or changes the
published run. Use a separate local output directory:

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache VECLIB_MAXIMUM_THREADS=2 \
  .venv/bin/python scripts/tesi/ch03_fixed_transport/check_bootstrap_reliability.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --out revisions/bootstrap-reliability-2026-09-18/run-64 \
  --block-days 1 2 4 8 16 32 64 \
  --publish thesis/generated
```

The default exploration stops at 16 days; the published diagnostic extends to 64
because no common plateau appeared. Blocks are non-overlapping intervals of real
calendar dates containing **all sites**. Their boundaries are anchored to
2000-01-01 and shifted by `0`, `floor(L/3)`, and `floor(2L/3)` days (unique shifts
only). Empty periods are not sampled, but dates are never compressed to an index
of flight days. Sampling occupied blocks of the eligible archive and then
restricting to the fixed cohort follows the baseline sampling-frame convention.
Missing cohort dates cause an error; no flight is silently dropped. Invalid dates
outside the cohort remain singleton archive units and their count is recorded.

Each partition uses 1000 replicates, with two independently seeded repetitions.
Every draw acts jointly on all 33 lags. The MSD at 100, 1000 and 10000 s and the
10--10000 s fitted H are recomputed from the **equal-flight** mean, including the
resampled flight-count denominator. Days are not equally weighted observations.
The report records standard errors, percentile intervals, ratios to the archived
site-day SE, valid replicate counts, contributing blocks, largest block fraction,
size balance, source hashes and seeds. The size-balance index is not an effective
number of independent observations. Figure bars span partitions and seeds; they
are **not confidence intervals**. Monte Carlo errors of the estimated bootstrap SD
are recorded separately and do not measure uncertainty in the diagnostic itself.

The report and CSV show sensitivity, not a test proving independence or coverage.
There is no automatic plateau detector or automatic replacement of manuscript
intervals. Seasonal composition and persistent site/pilot effects remain possible.
This MSD/H check does not validate quantile or kurtosis bands.

To redraw offline without caches, put the diagnostic JSON at `OUT/report.json`:

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python \
  scripts/tesi/ch03_fixed_transport/check_bootstrap_reliability.py \
  --out OUT --redraw --publish thesis/generated
```

Published inputs are `thesis/generated/ch3_transport_bootstrap_reliability.{json,csv,pdf}`
and its `_values.tex` macro file. Replicate arrays remain in the separate run folder.

### Locate daily dependence

The complementary correlogram uses the same validated caches and every flight in
the fixed cohort. It requires no annual resampling or discarded date intervals:

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache VECLIB_MAXIMUM_THREADS=2 \
  .venv/bin/python scripts/tesi/ch03_fixed_transport/check_daily_dependence.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --out revisions/bootstrap-reliability-2026-09-18/run-daily \
  --max-days 64 --publish thesis/generated
```

For MSD at lag `tau`, the flight contribution is `m_f(tau)/M_2(tau) - 1`.
Scaling by `M_2` cancels from the correlogram. For H it is the derivative of the
fit to the population curve: sum over fit lags of the relative MSD contribution
times `(log(tau) - mean(log(tau))) / (2 * sum((log(tau)-mean(log(tau)))**2))`.
It is not a mean of flight-specific H estimates. Contributions are **summed**
within each day, so unequal daily flight counts do not change the estimator.
Empty dates contribute zero to the observed estimator; no flight value is imputed.

For each actual calendar separation `h`, compute
`rho(h) = sum(U[d]*U[d+h]) / sum(U[d]**2)`. Use a common denominator rather than
normalising separately over occupied pairs; otherwise the contributions no longer
sum consistently in a variance calculation. The CSV records occupied pair counts
and every separation for all three MSDs and H. The compact thesis figure shows
MSD at 1000 s and H. No white-noise significance bands or automatic decorrelation
threshold are applied to this sparse, heterogeneous archive.

The only adjustment subtracts the flight-weighted mean contribution within each
**month of the year**, pooled across years, before daily aggregation. It retains
every flight and is solely a sensitivity check for mean seasonal composition.
It cannot remove year-specific, site, pilot, or all seasonal effects; it never
changes the reported point estimates or confidence bands.

For audit, the report also saves
`1 + 2*sum((1-h/L)*rho(h), h=1,...,L-1)`, the Bartlett-weighted covariance
contribution relative to independent **days**, not site-days. Its square root is
comparable to changing from one-day to longer blocks, but is not a calibrated SE
correction. The correlogram and blocking results use the same data and related
second moments; agreement is not independent validation or a coverage test.

The portable `ch3_transport_daily_dependence.{json,csv,pdf}` and `_values.tex`
are published in `thesis/generated`. The run directory retains full daily vectors,
counts, calendar dates, and monthly means in `{para,hang}-daily.npz`. Offline
redrawing uses the same command with `--out OUT --redraw --publish thesis/generated`,
without `--data`; `OUT/report.json` suffices.

## Test increment stationarity by origin position

Pooling every admissible origin inside a segment estimates one population law
only if the increment law does not depend on the origin. The diagnostic splits
each selected segment's admissible origins into three contiguous blocks of equal
size and measures the same equal-flight radial moments in each. The early and
late blocks hold identical origin counts in every segment, so each cohort flight
contributes to both and the late/early ratio is paired inside the saved site-day
draws. Under stationary increments that ratio is one at every lag.

This check reads trajectories, so it needs both the published run and the
coordinate store named in its `measurement-provenance.json`:

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache VECLIB_MAXIMUM_THREADS=2 \
  .venv/bin/python scripts/tesi/ch03_fixed_transport/check_origin_dependence.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --coords /Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1/arrays \
  --out revisions/origin-dependence-2026-09-18/run \
  --publish thesis/generated
```

Before any contrast is reported, pooling the three blocks must reproduce the
archived `lag-*.npz` equal-flight radial M1 and M2 to `rtol=1e-9` at every lag.
That identity ties the diagnostic to the published estimator; a mismatch raises
rather than warns. `--disciplines hang` runs the small cohort alone for a quick
check, and `--lags` restricts the grid, though the per-decade H fits need at
least three lags in each published fit range.

The published run takes about one minute for both disciplines. The portable
`ch3_transport_origin_dependence.{json,csv,pdf}` and `_values.tex` go to
`thesis/generated`; `{para,hang}-replicates.npz` keeps the block means, ratios
and per-flight lever arms locally. Offline redrawing uses `--out OUT --redraw
--publish thesis/generated` without `--data` or `--coords`.

Read the result as a falsification of increment stationarity for these segments.
It does not identify a mechanism, and its direction is opposite to the ageing of
a subordinated walk, so it is not evidence for one.

## Where the chapter text lives

Every sentence of the chapter is in `thesis/tesi/04-fixed-transport.tex`, which is
one file for the whole chapter. No script writes prose any more. The reporting
scripts emit only the numbers the prose cites, as `\newcommand` definitions:

- `ch3_transport_values.tex` from `write_ch3_text.py`
- `ch3_transport_bootstrap_reliability_values.tex` from `check_bootstrap_reliability.py`
- `ch3_transport_daily_dependence_values.tex` from `check_daily_dependence.py`
- `ch3_transport_origin_dependence_values.tex` from `check_origin_dependence.py`
- `ch3_transport_grid_bootstrap_values.tex` from `check_grid_bootstrap.py`

All four are `\input` at the top of the chapter. Edit the wording in the chapter
and rerun the script to refresh a number. Sentences whose wording depends on a
comparison holding, such as the cohort-effect paragraph, are guarded: if the
comparison stops holding, `write_ch3_text.py` raises instead of quietly leaving a
false claim in place, and the sentence must be rewritten by hand.

Tables stay generated, because their bodies are data rather than prose.

## Files retained on SSD

- `report.json`, `figures/`: everything needed for immediate redraw.
- Each discipline: `flights.parquet`, three `cohort-*.json`, `cluster-draws.npy`,
  `flight-msd.npy`, `msd.npz`, `native.npz`, `interpolation.parquet`, per-lag sufficient
  results `lag-*.npz`, and the consolidated `scaling-draws.npz`.
- `input-audit.json`, `native-provenance.json`, `measurement-provenance.json`: identities,
  source paths, sizes/timestamps, hashes and algorithm parameters.
- Raw files, cleaned fixes, segmentation, viewer data and PCA inputs are read-only.
  The old all-lag increment/owner caches are not recreated. Scratch `.increments-*`
  files are removed after each successful lag; an interrupted scratch file can be
  removed once its owning process is stopped.

The original experiment passages transferred into the new chapter are red in
`esperimenti.pdf`. Their older estimates and definitions remain historical; the
current results are in `main.pdf`. Anisotropy/PCA has only a placeholder in Chapter 3.

## Conditional MSD (Section 3.2)

The extension uses **paragliders only**, the same `C_10000` flight/segment cohort,
33 lags and archived 1000 paired site-day bootstrap draws as the main report.
It reads the saved flight-level MSD cache rather than remeasuring trajectories.
Before stratifying, it validates flight identities and reconstructs every baseline
bootstrap curve; it also checks the existing circuit-by-altitude point estimates.

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache VECLIB_MAXIMUM_THREADS=2 \
  .venv/bin/python scripts/tesi/ch03_fixed_transport/conditional_ch3_transport.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --out revisions/conditional-transport-2026-09-19/run-terrain \
  --publish thesis/generated
```

Use a fresh output directory for a new measurement. To redraw the existing run,
replace `--data ...` with `--redraw`. An offline redraw needs only `OUT/report.json`;
the portable copy is `thesis/generated/ch3_conditional.json`. No archived source
file is modified. `--conditional-out OUT` on `run_ch3_fixed.py` includes this
extension in the main workflow (measurement for a fresh output, redraw otherwise).

The comparisons are:

- Open versus closed, pooling altitude, alongside the existing circuit-by-altitude
  figure. Unknown declarations enter neither named circuit.
- Four initial-altitude classes, pooling circuits and equipment.
- Alps versus Pyrenees and Channel Coast versus Champagne-Lorraine, selected
  **by geographic box and broad altitude setting**: Low/High mountains for the
  mountain pair, Plains/Hills for the lowland pair. The classes in each pair are
  pooled. Champagne-Lorraine is broader than Champagne. The report records box
  counts, exclusions and retained counts separately.
- Beginners **EN A/B/C** versus experts **EN D/CCC**, first pooled and then within
  each of the four altitude classes (one figure, one panel per equipment group). Tandem, non-certified and unknown entries
  are excluded only from these equipment comparisons. The labels are equipment
  proxies and do not certify pilot experience. Historical experiments retain
  their older A/B versus C/D/CCC split; their saved outputs are not relabelled.

Every curve legend gives its actual fixed flight count, fitted H and nominal 90%
interval. H is half the OLS slope of the group mean, never the average of flight
exponents. Contrasts and altitude interactions use paired replicates. Intervals
are pointwise, not multiplicity-adjusted, and retain the dependence limitations
of the original site-day bootstrap.

The versioned report records group support, MSD bands, H intervals, circuit
composition, all paired H contrasts, source hashes and selection rules. The local
run additionally retains `membership.parquet` and `replicates.npz`. Generated
CSV files expose every curve and fit; five vector PDFs, two contrast tables and
numerical macros supply the thesis. The interpretation stays in
`thesis/tesi/04-fixed-transport.tex`.

The altitude-only comparison is descriptive: open-flight proportions are 91.1%
and 71.1% in Plains/Hills, versus 33.5% and 35.0% in the mountain classes.
Circuit-specific curves show larger H for open than closed flights in all four
classes, but opposite lowland-minus-mountain contrasts for the two circuits.
The manuscript therefore discusses relief mechanisms after this crossed
comparison, without claiming a monotonic terrain effect or treating pooled
H as an average of circuit H values. Regional comparisons remain descriptive
within a broad altitude setting; they do not match circuit composition.
The closed-route reversal has no established physical explanation in these
measurements. The leg-duration/return-geometry explanation is a hypothesis.

The regional interpretation distinguishes similar growth exponents in Channel
Coast and Champagne-Lorraine from the lower Pyrenean H and long-lag MSD relative
to the Alps. One proposed explanation is comparable spatial statistics of
lowland thermal triggers, such as heated asphalt and dark ploughed fields,
versus mountain lift tied to slope and ridge geometry. The Pyrenean result is
interpreted as consistent with stronger constraints on net progress and fewer
route choices than in the Alps. Neither a uniform trigger field nor a ranking
of accessible routes is measured: H is not a direct measure of freedom, and
weather, equipment, circuit mix and detailed launch altitude remain unmatched.
The lowland inference concerns these two regions and H, with differing MSD
amplitudes. SSA's lift-source guide and FAA Chapter 9 support the candidate
mechanisms, not their attribution to the regional contrast.

The spatial illustration uses viewer cells **High mountains #2 (H2)** in
Chartreuse and **Plains #1 (P1)** in Suisse Normande, at **100 and 600 m**
above the fixed cell reference. All available dates are pooled. The thesis
and seminar deck share the four direct viewer-data exports and France locator;
selection, counts and reproduction instructions are recorded in
`presentations/offsite2026/assets/screenshots/README.md`. The mechanism slide uses a scientific 3D perspective to show heated slope sources, separated
lowland heat sources and possible wind advection. The thesis distinguishes a
translated source pattern under shared constant wind from broadening when wind
or updraft strength varies across the pooled sample. Sheltered lower slopes and
stronger wind aloft are a possible profile, not an inferred mountain/lowland wind
hierarchy; P1 is inland. Both accounts distinguish observed spatial spread from
its proposed mechanisms. Intersection markers are saturated and nearly opaque
for visibility; coordinates, counts and selection are unchanged.

Section 3.2 now presents the marginal circuit comparison first, then altitude
composition and circuit-by-altitude interactions, regions, equipment, and a
methodological synthesis. Marginal comparisons pool other characteristics;
stratified comparisons fix selected categories. These observational comparisons
are not controlled one-factor-at-a-time experiments. The existing paired
interaction contrasts are retained as quantitative evidence. The factorial
implementation in Experimentals remains provisional and does not supply results
to the main chapter. Its motivation includes future group/solo comparisons
at common circuit, altitude and equipment settings.

The contribution figure `ch3_conditional_circuit_weights.pdf` shows
`w_c|a(tau) = (N_c,a/N_a) M_c,a(tau) / M_a(tau)` for open and closed circuits
**within each altitude class**. The full class, including unclassified flights,
remains the denominator. Unclassified MSD is the residual to one and is bounded
in the generated caption. Shares of different altitude classes do not sum to one
within a panel. These are observed shares without uncertainty bands, and are
not averaging weights for the exponents fitted over a lag interval.

`conditional_ch3_transport.py` regenerates the weights during measurement/redraw.
To update just this figure, its JSON record and its numeric macros offline:

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python \
  scripts/tesi/ch03_fixed_transport/circuit_msd_weights.py
```

The seminar deck uses the same computation with projection-sized typography.
The separate composition-standardization diagnostic under
`revisions/circuit-composition-2026-09-22/` remains a review artifact; its
reference-dependent percentage reductions are not promoted to the main text.

Section 3.2 palettes live in `conditional_plot_style.py`. Circuit, altitude,
region and equipment categories have semantic colours distinct from the
paraglider/hang-glider pair; the existing circuit-by-altitude renderer imports
the same altitude palette as the new extension.

The map, Chapter 2 coordinate table and regional selections share
`src/soaring/analysis/regions.py`. Regenerate the map and table directly from the
retained-flight metadata (no trajectory/MSD cache required):

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python \
  scripts/condivisi/generate_prelim_figure.py --map-only
```

The map contains the entire retained ensemble before altitude preselection.
The earlier Chapter 2 census partition remains unchanged: Champagne-Lorraine
lies inside its outside-massifs residual, as stated in the text. The regional
MSD comparison uses the new geography-plus-altitude intersection.

## Experimental joint factorial analysis (Experimentals, Section E.1)

The manuscript keeps this extension in `thesis/tesi/experimentals.tex`, after
the appendices, with a cross-reference from Section 3.2.

`factorial_ch3_transport.py` crosses the four altitude classes, open/closed
circuits and beginners/experts equipment groups. It reaggregates saved per-flight
MSDs into 16 disjoint cells; existing two-factor aggregate curves cannot recover
these intersections. Source flights, cohort manifest, lag grid and original
paired draws are validated with the same loader as the bootstrap audit.

```bash
VECLIB_MAXIMUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python \
  scripts/tesi/ch03_fixed_transport/factorial_ch3_transport.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --out revisions/factorial-transport-2026-09-21/run \
  --publish thesis/generated
```

Use a fresh output directory for new measurements. For offline rendering, pass
`--redraw --out <directory-containing-report.json> --publish thesis/generated`.
Neither operation compiles `main.pdf`; compile the manuscript only when ready.

The numerical module is `soaring.analysis.observables.factorial_transport`.
It implements a sum-to-zero, fixed-effects factorial decomposition of **cell
exponents with equal cell weights**, and its ordinary least-squares additive
projection. This is a descriptive ANOVA decomposition, not a balanced ANOVA of
individual flights. The 10 interaction dimensions are not a common error estimate.
No classical F tests are used; H remains the slope of the cell mean MSD, not a
mean of per-flight slopes or the slope of a reweighted mixture of cell MSDs.

Uncertainty propagates through paired cell exponent draws. The declared family
has 19 contrasts: eight circuit simple effects, eight equipment simple effects,
two Plains-minus-High-mountains circuit interactions, and their equipment
difference. Nominal simultaneous 90% intervals use a single-step maximum absolute
centred bootstrap deviation divided by fixed marginal bootstrap standard errors.
This first-order plug-in version does not recompute a standard error within each
draw and is not Romano-Wolf stepdown testing. Pointwise percentiles remain in the
CSV exports. The family is calibrated separately within each fit window/grouping;
it does not adjust for all exploratory choices or establish population coverage.
The report also saves separate 16-entry simultaneous families for cell exponents
and residuals; these are not used for significance markings in the manuscript.

All cells use the same four fit ranges and the fixed C_10000 flights/segments.
Sensitivity reruns use calendar days, three-day blocks (anchor 2000-01-01, one
offset) and 50 km UTM cell x altitude x month of year, pooling years. Each
alternative uses 1000 resamples and seeds 20260921/20260922. Draws cover the whole
eligible archive before restricting to cells. Missing labels or empty/nonfinite
replicates fail the run rather than being silently omitted.

Outputs include the full portable JSON report, two vector figures, decomposition
and sensitivity tables, numerical macros, and cell/contrast/component CSVs.
The revision run retains membership for all cohort flights (including exclusions),
baseline MSD replicate curves and all exponent draws. The manuscript marks the
section, figures and tables **Experimental**. Method/source checks are recorded
in `revisions/factorial-transport-2026-09-21/README.md`.
