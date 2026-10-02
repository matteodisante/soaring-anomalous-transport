"""Quick reference for viewer counts, methods and sources.

Configuration values come from the modules that use them. The per-tab Info panels
hold the longer explanations.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from ...analysis.segmentation.config import load_segmentation_config
from .. import thermal_regions
from ..geography import TERRAIN_BANDS
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
        ("tab-planes", "Thermal planes"),
        ("thermal-points", "Intersections"),
        ("tab-density", "Thermal density"),
        ("tab-trajectory", "Trajectory"),
        ("tab-map", "Map"),
        ("sources", "Data sources"),
        ("maps", "Background maps"),
        ("caveats", "Limitations"),
    ]
    links = " &nbsp;·&nbsp; ".join(
        f'<a href="#{key}">{label}</a>' for key, label in entries
    )
    return f'<a name="contents"></a><h2>Sources &amp; methods</h2><p>{links}</p>'


def _sources() -> str:
    return f"""
<a name="sources"></a><h3>Data sources</h3>
<table border="1" cellspacing="0" cellpadding="6" width="100%">
<tr><th>Source</th><th>Used for</th></tr>
<tr><td>FFVL CFD:
<a href="{FFVL_PARAGLIDING}">paragliders</a> /
<a href="{FFVL_HANG_GLIDING}">hang gliders</a></td>
<td>IGC positions, GNSS altitudes and times. The catalogue helps find flights.</td></tr>
<tr><td><a href="{RGE_ALTI_URL}" title="{DEM_LAYER}">IGN RGE ALTI</a><br>
<a href="{LICENCE_OUVERTE}">Licence Ouverte 2.0</a></td>
<td>Mean terrain elevation for cell categories and plane heights.</td></tr>
<tr><td><a href="{NATURAL_EARTH}">Natural Earth</a> (public domain)</td>
<td>Coastlines and borders in Map and regional density views.</td></tr>
</table>
<p>Prepared maps and thermal products are read offline from the SSD. Saved map and
elevation metadata record the source request and retrieval date; elevation rasters
also carry a SHA-256 hash.</p>
"""


def _maps() -> str:
    products = {
        "colour": ("Colour map", "Plan IGN v2"),
        "aerial": ("Aerial photo", "BD ORTHO"),
        "topography": ("Topography + contours", "Plan IGN v2 + elevation contours"),
    }
    rows = "".join(
        f'<tr><td>{name}</td><td><a href="{IGN_WMS}" '
        f'title="{LAYERS[kind]}">{product}</a></td></tr>'
        for kind, (name, product) in products.items()
    )
    pixel = CELL_M / 4000
    return f"""
<a name="maps"></a><h3>Background maps</h3>
<table border="1" cellspacing="0" cellpadding="6" width="100%">
<tr><th>Viewer layer</th><th>Source</th></tr>
{rows}
<tr><td>Shaded relief</td>
<td><a href="{HILLSHADE_URL}">Esri World Hillshade</a> and data contributors</td></tr>
</table>
<p>IGN maps: © IGN / Géoplateforme,
<a href="{LICENCE_OUVERTE}">Licence Ouverte 2.0</a>.
Cell images: 4000 &times; 4000 pixels ({pixel:g} m/pixel); hillshade: 600 &times; 600.
Regional images: 4000 pixels wide. Pixel size describes sampling, not accuracy.
Aerial acquisition dates appear below the controls and differ from flight dates.</p>
"""


def _trajectory_tab() -> str:
    return """
<a name="tab-trajectory"></a><h3>Trajectory</h3>
<ul>
<li><b>Raw:</b> IGC fixes and GNSS altitude, dashed grey. Triangle = first fix;
square = last fix. Recording gaps stay empty.</li>
<li><b>Cleaned:</b> the selected IGC is processed again with the current
configuration.</li>
<li><b>Colours:</b> flight phase, preprocessing segment or discipline. Lines stop at
segment boundaries, phase changes and gaps longer than 1.5 times the segment's
median interval.</li>
<li><b>Thermals only:</b> climb fixes. The title counts separate climb runs and sums
their durations (last minus first fix).</li>
</ul>
"""


def _map_tab() -> str:
    return f"""
<a name="tab-map"></a><h3>Map</h3>
<p>One launch per retained flight: its first free-flight fix after ground trimming.</p>
<ul>
<li><b>Density:</b> launches per degree-grid cell, logarithmic colour scale.
Cell width = max({_MIN_CELL_DEG:g}&deg;, visible longitude span /
{_TARGET_CELLS_ACROSS}); recalculated on zoom or pan.</li>
<li><b>Points:</b> hover or click individual flights when at most
{_SCATTER_MAX_POINTS:,} launches are visible.</li>
<li><b>Filters:</b> Region requires a launch inside its box;
Terrain uses launch altitude.
The altitude bands are the same as <a href="#tab-planes">Thermal planes</a>,
where categories use mean ground elevation instead.</li>
</ul>
"""


def _planes_tab() -> str:
    cell_km = int(CELL_M // 1000)
    grid = int(DEM_WINDOW["grid_m"])
    samples = int(CELL_M // grid) ** 2
    lo, mid, hi = (int(b[2]) for b in TERRAIN_BANDS[:3])
    return f"""
