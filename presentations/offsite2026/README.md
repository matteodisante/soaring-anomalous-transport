# EconophysicsLab offsite 2026

**The statistics of soaring flight** — Matteo Di Sante.

30 slides total, including the cover, closing research agenda, sources, bibliography, thanks and three appendices, entirely in English. Scope: the current
thesis introduction and dataset chapter, then Sections 3.1 and 3.2 of
`thesis/tesi/04-fixed-transport.tex`, plus the requested qualitative comparison
in the thermal-plane viewer. Only slides 4–7 cover preprocessing.
The palette and Palatino typography follow `presentations/theme.tex`. Header titles
are kept on one line; compilation rejects titles wider than 140 mm so the slide
number stays clear.

Key messages use bold Palatino in the existing steel-blue takeaway bands.
Two-line result bands distinguish the bold takeaway from supporting figures or
interpretation in regular weight, without introducing new emphasis colours.

Every empirical plot identifies the number of distinct flights in each plotted
category. Curve legends include `N`, each equipment contrast gives both group
sizes, and the thermal maps distinguish paraglider and hang-glider flights from
crossing counts. Cohort legends are discipline-specific. On slide 11, the legends
give the fixed counts from 10 s onward and the caption gives the smaller 1 s
counts. `render_figures.py` reads these numbers from the existing reports and
verified crossing CSVs, without remeasuring trajectories or changing fits.

The cover carries the supplied white Econophysics Lab mark with terminal squares
directly on blue at lower left. The white lower band is limited to CFM and ILB.
CFM appears without its tagline and ILB uses its wide vector mark. The offsite
title is separately typeset in condensed, light lettering directly on blue below
the cover illustration and beneath the Lab mark on the closing slide. Content
and appendix slides carry the Lab wordmark at the lower right, with a separate
120 mm area for source credits. The dark closing slide uses the supplied white
Lab mark. All four originals are stored unchanged in `assets/logos/`; see its
README for the source filenames.

- `offsite-2026.pdf`: projection deck, 16:9.
- `offsite-2026-notes.pdf`: the same 30 slides, with English speaker notes alongside.
- `offsite-2026.tex`: editable Beamer source.
- `render_figures.py`: redraws saved numerical arrays and confidence intervals.
- `preprocessing-global-frame.tex`: editable ellipsoid/ENU schematic adapted from
  the thesis coordinate figure; the tangent-plane close-up is inline in the deck.
- `render_thermal_panels.py`: exports slide 18 maps directly from the viewer's
  read-only prepared intersections and saved IGN colour maps, without screenshots.
- `measure_cadence_support.py`: measures the cadence-limited extension of C10000
  for slide 11; writes the portable `cadence-support-report.json`.
  It reads the SSD without changing
  the published thesis analysis. Large intermediate arrays stay in `build/`.
- `source-manifest.json`: source identities at the time of figure generation.

## Narrative

