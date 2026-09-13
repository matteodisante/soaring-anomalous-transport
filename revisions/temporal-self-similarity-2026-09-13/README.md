# Signed and two-interval scaling

The new measurement supports approximate intermediate-range scaling, with
explicit limits. Between 100 and 1600 s, one training exponent rescales signed
east/north increments and the tested projections of two consecutive intervals.

| Discipline, 100–1600 s | Training H | Spatial distance / upper bound | Temporal distance / upper bound |
|---|---:|---:|---:|
| Paragliders | 0.9152 | 0.0265 / 0.0313 | 0.0781 / 0.0829 |
| Hang gliders | 0.8985 | 0.0490 / 0.0640 | 0.0893 / 0.1043 |

These are cumulative-probability differences at fixed projections and thresholds,
with conditional 95% simultaneous date-bootstrap upper bounds. They are not
relative displacement errors or an omnibus distance between complete 4D laws.
Paragliders pass the declared 0.05 spatial and 0.10 temporal tolerances. The
hang-glider temporal comparison misses 0.10 and passes only 0.20. The full and
long grids have temporal lower bounds above 0.20 in both disciplines. Exact
invariance, arbitrary multi-time scaling, increment stationarity and an intrinsic
Hurst exponent are not established.

## Protocol and population

[protocol.json](protocol.json) was fixed before the first measurement in this
extension; earlier descriptive results informed the ranges. The exact final
executed sources and protocol are identified in
[measurement/contract.json](measurement/contract.json). Final source formatting
and the full-rebuild CLI reproduced every measured value and compressed-array
hash from the initial execution.

Every supported 10-s origin in every eligible segment contributes, without
crossing cleaning boundaries. Within a grid, all lags use the same origins.
Flights have equal total weight. Two consecutive increments require support
through twice the largest lag.

| Lag grid (s) | Required support (s) | Eligible para / hang |
|---|---:|---:|
| 10, 100, 1000, 10000 | 20000 | 14360 / 563 |
| 100, 200, 400, 800, 1600 | 3200 | 149831 / 5914 |
| 1000, 2000, 4000, 8000 | 16000 | 26977 / 1240 |

Whole calendar dates have a deterministic training/validation role shared across
disciplines. All eligible flights enter one role, except three intermediate-grid
paragliders with invalid dates. This is an independent evaluation split, not a
flight cap. Different support requirements admit different populations, so
between-grid contrasts do not isolate lag from cohort composition.

Training fits inverse-CDF magnitude quantiles at .25/.50/.75/.90, then averages
12 log-log slopes. Logarithmic histogram quantiles have a recorded 0.183% maximum
discretisation error; the slope bound is also saved. One scalar H and the training
radial median at the first lag stay fixed on validation flights. Validation CDF
probabilities are counted directly, including exact-zero atoms.

The 16 projections are four coordinate axes and every normalised pairwise
sum/difference. The 15 thresholds include zero and both tails. Bounds use 999
paired whole-date bootstrap draws over all lag pairs, directions and thresholds.
They are simultaneous within a discipline and grid, conditional on training;
weather and repeated pilots can remain dependent across dates. Finite directions
and thresholds can miss other changes. These are bootstrap confidence statements,
not finite-sample guarantees.

## Reproduction and retained inputs

[measurement/report.json](measurement/report.json) hashes both coordinate stores
and catalogues and inherits cleaning 2.3.0 provenance from the verified PCA update.
No cleaning parameter or existing numerical product was changed. The extension
also runs after full transport collection in `configs/rebuild.yaml`.

From the repository root, create a new immutable measurement:

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/measure_temporal_scaling.py --out /path/to/new-measurement --workers 4
.venv/bin/python scripts/reporting/ch3_global_transport/render_temporal_scaling.py --measurement /path/to/new-measurement
```

For a full rebuild, `generate_temporal_scaling.py --audit-dir ...` identifies
that run's coordinate stores and supplies its own manifest. It does not reuse
this revision's old stores. The standalone CLI defaults to the explicitly
verified current PCA coordinate manifest; use `--coordinate-manifest` for another
completed store.

Six NPZ archives retain training histograms, validation flight indexes, common
origin counts, date sums/counts, mean CDFs, all contrasts, and bootstrap errors.
The flight-index mapping is the hashed `flights.json` input. They occupy about
30 MB; per-origin 4D arrays are never materialised for the whole archive. Four
bounded workers and memory-mapped coordinates completed the measurement in
approximately 85 seconds. No cleaning-environment packages were changed.

Final arrays, reports, code/protocol, thesis and decks are mirrored under
`/Volumes/SSD_DISANTE/derived-audit/releases/temporal-self-similarity-2026-09-13/`.
`delivery.json` records their hashes and remaining disk capacity. Compact reports
and all thesis/slide figure inputs are committed; larger NPZ archives stay on the
SSD and in the local measurement directory.

The numerical/manuscript reviews verify all 98 inherited generated products and
five new outputs before presentation preparation. Seven new slides explain the
observable, support, training fit, CDF diagnostic, bootstrap and interpretation.
Presentation edits already present at the start of this work were preserved.
