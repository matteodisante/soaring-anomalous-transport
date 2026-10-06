"""Contextual explanations for the viewer's trajectory, map and route screens."""

from __future__ import annotations

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QPushButton, QVBoxLayout

from ..route_index import DISTANCE_PRESETS_KM, MAX_FLIGHTS, ROUTE_CELL_M
from ..thermal_ridges import DATASET_URL as RGE_ALTI_URL
from .info_browser import info_browser
from .source_notes import BD_ORTHO, FLIGHT_SOURCE_HTML, NATURAL_EARTH_WORLD


def _fullscreen_note():
    return """
<h3>Full screen</h3>
<p>The green macOS window button enlarges the complete viewer with its controls.
<b>Map full screen</b> enlarges the plot and hides its controls. Click the same
top-right button again to return; the camera and selected results are preserved.</p>
"""


def trajectory_html():
    """Explain the raw/cleaned comparison and the origin of phase labels."""
    return f"""
<h2>Trajectory</h2>
<p>Inspect one flight, compare its recording with the processed trajectory,
and examine search, climb and transition labels in 2D or 3D.</p>
<h3>How the trajectories are obtained</h3>
<ol>
<li><b>Raw:</b> decode the chosen IGC recording's positions, times and altitude
channels. The configured altitude policy selects the altitude used for display.</li>
<li><b>Cleaned:</b> process that recording with the current preprocessing
configuration: time/position checks, altitude cleaning, ground trimming, local
coordinate conversion, gap handling and smoothing. A Hampel flag by itself does
not delete a fix; the physical plausibility and rejoin rules make that decision.</li>
<li><b>Separate segments:</b> unsupported recording gaps remain breaks in the
line. Removed fixes are not new measurements; reconstructed values depend on
the interpolation and smoothing rules.</li>
</ol>
<h3>Reading and controlling the plot</h3>
<ul>
<li><b>Frame and axes:</b> geographic longitude/latitude or local East/North/height.
Local axes use the selected flight's origin. Choose two axes, or enable 3D.</li>
<li><b>Raw / cleaned:</b> compare the two paths; endpoint symbols mark the first
and last displayed fixes. Pan and zoom with the plot toolbar; use Reset view
to return to the initial framing. Save PDF exports the current figure.</li>
<li><b>Colour:</b> flight phase, preprocessing segment, or discipline.
<b>Thermals only</b> restricts the cleaned display to climb runs; it does not
detect individual thermal centres.</li>
</ul>
<h3>Where the phase labels come from</h3>
<p><b>Chapter 4 HMM:</b> the saved model from this work labels the processed
flight. <b>Vilpellet:</b> the transferred segmentation rules label the same
processed flight. <b>Compare side by side</b> shows both results. Unclassified
parts or unavailable models are reported instead of inventing labels.</p>
<p>Run counts and durations describe the selected segmentation; they are not
counts of distinct atmospheric thermals. This view reprocesses the selected
recording; archive-based views use their saved products and may reflect a
different preprocessing version.</p>
<h3>Sources</h3><p>{FLIGHT_SOURCE_HTML}: catalogue identities and IGC recordings.
The cleaning and segmentation are derived in this project. Recorder GNSS altitude
is not a harmonised terrain-clearance measurement.</p>
{_fullscreen_note()}
"""


