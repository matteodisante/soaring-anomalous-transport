"""Definitions and sources for the Thermal planes Info panel."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QWidget

from ..geography import TERRAIN_BANDS
from ..thermal_geometry import CELL_M
from ..thermal_ridges import DATASET_URL as RGE_ALTI_URL
from ..thermal_ridges import PARAMETERS as DEM_WINDOW
from .info_browser import info_browser
from .source_notes import (
    FLIGHT_SOURCE_HTML,
    LICENCE_OUVERTE,
    aerial_dates_html,
    background_sources_html,
)


def info_html() -> str:
    """Explain selection, intersections and sources using the active thresholds."""
    lo, mid, hi = (int(b[2]) for b in TERRAIN_BANDS[:3])
    cell_km = int(CELL_M // 1000)
    grid = int(DEM_WINDOW["grid_m"])
    samples = int(CELL_M // grid) ** 2
    return f"""
<h2>Thermal planes</h2>
<p>Each dot is a climb trajectory crossing one horizontal plane.
Colour identifies the discipline. <b>% points</b> adjusts dot opacity from 0 to
100% in every plane panel; it starts at 95%. <b>% background</b> adjusts the map
separately. Opacity changes preserve the selected intersections and their counts.</p>

<h3>Cell selection</h3>
<ol>
<li><b>Grid:</b> fixed {cell_km} &times; {cell_km} km squares over the
metropolitan-France map window, in Lambert-93 (EPSG:2154).</li>
<li><b>Count:</b> continuous Vilpellet climb runs, all archived dates and both
disciplines. Each run counts once per cell, including re-entry. Separate runs
from one flight count separately; duration and number of fixes add no weight.</li>
<li><b>Group:</b> by mean IGN terrain elevation over the entire cell.</li>
<li><b>Keep:</b> the three cells with most climbs in each group: 12 total.
Ties use grid coordinates (ix, then iy).</li>
</ol>
<p><b>Mean elevation bands:</b> Plains &lt; {lo} m; Hills {lo}&ndash;&lt;{mid} m;
Low mountains {mid}&ndash;&lt;{hi} m; High mountains &ge; {hi} m.</p>
<ul>
<li><b>Ranking stays fixed</b> when dates, height or segmentation change.
P, H, L and M identify the groups; rank 1 leads its group.</li>
<li><b>No regional quota or minimum spacing.</b> Nearby alpine cells can win
several places. A low valley can qualify as Plains; categories describe elevation.</li>
<li><b>Whole flights are labelled before clipping.</b> Take-off may be elsewhere.
Only continuous climb segments count; gaps, phase boundaries and isolated fixes
add no crossings.</li>
</ul>

<h3>Plane height and terrain source</h3>
<p><b>H = mean terrain elevation + selected z.</b></p>
<ul>
<li><a href="{RGE_ALTI_URL}">IGN RGE ALTI</a> supplies ground elevations:
{samples:,} samples per cell, {grid} m apart. The area-weighted mean uses unsmoothed
values inside the square, excludes any outer buffer and requires complete coverage.</li>
<li>This mean sets both the <b>terrain category</b> and the <b>plane reference</b>.
Launch-altitude statistics in Cell details are retained for comparison only.</li>
<li><b>z</b> is height above the cell mean. Local clearance varies with the ground
under each dot. The upper limit is the highest supported trajectory altitude
inside the cell minus its terrain mean.</li>
<li><b>Height increment:</b> spacing between selectable planes (10, 20, 50, 100
or 200 m). Each plane has zero thickness. Intersections are saved every 10 m,
plus the exact highest level; the same z always gives the same dots.</li>
</ul>

