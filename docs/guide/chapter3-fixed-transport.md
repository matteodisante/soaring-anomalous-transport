# Chapter 3: fixed-cohort transport

The current thesis analysis is independent of the historical experiments pipeline.
The numerical contract is in `revisions/msd-fixed-population-2026-09-17/PIANO.md`.
The published run is on SSD:

```
/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917
```

## Change a figure without measuring again

Edit colours, markers or layout in
`scripts/reporting/ch3_global_transport/render_ch3_fixed.py`, then run from the repo:

```bash
uv run python scripts/reporting/ch3_global_transport/run_ch3_fixed.py \
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
.venv/bin/python scripts/reporting/ch3_global_transport/summarize_ch3_fixed.py \
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
  scripts/reporting/ch3_global_transport/run_ch3_fixed.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-NEW
```

For the published run, coordinate collection was avoided by reusing the protected
PCA coordinate store. Every coordinate was then reconstructed from current cleaned
fixes and checked for exact agreement (maximum error: zero). The equivalent command is:

```bash
VECLIB_MAXIMUM_THREADS=2 uv run python \
  scripts/reporting/ch3_global_transport/run_ch3_fixed.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 \
  --reuse-coordinates /Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1/arrays
```

Completed lag files are reused only after checking their cohort fingerprint and
bootstrap dimensions. Input timestamps and sizes must still match the successful
full coordinate audit. A changed analysis convention requires a fresh run directory;
resume is intended for the same calculation interrupted between lag files.
The historical `scripts/rebuild_thesis.py` graph remains available for the experiments
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
