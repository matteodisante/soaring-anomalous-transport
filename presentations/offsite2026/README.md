# EconophysicsLab offsite 2026

**The statistics of soaring flight** — Matteo Di Sante.

15 slides total, including the cover, entirely in English. Scope: the current
thesis introduction and dataset chapter, then Sections 3.1 and 3.2 of
`thesis/tesi/04-fixed-transport.tex`, plus the requested qualitative comparison
in the thermal-plane viewer. Only slides 4–5 cover preprocessing.
The palette and Palatino typography follow `presentations/theme.tex`.

- `offsite-2026.pdf`: projection deck, 16:9.
- `offsite-2026-notes.pdf`: the same 15 slides, with English speaker notes alongside.
- `offsite-2026.tex`: editable Beamer source.
- `render_figures.py`: redraws the saved numerical arrays and confidence intervals
  at presentation size; it does not fit new models or rerun analysis.
- `source-manifest.json`: source identities at the time of figure generation.

## Narrative

1. Title and seminar occasion.
2. Soaring as transport with an energy budget.
3. FFVL archive, coverage and metadata.
4. Full cleaning/filtering procedure.
5. Real cleaning example and retained population.
6. Displacement and equal-flight MSD estimator.
7. Fixed population and measured duration-selection shift.
8. Fixed-population growth and varying local slopes.
9. Launch-altitude groups.
10. Regional comparisons within broad altitude settings.
11. Thermal-plane viewer: mountains and plains at two heights.
12. Open versus closed circuits.
13. Reversal of the altitude ordering by circuit.
14. Equipment contrast and altitude stratification.
15. Findings and the connection to the future modelling programme.

## Rebuild

From the repository root, using its existing Python environment and TeX install:

```bash
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_figures.py
python3 presentations/offsite2026/build.py
```

The deck reads the current source counters and two existing vector figures from
`thesis/generated`; the report-based figures are local to `assets/`. The notes
identify the populations, estimators, fit ranges, uncertainty conventions and
interpretive limits. The title path, flight-behaviour sketch and route diagrams
are explicitly schematic; the cleaning example and every numerical chart come
from the saved thesis material.

## Viewer screenshots (slide 11)

The four image areas are deliberately left open for the presenter's captures.
See [screenshot instructions](assets/screenshots/README.md). Adding the named
PNG files and recompiling replaces the placeholders automatically. Set the two
height labels in `offsite-2026.tex` at `ThermalLower` and `ThermalUpper`.
The slide distinguishes the qualitative observation from the proposed mechanisms.