def map_html():
    """Explain the population and adaptive geographic launch histogram."""
    from .map_view import _MIN_CELL_DEG, _SCATTER_MAX_POINTS, _TARGET_CELLS_ACROSS

    return f"""
<h2>Map</h2>
<p>Locate the first retained free-flight fix of each processed flight. A flight
contributes one launch location, regardless of its duration or number of fixes.</p>
<h3>How the map is obtained</h3>
<ol>
<li>Read retained flights and their first free-flight positions from the prepared
archive, after ground trimming. Catalogue metadata supplies the flight identity.</li>
<li>Apply the discipline, region and terrain filters. A region is a geographic
rectangle; terrain categories here use launch altitude. They do not use the
mean ground elevation that defines the Thermal planes categories.</li>
<li>Count launches in a longitude/latitude grid. Cell width is
max({_MIN_CELL_DEG:g}°, visible longitude span / {_TARGET_CELLS_ACROSS}).
The grid is recalculated after zooming or panning.</li>
</ol>
<h3>Reading and using the map</h3>
<ul>
<li>Colours show <b>launch counts per degree-grid cell</b> on a logarithmic scale.
This is not climb time, flight-path density or a probability per square kilometre.</li>
<li>When at most {_SCATTER_MAX_POINTS:,} launches are visible, individual points
can be inspected by hovering and clicking to open the flight in Trajectory.</li>
<li>Zone changes the view; Region and Terrain filter the launch population.
Reload refreshes the saved launch data.</li>
</ul>
<h3>Sources and limits</h3>
<p>{FLIGHT_SOURCE_HTML} supplies the flight archive. Borders and coastlines use
<a href="{NATURAL_EARTH_WORLD}">Natural Earth 1:50 million</a> (public domain).
Coverage reflects recorded, retained flights. Several flights may share a launch
site; a launch point is not the location of a thermal.</p>
{_fullscreen_note()}
"""


