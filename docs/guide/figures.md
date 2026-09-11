# Figure conventions

Scientific figures are vector PDFs. Draw them at the size used in the manuscript:
full text width is approximately 6.1 inches. Shrinking a wide canvas after export also
shrinks its labels. A panel grid should therefore be designed at its final width,
with enough height for axes, legends and captions.

The shared definitions are in `src/soaring/reporting/style.py`. `paper_style()` sets
Matplotlib typography without affecting numerical estimators. The discipline colours
are also exposed through `soaring.reporting.DISCIPLINES`.

| Meaning | Colour |
|---|---|
| Paragliders | Blue, `#3477A8` |
| Hang gliders | Terracotta, `#B5482A` |
| Transition / search / climb | Blue / orange / green, `PHASE_COLORS` |
| Alps / Pyrenees / Channel Coast | Terracotta / purple / blue, `REGION_COLORS` |
| Beginners (EN A/B) / experts (EN C/D/CCC), equipment-based proxies | Blue / terracotta, `EQUIPMENT_COLORS` |
| Displacement quantiles | The ordered palette in `QUANTILE_COLORS`, shared by empirical and explanatory plots |

Colours encode the variable named in the legend. Line styles distinguish comparisons
within a discipline, such as open versus closed tasks or first versus second differences.
The experience labels refer to the declared wing-class proxies; they are not individual
skill measurements. Analytical illustrations are
identified as such and are never presented as empirical measurements.

Axis labels give the quantity and units. Time since launch and within-flight lag are
different variables. Bands must state whether they describe between-flight variability,
bootstrap percentiles or another quantity. Pointwise bootstrap bands are not simultaneous
confidence bands. A histogram whose display clips the tail retains its full finite-sample
denominator, unless its caption explicitly defines a conditional distribution.

The visual reference is the original regional kinematics figure (formerly Figure 3.6):
muted colours, thin curves, light uncertainty bands, boxed axes and compact adjacent
panels. Use linear ratio axes where they expose the deviations around unity clearly,
with separate limits for position, velocity and acceleration.

Kinematic ratio plots show observed component second-moment ratios and paired flight
support. The 30-flight and 10-cluster display minima avoid drawing exceptionally sparse
points; they do not establish adequate precision. Coverage counts appear in legends.

Inspect the final PDF after regeneration. Check labels at printed size, legend overlap,
clipping, meaningful tick spacing, the visibility of reference lines and consistency
between each caption and the plotted estimator. A successful plotting command does not
perform that visual review.
