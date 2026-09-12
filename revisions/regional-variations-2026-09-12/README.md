# Regional second and third differences

Completed numerical measurement and manuscript extension. This uses the verified
coordinate stores of `regional-pca-lags-2026-09-12`; it does not change that PCA
measurement or repeat cleaning. Numerical code, report, thesis and supervisor
slides are one delivery. The separate terrain-axis work in another conversation
is not part of this measurement.

The protocol is specified in `scripts/reporting/ch3_global_transport/measure_regional_variations.py`:
18 physical lags from 10 to 10,000 s; three difference orders; available origins,
origins shared by orders, and origins shared by all orders and lags through 1,000 s.
All regional flights and supported segments are used. The main weights are equal
per flight, with an explicit pooled-origin sensitivity. Bootstrap groups are
site--day, with 500 replicates. Unknown group keys become identified singletons.
The common-context standardisation is descriptive, with no calibrated intervals.

The full measurement used 108,189 paragliders and 4,747 hang gliders. Measurement
and summary took 168.4 seconds with four workers. At 1000 s, the common-origin
paraglider RMS velocity changes are 5.31, 4.89 and 3.72 m/s for Alps, Pyrenees and
Channel Coast. The Alpine/coastal ratio is 1.426 (simultaneous 95% band
1.403–1.449); the Alpine/Pyrenean ratio is 1.086 (1.074–1.097). Short-lag ordering
differs. The context-standardised comparison retains the coastal contrast, but
has no calibrated intervals. No wind attribution or validated Hurst estimate is
made. Hang gliders have no shared three-region context strata.

`audit_numerics.py` verifies every regional flight identity and support rule,
directly reconstructs stencils on 45 flights per discipline, checks mixture
moments, distribution mass/energy and the 23 shared paraglider strata. Unit tests
check drift/acceleration cancellation, segment separation, circles, covariance
mixing and rotation, paired resampling, context weights, parallel execution and
position-error gains. Relevant PCA and rebuild/provenance tests also pass.

The six figures and generated values are identified by `figure-manifest.json`.
`numerical-update.json` records the new measurement while checking every inherited
PCA and baseline result unchanged. `manuscript-review.json` identifies the
123-page reviewed thesis. The slide delivery adds ten pages to Chapter 3 and
clarifies slide 7; its source manifest and validation record are in
`presentations/`. Both slide and note PDFs contain 85 pages.

To repeat the measurement from the same verified stores, use a **new** directory
and preserve the completed report:

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/measure_regional_variations.py \
  --out /path/to/a/new/regional-variation-run
```

Large per-flight arrays stay in ignored `arrays/`; the complete aggregate report
is versioned losslessly as `report.json.gz`. No flight-number cap or
longest-segment restriction is introduced.

The executed measurement CLI is archived as
`executed-measure-regional-variations.py.gz`, matching the report's original hash.
The current CLI additionally accepts absolute coordinate-store paths for the
full rebuild. The independent audit verifies unchanged ASTs for all non-main
functions and the unchanged measurement module. Original hashes are preserved.
The new `regional_variations` full-rebuild stage follows `transport_full`.

Visual review corrected the escaped tau in the four CDF titles. The first
rendering sources and review manifests are preserved in `first-render-*.gz`;
`render-label-correction.json` verifies that only that PDF changed and the
numerical report stayed identical. The final manifests identify the corrected
figure and rebuilt thesis.

To reproduce this delivery's review and presentation from the saved report:

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/render_regional_variations.py \
  --report revisions/regional-variations-2026-09-12/report.json.gz \
  --manifest revisions/regional-variations-2026-09-12/figure-manifest.json
.venv/bin/python revisions/regional-variations-2026-09-12/review_delivery.py
uv run --no-project --with pypdf python presentations/prepare_assets.py \
  --pca-update revisions/regional-pca-lags-2026-09-12 \
  --variation-update revisions/regional-variations-2026-09-12
uv run --no-project --with pypdf --with numpy --with matplotlib \
  python presentations/render_variation_panels.py
python3 presentations/build.py 3 --notes
uv run --no-project --with pypdf python presentations/validate.py
```

The focused review script intentionally checks this revision's recorded inputs;
later numerical or manuscript extensions need their own review lineage. The
separate terrain-axis comparison remains in `revisions/terrain-axis-2026-09-12/`.
