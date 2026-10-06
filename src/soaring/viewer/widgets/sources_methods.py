"""Quick reference for viewer data sources, counts and methods."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ...analysis.segmentation.config import load_segmentation_config
from ..thermal_geometry import CELL_M
from ..thermal_imagery import SERVICE as IGN_WMS
from ..thermal_ridges import DATASET_URL as RGE_ALTI_URL
from ..thermal_ridges import LAYER as DEM_LAYER
from ..thermal_ridges import PARAMETERS as DEM_WINDOW
from .info_browser import info_browser
from .screen_info import InfoButton
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
        ("views", "Screen summary"),
        ("sources", "Data sources"),
        ("maps", "Background maps"),
        ("tab-planes", "Thermal planes"),
        ("thermal-points", "Intersections"),
        ("tab-density", "Thermal density"),
        ("tab-trajectory", "Trajectory"),
        ("tab-map", "Map"),
        ("tab-routes", "Routes"),
        ("tab-3d", "3D terrain"),
        ("caveats", "Limitations"),
    ]
    links = " &nbsp;·&nbsp; ".join(
        f'<a href="#{key}">{label}</a>' for key, label in entries
    )
    return (
        '<a name="contents"></a><h2>Sources &amp; methods</h2>'
        "<p>A summary of the viewer. Each screen's <b>Info</b> button explains "
        "its calculation, controls and sources in detail.</p>"
        f"<p>{links}</p>"
    )


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
<b>Thermal density:</b> paths and elapsed time for climb hours/km².<br>
<b>Routes:</b> retained endpoints, cleaned paths and original IGC clocks.<br>
<b>3D terrain:</b> saved Vilpellet climb crossings.
</td></tr>
<tr><td>FFVL CFD<br>XML catalogue</td><td>
<b>Flight picker:</b> IDs, pilot names and catalogue metadata to find recordings.
IGC links associate each entry with its flight file; calendar timing comes
from the IGC recording.</td></tr>
<tr><td><a href="{RGE_ALTI_URL}" title="{DEM_LAYER}">IGN RGE ALTI</a><br>
Ground elevations</td><td><b>Thermal planes:</b> the highest ground elevation
sets the terrain category; the lowest sets the reference for H = lowest terrain + z.
Each cell uses {samples:,} samples at {grid} m spacing.<br>
<b>Thermal density → Cells:</b> reuses this terrain-based cell selection.<br>
<b>3D terrain / Routes:</b> terrain meshes, with the displayed sampling
resolution.</td></tr>
<tr><td>Natural Earth<br>
<a href="{NATURAL_EARTH_WORLD}">1:50 million</a> /
<a href="{NATURAL_EARTH}">1:10 million</a><br>
Admin-0 country polygons</td><td><b>Map</b> and <b>Thermal planes overview:</b>
coastlines and borders at 1:50 million and 1:10 million respectively.
<b>Route location:</b> 1:50 million polygons, available offline,
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
<li><b>Routes / 3D terrain:</b> IGN aerial imagery is draped over the terrain
mesh. Routes also offers grayscale relief and an independent all-flight thermal
overlay; the locator uses Natural Earth.</li>
<li><b>Traceability:</b> IGN image and elevation metadata retain source requests
and retrieval dates; elevation rasters also have SHA-256 hashes.</li>
</ul>
<p>IGN images are served by <a href="{IGN_WMS}">Géoplateforme WMS</a>.
© IGN, <a href="{LICENCE_OUVERTE}">Licence Ouverte 2.0</a>.
Natural Earth: public domain. Hillshade: Esri and data contributors.</p>
"""


