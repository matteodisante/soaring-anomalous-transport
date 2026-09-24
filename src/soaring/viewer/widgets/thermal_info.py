"""The Info panel of the Thermal planes tab: how its non-obvious numbers arise."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QTextBrowser, QVBoxLayout, QWidget

from ..geography import TERRAIN_BANDS
from ..thermal_geometry import CELL_M


def info_html() -> str:
    """The panel text; thresholds are read from the code that applies them."""
    lo, mid, hi = (int(b[2]) for b in TERRAIN_BANDS[:3])
    cell_km = int(CELL_M // 1000)
    return f"""
<h3>Cells</h3>
<p>Each cell is a {cell_km} x {cell_km} km square of a Lambert-93 grid. Its
population counts every <b>distinct flight that crosses it</b>, wherever the flight
started; a flight that returns counts once. Twelve cells are offered: the three
busiest in each category (P Plains, H Hills, L Low mountains, M High mountains).
Rank 1 is the busiest <i>within its category</i>. Population and ranking use all
dates and do not change with the selected interval or segmentation.</p>

<h3>Mean terrain elevation and its source</h3>
<p>The plane reference is the <b>area-weighted mean terrain elevation inside
the entire {cell_km} x {cell_km} km cell</b>. Source:
<a href="https://www.data.gouv.fr/datasets/rge-alti-r">IGN RGE ALTI</a>,
Licence Ouverte 2.0. Saved elevation rasters are sampled every <b>25 m</b>:
200 x 200 = <b>40,000 elevations per cell</b>. The mean uses the unsmoothed
elevations and excludes the 500 m buffer used to derive crests. Complete valid
terrain coverage is required. The source query, retrieval date, raster hash,
sampling and coverage are saved with the data. Sampling is distinct from
vertical accuracy; RGE ALTI's native product is finer than these extracts.</p>

<h3>Categories</h3>
<p>The existing cell selection uses the median screened GNSS launch altitude:
Plains &lt; {lo} m, Hills {lo}&ndash;{mid} m,
Low mountains {mid}&ndash;{hi} m, High mountains &ge; {hi} m. They are altitude
bands. Launch medians and their supporting counts are retained in cell details
for the ranking; the plane uses the DEM mean described above.</p>

<h3>The horizontal plane</h3>
<p><b>Plane altitude = mean terrain elevation + selected z.</b> Each cell has
one fixed reference; this is height above the cell mean, rather than clearance
above the terrain directly under a dot. The slider goes from 0 to the highest
supported trajectory altitude inside the cell minus the terrain mean.</p>
<p><b>Height increment</b> is the spacing between selectable planes (10, 20,
50, 100 or 200 m). Every plane has <b>zero thickness</b>. The viewer selects
precomputed exact intersections on a 10 m lattice, plus the exact highest level.
No altitude tolerance band or slab is used.</p>

<a name="thermal-points"></a>
<h3>How thermal points are calculated</h3>
<p><b>Each dot represents one intersection of a climb trajectory with the
selected horizontal plane.</b> The calculation follows these steps:</p>
<ol>
<li><b>Select continuous climb edges.</b> Take pairs of consecutive fixes in
the processed trajectory. Both fixes must be labelled <b>climb</b> by the selected
method (this work / HMM or Vilpellet), within the same continuous climb run.
Trajectory gaps and segment or phase boundaries are never bridged.</li>
<li><b>Set the absolute plane altitude.</b> Let H = mean terrain elevation of
the cell + selected z. For an edge with endpoint altitudes z<sub>0</sub> and
z<sub>1</sub>, compute the intersection fraction:<br>
<b>f = (H &minus; z<sub>0</sub>) / (z<sub>1</sub> &minus; z<sub>0</sub>).</b><br>
An intersection must lie between the endpoints (0 &le; f &le; 1).
There is no extrapolation. Horizontal edges, including those lying in the plane,
are omitted because they have no isolated intersection.</li>
<li><b>Interpolate position and time.</b> Join the two fixes with a straight
segment and calculate:<br>
x = x<sub>0</sub> + f (x<sub>1</sub> &minus; x<sub>0</sub>)<br>
y = y<sub>0</sub> + f (y<sub>1</sub> &minus; y<sub>0</sub>)<br>
t = t<sub>0</sub> + f (t<sub>1</sub> &minus; t<sub>0</sub>).<br>
Here x and y are Lambert-93 coordinates and t is UTC time. Shared vertices of
adjacent nonhorizontal edges are counted once; terminal intersections are kept.
Both upward and downward intersections within a climb-labelled run are included.</li>
<li><b>Filter and display.</b> Keep intersections inside the selected
{cell_km} x {cell_km} km cell and the requested date/time interval. The daily
comparison additionally filters by the Paris hour band. Plot the horizontal
positions of intersections at <b>the selected plane only</b>, pooling all
selected flights and dates. Point colour identifies the flight discipline.</li>
</ol>
<p><b>Example:</b> for H = 1,000 m, consecutive climb fixes at 997 m and
1,003 m give f = 0.5: the dot is halfway between their positions and times.
Neither fix needs to be at 1,000 m. An edge entirely below or above H gives no dot,
even if it is close to the plane.</p>
<p>The intersections are prepared at 10 m height intervals and at the cell's exact
highest level. <b>Height increment changes the spacing of selectable planes,
not their thickness.</b> At a given z, the same intersections are shown regardless
of the increment used to reach it.</p>
<p><b>Reading the counts:</b> one flight can intersect the same plane several
times and contribute several dots. The number of points counts intersections;
the number of flights counts distinct contributing flights. Several dots can
belong to one thermal. No clustering or estimation of thermal centres is applied.</p>