1. Title and seminar occasion, with Lake Maggiore, Isola dei Pescatori and the Alps in a perspective illustration. Gliding and search lead into a helical climb inside a thermal rising from a sun-warmed mainland slope; the foreground island includes its bell tower and red waterfront building without signage.
2. Soaring as transport with an energy budget.
3. FFVL archive, coverage and metadata.
4. Preprocessing steps 1--3: a channel-role diagram for GNSS altitude and barometry, the physical fix-deletion rule, and a timeline distinguishing take-off, intermediate landing, relaunch and final landing. The altitude spectral comparison remains in the speaker notes.
5. Preprocessing steps 4--5: selection bars with cutoffs positioned at the observed rejection fractions (both disciplines, among logs reaching each sequential check), a 3D geographic-to-local coordinate diagram adapted from the thesis, and explicit retention after the full pipeline. The census gives 1.13%, 0.09% and 2.68% rejected by the duration, path and altitude-range minima, respectively.
6. Preprocessing step 6: short-gap interpolation versus long-gap splitting.
7. Preprocessing step 7: the moving cubic Savitzky--Golay fit, with position and analytic derivatives evaluated at the window centre; no subsequent finite differences.
8. Displacement and equal-flight MSD estimator, with admissible origins and gaps.
9. Bridge: TA-MSD over all available flights beside the share of flights contributing at each lag. The circled end of the MSD (from 10^4 s) is where the steep loss of flights beyond about 6x10^3 s acts, so an all-flight H fit mixes dynamics with a changing flight set, as does any lag-dependent statistic. A framed box lists the desiderata for one population: same flights at every lag, longest lag range, N of the same order as at 10 s.
10. C10000 meets those desiderata: no loss of flights up to 10,000 s, at least 251 origins per segment at the largest lag, 30% of paragliders and 38% of hang gliders available at 10 s. The measured duration-selection shift in H, about 2%, is the cost.
11. C10000 from 1 s, with growing cadence support below 10 s and fixed support above; fitted growth over 10–10,000 s is superdiffusive.
12. Terrain (launch-altitude proxy), experience (Beginners = EN A/B/C, Experts = EN D/CCC) and circuit type; pooled circuit comparisons versus comparisons within altitude classes, with remaining weather and equipment differences explicit. OFAT is introduced in the factorial appendix.
13. Open versus closed circuits: slower growth for return routes, linked to the displacement reduction caused by turns and returns.
14. Plains > Hills > Mountains in pooled H; circuit composition motivates the within-altitude comparison.
15. Circuit contributions depend on both flight fractions and MSD; changing shares affect amplitude and fitted H.
16. The altitude ordering reverses by circuit: a quantified interaction.
17. Regional comparisons show similar H in the two lowlands and a lower H in the Pyrenees than in the Alps. The interpretation proposes broadly distributed lowland thermal triggers and stronger Pyrenean route constraints from terrain-linked lift; neither trigger uniformity nor route accessibility is measured here.
18. Thermal-plane maps: requested viewer cells High mountains #2 (H2, Chartreuse, Alps) and Plains #1 (P1, Suisse Normande, Channel Coast), at 100 and 600 m above each cell reference. All dates and years are pooled. Coloured IGN maps, crossing/flight counts, approximate red crests derived from IGN RGE ALTI and a France locator also appear in the thesis.
19. Scientific 3D perspective schematic: heated mountain slopes versus separated lowland heat sources, with possible wind profiles and advection. Source distribution plus variable wind may broaden pooled climb locations aloft; terrain guidance is a proposed explanation for the narrower circuit gap.
20. Experts-versus-Beginners contrasts persist within altitude classes and vary across them; a constant speed multiplier cannot explain a difference in H.
21. Work in progress: continuous-observation HMM across cadences, anisotropy and distribution scaling.
22. Proposed two-phase transport model: gliding generates displacement; contiguous search and thermalling episodes merge into one waiting phase. Estimate total waiting times, glide lengths/durations and directional memory, then test the 2D-plus-time model with Monte Carlo simulations. Vilpellet's phase-resolved observations motivate the reduction; neglecting motion during waiting remains an approximation to test.
23. Exposure-aware lift maps and routing under an explicit objective (solo/grouped flight moved to the appendix).
24. Flight, terrain, map and analysis sources with clickable links.
25. Selected bibliography.
26. Take-home messages and open questions.
27. Thanks and discussion.
28. Appendix: quantitative factorial model, six additive and ten interaction coefficients, and editable OFAT/full-factorial grids.
29. Appendix: solo versus group feasibility; group means co-present flights in one cell within about 15 minutes, and the most populated 5 x 5 km cell (Low mountains) holds at most 63 flights in its peak quarter hour (22 July 2023, 13:15--13:30), an upper bound before any split over 32 cells.
30. Appendix: vector velocity autocorrelation as speed-weighted directional agreement; unit-vector correlation and the distinction from mean drift.
31. Appendix: cluster bootstrap with replacement and limitations of current bands.

Numerical estimates retain their archived confidence intervals. A marginal comparison pools
other characteristics; a stratified comparison fixes a selected category.
Neither is a controlled OFAT experiment. Unequal factor frequencies and
interactions in H are distinguished. The factorial implementation remains under
review in Experimentals; this deck motivates it without presenting its results.

Questions guide slides 9, 10, 12, 13, 14, 16, 17, 18 and 19, where the audience needs
an explicit comparison to interpret the evidence. Their titles state the question,
while plots and conclusions supply the answer. Definitions and the factorial model retain topic titles.

The conditional sequence follows observations → composition → stratification →
spatial evidence → physical interpretation → joint analysis. Visible conclusions
explain what each result implies; notes retain the statistical qualifications and
presentation transitions. Slide 16 emphasises the observed increase in spatial
spread with height in P1 relative to the persistent slope-and-ridge concentration in H2.

## Rebuild

From the repository root, using its existing Python environment and TeX install:

```bash
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_figures.py
python3 presentations/offsite2026/build.py
```

Slide 11 keeps C10000 as its parent population and its selected segment identities.
For 1--9 s, segments enter when their native cadence is no larger than the lag;
native origins and linearly interpolated endpoints stay within each selected span.
At 10 s all 46,273 paraglider and 2,326 hang-glider flights contribute, and support
stays constant through 10,000 s. From 10 s the original common-grid estimator is
evaluated at dense multiples of 10 s, reproducing every published per-flight point.
This differs from Figure 3.1, which uses the general population and requires exact
native short-lag resolution, so its support need not increase monotonically.

