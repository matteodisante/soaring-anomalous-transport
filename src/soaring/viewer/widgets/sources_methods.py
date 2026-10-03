"""Quick reference for viewer data sources, counts and methods."""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ...analysis.segmentation.config import load_segmentation_config
from ..geography import TERRAIN_BANDS
from ..thermal_geometry import CELL_M
from ..thermal_imagery import SERVICE as IGN_WMS
from ..thermal_ridges import DATASET_URL as RGE_ALTI_URL
from ..thermal_ridges import LAYER as DEM_LAYER
from ..thermal_ridges import PARAMETERS as DEM_WINDOW
from .info_browser import info_browser
from .map_view import _MIN_CELL_DEG, _SCATTER_MAX_POINTS, _TARGET_CELLS_ACROSS
from .source_notes import (
    FLIGHT_SOURCE_HTML,
    LICENCE_OUVERTE,
    NATURAL_EARTH,
    NATURAL_EARTH_WORLD,
    aerial_dates_html,
    background_sources_html,
)


def _contents() -> str:
    entries = [
        ("sources", "Data sources"),
        ("maps", "Background maps"),
        ("tab-planes", "Thermal planes"),
        ("thermal-points", "Intersections"),
        ("tab-density", "Thermal density"),
        ("tab-trajectory", "Trajectory"),
        ("tab-map", "Map"),
        ("caveats", "Limitations"),
    ]
    links = " &nbsp;·&nbsp; ".join(
        f'<a href="#{key}">{label}</a>' for key, label in entries
    )
    return f'<a name="contents"></a><h2>Sources &amp; methods</h2><p>{links}</p>'


