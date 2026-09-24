# EconophysicsLab offsite 2026

**The statistics of soaring flight** — Matteo Di Sante.

25 slides total, including the cover, closing research agenda, thanks, appendices and sources, entirely in English. Scope: the current
thesis introduction and dataset chapter, then Sections 3.1 and 3.2 of
`thesis/tesi/04-fixed-transport.tex`, plus the requested qualitative comparison
in the thermal-plane viewer. Slide 5 alone covers preprocessing and the choice of C10000;
appendix slides 16–21 give the detail.
The palette and Palatino typography follow `presentations/theme.tex`. Header titles
are kept on one line; compilation rejects titles wider than 140 mm so the slide
number stays clear.

Key messages use bold Palatino in the existing steel-blue takeaway bands.
Two-line result bands distinguish the bold takeaway from supporting figures or
interpretation in regular weight, without introducing new emphasis colours.

Every empirical plot identifies the number of distinct flights in each plotted
category. Curve legends include `N`, each equipment contrast gives both group
sizes, and the thermal maps distinguish paraglider and hang-glider flights from
crossing counts. Cohort legends are discipline-specific. On slide 22, the legends
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
- `render_regional_climb_maps.py`: draws archived regional maps over OpenTopoMap terrain;
  full Pyrenees and western Alps use matched 450 × 220 km views, while the two
  lowland examples use matched 100 × 65 km views.
- `render_thermal_mechanism.py`: draws the slide-10 schematic of slope-bound
  mountain thermals against scattered lowland triggers.
- `render_thermal_panels.py`: exports earlier H2/P1 maps directly from the viewer's
  read-only prepared intersections and saved IGN colour maps, without screenshots.
- `render_cell_locators.py`: reproduces the appendix locator maps and exact cell
  coordinates from `plane-cells-report.json` and the archived regional basemaps.
  The slide gives WGS84 centres and exact Lambert-93 bounds, and links back to
  slide 11. Full-precision corner coordinates are in `cell-locator-report.json`.
- `measure_plane_cells.py`: finds the busiest 20 km cell in each regional box and
  intersects its own-HMM climbs with one plane 800 m above the cell's mean IGN
  terrain, through the viewer's explorer; writes `assets/plane-cells/`.
- `render_plane_cells.py`: draws the slide-11 maps and their equal-sample
  concentration from those saved files.
- `measure_plane_cell_animation.py`: intersects the same climb segments with
  seven planes from 200 to 1,400 m above each cell's mean terrain.
- `render_plane_cell_animation.py`: exports four GIFs and the PNG frames for
  slide 11's PDF animation.
- `measure_cadence_support.py`: measures the cadence-limited extension of C10000
  for slide 22; writes the portable `cadence-support-report.json`.
  It reads the SSD without changing
  the published thesis analysis. Large intermediate arrays stay in `build/`.
- `measure_open_circuits.py`: repeats the thesis regional and Experts-versus-Beginners
  contrasts (Sections 3.2.3–3.2.4) on open circuits only, with the same cohort,
  estimator, fit and archived paired draws; writes `open-circuits-report.json` and the
  macros in `open-circuits-values.tex`.
- `source-manifest.json`: source identities at the time of figure generation.

## Narrative

1. Title and seminar occasion, with Lake Maggiore, Isola dei Pescatori and the Alps.
2. The soaring flight cycle: landscape and phase schematic. Thermals let pilots cover long distances without an engine.
3. FFVL archive, coverage and metadata.
4. The MSD estimator: time averaging along each flight, then equal weighting across flights, beside Vilpellet et al. Figure 1. The equations are enlarged slightly, with the per-flight definition kept on one line.
5. From raw tracklogs to the fixed cohort C10000, with links to the preprocessing and cohort appendices.
6. Flight characteristics: circuit, launch-altitude class and wing class, and the distinction between marginal and stratified comparisons.
7. Open versus closed circuits: slower growth for return routes, linked to turns and returns.
8. The open–closed H gap depends on altitude. Mountain terrain constrains both circuit types and narrows their difference.
9. Regional comparisons: H separates the Alps and Pyrenees more clearly than Channel Coast and Champagne-Lorraine.
10. Schematic interpretation: mountain lift follows relief, while lowland triggers are scattered. This is an illustration without measured wind or airflow.
11. One combined thermal-plane slide: mountain lift follows ridges, lowland lift spreads aloft. Four animations begin at 800 m, reproducing the former static maps. Region names and reference flight counts sit above the maps; the lower band suggests easier thermal access aloft in lowlands and a possible connection to regional Hurst contrasts. There are no extra Mountains/Lowlands headings.
12. Experts-versus-Beginners contrasts on open circuits: higher H for Experts in every altitude class, related to the shorter search phase reported by Vilpellet et al.
13. Take-home messages: scaling, route and wing, terrain, and lift geography.
14. Work in progress: segmentation, stochastic models, anisotropy, distribution scaling, and solo versus group flight.
15. Thanks and discussion.
16. Appendix: GNSS and barometric channels, fix-level cleaning, airborne intervals.
17. Appendix: flight selection and geographic-to-local coordinates.
18. Appendix: short-gap interpolation and the uniform time grid.
19. Appendix: Savitzky–Golay smoothing and derivatives.
20. Appendix: changing flight support at long lags and the requirements for one fixed population.
21. Appendix: support and selection costs of C10000.
22. Appendix: displacement growth from 1 s to 10,000 s, with growing cadence support below 10 s and fixed support above it.
23. Appendix: bootstrap confidence intervals and limitations.
24. Appendix: exact locations of the four 20 km cells, with regional maps, WGS84 centres and Lambert-93 bounds.
25. Flight, terrain, map and analysis sources with clickable links.

