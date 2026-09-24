# EconophysicsLab offsite 2026

**The statistics of soaring flight** — Matteo Di Sante.

25 slides total, including the cover, closing research agenda, thanks, appendices and sources, entirely in English. Scope: the current
thesis introduction and dataset chapter, then Sections 3.1 and 3.2 of
`thesis/tesi/04-fixed-transport.tex`, plus the requested qualitative comparison
in the thermal-plane viewer. Slide 4 alone covers preprocessing and the choice of C10000;
appendix slides 17–22 give the detail.
The palette and Palatino typography follow `presentations/theme.tex`. Header titles
are kept on one line; compilation rejects titles wider than 140 mm so the slide
number stays clear.

Key messages use bold Palatino in the existing steel-blue takeaway bands.
Two-line result bands distinguish the bold takeaway from supporting figures or
interpretation in regular weight, without introducing new emphasis colours.

Every empirical plot identifies the number of distinct flights in each plotted
category. Curve legends include `N`, each equipment contrast gives both group
sizes, and the thermal maps distinguish paraglider and hang-glider flights from
crossing counts. Cohort legends are discipline-specific. On slide 6, the legends
give the fixed counts from 10 s onward and the caption gives the smaller 1 s
counts. `render_figures.py` reads these numbers from the existing reports and
verified crossing CSVs, without remeasuring trajectories or changing fits.

The cover's white lower band spans the full width and carries the Econophysics
Lab wordmark, CFM and ILB. CFM appears without its tagline and ILB uses its wide vector mark. The offsite
title is separately typeset in condensed, light lettering directly on blue below
the cover illustration and beneath the Lab mark on the closing slide. Content
and appendix slides carry the Lab wordmark at the lower right, with a separate
120 mm area for source credits. The dark closing slide uses the supplied white
Lab mark. All four originals are stored unchanged in `assets/logos/`; see its
README for the source filenames.

- `offsite-2026.pdf`: projection deck, 16:9.
- `offsite-2026-notes.pdf`: the same 25 slides, with English speaker notes alongside.
- `offsite-2026.tex`: editable Beamer source.
- `render_figures.py`: redraws saved numerical arrays and confidence intervals.
- `preprocessing-global-frame.tex`: editable ellipsoid/ENU schematic adapted from
  the thesis coordinate figure; the tangent-plane close-up is inline in the deck.
- `render_regional_climb_density.py`: intersects continuous native own-HMM
  climb edges with horizontal planes every 10 m ASL, using the viewer routine,
  and pools every crossing into 1 km regional bins over all dates and heights.
- `render_regional_climb_maps.py`: draws appendix slides 23–24 over OpenTopoMap terrain;
  full Pyrenees and western Alps use matched 450 × 220 km views, while the two
  lowland examples use matched 100 × 65 km views.
- `render_thermal_mechanism.py`: draws the slide-10 schematic of slope-bound
  mountain thermals against scattered lowland triggers.
- `render_thermal_panels.py`: exports slide 18 maps directly from the viewer's
  read-only prepared intersections and saved IGN colour maps, without screenshots.
- `measure_plane_cells.py`: finds the busiest 10 km cell in each regional box and
  intersects its own-HMM climbs with one plane 600 m above the cell's mean IGN
  terrain, through the viewer's explorer; writes `assets/plane-cells/`.
- `render_plane_cells.py`: draws the slide-11 maps and their equal-sample
  concentration from those saved files.
- `measure_cadence_support.py`: measures the cadence-limited extension of C10000
  for slide 6; writes the portable `cadence-support-report.json`.
  It reads the SSD without changing
  the published thesis analysis. Large intermediate arrays stay in `build/`.
- `measure_open_circuits.py`: repeats the thesis regional and Experts-versus-Beginners
  contrasts (Sections 3.2.3–3.2.4) on open circuits only, with the same cohort,
  estimator, fit and archived paired draws; writes `open-circuits-report.json` and the
  macros in `open-circuits-values.tex`.
- `source-manifest.json`: source identities at the time of figure generation.

## Narrative