def _sources() -> str:
    grid = int(DEM_WINDOW["grid_m"])
    samples = int(CELL_M // grid) ** 2
    return f"""
<a name="sources"></a><h3>Data sources</h3>
<table border="1" cellspacing="0" cellpadding="8" width="100%">
<tr><th width="28%">Source / data</th><th>Where and why</th></tr>
<tr><td>{FLIGHT_SOURCE_HTML}<br>IGC recordings</td><td>
<b>Trajectory:</b> recorded positions, GNSS altitudes and times for raw / cleaned
comparison.<br>
<b>Map:</b> first retained free-flight fix for each launch location.<br>
<b>Thermal planes:</b> climb paths and plane crossings.<br>
<b>Thermal density:</b> paths and elapsed time for climb hours/km².
</td></tr>
<tr><td>FFVL CFD<br>XML catalogue</td><td>
<b>Flight picker:</b> IDs, pilot names and catalogue metadata to find recordings.
IGC links associate each entry with its flight file; calendar timing comes
from the IGC recording.</td></tr>
<tr><td><a href="{RGE_ALTI_URL}" title="{DEM_LAYER}">IGN RGE ALTI</a><br>
Ground elevations</td><td><b>Thermal planes:</b> mean ground elevation sets
the terrain category and reference for H = mean terrain + z.
Each cell uses {samples:,} samples at {grid} m spacing.<br>
<b>Thermal density → Cells:</b> reuses this terrain-based cell selection.</td></tr>
<tr><td>Natural Earth<br>
<a href="{NATURAL_EARTH_WORLD}">1:50 million</a> /
<a href="{NATURAL_EARTH}">1:10 million</a><br>
Admin-0 country polygons</td><td><b>Map</b> and <b>Thermal planes overview:</b>
coastlines and borders at 1:50 million and 1:10 million respectively,
to locate launches and selected cells.
They provide geographic context; region filters use rectangular bounds.</td></tr>
</table>
<p><b>Derived here:</b> cleaned trajectories, HMM / Vilpellet phase labels,
cell rankings, crossings and time grids. These are computed from the archive.</p>
"""


def _maps() -> str:
    return f"""
<a name="maps"></a><h3>Background maps</h3>
{background_sources_html()}
{aerial_dates_html()}
<ul>
<li><b>Thermal planes:</b> saved IGN cell images, 4000 &times; 4000 pixels
({CELL_M / 4000:g} m/pixel); hillshade 600 &times; 600. Prepared maps and
crossings are read offline from the SSD.</li>
<li><b>Thermal density:</b> reuses suitable cell images or requests the current
view online, up to 2048 pixels per side and down to 1.25 m/pixel.
Cached views work offline while retained in the 512 MiB cache.</li>
<li><b>Traceability:</b> IGN image and elevation metadata retain source requests
and retrieval dates; elevation rasters also have SHA-256 hashes.</li>
</ul>
<p>IGN images are served by <a href="{IGN_WMS}">Géoplateforme WMS</a>.
© IGN, <a href="{LICENCE_OUVERTE}">Licence Ouverte 2.0</a>.
Natural Earth: public domain. Hillshade: Esri and data contributors.</p>
"""


def _trajectory_tab() -> str:
    return """
<a name="tab-trajectory"></a><h3>Trajectory</h3>
<ul>
<li><b>Raw:</b> IGC fixes and GNSS altitude, dashed grey.
Triangle = first fix; square = last. Recording gaps stay empty.</li>
<li><b>Cleaned:</b> selected IGC reprocessed with the current configuration.</li>
<li><b>Colours:</b> phase, preprocessing segment or discipline. Lines stop at
segment / phase boundaries and gaps &gt; 1.5 times the segment's median interval.</li>
<li><b>Thermals only:</b> climb fixes. The title counts climb runs and sums
their durations (last minus first fix).</li>
</ul>
"""


def _map_tab() -> str:
    return f"""
<a name="tab-map"></a><h3>Map</h3>
<p>One launch per retained flight: its first free-flight fix after ground trimming.</p>
<ul>
<li><b>Density:</b> launches per degree-grid cell, logarithmic colours.
Cell width = max({_MIN_CELL_DEG:g}&deg;, visible longitude span /
{_TARGET_CELLS_ACROSS}); updates on zoom and pan.</li>
<li><b>Points:</b> hover or click flights when at most
{_SCATTER_MAX_POINTS:,} launches are visible.</li>
<li><b>Region:</b> launch inside the selected box. <b>Terrain:</b> launch altitude,
using the Thermal planes elevation bands. Thermal planes applies them to mean ground
elevation instead.</li>
</ul>
"""


def _planes_tab() -> str:
    cell_km = int(CELL_M // 1000)
    lo, mid, hi = (int(b[2]) for b in TERRAIN_BANDS[:3])
    return f"""
<a name="tab-planes"></a><h3>Thermal planes</h3>
<ul>
<li><b>Selection:</b> fixed {cell_km} &times; {cell_km} km Lambert-93 squares;
three per terrain category with the most continuous Vilpellet climb runs.
All archived dates and both disciplines contribute.</li>
<li><b>Counting:</b> each run counts once per visited cell, including re-entry.
Separate runs from one flight count separately. Gaps and phase boundaries stay
separate; duration adds no weight.</li>
<li><b>Categories:</b> Plains &lt; {lo} m; Hills {lo}&ndash;&lt;{mid} m;
Low mountains {mid}&ndash;&lt;{hi} m; High mountains &ge; {hi} m.
These are mean-elevation bands. No regional quota.</li>
<li><b>Fixed ranking:</b> dates, height and displayed segmentation do not change
the selected cells. Cell visitors counts distinct flights, any phase or altitude.</li>
</ul>
<a name="thermal-points"></a><h3>Intersection points</h3>
<ul>
<li><b>Plane:</b> H = cell mean terrain + selected z; zero thickness.
Height increment sets the spacing between selectable planes.</li>
<li><b>Dot:</b> a linearly interpolated crossing between consecutive climb fixes,
at H and within the visible area and time interval. Upward and downward crossings
count; shared vertices count once; horizontal edges are skipped.</li>
<li><b>Counts:</b> one flight can add several dots; contributing flights counts
unique flights. Neighbours use the central cell's same absolute H.</li>
<li><b>Time:</b> Europe/Paris. Daily panels default to 08&ndash;11, 11&ndash;15,
15&ndash;18, end excluded. Default day: busiest June&ndash;August day.</li>
</ul>
<p>Formulas and examples: <b>Thermal planes → Info</b>.</p>
"""


def _density_tab() -> str:
    return f"""
<a name="tab-density"></a><h3>Thermal density</h3>
<ul>
<li><b>Measure:</b> cumulative climb hours / ground area in km².
Linear climb edges split their elapsed time across 50 &times; 50 m pixels.</li>
<li><b>Coverage:</b> all dates, heights and both disciplines; take-off can be
elsewhere. Regions use HMM decisions (one every
{load_segmentation_config().decision_step_s:g} s); cells use HMM or Vilpellet.</li>
<li><b>Reading:</b> logarithmic colours. Zero is transparent; unvisited places
and observed places with no climb time look the same. Values depend on flight
coverage and are neither probabilities nor annual rates.</li>
</ul>
<p>Calculation and example: <b>Thermal density → Info</b>.</p>
"""


def _caveats() -> str:
    return """
<a name="caveats"></a><h3>Limitations</h3>
<ul>
<li><b>Altitude:</b> recorder GNSS datums are not harmonised with IGN normal heights.
z measures height above the cell mean; local terrain clearance varies.</li>
<li><b>Interpolation:</b> straight segments approximate curved flight paths;
error grows with fix spacing and curvature.</li>
<li><b>Thermals:</b> climb labels and crossings do not identify thermal centres.</li>
<li><b>Backgrounds:</b> pixel spacing is sampling, not positional accuracy.
Photo acquisition dates differ from flight dates.</li>
</ul>
<p><a href="#contents">Back to contents</a></p>
"""


def sources_html() -> str:
    """Build the reference page, with data sources before tab summaries."""
    return "".join(
        (
            _contents(),
            _sources(),
            _maps(),
            _planes_tab(),
            _density_tab(),
            _trajectory_tab(),
            _map_tab(),
            _caveats(),
        )
    )


class SourcesMethods(QWidget):
    """A read-only page with a table of contents; built on first display."""

    def __init__(self, parent: QWidget | None = None):
        """Create an empty browser; reading configs waits for the tab to open."""
        super().__init__(parent)
        self._browser = info_browser(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._browser)

    def ensure_loaded(self) -> None:
        """Fill the page the first time the tab is shown."""
        if not self._browser.toPlainText():
            self._browser.setHtml(sources_html())