<h3>Zoom and neighbouring cells</h3>
<p><b>Zoom +</b> and <b>Zoom -</b> change the visible width between 0.5 and
10 km. Use the toolbar's hand tool to drag the map; navigation is bounded to
the selected cell and its eight immediate neighbours. <b>Reset cell</b> restores
the central 5 x 5 km square. Zoom and pan are retained when changing the height
or background. The dashed square marks the selected cell.</p>
<p>When looking outside that square, the viewer loads <b>all flights crossing
each neighbouring cell</b> in the chosen time interval, including flights that
never crossed the central cell. Every visible point is intersected with the
<b>same absolute plane H = selected cell's mean terrain + z</b>. Neighbouring
terrain means do not tilt or step the plane. Counts of points and contributing
flights refer to the visible map area; the central cell's visitor count is
reported separately.</p>
<p>First exploration needs the processed flight archives and Internet access for
uncached IGN terrain and maps. Missing whole flights are labelled in the background
with the selected method, before spatial or temporal cuts. Products are cached on
the SSD and can be reused. Cancel stops loading without displaying a partial
neighbourhood. The twelve ranked cells remain available from the standalone file.</p>

<h3>Trajectory source and vertical datum</h3>
<p>Trajectories are processed <b>FFVL Coupe Fédérale de Distance IGC recordings</b>
for paragliders and hang gliders. Flight heights use the recorder's GNSS altitude
field. The selected method supplies climb labels, and positions and times of
crossings are interpolated from consecutive climb fixes. IGN supplies normal
terrain heights; the geoid/ellipsoid convention in the IGC files is not harmonised
across recorders. The displayed height difference retains that vertical datum
uncertainty.</p>

<h3>Time</h3>
<p>Dates and hours are Europe/Paris local time. The UTC time of a flight is
recovered from the raw IGC header date and first fix, plus the offset removed by
trimming. Flights without a recoverable UTC stay in the cell population but cannot
enter a calendar interval. Morning / midday / afternoon panels use half-open hour
bands at the same z. The default reference day is the busiest June&ndash;August
day of the cell.</p>

<h3>Backgrounds</h3>
<p><b>Topography + contours &middot; IGN</b> combines Plan IGN with the official
<a href="https://www.data.gouv.fr/datasets/courbes-de-niveau-4">IGN elevation
contours</a>, via the WMS layers GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2 and
ELEVATION.CONTOUR.LINE. The IGN colour map and BD ORTHO aerial photographs are
also available, together with Esri World Hillshade. IGN cell maps are saved at
4,000 x 4,000 pixels (1.25 m/pixel); sampling does not imply metre-level map
accuracy. Background opacity starts at 85% and is adjustable. Attribution,
sampling and aerial acquisition dates appear below the controls.</p>
<h3>Estimated crests and official IGN data</h3>
<p><b>The red crest lines are our estimates from official IGN RGE ALTI elevations.</b>
They are optional and off initially. They use a 25 m DEM, 50 m Gaussian smoothing,
transverse height maxima, and drop/length thresholds. The raster's saved hash and
IGN source are checked before drawing. They are scale-dependent, can be fragmented
or misplaced, and have not been certified by IGN as ridge vectors.</p>
<p>The BD TOPO features named &ldquo;Crête&rdquo; in the queried IGN service are
toponymic points; they do not provide a continuous crest trace. Official elevation
contours describe equal-height lines and are labelled as contours. The terrain
mean is calculated from numerical elevations independently of these overlays.</p>
"""


class ThermalInfo(QDialog):
    """A non-modal, resizable reading panel."""

    def __init__(self, parent: QWidget | None = None):
        """Show the static text in a rich-text browser."""
        super().__init__(parent)
        self.setWindowTitle("Thermal planes: how things are computed")
        self.resize(560, 640)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(info_html())
        layout = QVBoxLayout(self)
        layout.addWidget(browser)