1. Title and seminar occasion, with Lake Maggiore, Isola dei Pescatori and the Alps in a perspective illustration. Gliding and search lead into a helical climb inside a thermal rising from a sun-warmed mainland slope; the foreground island includes its bell tower and red waterfront building without signage.
2. Soaring as transport with an energy budget: phase schematic with a pointer to the Vilpellet et al. HMM segmentation, the time-averaged MSD (per flight, then over flights), the definition of H, and Vilpellet et al. Fig. 1 (French flights, 2016–2021).
3. FFVL archive, coverage and metadata.
4. From raw tracklogs to the fixed cohort C10000. Left: the seven preprocessing stages, grouped as their four appendix slides, each row linking to its slide, then the retained counts. Right: the rule T_s >= 12,500 s, a paraglider support curve of all available flights against the flat C10000 line (real counts from ch3_transport_report.json), the cohort sizes and the ~2% cost in H. Appendix slides 17–22 hold the detail and link back to slide 4.
5. Equal-flight MSD estimator within retained segments. Left: the MSD panel of the cadence-support slide (`assets/fixed-msd`, rendered by `render_figures.py`), compared with Vilpellet et al.: H ≈ 0.88 for both disciplines there, 0.88 for paragliders and 0.85 for hang gliders here.
6. C10000 from 1 s, with growing cadence support below 10 s and fixed support above; fitted growth over 10–10,000 s is superdiffusive.
7. Terrain (launch-altitude proxy), experience (Beginners = EN A/B/C, Experts = EN D/CCC) and circuit type; pooled circuit comparisons versus comparisons within altitude classes, with remaining weather and equipment differences explicit. OFAT is introduced in the factorial appendix.
8. Open versus closed circuits: slower growth for return routes, linked to the displacement reduction caused by turns and returns.
9. Pooled H ranks Plains > Hills > Mountains, but an altitude-only comparison mixes terrain with composition: each class holds different shares of open circuits and Experts, and a group enters the class MSD as flight share times MSD, so open flights outweigh their number (Low mountains: 34% of flights, 61% of the MSD at 10^4 s). Circuit type shifts the weight more than wing class.
10. The altitude ordering reverses by circuit: a quantified interaction.
11. Experts-versus-Beginners contrasts, open circuits only (`measure_open_circuits.py`): higher H for Experts in every altitude class (+0.028 pooled, 0.010–0.023 within classes), largest in Low mountains.
12. Regional comparisons, open and closed circuits pooled (thesis Section 3.2.3), lowlands left and mountains right: the Alps--Pyrenees difference in H is clearly non-zero (0.037), while the lowland one is practically zero (−0.002, nominal interval includes zero). The open-circuit check (`measure_open_circuits.py`) shrinks the mountain difference to 0.011 and keeps the ordering. Possible reason: mountain lift follows each range's slopes, while lowland triggers are scattered alike.
13. 3D schematic of that explanation (`render_thermal_mechanism.py`): strong mountain thermals fed up the spurs and released along the crest, against weaker lowland thermals over heated surfaces of several kinds scattered at random. No wind.
14. Take-home messages, before the work in progress: a 2x2 grid in the style of slide 15, each finding beside a pictogram of its evidence. Scaling: fitted H between the diffusive and ballistic references, same flights at every lag. Route and wing: open above closed and, on open routes, experts above beginners, drawn as two glyph pairs without values; the Expert canopy is longer and thinner, in the colours of the equipment figure. Terrain: open and closed H across altitude classes, with the circuit gap narrowing from 0.13 to 0.02. Lift geography: schematic H2 and P1 crossings at 600 m. The band states that every group is strongly superdiffusive, that route, terrain and wing shape H jointly, and the working hypothesis that terrain acts through where lift is found.
15. Work in progress: phase segmentation, directional memory and distribution scaling.
16. Thanks and discussion.
17. Appendix: preprocessing steps 1--3: a channel-role diagram for GNSS altitude and barometry, the physical fix-deletion rule, and a timeline distinguishing take-off, intermediate landing, relaunch and final landing. The altitude spectral comparison remains in the speaker notes.
18. Appendix: preprocessing steps 4--5: selection bars with cutoffs positioned at the observed rejection fractions (both disciplines, among logs reaching each sequential check), a 3D geographic-to-local coordinate diagram adapted from the thesis, and explicit retention after the full pipeline. The census gives 1.13%, 0.09% and 2.68% rejected by the duration, path and altitude-range minima, respectively.
19. Appendix: preprocessing step 6: short-gap interpolation versus long-gap splitting.
20. Appendix: preprocessing step 7: the moving cubic Savitzky--Golay fit, with position and analytic derivatives evaluated at the window centre; no subsequent finite differences.
21. Appendix: TA-MSD over all available flights beside the share of flights contributing at each lag. The circled end of the MSD (from 10^4 s) is where the steep loss of flights beyond about 6x10^3 s acts, so an all-flight H fit mixes dynamics with a changing flight set, as does any lag-dependent statistic. A framed box lists the desiderata for one population: same flights at every lag, longest lag range, N of the same order as at 10 s.
22. Appendix: C10000 meets those desiderata: no loss of flights up to 10,000 s, at least 251 origins per segment at the largest lag, 30% of paragliders and 38% of hang gliders available at 10 s. The measured duration-selection shift in H, about 2%, is the cost.
23. Appendix: velocity and directional memory.
24. Appendix: bootstrap confidence intervals and limitations.
25. Flight, terrain, map and analysis sources with clickable links.

Numerical estimates retain their archived confidence intervals. A marginal comparison pools
other characteristics; a stratified comparison fixes a selected category.
Neither is a controlled OFAT experiment. Unequal factor frequencies and
interactions in H are distinguished. The factorial implementation remains under
review in Experimentals; this deck motivates it without presenting its results.

Questions guide slides 7–13 and appendix slides 21–22, where the audience needs
an explicit comparison to interpret the evidence. Their titles state the question,
while plots and conclusions supply the answer. Definitions and the factorial model retain topic titles.