<a name="tab-planes"></a><h3>Thermal planes</h3>
<ol>
<li><b>Grid:</b> divide the metropolitan-France map window into fixed
{cell_km} &times; {cell_km} km squares in Lambert-93 (EPSG:2154).</li>
<li><b>Count climbs:</b> continuous <b>Vilpellet climb runs</b> from eligible processed
flights, over all dates and both disciplines. Each run counts once per cell,
including re-entry; separate runs from one flight count separately.
Take-off can be elsewhere.</li>
<li><b>Select:</b> the <b>three cells with most climbs in each terrain category</b>
(12 total). Categories use mean IGN ground elevation over the whole cell.</li>
</ol>
<p><b>Mean terrain bands:</b> Plains &lt; {lo} m · Hills {lo}&ndash;&lt;{mid} m ·
Low mountains {mid}&ndash;&lt;{hi} m · High mountains &ge; {hi} m.<br>
These describe elevation, not slope. There is no regional quota: a low alpine valley
can qualify as Plains.</p>
<p>Selection stays fixed when changing dates, height or segmentation method;
the ranking always uses Vilpellet. Gaps and phase boundaries are never bridged.
Duration and number of fixes add no weight.</p>
<table border="1" cellspacing="0" cellpadding="6" width="100%">
<tr><th>Count</th><th>Meaning</th></tr>
<tr><td>Vilpellet climbs</td><td>Continuous climb runs used to rank the cell.</td></tr>
<tr><td>Cell visitors</td><td>Distinct flights crossing the cell, any phase or
altitude.</td></tr>
<tr><td>Visible points</td><td>Climb crossings of the selected plane in the visible
area and time interval. One flight can contribute several.</td></tr>
<tr><td>Contributing flights</td><td>Distinct flights behind those visible
points.</td></tr>
</table>

<a name="thermal-points"></a><h3>Intersection points</h3>
<p><b>Plane altitude H = mean terrain + selected z.</b> The terrain mean uses
{samples:,} IGN samples per cell, spaced {grid} m apart, with complete valid coverage.
Height is relative to this cell mean, not the ground beneath each dot.</p>
<ul>
<li><b>A dot</b> is where the segment between consecutive climb-labelled fixes crosses
H, interpolating position and time linearly. Labels come from the selected method
applied to the whole processed flight; gaps and phase boundaries stay separate.</li>
<li><b>Crossings:</b> both upward and downward within a climb run. Shared vertices
count once; horizontal edges are skipped. Dots are coloured by discipline.</li>
<li><b>Height increment:</b> spacing between selectable planes. Intersections are
prepared every 10 m plus the highest level; each plane has zero thickness.</li>
<li><b>Neighbours:</b> their flights use the selected cell's same absolute plane H.</li>
<li><b>Daily panels:</b> Paris time, by default 08&ndash;11, 11&ndash;15 and
15&ndash;18 (end excluded). The default day is the busiest June&ndash;August day.</li>
</ul>
<p><b>Many climbs can yield few dots:</b> only climbs crossing this exact height,
inside the displayed area and time interval, contribute. Open <b>Thermal planes →
Info</b> for the interpolation formula and worked example.</p>
"""


def _density_tab() -> str:
    fine = thermal_regions.FINE_DEG
    seg = load_segmentation_config()
    return f"""
<a name="tab-density"></a><h3>Thermal density</h3>
<table border="1" cellspacing="0" cellpadding="6" width="100%">
<tr><th>View</th><th>Points counted</th><th>Interpretation</th></tr>
<tr><td>Regions</td><td>HMM climb decisions, one every {seg.decision_step_s:g} s;
all heights. Flights must launch inside the region's box.</td>
<td>Time spent climbing. Finest bins: {fine:g}&deg;; coarser when zoomed out.</td></tr>
<tr><td>Cells</td><td>Plane intersections pooled across 10 m height levels,
using the selected segmentation and all dates.</td>
<td>More height levels crossed = more points. Bins: multiples of 10 m,
about 150 across the view.</td></tr>
</table>
<p>Counts are points, not distinct thermals or flights. Colours use a logarithmic scale
from 1 to the visible maximum; empty bins are transparent. Each panel rescales on zoom,
so compare counts rather than colours across panels. Open <b>Thermal density → Info</b>
for binning details.</p>
"""


def _caveats() -> str:
    return """
<a name="caveats"></a><h3>Limitations</h3>
<ul>
<li><b>Altitude:</b> recorder GNSS datums are not harmonised with IGN normal heights;
height above the terrain mean retains this uncertainty.</li>
<li><b>Interpolation:</b> straight segments approximate curved flight paths;
error increases with fix spacing and curvature.</li>
<li><b>Thermals:</b> climb labels and intersection dots do not identify thermal
centres.</li>
</ul>
<p><a href="#contents">Back to contents</a></p>
"""


def sources_html() -> str:
    """The full page; thresholds come from the configuration and the code."""
    return "".join(
        (
            _contents(),
            _planes_tab(),
            _density_tab(),
            _trajectory_tab(),
            _map_tab(),
            _sources(),
            _maps(),
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
