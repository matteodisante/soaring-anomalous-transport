"""The Sources & methods tab: where each dataset and map comes from, how plots are made.

One reference page for the whole viewer, separate from the per-tab Info panels. Every
number that a configuration file or a module constant owns is read from there, so the
text follows the code that applies it.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from ...analysis.segmentation.config import load_segmentation_config
from .. import thermal_regions
from ..geography import REGIONS, TERRAIN_BANDS
from ..thermal_geometry import CELL_M
from ..thermal_imagery import LAYERS
from ..thermal_imagery import SERVICE as IGN_WMS
from ..thermal_relief import SOURCE_URL as HILLSHADE_URL
from ..thermal_ridges import DATASET_URL as RGE_ALTI_URL
from ..thermal_ridges import LAYER as DEM_LAYER
from ..thermal_ridges import PARAMETERS as DEM_WINDOW
from .map_view import _MIN_CELL_DEG, _SCATTER_MAX_POINTS, _TARGET_CELLS_ACROSS

FFVL_PARAGLIDING = "https://parapente.ffvl.fr"
FFVL_HANG_GLIDING = "https://delta.ffvl.fr"
NATURAL_EARTH = "https://www.naturalearthdata.com/"
LICENCE_OUVERTE = "https://www.etalab.gouv.fr/licence-ouverte-open-licence/"


def _contents() -> str:
    entries = [
        ("sources", "Data sources"),
        ("maps", "Background maps"),
        ("tab-trajectory", "Trajectory tab"),
        ("tab-map", "Map tab"),
        ("tab-planes", "Thermal planes tab"),
        ("tab-density", "Thermal density tab"),
        ("caveats", "Known limitations"),
    ]
    sub = {
        "tab-planes": '<ul><li><a href="#thermal-points">How the intersection points '
        "are calculated</a></li></ul>"
    }
    items = "".join(
        f'<li><a href="#{key}">{label}</a>{sub.get(key, "")}</li>'
        for key, label in entries
    )
    return f"<h2>Sources and methods</h2><ul>{items}</ul>"


def _sources() -> str:
    cell_km = int(CELL_M // 1000)
    return f"""
<a name="sources"></a><h3>Data sources</h3>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>Data</th><th>Source</th><th>Used for</th></tr>
<tr><td>Flight tracks (IGC files) and flight catalogue</td>
<td>FFVL Coupe Fédérale de Distance:
<a href="{FFVL_PARAGLIDING}">parapente.ffvl.fr</a> (paragliders) and
<a href="{FFVL_HANG_GLIDING}">delta.ffvl.fr</a> (hang gliders)</td>
<td>Every trajectory, climb label and point in the viewer. The catalogue
(<i>catalog.csv</i>) only helps to find a flight; positions, altitudes and times always
come from the IGC file.</td></tr>
<tr><td>Coastlines and national borders</td>
<td><a href="{NATURAL_EARTH}">Natural Earth</a> admin-0 countries, public domain,
decimated into <i>data/basemap.json</i> by scripts/tools/build_basemap.py</td>
<td>Land/sea basemap of the Map tab and of the regional density maps</td></tr>
<tr><td>Terrain elevation</td>
<td><a href="{RGE_ALTI_URL}">IGN RGE ALTI</a>, WMS layer {DEM_LAYER} of the
Géoplateforme ({IGN_WMS}), float elevations,
<a href="{LICENCE_OUVERTE}">Licence Ouverte 2.0</a></td>
<td>Mean terrain of each {cell_km} x {cell_km} km cell
(category and plane reference)</td></tr>
<tr><td>Background maps</td><td>IGN Géoplateforme and Esri, listed in
<a href="#maps">Background maps</a></td><td>Thermal planes and Thermal density</td></tr>
</table>
<p>All prepared products (cell census, climb edges, intersections, images, elevation
rasters) are saved on the SSD by the scripts in scripts/pipeline/ and carry their
request URL, retrieval date and, for elevations, a SHA-256 hash of the raster. The
viewer reads them offline and makes no network request.</p>
"""


def _maps() -> str:
    names = {
        "colour": "Colour map · IGN",
        "aerial": "Aerial photo · IGN",
        "topography": "Topography + contours · IGN",
    }
    products = {
        "colour": "Plan IGN v2",
        "aerial": "BD ORTHO orthophotographs",
        "topography": "Plan IGN v2 with the official elevation contours",
    }
    rows = "".join(
        f"<tr><td>{names[kind]}</td><td>{products[kind]}</td>"
        f"<td>{LAYERS[kind].replace(',', ', ')}</td>"
        "<td>© IGN / Géoplateforme, Licence Ouverte 2.0</td></tr>"
        for kind in ("colour", "aerial", "topography")
    )
    pixel = CELL_M / 4000
    return f"""
