"""Density maps of climb points, for the regional boxes and for the thermal cells."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import geography, thermal_regions
from ..density_view import AdaptiveDensity, histogram_source
from ..thermal_ridges import draw_ridges, load_ridges
from ..thermal_store import load_store
from .thermal_plane import _Worker

INFO_HTML = """
<h3>Regions</h3>
<p>Each box is one of the five regional boxes of the thesis map (Alps, Pyrenees,
Massif Central, Channel Coast, Champagne-Lorraine). Only flights that <b>launch inside
the box</b> are used, the same population every other regional analysis uses; their
points may lie outside the box, and are drawn wherever they fall in the frame.</p>
<p>A point is a position of the HMM segmentation labelled <b>climb</b>, on the
segmentation's own decision grid (this work, not Vilpellet's segmentation).
Positions are converted from each flight's local east/north frame back to longitude
and latitude. <b>All heights are pooled</b>: a region has no single ground level.</p>
<p>Points are counted in bins of 0.001&deg; (about 75&ndash;100 m). The viewer sums
them into coarser bins of 0.003, 0.01 and 0.03&deg; and shows the coarsest level that
still gives at least 1000 bins across the visible width. Zooming therefore makes the
pixels smaller, down to the 0.001&deg; bins, which are the finest stored.</p>
<p>A count is the number of climb-labelled points, not of thermals or flights. A long
climb contributes many points, so the map shows where time is spent climbing.</p>

<h3>Cells</h3>
<p>The cells are the 5 x 5 km squares of the Thermal planes tab. A point is where a
<b>climb</b> segment crosses one of the horizontal planes, one every 10 m of height
above the cell's ground altitude; <b>all planes are pooled</b> into one map. A climb
crossing several planes gives one point on each, so a count is proportional to the
height climbed in the bin. The pooled points are those of the chosen segmentation
(this work or Vilpellet) over every date. Bins are chosen to give about 150 across
the visible window, never finer than 10 m.</p>

