# Full-range altitude fits integrated into the thesis

**Superseded comparison:** the current thesis now uses the
[paraglider-only open/closed circuit split](../altitude-hurst-open-closed-2026-09-15/README.md).
The record below describes the earlier two-discipline comparison.

The completed [10-10000 s measurement](../altitude-hurst-10-10000-2026-09-15/README.md)
is now included in the compiled 142-page `thesis/main.pdf`:

| Content | Thesis reference | Printed page | PDF page position |
|---|---|---:|---:|
| Fit definition and site-day bootstrap | Section 3.4.4 | 76 | 80 |
| Four altitude curves, fits and 95% intervals | Figure 3.20 | 77 | 81 |
| Full numerical estimates and 95% intervals | Table 3.9 | 78 | 82 |

The figure and table cover paragliders and hang gliders, each with available
segments and the fixed long-segment control. All estimates use one fit on the
59 requested lags from 10 to 10000 s and the completed 2000 site-day bootstrap
draws. The text distinguishes effective moment scaling from an intrinsic Hurst
parameter and states what the intervals assume and omit.

`report.json` is an identical copy of the completed numerical measurement.
The generator's `--thesis-out` option exports the main figure, table, parameter
macros and report into `thesis/generated/ch3_altitude_hurst*`. The new
`altitude_hurst` rebuild stage follows `grouped_tamsd` and uses that run's
fresh segment arrays and grouping metadata. Its producer declarations are
included in the regenerated provenance index.

## Verification

`review_delivery.py` checks all 103 inherited generated products and all
environmental input identities against the September 14 parent review. It checks
the exact measurement-function ASTs against the archived executed source,
numerical input hashes, current SSD cleaning manifests and table stat/footer
identities. This does not claim a new full-byte scan of the cleaned trajectory
tables. The independent 59-lag regressions and all 16 table entries match the
saved results. The added figure is byte-identical to the standalone full-range
figure already inspected.

The compiled PDF has no overfull boxes, unresolved references or LaTeX warnings.
PDF pages 79-82 were rendered with Poppler and inspected, including the existing
altitude plot and the new subsection, figure and table. Thirty-two numerical and
rebuild tests passed. The rebuild integration tests required execution outside
the sandbox because their existing process-priority call is sandbox-restricted.
Ruff lint and format checks passed.

The provenance checker identifies all new products and their stage. Its two
pre-existing missing-header warnings remain for `ch3_temporal_scaling_bounds.tex`
and `ch3_temporal_scaling_population.tex`; both files are unchanged.

`manuscript-review.json` records the parent lineage, all 107 generated product
identities, the new fit results, final source/PDF hashes and the locations above.
The three edited existing source files are preserved as `*.before.txt`.

## Redraw and compile

```bash
MPLCONFIGDIR=/tmp/soaring-altitude-mpl XDG_CACHE_HOME=/tmp/soaring-altitude-cache \
.venv/bin/python scripts/reporting/ch3_global_transport/generate_altitude_hurst.py \
  --record-dir revisions/altitude-hurst-thesis-2026-09-15 \
  --out revisions/altitude-hurst-thesis-2026-09-15/figures \
  --thesis-out thesis/generated --render-only
bash scripts/build_docs.sh thesis
```

Completed review records remain immutable; any later manuscript changes need
a new review record rather than rerunning the existing review in place.