<a name="maps"></a><h3>Background maps</h3>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>Viewer name</th><th>Product</th><th>Layer</th><th>Attribution</th></tr>
{rows}
<tr><td>Shaded relief</td><td>Esri World Hillshade</td>
<td><a href="{HILLSHADE_URL}">ArcGIS MapServer export</a></td>
<td>Esri World Hillshade and data contributors</td></tr>
</table>
<p>IGN images come from one WMS 1.3.0 GetMap request ({IGN_WMS}) per extent, in
Lambert-93 (EPSG:2154) for the cells and in longitude/latitude (CRS:84) for France and
the regional boxes. A cell image is 4000 x 4000 pixels, i.e. {pixel:g} m/pixel; a
regional image is 4000 pixels wide. Large topography requests are split into four tiles
at the same ground sampling and joined without resampling. The pixel size is a sampling
choice and does not imply map accuracy at that scale.</p>
<p>The aerial photographs are a mosaic of flights on different dates. For each cell the
acquisition dates are read from IGN's mosaic graph
(WFS layer ORTHOIMAGERY.ORTHOPHOTOS.GRAPHE-MOSAIQUAGE:graphe_bdortho, field date_vol)
and shown under the controls. They differ from the flight dates.</p>
<p>The hillshade is exported by the Esri service for the exact requested extent: 600 x
600 pixels per cell, 4000 pixels wide per region. The extent the service actually
returns is saved and used to place the image.</p>
"""


def _trajectory_tab() -> str:
    return """
<a name="tab-trajectory"></a><h3>Trajectory tab</h3>
<ul>
<li><b>Raw</b> (dashed grey): the B records of the IGC file with the GNSS altitude, with
real gaps left empty. The triangle and square mark the first and last recorded fix. In
the local frame the raw track is projected into the processed trajectory's own frame;
missing altitudes are interpolated only inside that projection, never displayed.</li>
<li><b>Cleaned</b>: the full pipeline is rerun on the selected IGC file with the current
configuration, so the plot reflects the code as it is now rather than the archive.
In the geographic frame E, N, z are converted back to latitude and longitude.</li>
<li><b>Colours.</b> By flight phase (the selected segmentation), by preprocessing
segment, or one colour per discipline. A line is never drawn across a segment boundary,
a gap longer than 1.5 times the segment's median interval, or a change of phase.</li>
<li><b>Thermals only</b> keeps the climb fixes. The title counts thermals as the number
of separate climb runs, and the minutes as the sum of each run's duration (last minus
first fix).</li>
</ul>
"""


def _map_tab() -> str:
    regions = ", ".join(REGIONS)
    lo, mid, hi = (int(b[2]) for b in TERRAIN_BANDS[:3])
    return f"""
<a name="tab-map"></a><h3>Map tab</h3>
<p>One point per flight kept by the pipeline: the launch position (lat0, lon0) is the
origin of its local frame, i.e. the first fix of free flight after ground trimming.
Flights dropped by a pipeline gate are not shown.</p>
<ul>
<li><b>Density.</b> The visible window is divided into square cells of
max({_MIN_CELL_DEG:g}&deg;, visible longitude span / {_TARGET_CELLS_ACROSS}) and the
launches in each cell are counted, on a logarithmic colour scale. The mesh is recomputed
after every zoom or pan.</li>
<li><b>Points.</b> With at most {_SCATTER_MAX_POINTS} launches in view, each flight is
drawn as a point that can be hovered or clicked.</li>
<li><b>Region filter</b> ({regions}): launch inside the region's longitude/latitude
box.</li>
<li><b>Terrain filter</b>: launch altitude alt0 in the bands of arXiv:2608.00241 Eq. 1,
Plains &lt; {lo} m, Hills {lo}&ndash;{mid} m, Low mountains {mid}&ndash;{hi} m, High
mountains &ge; {hi} m.</li>
<li>The aspect ratio is 1/cos(mean latitude of the view), so shapes are not stretched.
</li>
</ul>
"""


def _planes_tab() -> str:
    cell_km = int(CELL_M // 1000)
    grid = int(DEM_WINDOW["grid_m"])
    samples = int(CELL_M // grid) ** 2
    lo, mid, hi = (int(b[2]) for b in TERRAIN_BANDS[:3])
    return f"""
