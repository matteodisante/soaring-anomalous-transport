# EconophysicsLab offsite 2026

**The statistics of soaring flight** — Matteo Di Sante.

15 slides total, including the cover and one bootstrap appendix, entirely in English. Scope: the current
thesis introduction and dataset chapter, then Sections 3.1 and 3.2 of
`thesis/tesi/04-fixed-transport.tex`, plus the requested qualitative comparison
in the thermal-plane viewer. Only slides 4–5 cover preprocessing.
The palette and Palatino typography follow `presentations/theme.tex`.

- `offsite-2026.pdf`: projection deck, 16:9.
- `offsite-2026-notes.pdf`: the same 15 slides, with English speaker notes alongside.
- `offsite-2026.tex`: editable Beamer source.
- `render_figures.py`: redraws saved numerical arrays and confidence intervals.
- `measure_cadence_support.py`: measures the cadence-limited extension of C10000
  for slide 8; writes the portable `cadence-support-report.json`.
  It reads the SSD without changing
  the published thesis analysis. Large intermediate arrays stay in `build/`.
- `source-manifest.json`: source identities at the time of figure generation.

## Narrative

1. Title and seminar occasion.
2. Soaring as transport with an energy budget.
3. FFVL archive, coverage and metadata.
4. Preprocessing steps 1--3: altitude, fixes and airborne interval, with schematics.
5. Preprocessing steps 4--6: flight selection, coordinates and time grid; retention.
6. Displacement and equal-flight MSD estimator, with admissible origins and gaps.
7. Fixed population and measured duration-selection shift.
8. C10000 from 1 s, with growing cadence support below 10 s and fixed support above.
9. Launch-altitude groups and their different open/closed circuit composition.
10. Regional comparisons within broad altitude settings.
11. Thermal-plane viewer: mountains and plains at two heights.
12. Open versus closed circuits.
13. Reversal of the altitude ordering by circuit.
14. Equipment contrast and altitude stratification.
15. Appendix: cluster bootstrap with replacement and limitations of current bands.

## Rebuild

From the repository root, using its existing Python environment and TeX install:

```bash
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_figures.py
python3 presentations/offsite2026/build.py
```

Slide 8 keeps C10000 as its parent population and its selected segment identities.
For 1--9 s, segments enter when their native cadence is no larger than the lag;
native origins and linearly interpolated endpoints stay within each selected span.
At 10 s all 46,273 paraglider and 2,326 hang-glider flights contribute, and support
stays constant through 10,000 s. From 10 s the original common-grid estimator is
evaluated at dense multiples of 10 s, reproducing every published per-flight point.
This differs from Figure 3.1, which uses the general population and requires exact
native short-lag resolution, so its support need not increase monotonically.

Local H uses a +/-0.25-decade log-log regression window, expanded to the nearest
three measured lags when sparse; the 1 s estimate uses the one-sided 1--3 s window.
Short-lag slopes also reflect changes in sample composition. Global fits reuse the
original 33 lags over 10--10,000 s and remain unchanged. The original 1,000 site-day
bootstrap draws are reused. Other transport slides use the same published C10000.

To reproduce this supplementary measurement with the SSD mounted:

```bash
VECLIB_MAXIMUM_THREADS=2 .venv/bin/python presentations/offsite2026/measure_cadence_support.py
```

The deck reads the current source counters and two existing vector figures from
`thesis/generated`; the report-based figures are local to `assets/`. The notes
identify the populations, estimators, fit ranges, uncertainty conventions and
interpretive limits. The title path, flight-behaviour sketch, preprocessing,
displacement, route and bootstrap diagrams
are explicitly schematic; numerical charts come from
saved thesis material or the supplementary cadence-support measurement above.

Confidence bands and error bars retain the nominal 90% bootstrap intervals.
The results slides flag that the current clusters remain too fine and probably
understate uncertainty. The appendix explains sampling with replacement and the
unresolved dependence across groups; it replaces the former summary slide to
preserve the 15-slide limit. The grid-bootstrap check is discussed as an unfinished
diagnostic, not as a validated replacement for the intervals plotted here.

## Viewer screenshots (slide 11)

The four image areas are deliberately left open for the presenter's captures.
See [screenshot instructions](assets/screenshots/README.md). Adding the named
PNG files and recompiling replaces the placeholders automatically. Set the two
height labels in `offsite-2026.tex` at `ThermalLower` and `ThermalUpper`.
The slide distinguishes the qualitative observation from the proposed mechanisms.