Numerical estimates retain their archived confidence intervals. A marginal comparison pools
other characteristics; a stratified comparison fixes a selected category.
Neither is a controlled OFAT experiment. Unequal factor frequencies and
interactions in H are distinguished. The factorial implementation remains under
review in Experimentals; this deck motivates it without presenting its results.

Questions introduce the statistical comparisons. The thermal-plane title states its
spatial observations directly. Speaker notes keep the Hurst interpretation distinct
from a measured causal relationship or a thermal encounter probability.

## Rebuild

From the repository root, using its existing Python environment and TeX install:

```bash
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_figures.py
python3 presentations/offsite2026/build.py
```

The build validates each compiled PDF, replaces the delivered file atomically,
and leaves identical PDFs untouched. Preview and continuous-preview modes are
explicitly disabled.

### VS Code save dialog during refresh

`mathematic.vscode-pdf` 0.2.5 uses pdf.js, which treats `animate` frame visibility
changes as modified form annotations. Its automatic file refresh closes the old
document, and pdf.js tries to download those changes through macOS's Save dialog.
This is separate from the Python build.

`vscode-pdf-animation-reload.patch` fixes the extension's refresh handler. It
clears the modified flag only when every change is a visibility change on an
identified `animate` frame. Text annotations, form values and other edits retain
the viewer's normal save handling. The patch is installed locally; to reapply it
to the same extension version after reinstalling:

```bash
patch -p1 -d "$HOME/.vscode/extensions/mathematic.vscode-pdf-0.2.5" < presentations/offsite2026/vscode-pdf-animation-reload.patch
```

Close and reopen the PDF tab to load the updated handler. An extension update
may overwrite this local fix and needs a fresh compatibility check.

Slide 22 keeps C10000 as its parent population and its selected segment identities.
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
paraglider C10000 regional populations behind slide 9, including all available
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

## The 800 m reference plane (slide 11)

Each regional box of the $H$ comparison contributes the 20 km Lambert-93 cell
(4 × 4 viewer cells) lying wholly inside it and crossed by the most distinct
flights in the viewer census, over all dates and both disciplines. On the slide,
the plane is 800 m above the cell's mean IGN RGE ALTI terrain; the mean terrain
is the average of its sixteen 5 km viewer references. The mean-terrain values
are in the speaker notes. The plane is horizontal, not
terrain-following. Crossings use the viewer's explorer: census visitors of each
5 km cell, own-HMM climb edges from the published snapshot or decoded (in
parallel, once per flight) into `thermal-climbs.sqlite3`, and
`plane_intersections` at that absolute altitude. Relief is shaded with one
fixed light and no per-panel contrast stretch, so the plains look as flat as they
are; brown marks terrain above the plane.

The concentration check in the speaker notes is the share of 250 m squares holding
half of the first crossings of the same number of flights drawn per cell (as many as the
smallest cell holds: all 474 in Champagne-Lorraine), with uniform points as the
reference. At every square size from 100 m to 1 km only the Channel Coast is
wider; Champagne-Lorraine is about as compact as the mountain cells, so the
contrast the slide states is one of shape (`plane-cells-concentration.json`). `plane-cells-report.json`
also records how far the contributing flights started from each cell's densest
spot: the lowland and Pyrenean hotspots are near launch, the Alpine one is not.

With the SSD connected and internet for IGN terrain:

```bash
.venv/bin/python presentations/offsite2026/measure_plane_cells.py
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_plane_cells.py
```

## Height sweep in the same cells (slide 11)

The four maps cover 200 to 1,400 m above each cell's fixed mean terrain in
200 m steps. Playback starts at 800 m, continues through 1,000, 1,200 and
1,400 m, then wraps to 200, 400 and 600 m. Measurement arrays retain their
ascending height order; the renderer alone rotates the presentation sequence.
Frame `00` is the 800 m reference in every GIF, in the PDF's `poster=first`
image and in the speaker notes. Its crossing coordinates match the saved static
maps. The PDF plays PNG frames in viewers supporting `animate`; standalone GIFs
in `assets/plane-cells/` remain linked from the slide.

```bash
PYTHONPATH=src .venv/bin/python presentations/offsite2026/measure_plane_cell_animation.py
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_plane_cell_animation.py
```

## Archived viewer maps (H2 and P1)

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
above the viewer's fixed cell reference, rather than above local terrain. Contributing flights change with height. The earlier comparison highlighted the observed widening
of climb locations from 100 to 600 m in P1, while H2 remains concentrated near slopes and ridges.
This supports freer use of space aloft in the plains cell; its contribution to H
and generality across sites are not quantified.

The schematic on slide 10 is `assets/thermal-mechanism.pdf`, drawn by
`render_thermal_mechanism.py` from an analytic ridge and a hand-placed lowland
layout; it contains no data. Mountain thermals start from upslope flow that
follows the terrain gradient along sun-facing spurs and leave from the crest, so
their pattern traces the relief. Lowland thermals are weaker and vertical, over a
ploughed fields, a car park, a warehouse roof and a village,
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
