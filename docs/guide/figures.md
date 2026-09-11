# Figure conventions

Scientific figures are vector PDFs. Draw them at the size used in the manuscript:
full text width is approximately 6.1 inches. Shrinking a wide canvas after export also
shrinks its labels. A panel grid should therefore be designed at its final width,
with enough height for axes, legends and captions.

The shared definitions are in `src/soaring/reporting/style.py`. `paper_style()` sets
Matplotlib typography without affecting numerical estimators. The discipline colours
are also exposed through `soaring.reporting.DISCIPLINES`.

Colour is a variable, so each comparison owns a set and no two comparisons share a
value. Choose a colour by importing the set, never by writing a hex literal at the
call site; `tests/reporting/test_palette.py` fails the build otherwise.

| Comparison | Colours | Set |
|---|---|---|
| Paragliders / hang gliders | Blue `#3477A8` / terracotta `#B5482A` | `DISCIPLINE_COLORS` |
| Beginners (EN A/B) / experts (EN C/D/CCC) | Violet `#6A3D9A` / ochre `#C98A1E` | `EQUIPMENT_COLORS` |
| Alps / Pyrenees / Massif Central / Channel Coast | Wine / brown / sage / teal | `REGION_COLORS` |
| Transition / search / climb | Teal `#2E7D8A` / plum `#A9629E` / green `#4E8A5B` | `PHASE_COLORS` |
| Horizontal / barometric / GNSS channel | Neutral / teal / plum | `CHANNEL_COLORS` |
| East / north / radius | Teal / plum / neutral | `COMPONENT_COLORS` |
| Displacement quantiles | An ordered ramp, empirical and explanatory plots alike | `QUANTILE_COLORS` |

The discipline pair and the equipment pair are reserved for the whole document.
Chapter 3 sets those two comparisons side by side, so an equipment split wearing the
discipline colours would be read as a discipline split. Nothing else may use those
five values. The remaining sets avoid them and are internally distinct; they may sit
in neighbouring hue bands, because no figure and no chapter shows two of them at once.

A curve that is not a population takes `ILLUSTRATION_COLORS`: the limbs of an
analytic illustration, the input and output of a filter, what a cleaning rule keeps
against what it marks. A panel holding a single series carries no comparison and is
drawn in `TRACE_COLOR`. Parts of one stacked total take `STACK_GREYS` and nested
sampling controls take `CONTROL_GREYS`, because a ramp says "more of the same
quantity" where a categorical set would suggest unrelated groups.

TikZ diagrams keep the document accents `figblue`, `figred` and `figgreen` for
coordinate frames, processing levels and similar structural labels. Those are not
populations, and the word they label is always beside them.

Line styles distinguish comparisons within a discipline, such as open versus closed
tasks or first versus second differences. The experience labels refer to the declared
wing-class proxies; they are not individual skill measurements. Analytical
illustrations are identified as such and are never presented as empirical
measurements.

Axis labels give the quantity and units. Time since launch and within-flight lag are
different variables. Bands must state whether they describe between-flight variability,
bootstrap percentiles or another quantity. Pointwise bootstrap bands are not simultaneous
confidence bands. A histogram whose display clips the tail retains its full finite-sample
denominator, unless its caption explicitly defines a conditional distribution.

The visual reference is the east--north second-moment ratio figure in Chapter 3:
muted colours, thin curves, light uncertainty bands, boxed axes with all four spines, a
pale major grid, a frameless legend inside the axes, left-set panel titles and sentence-case
axis labels carrying units in square brackets. Use linear ratio axes where they expose the
deviations around unity clearly, with separate limits for position, velocity and acceleration.

Hand-drawn schematics in the manuscript follow the same reference. `main.tex` loads DejaVu
Sans and `sansmath` and defines `\figfont`, so a TikZ picture opened with the `schematic`
style sets its text and its mathematics in the face the plots use, at the size they print
at. The companion styles `fig axis`, `fig grid`, `fig rule`, `fig tick`, `fig note`,
`fig label` and `panel title` carry the matching line weights, greys and label sizes. Draw a
schematic axis as a closed box with outward ticks, and place a panel title above its panel,
flush left. `\figfont` belongs in a `font=` key, never in node text: `\sansmath` inside a
node's body stops TikZ's path parser.

Kinematic ratio plots show observed component second-moment ratios and paired flight
support. The 30-flight and 10-cluster display minima avoid drawing exceptionally sparse
points; they do not establish adequate precision. Coverage counts appear in legends.

Inspect the final PDF after regeneration. Check labels at printed size, legend overlap,
clipping, meaningful tick spacing, the visibility of reference lines and consistency
between each caption and the plotted estimator. A successful plotting command does not
perform that visual review.