def routes_html():
    """Describe route selection, timestamps, overlays and independent populations."""
    km = ROUTE_CELL_M / 1000
    presets = ", ".join(map(str, DISTANCE_PRESETS_KM))
    return f"""
<h2>Routes · 50&ndash;300 km</h2>
<p>Compare cleaned trajectories that begin in the same cell A and end in the
same cell B, over a 3D terrain surface. The side map locates the selected area.</p>
<h3>How flights and ranks are selected</h3>
<ol>
<li>Take each flight's first and last <b>retained cleaned fixes</b>. Convert its
local coordinates using its own saved origin, then assign endpoints to fixed
{km:g} &times; {km:g} km Lambert-93 cells. A → B and B → A are different pairs;
merely crossing the cells is insufficient.</li>
<li>Select a cell-centre distance: presets {presets} km use ±10 km intervals.
This distance is not the flown path length. Pairs shared by both requires both
disciplines to occur in that exact directed pair.</li>
<li>Rank matching flights by elapsed time from first to last retained fix,
including gaps. Rank 1 is shortest; ties use discipline and flight ID.
The fastest/slowest labels refer to this duration ranking, not measured airspeed.</li>
<li>Display at most {MAX_FLIGHTS} flights: the five shortest and five longest,
plus {MAX_FLIGHTS - 10} evenly spaced interior duration ranks. If fewer exist,
show all. The displayed and matching counts remain separate.</li>
</ol>
<h3>Flights departing together</h3>
<p>Load a pair, enable <b>Departure window</b>, choose <b>Day (Paris)</b>,
<b>From</b> and the window length, then click <b>Apply</b>. The initial window
is 30 minutes. Days and their counts cover every flight in the pair, including
those outside the 300-flight sample; the initial day has the most dated departures.
The start follows the first departure's minute. Changing day keeps a matching
interval, or moves the start to that day's first departure if it would be empty.</p>
<p>The interval includes its start and excludes its end: 12:00 for 30 minutes
means 12:00 &le; departure &lt; 12:30 on that local day. The live count shows
how many match before loading. The interval stays within one civil day;
unavailable dates are counted and excluded from an active filter.</p>
<p>The controls show a <b>Preview</b>; <b>Displayed departures</b> above the map
identifies the applied selection. Editing keeps the current scene visible until
Apply finishes loading. Empty previews disable loading. Failed or cancelled loads
retain the previous scene and explain that it is still displayed.</p>
<p>Filtering happens <b>before</b> duration ranking and sampling. Ranks and the
fastest/slowest groups are recomputed within the chosen departure cohort.
The first/last retained-fix definitions remain unchanged. Arrival may be on a
later day. Untick the filter and Apply to restore all departures; changing the
route or discipline resets the time filter. CET/CEST appears in the flight table;
if a local autumn hour repeats, both occurrences match the clock window.</p>
<p>This selects candidate groups for comparing solo and group flight. Close
departure times alone do not establish shared flight: examine simultaneous
spatial proximity along the trajectories too. The thermal overlay continues
to use all archived flights, independent of the day and time filter.</p>
<h3>Table and trajectory controls</h3>
<ul>
<li><b>Departure / arrival:</b> dates and times of the retained endpoints in
Europe/Paris, with CET/CEST. Restore the IGC UTC origin, trimming offset and
relative endpoint times. Unavailable clocks are labelled explicitly.</li>
<li>The five fastest are cyan and the five slowest lime green; groups can overlap
when fewer than ten flights match. Selecting rows highlights flights in blue.
Filters, track width and vertical exaggeration change the display, not the data.</li>
<li>All retained fixes are drawn, with separate segments across unsupported gaps.
Circle = first retained fix; square = last. Drag to orbit, Shift + drag to pan,
scroll/pinch to zoom; Top view and Reset view restore useful camera positions.</li>
</ul>
<h3>What the thermal colours measure</h3>
<p><b>Thermal hours · all flights</b> uses all HMM-classified flights crossing
the area, both disciplines and all dates/heights. It is independent of the
selected endpoint pair and fastest/slowest filters.</p>
<p>Consecutive climb decisions in one continuous segment contribute their elapsed
time to the 50 &times; 50 m pixels crossed, assuming linear motion. Gaps beyond
1.5 decision steps are excluded. Density = seconds / (3600 &times; area in km²).
Thus 36 seconds in a 50 m pixel gives <b>4 h/km²</b>. Coarser display pixels sum
seconds and divide by their larger area; they do not create observations.</p>
<p>This is recorded climb residence time, not thermal counts or a probability.
Zero also includes unvisited places. The colours are draped on the same terrain
mesh as the background, and remain independent of which routes are highlighted.</p>
<h3>Terrain, imagery and access</h3>
<p><a href="{RGE_ALTI_URL}">IGN RGE ALTI</a> supplies the elevation overview,
bounded at 600 samples per side and 100 m spacing or coarser.
<a href="{BD_ORTHO}">IGN BD ORTHO</a> supplies north-up aerial imagery, up to
3072 pixels on the longest side. Switching surface appearance keeps the geometry.
Missing terrain remains missing. The France/world locator uses
<a href="{NATURAL_EARTH_WORLD}">Natural Earth</a>.</p>
<p>{FLIGHT_SOURCE_HTML} supplies recordings. Prepare / refresh index builds a
reusable endpoint census and all-flight thermal product on the SSD. Loading a pair
reads its saved tracks and small terrain/image windows; cached windows work offline.
Dates read the candidate recordings' headers/first fixes without rerunning
cleaning.</p>
<p>GNSS and IGN height datums are not harmonised; no precise ground clearance is
implied. Photo dates differ from flight dates. The comparison sample preserves
duration extremes and is not a random population estimate.</p>
{_fullscreen_note()}
"""