<a name="thermal-points"></a><h3>Intersection points</h3>
<ol>
<li>Take consecutive processed fixes labelled <b>climb</b> by the selected
HMM or Vilpellet method, within one continuous climb run.</li>
<li>For endpoint altitudes z<sub>0</sub>, z<sub>1</sub>, calculate
<b>f = (H &minus; z<sub>0</sub>) / (z<sub>1</sub> &minus; z<sub>0</sub>)</b>.
Keep 0 &le; f &le; 1; skip horizontal edges.</li>
<li>Interpolate position and time:
<b>(x, y, t) = (x<sub>0</sub>, y<sub>0</sub>, t<sub>0</sub>) +
f &times; (&Delta;x, &Delta;y, &Delta;t)</b>.
Coordinates are Lambert-93; time is UTC.</li>
<li>Keep crossings in the visible area and selected time interval.
Both upward and downward crossings count. Shared vertices count once;
terminal crossings are kept.</li>
</ol>
<p><b>Example:</b> H = 1,000 m; fixes at 997 and 1,003 m give f = 0.5.
The crossing lies halfway between their positions and times.</p>

<h3>Counts</h3>
<table border="1" cellspacing="0" cellpadding="8" width="100%">
<tr><th>Label</th><th>What it counts</th></tr>
<tr><td>Vilpellet climbs</td><td>Continuous climb runs used for ranking.</td></tr>
<tr><td>Cell visitors</td><td>Distinct flights crossing the central cell,
any phase or altitude, all dates.</td></tr>
<tr><td>Visible points</td><td>Crossings of this exact plane in the visible area
and selected interval. One flight can add several.</td></tr>
<tr><td>Contributing flights</td><td>Distinct flights behind the visible
points.</td></tr>
</table>
<p>A busy cell can show few dots: flights wholly above or below H contribute none.
For a terrain mean of 289 m and z = 100 m, only crossings at H = 389 m count.</p>

<h3>Navigation and time</h3>
<ul>
<li><b>Zoom + / &minus;:</b> visible width 0.5&ndash;10 km. Drag with the toolbar's
hand tool. Navigation covers the selected cell and its eight neighbours.
<b>Reset cell</b> returns to the central {cell_km} &times; {cell_km} km square.</li>
<li><b>Neighbours:</b> include their own visiting flights at the same absolute H.
The dashed square marks the central cell. Zoom and pan persist across height
and background changes.</li>
<li><b>Calendar:</b> Europe/Paris time. UTC comes from the IGC header, first fix
and trimming offset. Flights without recoverable UTC remain in the cell population
but cannot enter a calendar interval.</li>
<li><b>Daily panels:</b> default bands 08&ndash;11, 11&ndash;15, 15&ndash;18,
end excluded, at the same z. The default day is the busiest June&ndash;August day.</li>
</ul>

<h3>Flight data and limits</h3>
<ul>
<li><b>Source:</b> {FLIGHT_SOURCE_HTML}. IGC positions, GNSS altitudes and times
supply the trajectories. This work's HMM or Vilpellet supplies the climb labels.</li>
<li><b>Altitude:</b> recorder GNSS datums are not harmonised with IGN normal
heights. The height difference retains this uncertainty.</li>
<li><b>Interpolation:</b> straight segments approximate curved paths;
error grows with fix spacing and curvature.</li>
<li><b>Dots:</b> trajectory crossings. Several can belong to one thermal;
thermal centres are not estimated.</li>
</ul>

<h3>Backgrounds and access</h3>
{background_sources_html()}
{aerial_dates_html()}
<ul>
<li><b>Saved images:</b> IGN cell maps 4,000 &times; 4,000 pixels
({CELL_M / 4000:g} m/pixel); hillshade 600 &times; 600. Pixel size is sampling,
not positional accuracy. Background opacity starts at 85%.</li>
<li><b>Offline:</b> prepared crossings, neighbours and maps are read from the SSD.</li>
<li><b>Provenance:</b> saved elevation queries, retrieval dates, raster hashes
and coverage make the terrain mean traceable.
IGN data: <a href="{LICENCE_OUVERTE}">Licence Ouverte 2.0</a>.</li>
</ul>
"""


class ThermalInfo(QDialog):
    """A non-modal, resizable reading panel."""

    def __init__(self, parent: QWidget | None = None):
        """Show the definitions in a readable rich-text browser."""
        super().__init__(parent)
        self.setWindowTitle("Thermal planes: methods and sources")
        self.resize(780, 780)
        browser = info_browser(self)
        browser.setHtml(info_html())
        layout = QVBoxLayout(self)
        layout.addWidget(browser)