def _views() -> str:
    return f"""
<a name="views"></a><h3>Screen summary</h3>
<table border="1" cellspacing="0" cellpadding="8" width="100%">
<tr><th width="23%">Screen</th><th>What is measured and how</th></tr>
<tr><td><a name="tab-trajectory"></a><b>Trajectory</b></td><td>
One IGC flight, raw and reprocessed with the current configuration.
Compare HMM and Vilpellet phase labels on the cleaned path. Gaps remain separate.
Climb runs describe the segmentation, not distinct thermals.</td></tr>
<tr><td><a name="tab-map"></a><b>Map</b></td><td>
One first free-flight position per retained flight. An adaptive degree grid counts
launches; zoomed views allow individual-flight inspection. Terrain filters here
use launch altitude.</td></tr>
<tr><td><a name="tab-planes"></a><b>Thermal planes</b><br>
<a name="thermal-points"></a>Intersection points</td><td>
Twelve fixed 5 &times; 5 km cells: three per highest-ground-elevation category, ranked
by continuous Vilpellet climb runs. Dots interpolate climb crossings of
H = lowest IGN terrain + z, within the selected dates. One flight may add many dots;
unique contributing flights are counted separately. Ranking stays fixed.</td></tr>
<tr><td><a name="tab-density"></a><b>Thermal density</b></td><td>
Cumulative climb hours/km² over all dates and heights. Split edge durations over
50 m pixels, then divide seconds by 3600 and pixel area. Regions use HMM decisions,
one every {load_segmentation_config().decision_step_s:g} s; cells offer HMM or
Vilpellet. Both disciplines contribute. This is residence time, not thermal
counts.</td></tr>
<tr><td><a name="tab-routes"></a><b>Routes · 50&ndash;300 km</b></td><td>
Cleaned flights sharing directed 10 &times; 10 km endpoint cells. Distance is between
cell centres; ranks use retained elapsed duration. At most 300 flights preserve
both groups of five duration extremes. An optional day and departure-time window
filters the entire pair before ranking and sampling, for comparing departure cohorts.
The table includes departure/arrival dates
in Europe/Paris. Terrain and imagery provide context; the thermal overlay uses
all classified flights, independently of the displayed route sample.</td></tr>
<tr><td><a name="tab-3d"></a><b>3D terrain</b></td><td>
Snapshot of the selected Thermal planes cell and dates, in a 5 or 10 km square.
All saved Vilpellet crossings every 20 m above the central cell's lowest ground,
without random thinning. Terrain and points use metres with no vertical
exaggeration.</td></tr>
<tr><td><b>Route location</b></td><td>
France/world context for the current route footprint and endpoint cells.
Expand map provides zoom and pan without altering the selected flights.</td></tr>
</table>
<p><b>Calendar times:</b> IGC date + first accepted fix clock + trimming offset
+ relative trajectory time; displayed in Europe/Paris (CET/CEST). Catalogue dates
locate files, but do not replace missing IGC clocks.</p>
<p><b>Different populations:</b> launch counts, climb-run counts, intersection
counts and climb hours/km² answer different questions. They are not interchangeable.</p>
"""


def _caveats() -> str:
    return """
<a name="caveats"></a><h3>Limitations</h3>
<ul>
<li><b>Altitude:</b> recorder GNSS datums are not harmonised with IGN normal heights.
z measures height above the cell's lowest ground; local terrain clearance varies.</li>
<li><b>Interpolation:</b> straight segments approximate curved flight paths;
error grows with fix spacing and curvature.</li>
<li><b>Thermals:</b> climb labels and crossings do not identify thermal centres.</li>
<li><b>Backgrounds:</b> pixel spacing is sampling, not positional accuracy.
Photo acquisition dates differ from flight dates.</li>
</ul>
<p><a href="#contents">Back to contents</a></p>
"""


def sources_html() -> str:
    """Summarise all screens and their sources; detailed help stays in each view."""
    return "".join(
        (
            _contents(),
            _views(),
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
        self._info = InfoButton("summary", self)
        self._browser = info_browser(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._browser)

    def ensure_loaded(self) -> None:
        """Fill the page the first time the tab is shown."""
        if not self._browser.toPlainText():
            self._browser.setHtml(sources_html())