<h3>Colours</h3>
<p>The colour scale is logarithmic, from 1 to the largest count in the visible
window, and is redrawn when you zoom. Values of 0 are transparent. Each panel has
its own scale, so colours are not comparable between panels. <b>Terrain</b> and
<b>Density</b> set the opacity of the background image and of the density colours,
from 0% to 100%.</p>
"""


class DensityInfo(QDialog):
    """How the density maps are computed."""

    def __init__(self, parent: QWidget | None = None):
        """Show the explanation in a small window."""
        super().__init__(parent)
        self.setWindowTitle("Thermal density: how the maps are computed")
        self.resize(560, 640)
        text = QTextBrowser()
        text.setHtml(INFO_HTML)
        layout = QVBoxLayout(self)
        layout.addWidget(text)


class ThermalDensity(QWidget):
    """Regions or cells, one at a time or side by side, with zoom-adaptive pixels."""

    def __init__(self, parent=None):
        """Build controls without reading any archive at application startup."""
        super().__init__(parent)
        self._regions: dict | None = None
        self._store = None
        self._cells = []
        self._planes = {}
        self._worker: _Worker | None = None
        self._pending = False
        self._tried = False
        self._densities: list[AdaptiveDensity] = []
        self._backdrops = []
        self._limits = {}
        self._reliefs = {}
        self._info_panel: DensityInfo | None = None

        self._area = QComboBox()
        self._area.addItem("Regions", "regions")
        self._area.addItem("Cells", "cells")
        self._item = QComboBox()
        self._item.setMinimumContentsLength(24)
        self._source = QComboBox()
        self._source.addItem("This work (HMM)", "own")
        self._source.addItem("Jérémie (Vilpellet)", "vilpellet")
        self._source.setCurrentIndex(1)
        self._background = QComboBox()
        self._background.addItem("Colour map · IGN", "colour")
        self._background.addItem("Aerial photo · IGN", "aerial")
        self._background.addItem("Shaded relief", "relief")
        self._background.addItem("None", "none")
        self._terrain = QDoubleSpinBox()
        self._terrain.setRange(0, 100)
        self._terrain.setDecimals(0)
        self._terrain.setSingleStep(5)
        self._terrain.setValue(85)
        self._terrain.setSuffix("% terrain")
        self._strength = QDoubleSpinBox()
        self._strength.setRange(0, 100)
        self._strength.setDecimals(0)
        self._strength.setSingleStep(5)
        self._strength.setValue(100)
        self._strength.setSuffix("% density")
        self._ridges = QCheckBox("Estimated crests · IGN DEM")
        self._ridges.setChecked(False)
        self._ridges.setToolTip(
            "Our estimates from official IGN RGE ALTI elevations; "
            "not official IGN crest vectors."
        )
        self._info = QPushButton("i")
        self._info.setFixedWidth(28)
        self._info.setToolTip("How the density maps are computed")
        self._reload = QPushButton("Reload SSD data")
        self._status = QLabel(
            "Prepare with scripts/pipeline/prepare_thermal_regions.py."
        )
        self._status.setWordWrap(True)
        self._figure = Figure(figsize=(10, 6), layout="constrained")
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)

        top = QHBoxLayout()
        for widget in (self._area, self._item, self._source):
            top.addWidget(widget)
        top.addStretch(1)
        top.addWidget(self._reload)
        top.addWidget(self._info)
        look = QHBoxLayout()
        look.addWidget(QLabel("Background"))
        for widget in (self._background, self._terrain, self._strength, self._ridges):
            look.addWidget(widget)
        look.addWidget(self._toolbar, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(look)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._status)

        self._area.currentIndexChanged.connect(self._area_changed)
        self._item.currentIndexChanged.connect(self._draw)
        self._source.currentIndexChanged.connect(self._draw)
        self._background.currentIndexChanged.connect(self._draw)
        self._terrain.valueChanged.connect(self._terrain_changed)
        self._strength.valueChanged.connect(self._strength_changed)
        self._ridges.toggled.connect(self._draw)
        self._reload.clicked.connect(self._load)
        self._info.clicked.connect(self._show_info)
        self._area_changed()

    def ensure_loaded(self):
        """Read the prepared files once, when the tab is first shown."""
        if not self._tried:
            self._tried = True
            self._load()

    def invalidate(self):
        """Drop results after the application's archive folders change."""
        self.shutdown()
        self._regions = self._store = None
        self._cells, self._planes, self._reliefs = [], {}, {}
        self._tried = False
        self._area_changed()

    def shutdown(self):
        """Join a running read before Qt destroys its owning widget."""
        if self._worker is not None:
            self._worker.cancel.set()
            self._worker.succeeded.disconnect()
            self._worker.wait()
            self._worker = None

    def set_compact(self, compact):
        """Hide the status line so the plots fill a full-screen window."""
        self._status.setVisible(not compact)

    def _load(self):
        self._planes, self._reliefs, self._limits = {}, {}, {}
        self._regions = thermal_regions.load_regions()
        if self._regions is None:
            self._status.setText(
                "Prepared thermal-regions.npz not found. Connect the SSD and run "
                "scripts/pipeline/prepare_thermal_regions.py."
            )
        try:
            self._store = load_store()
            self._cells = self._store.cells() if self._store else []
        except (OSError, ValueError) as exc:
            self._store, self._cells = None, []
            self._status.setText(f"Could not open the thermal-plane store: {exc}")
        self._area_changed()

    def _show_info(self):
        if self._info_panel is None:
            self._info_panel = DensityInfo(self)
        self._info_panel.show()
        self._info_panel.raise_()

    def _rank(self, cell):
        peers = [c for c in self._cells if c.terrain == cell.terrain]
        return peers.index(cell) + 1

    def _area_changed(self, *_):
        cells = self._area.currentData() == "cells"
        self._source.setVisible(cells)
        self._ridges.setVisible(cells)
        self._item.blockSignals(True)
        self._item.clear()
        if cells:
            for terrain in geography.TERRAIN_ORDER:
                group = [c for c in self._cells if c.terrain == terrain]
                if len(group) > 1:
                    self._item.addItem(
                        f"{terrain}: {len(group)} cells side by side",
                        ("group", terrain),
                    )
            for cell in self._cells:
                self._item.addItem(
                    f"{cell.terrain} #{self._rank(cell)} · {cell.flights:,} flights "
                    f"· ground {cell.ground_m:g} m",
                    ("cell", (cell.ix, cell.iy)),
                )
        else:
            self._item.addItem("All regions side by side", None)
            for name in thermal_regions.REGIONS:
                self._item.addItem(name, name)
        self._item.blockSignals(False)
        self._draw()

    def _panels(self):
        """What to draw: ``(key, kind, subject)`` triples, one per panel."""
        data = self._item.currentData()
        if self._area.currentData() == "regions":
            names = list(thermal_regions.REGIONS) if data is None else [data]
            return [(name, "region", name) for name in names]
        if data is None:
            return []
        what, value = data
        if what == "group":
            cells = [c for c in self._cells if c.terrain == value]
        else:
            cells = [c for c in self._cells if (c.ix, c.iy) == value]
        return [((c.ix, c.iy), "cell", c) for c in cells]

    def _release(self):
        for density in self._densities:
            density.close()
        self._densities, self._backdrops = [], []

    def _remember_limits(self):
        for key, ax in self._axes_by_key.items():
            self._limits[key] = (ax.get_xlim(), ax.get_ylim())

    def _terrain_changed(self, *_):
        for image in self._backdrops:
            image.set_alpha(self._terrain.value() / 100)
        self._canvas.draw_idle()

    def _strength_changed(self, *_):
        for density in self._densities:
            density.set_alpha(self._strength.value() / 100)
        self._canvas.draw_idle()

    def _background_image(self, kind, key=None, cell=None):
        """One saved terrain image, decoded once and kept for later redraws."""
        if self._store is None or kind == "none":
            return None
        cache_key = (kind, key or (cell.ix, cell.iy))
        if cache_key not in self._reliefs:
            self._reliefs[cache_key] = self._store.background(cell, kind, key=key)
        return self._reliefs[cache_key]

    def _draw(self, *_):
        if hasattr(self, "_axes_by_key"):
            self._remember_limits()
        self._release()
        self._figure.clear()
        self._axes_by_key = {}
        panels = self._panels()
        cells = self._area.currentData() == "cells"
        if cells and not self._start_missing(panels):
            self._canvas.draw_idle()
            return
        if not panels:
            self._canvas.draw_idle()
            return
        columns = 1 if len(panels) == 1 else (3 if not cells else len(panels))
        rows = -(-len(panels) // columns)
        axes = np.atleast_1d(
            self._figure.subplots(rows, columns, squeeze=False)
        ).ravel()
        for ax in axes[len(panels) :]:
            ax.axis("off")
        for ax, (key, kind, subject) in zip(axes, panels, strict=False):
            self._axes_by_key[key] = ax
            if kind == "region":
                self._draw_region(ax, subject)
            else:
                self._draw_cell(ax, subject)
            if key in self._limits:
                ax.set_xlim(self._limits[key][0])
                ax.set_ylim(self._limits[key][1])
        for density in self._densities:
            density.refresh()
            density.add_colorbar(self._figure)
        self._canvas.draw_idle()

    def _start_missing(self, panels):
        """Read the cells not yet in memory; ``True`` when everything is present."""
        if self._store is None or not panels:
            if self._store is None:
                self._status.setText(
                    "Prepared thermal-planes.sqlite3 not found. Connect the SSD."
                )
            return False
        source = self._source.currentData()
        missing = [c for _, _, c in panels if (c.ix, c.iy, source) not in self._planes]
        if not missing:
            return True
        if self._worker is not None:
            self._pending = True
            return False
        store = self._store
        start, end = store.time_extent()
        start, end = (-1e18, 1e18) if start is None else (start, end)

        def read(progress, cancel):
            return {
                (c.ix, c.iy, source): store.read_plane(
                    c, start, end, source, progress=progress, cancel=cancel
                )
                for c in missing
            }

        self._status.setText(f"Reading {len(missing)} cell(s) from the SSD…")
        self._worker = _Worker(read, self)
        self._worker.progress.connect(self._progress)
        self._worker.failed.connect(self._progress)
        self._worker.succeeded.connect(self._received)
        self._worker.finished.connect(self._finished)
        self._worker.start()
        return False

    def _progress(self, message):
        if self.sender() is self._worker:
            self._status.setText(message)

    def _received(self, planes):
        if self.sender() is self._worker:
            self._planes.update(planes)
            self._status.setText(
                f"{sum(p.selected for p in planes.values()):,} flight visits read. "
                "All heights pooled."
            )
            self._pending = True

    def _finished(self):
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            if self._pending:
                self._pending = False
                self._draw()
        worker.deleteLater()

    def _add_backdrop(self, ax, image, extent):
        if image is None:
            return
        pixels, info = image
        self._backdrops.append(
            ax.imshow(
                pixels,
                extent=extent(info["extent"]),
                origin="upper",
                alpha=self._terrain.value() / 100,
                zorder=0.5,
                aspect=ax.get_aspect(),
            )
        )

    def _draw_region(self, ax, name):
        box = thermal_regions.REGIONS[name]
        frame = thermal_regions.extent(box)
        basemap = geography.load_basemap()
        if basemap:
            geography.draw_land(ax, basemap["france"]["rings"], frame)
        else:
            ax.set_xlim(frame[0], frame[2])
            ax.set_ylim(frame[1], frame[3])
        image = self._background_image(
            self._background.currentData(), key=f"region/{name}"
        )
        self._add_backdrop(ax, image, lambda e: (e[0], e[2], e[1], e[3]))
        ax.set_xlim(frame[0], frame[2])
        ax.set_ylim(frame[1], frame[3])
        points = 0
        if self._regions is not None:
            region = self._regions[name]
            points = region.points
            self._densities.append(
                AdaptiveDensity(
                    ax,
                    region.window,
                    label="Climb points per bin",
                    unit="°",
                    alpha=self._strength.value() / 100,
                )
            )
        west, east, south, north = box
        ax.add_patch(
            Rectangle(
                (west, south),
                east - west,
                north - south,
                fill=False,
                edgecolor="black",
                linewidth=1.2,
                zorder=5,
            )
        )
        ax.set_title(f"{name} · {points:,} points", fontsize=10)
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")

    def _draw_cell(self, ax, cell):
        ax.set(xlim=(0, 5), ylim=(0, 5), xlabel="East (km)", ylabel="North (km)")
        ax.set_aspect("equal")
        ax.grid(alpha=0.15)
        west, south, _, _ = cell.bounds
        image = self._background_image(self._background.currentData(), cell=cell)
        self._add_backdrop(
            ax,
            image,
            lambda e: (
                (e[0] - west) / 1000,
                (e[2] - west) / 1000,
                (e[1] - south) / 1000,
                (e[3] - south) / 1000,
            ),
        )
        ax.set(xlim=(0, 5), ylim=(0, 5))
        if self._ridges.isChecked():
            try:
                ridges = load_ridges(cell)
            except (OSError, ValueError, KeyError):
                ridges = None
            if ridges is not None:
                draw_ridges(ax, cell, ridges)
        plane = self._planes.get((cell.ix, cell.iy, self._source.currentData()))
        count = flights = 0
        points = plane.points if plane is not None else None
        if points is not None and not points.empty:
            count = len(points)
            flights = len(points[["discipline", "flight_id"]].drop_duplicates())
            self._densities.append(
                AdaptiveDensity(
                    ax,
                    histogram_source(
                        (points.x - west) / 1000,
                        (points.y - south) / 1000,
                        (0, 5),
                        (0, 5),
                        min_bin=0.01,
                        bins=150,
                    ),
                    label="Crossings per bin",
                    unit="km",
                    alpha=self._strength.value() / 100,
                )
            )
        ax.set_title(
            f"{cell.terrain} #{self._rank(cell)} · ground {cell.ground_m:g} m\n"
            f"{count:,} points · {flights:,} flights",
            fontsize=10,
        )
