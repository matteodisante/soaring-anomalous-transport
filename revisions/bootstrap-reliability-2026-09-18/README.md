# Bootstrap reliability, 18 September 2026

The calendar-block diagnostic reuses the saved per-flight MSDs of the published
Chapter 3 fixed cohort. It does not alter source trajectories or published
site-day bootstrap replicates.

## Result

No common plateau appears from 1 to 64 calendar days. At 64 days, the standard
error of the fitted H is 2.14–2.42 times the site-day value for paragliders and
1.09–1.21 for hang gliders. The three MSD standard-error factors span 2.08–3.69
and 1.00–2.05, respectively. All point estimates are unchanged. Paraglider
uncertainty is materially sensitive to wider grouping; the diagnostic does not
certify independence or select an optimal block length.

At the largest duration, 125–126 blocks contribute for paragliders and 94 for
hang gliders. The largest contains at most 4.05% and 5.55% of the cohort,
respectively. All 1000 replicates in all 36 configurations per discipline have
complete support. Larger blocks may incorporate seasonal/compositional changes
as well as residual dependence, so the increase is not a pure correlation estimate.

## Reproduce

See `docs/guide/chapter3-fixed-transport.md`, section “Check reliability of
bootstrap uncertainty”, for the measurement and offline redraw commands. The
first exploration (`run/`) used 1–16 days; `run-64/` extends the same procedure
to 32 and 64 days, without changing any measurement choices. Each uses two seeds
and up to three offsets per duration. Run directories and replicate arrays remain
local. The portable final report, complete CSV, figure and numerical prose are
versioned in `thesis/generated/ch3_transport_bootstrap_reliability*`.

The original site-day intervals remain in the main analysis and are explicitly
identified as conditional baseline estimates. No blanket inflation factor is
applied to quantiles, moments, circuit contrasts or other untested statistics.

## Daily dependence check

`run-daily/` uses all 46,273 paraglider and 2,326 hang-glider cohort flights,
with no annual blocking and no discarded intervals. Daily contributions are sums
of centred flight contributions to the MSD and linearised H. Empty calendar dates
are retained, and daily means are never averaged with equal weights.

For MSD at 1000 s, the one-day autocovariance ratios are 0.214 and 0.186
(paragliders, hang gliders). Subtracting flight-weighted month-of-year means across
years gives 0.191 and 0.169. Mean ratios over 17–64 days remain positive: 0.0184
and 0.0225 originally, 0.0201 and 0.0214 after centring. The tail is therefore not
removed by this simple seasonal adjustment; the analysis does not identify its
cause or certify independence at a selected block duration.

The Bartlett covariance factors provide a numerical cross-check of blocking.
For example, their square roots at 32 and 64 days are 1.764 and 1.971 for
paraglider MSD at 1000 s, but 1.472 and 1.521 for H. These are relative to
independent **days**, not the site-day baseline. They are not new confidence
intervals. The thesis keeps the original blocking figure and adds one compact
correlogram; complete values for all four statistics are saved in the portable
daily-dependence JSON and CSV.

## Checks

- Reconstructed all 1000 archived baseline curves and the observed curve for both
  disciplines, matching at relative tolerance 1e-10.
- Validated manifest hashes, flight ordering, lag grid and published point estimates.
- Confirmed no missing dates in either fixed cohort; no cohort flight was dropped.
- Tests cover calendar gaps, year boundaries, shifted partitions, unequal flight
  weights, whole-curve fits, missing dates, altered/reordered caches, and a simulated
  shared daily shock with the expected square-root-of-eight SE inflation.
- Daily tests cover empty dates, uneven flight counts, pooled monthly centring,
  finite-difference validation of the H derivative, the exact identity between
  Bartlett covariance factors and overlapping block sums, independent and AR(1)
  controls, missing/degenerate input, and portable report rendering.

## Revised grouping: fixed cells, altitude class and month of year

User specification: use initial position to assign one fixed cell, with side at
most 50 km; retain the four launch-altitude classes and pool each calendar month
across all years. The abandoned site-distance clustering was removed before use.
The new module is `grid_bootstrap.py`; reporting is `check_grid_bootstrap.py`.
Full commands and grid conventions are in the guide. `run-grid/` retains all
assignments, draws and curves; the portable report includes the fixed grid and
occupied cell catalogue. `prior-reliability-section.tex` preserves the preceding
calendar-based thesis discussion; those diagnostics remain reproducible.

The main-cohort baseline has 1,901 paraglider and 267 hang-glider groups, compared
with 25,682 and 1,768 site-day groups. Median sizes are 3 and 2 flights. Singletons
are 33.5% and 43.4% of groups, but only 1.4% and 5.0% of flights (previously 39.5%
and 61.8% of flights). Largest groups hold 4.4% and 13.4% of flights, so the sparse
hang-glider sample remains uneven. No main-cohort flight has missing grouping keys;
three invalid dates remain singleton units outside the paraglider main cohort.

H SEs are 3.97–4.05 and 2.00–2.05 times the original site-day SEs. Merging three
adjacent months raises median H SE by factors 1.49 and 1.40 relative to the new
one-month baseline. In hang gliders, grid shifts give MSD SE at 1000 s between
0.98 and 1.87 times the unshifted-grid value. The finer-cell result can exceed the
coarser one: this is not an assumed monotone variance-inflation procedure.

All point estimates agree with the published baseline and all 1000 replicates
have complete support in each of 36 configurations per discipline. The grouping
reduces singleton flight mass, but sensitivity to seasonal unions and boundaries
prevents declaring it independent or its intervals calibrated. Published bands
for other statistics have not been silently replaced.