<a name="tab-planes"></a><h3>Thermal planes tab</h3>
<p><b>Cells.</b> Lambert-93 is cut into {cell_km} x {cell_km} km squares. The census
walks every processed flight in Lambert-93, splitting each step at the grid lines, so a
square crossed between two fixes also counts. Selection uses the number of continuous
<b>Vilpellet climb runs</b> intersecting each square, over all dates and both
disciplines.
One episode counts once per cell, including repeated entries; different episodes from
one flight count separately. Sample count and duration add no weight. Gaps and phase
boundaries are never bridged. Whole-flight eligibility guards remain active.
The three squares with most climbs in each category are selected during preparation.
This ranking remains Vilpellet-based when displaying HMM intersections. The separate
visitor count includes every flight phase and altitude. The category uses mean IGN
terrain
elevation over the entire square, also used as the plane reference: Plains
&lt; {lo} m, Hills {lo}&ndash;{mid} m, Low mountains {mid}&ndash;{hi} m, High mountains
&ge; {hi} m. These bands describe elevation, not slope or relief. Launch medians
are audit information only; cells without internal starts are eligible. The viewer
requires mean-terrain categories. Visitor-ranked snapshots identify their count as
cell visitors; prepare again to use the Vilpellet climb-run ranking. There is no
regional quota: a low alpine valley can qualify as Plains.</p>
<p><b>Plane reference.</b> The RGE ALTI elevations of the cell are sampled every
{grid} m ({samples:,} values per cell). The reference is their area-weighted mean over
the whole cell, unsmoothed, with complete valid coverage required. The plane altitude is
<b>H = mean terrain + z</b>, one fixed value per cell.</p>

<a name="thermal-points"></a><h4>How the intersection points are calculated</h4>
<p>Each dot is a point where a climbing trajectory crosses the horizontal plane H. The
trajectory between two recorded positions is <b>interpolated linearly</b>; no curve is
fitted through the climb.</p>
<ol>
<li><b>Trajectory.</b> The processed trajectory of the archive: cleaned, resampled at
its native interval (PCHIP in E and N, linear in altitude across short holes) and
smoothed by a cubic Savitzky&ndash;Golay filter (configs/preprocessing.yaml).
Positions are converted to Lambert-93 x, y; z is the smoothed GNSS altitude; t is UTC.
</li>
<li><b>Climb labels.</b> The whole flight is labelled by the selected segmentation
before any cut in space or time, so a climb that starts outside the cell keeps its
label.</li>
<li><b>Climb edges.</b> Two consecutive fixes form an edge when both are labelled climb,
they belong to the same segment and the same uninterrupted climb run, and they are at
most 1.5 times the segment's median interval apart. Gaps, segment boundaries and phase
changes are therefore never bridged.</li>
<li><b>Crossing fraction.</b> For an edge from (x<sub>0</sub>, y<sub>0</sub>,
z<sub>0</sub>, t<sub>0</sub>) to (x<sub>1</sub>, y<sub>1</sub>, z<sub>1</sub>,
t<sub>1</sub>):<br>
<b>f = (H &minus; z<sub>0</sub>) / (z<sub>1</sub> &minus; z<sub>0</sub>)</b><br>
The edge crosses the plane when 0 &le; f &lt; 1. The end vertex (f = 1) is kept only at
the last edge of a run, so a fix shared by two edges is counted once. Horizontal edges
(z<sub>0</sub> = z<sub>1</sub>) have no single crossing and are skipped. Nothing is
extrapolated beyond an edge.</li>
<li><b>Linear interpolation.</b><br>
x = x<sub>0</sub> + f (x<sub>1</sub> &minus; x<sub>0</sub>)<br>
y = y<sub>0</sub> + f (y<sub>1</sub> &minus; y<sub>0</sub>)<br>
t = t<sub>0</sub> + f (t<sub>1</sub> &minus; t<sub>0</sub>)<br>
Upward and downward crossings inside a climb run are both kept.</li>
<li><b>Height lattice.</b> The crossings are prepared offline for z = 0, 10, 20, ... m
and for the cell's highest supported level. The height increment only spaces the
selectable planes; every plane has zero thickness.</li>
<li><b>Filters and display.</b> A crossing is kept when x and y fall inside the cell
(west and south edges included, east and north excluded) and t inside the selected
interval. Dots are coloured by discipline; axes are km from the cell's south-west
corner.</li>
</ol>
<p><b>Example:</b> with H = 1,000 m and consecutive climb fixes at 997 m and 1,003 m,
f = 0.5 and the dot lies halfway between their positions and times.</p>
<p><b>Counts.</b> A flight can cross one plane several times. The point count counts
crossings; the flight count counts distinct flights. No clustering and no thermal-centre
estimate is applied.</p>
<p><b>Neighbouring cells</b> (Zoom &minus;). The eight surrounding squares are prepared
the same way from all the flights that cross them, on the same absolute plane H of the
selected cell; their own terrain means play no part.</p>
<p><b>Morning / midday / afternoon.</b> The crossings at the same z are split by Paris
clock hour into half-open bands, by default 08&ndash;11, 11&ndash;15 and 15&ndash;18.
The default reference day is the cell's busiest June&ndash;August day.</p>
"""


def _density_tab() -> str:
    factors = sorted(thermal_regions.FACTORS)
    levels = ", ".join(f"{thermal_regions.FINE_DEG * f:g}&deg;" for f in factors[1:])
    fine = thermal_regions.FINE_DEG
    seg = load_segmentation_config()
    return f"""