def terrain_html():
    """Explain the separate snapshot and stacked intersection levels."""
    return f"""
<h2>3D terrain · selected cell</h2>
<p>This is a snapshot of the cell and dates selected in Thermal planes.
It shows the terrain and climb intersections at horizontal levels every 20 m.</p>
<h3>How the points are obtained</h3>
<ol>
<li>Use the saved <b>Vilpellet</b> climb intersections, even when the parent
2D view displays HMM. For each level, H = central cell mean terrain + z.</li>
<li>Linearly interpolate crossings of consecutive climb fixes with each plane.
Keep the selected date interval and the 5 &times; 5 or 10 &times; 10 km area
centred on the cell. Neighbouring points use the same absolute reference planes.</li>
<li>Draw every retained intersection, without random thinning. A point is a
crossing, not a whole flight or a detected thermal centre; the same flight can
produce many points. The summary reports distinct contributing flights.</li>
</ol>
<h3>Controls</h3>
<p>Changing Area reloads the same date interval at the chosen extent. Point opacity
and size change appearance only. Terrain can be hidden to reveal occluded points.
Terrain colours and Aerial photo share the same mesh. Axes use metres at 1:1 scale.</p>
<p>Drag to orbit, Shift + drag to pan, Alt + drag to look around. Scroll or pinch
to zoom. Click the scene before keyboard navigation: W/S forward/back, A/D
left/right, Q/E down/up. Top view and Reset view reframe the scene.</p>
<p>Changing the parent tab's dates or cell does not silently replace this snapshot:
click <b>3D terrain · selected cell</b> again to apply the new selection.</p>
<h3>Sources and limits</h3>
<p>{FLIGHT_SOURCE_HTML}: IGC paths and times; Vilpellet supplies climb labels.
<a href="{RGE_ALTI_URL}">IGN RGE ALTI</a>: terrain and mean ground reference.
<a href="{BD_ORTHO}">IGN BD ORTHO</a>: aerial appearance. Prepared products
are read from the SSD. GNSS and terrain height datums are not harmonised, and
linear interpolation approximates curved paths. Photos may predate the flights.</p>
{_fullscreen_note()}
"""


def locator_html():
    """Explain the expanded geographic context map without implying new data."""
    return f"""
<h2>Route location · France / world</h2>
<p>Locate the area shown in Routes at a national or global scale.</p>
<p>The outlined footprint is the current route scene's bounding rectangle,
converted from Lambert-93 to longitude/latitude. A and B mark its departure and
arrival cells. These are geographic references, not additional trajectories.</p>
<p>France / World changes the context; the toolbar zooms and pans. The map follows
the selected route scene and does not change flight selection or scientific results.</p>
<p>Borders and coastlines use the bundled
<a href="{NATURAL_EARTH_WORLD}">Natural Earth 1:50 million</a> polygons, public
domain. No online tiles are needed. This small-scale context is not a precision
terrain map.</p>
"""


def summary_html():
    """Explain the role of the common source summary."""
    return """
<h2>Sources &amp; methods</h2>
<p>This page is the viewer-wide summary: what each screen measures, which source
supplies its data, and the limitations shared by the views.</p>
<p>Use the links at the top to jump between sections. Open <b>Info</b> in the
screen you are using for its calculation steps, examples and controls. Source
links open the provider's page in your browser; reading this summary does not
load flights, download maps or recompute scientific results.</p>
"""


_TOPICS = {
    "trajectory": ("Trajectory", trajectory_html),
    "map": ("Map", map_html),
    "routes": ("Routes", routes_html),
    "terrain": ("3D terrain", terrain_html),
    "locator": ("Route location", locator_html),
    "summary": ("Sources & methods", summary_html),
}


class InfoButton(QPushButton):
    """Open and reuse a modeless explanation belonging to this screen."""

    def __init__(self, topic, parent=None):
        """Keep help lazy: no archive reads, configuration reads or dialogs yet."""
        super().__init__("Info", parent)
        self._title, self._contents = _TOPICS[topic]
        self._dialog = None
        self.setAutoDefault(False)
        self.setToolTip(f"{self._title}: what is shown, calculations and data sources")
        self.clicked.connect(self._show_info)

    def _show_info(self):
        """Show readable local explanations without changing the active scene."""
        if self._dialog is None:
            self._dialog = QDialog(self)
            self._dialog.setWindowTitle(f"{self._title}: methods and sources")
            size = QSize(800, 780)
            if self.screen() is not None:
                size = size.boundedTo(
                    self.screen().availableGeometry().size() - QSize(40, 60)
                )
            self._dialog.resize(size)
            browser = info_browser(self._dialog)
            browser.setHtml(self._contents())
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self._dialog.close)
            layout = QVBoxLayout(self._dialog)
            layout.addWidget(browser)
            layout.addWidget(buttons)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()
