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

<h3>Ground altitude of a cell (ASL)</h3>
<p>The tracks only carry altitude above sea level, so the cell has no ground
altitude of its own. It is estimated from the flights that <b>start inside it</b>:</p>
<ol>
<li>For each such flight, take the <b>first parseable fix of the raw IGC track,
before trimming</b>, and its GNSS altitude.</li>
<li>Discard the start if the GNSS is declared invalid, the altitude is zero or
outside the plausibility bounds, or two later fixes (within 120 s) imply an
impossible horizontal or vertical jump from it. It is never replaced by a later
fix or a barometric value.</li>
<li>The ground altitude is the <b>median</b> of the remaining starting altitudes.
The number of starts is shown in the cell details; fewer than 10 means a fragile
median.</li>
</ol>
<p>This is a launch altitude, not a terrain model: a low valley can be labelled
Plains.</p>

<h3>Categories</h3>
<p>Set by the ground altitude above: Plains &lt; {lo} m, Hills {lo}&ndash;{mid} m,
Low mountains {mid}&ndash;{hi} m, High mountains &ge; {hi} m. They are altitude
bands, not a geomorphological classification.</p>

<h3>The horizontal plane (AGL)</h3>
<p>The z of the plane is <b>height above the cell's ground altitude</b>:
AGL = altitude ASL &minus; ground. It is one fixed value per cell, not the terrain
height under each point. The slider goes from 0 to the highest trajectory altitude
inside the cell (any flight, any label) minus the ground. Trajectory altitude and
ground both come from the recorders' GNSS altitude field. Its geoid/ellipsoid
convention is not harmonised across recorders, so AGL is approximate by that
difference.</p>

<h3>Dots</h3>
<p>Each dot is where a trajectory segment labelled <b>climb</b> crosses the
plane (linear interpolation between two consecutive fixes of the same climb).
Several dots can come from one thermal: they are observed crossings, not thermal
centres. The segmentation is either this work (HMM) or Vilpellet.</p>

<h3>Time</h3>
<p>Dates and hours are Europe/Paris local time. The UTC time of a flight is
recovered from the raw IGC header date and first fix, plus the offset removed by
trimming. Flights without a recoverable UTC stay in the cell population but cannot
enter a calendar interval. Morning / midday / afternoon panels use half-open hour
bands at the same z. The default reference day is the busiest June&ndash;August
day of the cell.</p>

<h3>Backgrounds</h3>
<p>IGN maps, aerial photos and shaded relief are only backdrops. They play no part
in the ground altitude or in the AGL.</p>
"""


class ThermalInfo(QDialog):
    """A non-modal, resizable reading panel."""

    def __init__(self, parent: QWidget | None = None):
        """Show the static text in a rich-text browser."""
        super().__init__(parent)
        self.setWindowTitle("Thermal planes: how things are computed")
        self.resize(560, 640)
        browser = QTextBrowser()
        browser.setHtml(info_html())
        layout = QVBoxLayout(self)
        layout.addWidget(browser)