The conditional sequence follows observations → composition → stratification →
spatial evidence → physical interpretation → joint analysis. Visible conclusions
explain what each result implies; notes retain the statistical qualifications and
presentation transitions. Slide 18 emphasises the observed increase in spatial
spread with height in P1 relative to the persistent slope-and-ridge concentration in H2.

## Rebuild

From the repository root, using its existing Python environment and TeX install:

```bash
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_figures.py
python3 presentations/offsite2026/build.py
```

Slide 6 keeps C10000 as its parent population and its selected segment identities.
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
VECLIB_MAXIMUM_THREADS=2 .venv/bin/python presentations/offsite2026/measure_open_circuits.py
```

The deck reads the current source counters and two existing vector figures from
`thesis/generated`; the report-based figures are local to `assets/`. The altitude-composition plot compares flight shares with shares of the class MSD at 10^4 s
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

## Regional climb-use maps (appendix slides 23–24)

The Pyrenees map shows the full Atlantic-to-Mediterranean chain in a 450 × 220 km
view; the western Alpine view covers the same physical area. The two lowland
examples each cover 100 × 65 km. They use the exact
paraglider C10000 regional populations behind slide 12, including all available
dates and heights. Archived own-HMM climb intervals label the native cleaned
trajectory; edges cannot cross phase changes, preprocessing boundaries or gaps.
The viewer's `thermal_daily.lattice_points` routine intersects those edges with
horizontal planes at every 10 m of absolute GNSS altitude. Regional maps use this
common ASL lattice because an entire region has no single ground reference; the
viewer's small cells instead use their fixed local ground reference.

Every crossing contributes to its 1 km horizontal bin, including repeated
crossings by one flight. Both upward and downward crossings inside climb phases
are retained; shared vertices count once, terminal vertices are retained, and
horizontal coplanar edges are omitted. The map shows absolute crossings per km²,
with a 2 km Gaussian display smooth, an 8 km margin before cropping, and a common
logarithmic colour scale from 1 to 10,000 (higher counts saturate). A 500 m
monotonic ascent contributes approximately 50 points. Counts also reflect flight
exposure and vertical climb extent; those points are not independent thermals.
Slide 25 explains the four steps and the distinction between flights and crossings.
Transparent
density sits over OpenTopoMap relief and contours, whose topography derives from
OpenStreetMap and SRTM independently of the flight tracks. These are maps of
observed climb use, not direct maps of all thermals or a causal explanation of
regional H. Source counts, map extents, tile provenance and hashes are in
`assets/regional-climb/counts-report.json`.

With the SSD connected, rebuild them before compiling:

```bash
.venv/bin/python presentations/offsite2026/render_regional_climb_density.py
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_regional_climb_maps.py
```

The saved PDF maps allow deck compilation without the SSD.

## One plane in four regional cells (slide 11)

Each regional box of the $H$ comparison contributes the 10 km Lambert-93 cell
(2 × 2 viewer cells) lying wholly inside it and crossed by the most distinct
flights in the viewer census, over all dates and both disciplines. One horizontal
plane per cell sits at the mean IGN RGE ALTI terrain of the cell plus 600 m, the
average of its four 5 km viewer references; it is not terrain-following.
Crossings use the viewer's explorer: census visitors of each 5 km cell, own-HMM
climb edges from the published snapshot or decoded into `thermal-climbs.sqlite3`,
and `plane_intersections` at that absolute altitude. Relief is shaded with one
fixed light and no per-panel contrast stretch, so the plains look as flat as they
are; brown marks terrain above the plane.

The concentration under each map is the share of 250 m squares holding half of
the first crossings of 500 flights drawn per cell (all 500 in Champagne-Lorraine),
with uniform points as the reference. The mountain-lowland ranking holds at 100
and 250 m; at 500 m Champagne-Lorraine ties the Alps and at 1 km only the Channel
Coast stays wider (`plane-cells-concentration.json`). `plane-cells-report.json`
also records how far the contributing flights started from each cell's densest
spot: the lowland and Pyrenean hotspots are near launch, the Alpine one is not.

With the SSD connected and internet for IGN terrain:

```bash
.venv/bin/python presentations/offsite2026/measure_plane_cells.py
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_plane_cells.py
```

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

The schematic on slide 10 is `assets/thermal-mechanism.pdf`, drawn by
`render_thermal_mechanism.py` from an analytic ridge and a hand-placed lowland
layout; it contains no data. Mountain thermals start from upslope flow that
follows the terrain gradient along sun-facing spurs and leave from the crest, so
their pattern traces the relief. Lowland thermals are weaker and vertical, over a
ploughed fields, a quarry, a car park, a warehouse roof and a village,
placed irregularly; one heated field releases none. Wavy lines are ascent cues,
not measured rotation.
The earlier AI-generated `thermal-mechanism-3d`, `thermal-landscapes` and 2D
`thermal-mechanism-schematic` drafts are unused.

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