Local H uses a +/-0.25-decade log-log regression window, expanded to the nearest
three measured lags when sparse; the 1 s estimate uses the one-sided 1--3 s window.
Short-lag slopes also reflect changes in sample composition. The 1–10 s grey background and the ballistic reference annotation are omitted.
Global fits reuse the
original 33 lags over 10--10,000 s and remain unchanged. The original 1,000 site-day
bootstrap draws are reused. Other transport slides use the same published C10000.

To reproduce this supplementary measurement with the SSD mounted:

```bash
VECLIB_MAXIMUM_THREADS=2 .venv/bin/python presentations/offsite2026/measure_cadence_support.py
```

The deck reads the current source counters and two existing vector figures from
`thesis/generated`; the report-based figures are local to `assets/`. The within-altitude weight plot uses the shared `circuit_msd_weights.py` renderer
and retains unclassified flights in the class denominator. The notes
identify the populations, estimators, fit ranges, uncertainty conventions and
interpretive limits. The title path, flight-behaviour sketch, preprocessing,
displacement, route and bootstrap diagrams
are explicitly schematic; numerical charts come from
saved thesis material or the supplementary cadence-support measurement above.

Confidence bands and error bars retain the nominal 90% bootstrap intervals.
The results slides flag that the current clusters remain too fine and probably
understate uncertainty. The appendix explains sampling with replacement and the
unresolved dependence across groups; it remains the final appendix after the expanded conditional-analysis sequence. The grid-bootstrap check is discussed as an unfinished
diagnostic, not as a validated replacement for the intervals plotted here.

## Viewer maps (slide 18)

The four maps are populated by direct exports from the viewer's prepared data.
See [selection and provenance](assets/screenshots/README.md). To regenerate with
the SSD connected, run before compiling:

```bash
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_thermal_panels.py
```

The saved PDF maps and generated count macros allow deck compilation without
the SSD. The two 5 km cells retain the same dates, Vilpellet segmentation and
bounds within each pair. Every map pools the full prepared archive, across all available dates and years,
without a seasonal restriction. H2 is near Aulp du Seuil in the
Chartreuse; P1 is in inland Suisse Normande. The two planes are 100 and 600 m
above the viewer's fixed cell reference, rather than above local terrain. Contributing flights change with height. The slide highlights the observed widening
of climb locations from 100 to 600 m in P1, while H2 remains concentrated near slopes and ridges.
This supports freer use of space aloft in the plains cell; its contribution to H
and generality across sites are not quantified.

The schematic on slide 19 is `assets/thermal-mechanism-3d.png`; its
generation prompt is saved alongside. It illustrates possible thermally driven
air columns and wind advection, not mechanical ridge lift or measured flow in the selected cells. Helical lines are ascent cues rather than measured rotation; fragmented upper sections illustrate possible shear disruption. Sources are on heated mountain slopes, rather than exclusively on crests. The sheltered-slope/stronger-wind-aloft scenario is conditional; valleys can also channel strong wind, and P1 is inland. A shared constant wind translates a source pattern; variation across dates can broaden pooled crossings. These distinctions are retained in the thesis and speaker notes.
The earlier `thermal-landscapes` and 2D `thermal-mechanism-schematic` drafts are unused.

The cover uses `assets/cover-lago-maggiore-contrast.png`, a transparent illustration
edited with the built-in image_gen tool from the previous mountain scene.
Its prompt and visual-reference sources are saved in
`assets/cover-lago-maggiore-prompt.txt`,
`assets/cover-lago-maggiore-contrast-prompt.txt` and
`assets/cover-lago-maggiore-sources.md`. Lake Maggiore and Isola dei Pescatori
identify the offsite setting, using the supplied red-building photograph and
an aerial view from the municipal tourism site. The building has no name or
signage. The path remains above the landscape; the thermal rises from a heated
mainland slope, separate from the island. Upward airflow filaments and the
aircraft's drifting helix remain distinct. The contrast revision keeps the pale
flight path and lowers the mountain highlights to slate blue so glide and search
remain legible at cover size. The scene is geographically inspired,
not a literal topographic reconstruction or a measured flight. The earlier
`cover-flight-3d.png`, `cover-flight-3d-v2.png` and `cover-lago-maggiore.png`
are retained as unused drafts. The title,
subtitle, author, occasion and original institutional logos remain separate
Beamer elements.