<a name="tab-density"></a><h3>Thermal density tab</h3>
<p><b>Regions</b> ({", ".join(thermal_regions.REGIONS)}). Only flights that launch
inside the box are used; the map frame extends {thermal_regions.PAD_DEG:g}&deg; beyond
it, so their points outside the box are drawn too. The points are the climb-labelled
decisions of <b>this work's HMM</b> (the segmentation selector applies to cells only),
one every {seg.decision_step_s:g} s. Their positions are the smoothed E, N, z linearly
interpolated at the decision times, converted to longitude and latitude. All heights are
pooled. The points are counted in bins of {fine:g}&deg; (about 111 m north&ndash;south
and 70&ndash;83 m east&ndash;west in France). Coarser levels ({levels}) are sums of
those bins; the viewer shows the coarsest level that still gives at least 1000 bins
across the visible width. A count measures time spent climbing, since a long climb
gives many points.</p>
<p><b>Cells.</b> The intersection points of the <a href="#thermal-points">Thermal planes
tab</a> at every 10 m level, pooled into one map, with the selected segmentation and all
dates. A climb crossing several planes gives one point on each, so a count is
proportional to the height climbed in the bin. Bins are multiples of 10 m, about 150
across the visible window.</p>
<p><b>Colours.</b> Logarithmic scale from 1 to the largest count in the visible window,
recomputed on zoom; empty bins are transparent. Each panel has its own scale.</p>
"""


def _caveats() -> str:
    return """
<a name="caveats"></a><h3>Known limitations</h3>
<ul>
<li>The GNSS altitude convention (geoid or ellipsoid) is not harmonised across
recorders, while IGN gives normal heights. Heights above the terrain mean carry this
datum uncertainty.</li>
<li>Linear interpolation between fixes replaces the true path by a chord; the error
grows with the interval between fixes and with the curvature of the climb.</li>
<li>The density maps count points, not thermals or flights.</li>
<li>Aerial photographs and maps are dated by their own acquisition, not by the
flights.</li>
</ul>
"""


def sources_html() -> str:
    """The full page; thresholds come from the configuration and the code."""
    return "".join(
        (
            _contents(),
            _sources(),
            _maps(),
            _trajectory_tab(),
            _map_tab(),
            _planes_tab(),
            _density_tab(),
            _caveats(),
        )
    )


class SourcesMethods(QWidget):
    """A read-only page with a table of contents; built on first display."""

    def __init__(self, parent: QWidget | None = None):
        """Create an empty browser; reading configs waits for the tab to open."""
        super().__init__(parent)
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._browser)

    def ensure_loaded(self) -> None:
        """Fill the page the first time the tab is shown."""
        if not self._browser.toPlainText():
            self._browser.setHtml(sources_html())
