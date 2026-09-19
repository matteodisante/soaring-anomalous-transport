# Conditional MSD and H in Section 3.2

Reorganises Section 3.2 into circuit, orography and equipment studies, with a
common introduction and estimator. The requested beginners/experts split is
A/B/C versus D/CCC in both Chapters 2 and 3. Historical experiments retain their
original split and estimates.

Regional comparisons select geography and broad launch-altitude setting:
Low/High mountains in Alps/Pyrenees, Plains/Hills in Coast/Champagne-Lorraine. The four altitude classes remain
separate for altitude and equipment analyses. All curves use the fixed paraglider
cohort; legends give per-curve flight counts. Estimates and intervals reuse the
published 1000 paired site-day draws. These intervals inherit the existing
limitations of that resampling design and do not establish causal orographic or
pilot-experience effects.

Reproduction and source contracts are in
[the Chapter 3 guide](../../docs/guide/chapter3-fixed-transport.md#conditional-msd-section-32).
The source Chapter 3 before restructuring is in `before/`.

## Outputs

- `run-terrain/report.json`: complete portable report, also published as
  `thesis/generated/ch3_conditional.json`.
- `run-terrain/membership.parquet`: exact flight identities and selection masks.
- `run-terrain/replicates.npz`: paired MSD replicate curves for all groups.
- `thesis/generated/ch3_conditional*`: figures, numeric TeX inputs, fit and curve CSVs.

The regional contrast in H is resolved for Alps minus Pyrenees (about 0.037),
whereas the Coast minus Champagne-Lorraine interval includes zero. Experts have
larger H in each altitude class; the separation is largest in Low mountains.
Its change across altitude is evaluated using paired differences of differences,
not by the overlap of separate confidence intervals.

## Validation

- 27 targeted tests pass (conditional membership, paired bootstrap reduction,
  fixed transport, existing circuit joins and Chapter 3 fits).
- Ruff and `git diff --check` pass for the changed sources.
- `main.tex` compiles, with visual review of the edited Chapter 2 passage and
  Section 3.2, including all seven MSD figures (six new and one preserved).
- Section 3.2 uses semantic palettes from `conditional_plot_style.py`; none uses
  the discipline blue/orange pair. Altitude colours agree between the pooled
  altitude figure and the circuit-by-altitude figure. Equipment colours remain
  consistent across its three figures.

## Geographic definition and terrain preselection update

The original geography-only run remains locally in `run/`; the published result
now comes from `run-terrain/`. Of the fixed-cohort flights in each geographic box,
the terrain restriction excludes 385 from Alps, 103 from Pyrenees, 17 from
Channel Coast and 24 from Champagne-Lorraine. The retained counts are 32790,
2257, 1068 and 798 respectively. Nonregional results are unchanged.

Chapter 2 now defines the box limits quantitatively and shows Champagne-Lorraine
in Figure 2.23. The generated coordinate table and map consume the same shared
box constants as the regional analysis. `--map-only` reads current retained-flight
metadata directly, independent of the historical MSD audit arrays.
