"""Cumulative thermal residence time per square kilometre over regional maps."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure
from matplotlib.patches import Polygon
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...analysis.segmentation.config import load_segmentation_config
from .. import geography, thermal_regions
from ..density_maps import view_request
from ..density_view import AdaptiveDensity
from ..thermal_geometry import project
from ..thermal_store import load_store
from ..thermal_time import cache_path, load_grids
from .density_background import DensityBackgrounds
from .flow_layout import FlowLayout
from .thermal_plane import _Worker

INFO_HTML = f"""
<h3>Thermal density · hours/km²</h3>
<p>This map measures <b>cumulative time spent in the climb phase per unit ground
area</b>, across the full available archive and all heights. It is not an encounter
probability, a count of distinct atmospheric thermals, or a rate per year.</p>
<ol>
<li><b>Select thermal segments.</b> Keep continuous edges whose two endpoints belong
to the same climb run. Never connect separate flights, phases or data gaps.
Regions use this work's HMM decisions; cells use the selected HMM or Vilpellet
segmentation, exactly as in Thermal planes.</li>
<li><b>Project horizontally.</b> Convert positions to Lambert-93 (metres). Keep
elapsed time and pool every altitude. There are no horizontal planes and no 10 m
vertical grouping. Even a horizontally stationary edge contributes its duration.</li>
<li><b>Distribute time.</b> Divide the map into 50 &times; 50 m pixels. Approximate each
edge by linear motion between its endpoints. Split at every pixel boundary and
assign each pixel exactly the elapsed time spent inside it. An edge already in a
thermal when it enters a pixel contributes only its time inside.</li>
<li><b>Sum and normalise.</b> Add these seconds across all trajectories and dates,
divide by 3600, then by the pixel's area in km²:
<b>D(B) = Σ time inside B / (3600 &times; area(B))</b>.<br>
For example, 36 seconds in a 50 &times; 50 m pixel give
0.01 hours / 0.0025 km² = <b>4 hours/km²</b>.</li>
</ol>
<h3>Regions and cells</h3>
<p>Regions show the five thesis areas with a surrounding margin. All trajectories
crossing the displayed frame contribute, even if take-off was elsewhere. Their HMM
geometry uses consecutive decisions (one every
{load_segmentation_config().decision_step_s:g} s); gaps longer than 1.5
nominal decision steps are excluded. Cells are the same twelve 5 &times; 5 km squares as
Thermal planes and reuse its saved continuous climb edges. There is no date filter
in this tab. Paragliders and hang gliders are pooled.</p>
<p>Separate pilots flying simultaneously each add their own time. Frequently flown
locations and long climbs therefore accumulate more hours. Unvisited places and
observed places without climb time both remain transparent: absence of colour does
not establish absence of thermals. Overlapping regional frames must not be summed.</p>
<h3>Zoom, colours and backgrounds</h3>
<p>Zoom with the toolbar or mouse wheel; pan with the toolbar. When zoomed out,
neighbouring pixels are combined by summing their time and dividing by their total
area. Zoom reveals the original 50 m grid, never invented finer thermal detail.
Axes use Lambert-93 kilometres. Each title reports total thermal hours in its
whole frame, not just the zoomed view.</p>
<p>Colours share a fixed logarithmic scale from 0.01 hours/km² to the largest
50 m value in the prepared product, for all panels, segmentations and zoom levels.
Positive values below 0.01 use the lightest colour; zero is transparent. Terrain
and Density control the two opacities independently.</p>
<p>The backgrounds are the same IGN Plan, aerial, Plan + contours, and Esri hillshade
layers used in Thermal planes. Saved cell backgrounds are reused when sufficiently
detailed. Other views request a newly georeferenced image at screen
resolution (up to 2048 pixels per side, down to 1.25 m/pixel). New uncached views
need an internet connection; cached views work offline while retained in the
512 MiB cache.
On a failed request an existing background may remain at its previous resolution;
the status line reports this. Aerial acquisition dates differ from flight dates.</p>
"""


class DensityInfo(QDialog):
    """How the density maps are computed."""

    def __init__(self, parent=None):
        """Show the complete definition alongside the plots."""
        super().__init__(parent)
        self.setWindowTitle("Thermal density: how the maps are computed")
        self.resize(660, 720)
        text = QTextBrowser()
        text.setHtml(INFO_HTML)
        layout = QVBoxLayout(self)
        layout.addWidget(text)


class ThermalDensity(QWidget):
    """Prepared time grids with adaptive density and geographic backgrounds."""

    def __init__(self, parent=None):
        """Build responsive controls without reading the archive at startup."""
        super().__init__(parent)
        self._grids, self._metadata = {}, {}
        self._cells = []
        self._worker = None
        self._tried = False
        self._densities = []
        self._backdrops, self._axes_by_key, self._limits = {}, {}, {}
        self._maps = None
        self._map_note = ""
        self._map_errors = {}
        self._info_panel = None
        self._norm = LogNorm(0.01, 1, clip=True)
        self._area = QComboBox()
        self._area.addItem("Regions · HMM", "regions")
        self._area.addItem("Cells", "cells")
        self._item = QComboBox()
        self._item.setMinimumContentsLength(24)
        self._item.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._source = QComboBox()
        self._source.addItem("This work (HMM)", "own")
        self._source.addItem("Jérémie (Vilpellet)", "vilpellet")
        self._source.setCurrentIndex(1)
        self._background = QComboBox()
        for text, kind in (
            ("Topography + contours · IGN", "topography"),
            ("Colour map · IGN", "colour"),
            ("Aerial photo · IGN", "aerial"),
            ("Shaded relief · Esri", "relief"),
            ("None", "none"),
        ):
            self._background.addItem(text, kind)
        self._terrain = self._opacity(85, "% terrain")
        self._strength = self._opacity(80, "% density")
        self._info = QPushButton("i")
        self._info.setFixedWidth(28)
        self._info.setToolTip("How hours/km² are computed")
        self._reload = QPushButton("Reload SSD data")
        self._status = QLabel(
            "Prepare with scripts/pipeline/prepare_thermal_density.py."
        )
        self._status.setWordWrap(True)
        self._figure = Figure(figsize=(10, 6), layout="compressed")
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._request_maps)
        self._canvas.mpl_connect("resize_event", lambda _: self._debounce.start())
        self._canvas.mpl_connect("scroll_event", self._scroll)
        top, look = FlowLayout(), FlowLayout()
        for widget in (self._area, self._item, self._source, self._reload, self._info):
            top.addWidget(widget)
        look.addWidget(QLabel("Background"))
        for widget in (self._background, self._terrain, self._strength, self._toolbar):
            look.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(look)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._status)
        self._area.currentIndexChanged.connect(self._area_changed)
        self._item.currentIndexChanged.connect(self._draw)
        self._source.currentIndexChanged.connect(self._draw)
        self._background.currentIndexChanged.connect(self._background_changed)
        self._terrain.valueChanged.connect(self._terrain_changed)
        self._strength.valueChanged.connect(self._strength_changed)
        self._reload.clicked.connect(self._load)
        self._info.clicked.connect(self._show_info)
        self._area_changed()

    @staticmethod
    def _opacity(value, suffix):
        widget = QDoubleSpinBox()
        widget.setRange(0, 100)
        widget.setDecimals(0)
        widget.setSingleStep(5)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def ensure_loaded(self):
        """Load the compact prepared product when this tab is first opened."""
        if not self._tried:
            self._tried = True
            self._load()

    def invalidate(self):
        """Release old data after changing archive folders."""
        self.shutdown()
        self._grids, self._metadata, self._limits, self._cells = {}, {}, {}, []
        self._tried = False
        self._area_changed()

    def shutdown(self):
        """Finish a local read and detach pending network work from the widget."""
        self._debounce.stop()
        if self._maps:
            self._maps.close()
            self._maps.deleteLater()
            self._maps = None
        if self._worker:
            self._worker.cancel.set()
            self._worker.succeeded.disconnect()
            self._worker.wait()
            self._worker = None

    def set_compact(self, compact):
        """Hide the status line when plots fill a full-screen window."""
        self._status.setVisible(not compact)

    def _load(self):
        if self._worker:
            return
        self._status.setText("Reading prepared thermal hours from the SSD…")
        self._reload.setEnabled(False)

        def read(progress, cancel):
            grids, metadata = load_grids()
            store = load_store()
            return grids, metadata, store.cells() if store else [], cache_path().parent

        self._worker = _Worker(read, self)
        self._worker.failed.connect(self._status.setText)
        self._worker.succeeded.connect(self._received)
        self._worker.finished.connect(self._finished)
        self._worker.start()

    def _received(self, result):
        self._grids, self._metadata, self._cells, folder = result
        maximum = max(
            (
                float(g.seconds.max()) / 3600 / (g.step / 1000) ** 2
                for g in self._grids.values()
                if len(g.seconds)
            ),
            default=1,
        )
        self._norm = LogNorm(0.01, max(1, maximum), clip=True)
        if self._maps:
            self._maps.close()
            self._maps.deleteLater()
        self._maps = DensityBackgrounds(folder / "density-maps", self)
        self._maps.ready.connect(self._map_received)
        self._maps.failed.connect(self._map_failed)
        self._limits = {}
        self._area_changed()

    def _finished(self):
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            self._reload.setEnabled(True)
        worker.deleteLater()

    def _show_info(self):
        if self._info_panel is None:
            self._info_panel = DensityInfo(self)
        self._info_panel.show()
        self._info_panel.raise_()

    def _rank(self, cell):
        return [c for c in self._cells if c.terrain == cell.terrain].index(cell) + 1

    def _area_changed(self, *_):
        cells = self._area.currentData() == "cells"
        self._source.setVisible(cells)
        self._item.blockSignals(True)
        self._item.clear()
        if cells:
            for terrain in geography.TERRAIN_ORDER:
                group = [c for c in self._cells if c.terrain == terrain]
                if group:
                    self._item.addItem(
                        f"{terrain}: {len(group)} cells", ("group", terrain)
                    )
            for cell in self._cells:
                self._item.addItem(
                    f"{cell.terrain} #{self._rank(cell)} · ground {cell.ground_m:g} m",
                    ("cell", (cell.ix, cell.iy)),
                )
        else:
            self._item.addItem("All regions side by side", None)
            for name in thermal_regions.REGIONS:
                self._item.addItem(name, name)
        self._item.blockSignals(False)
        self._draw()

    def _panels(self):
        data = self._item.currentData()
        if self._area.currentData() == "regions":
            names = list(thermal_regions.REGIONS) if data is None else [data]
            return [(f"region/{name}/own", name) for name in names]
        if data is None:
            return []
        what, value = data
        cells = [
            c
            for c in self._cells
            if (c.terrain == value if what == "group" else (c.ix, c.iy) == value)
        ]
        source = self._source.currentData()
        return [
            (f"cell/{c.ix}/{c.iy}/{source}", f"{c.terrain} #{self._rank(c)}")
            for c in cells
        ]

    def _draw(self, *_):
        for key, ax in self._axes_by_key.items():
            self._limits[key.rsplit("/", 1)[0]] = ax.get_xlim(), ax.get_ylim()
        for density in self._densities:
            density.close()
        if self._maps:
            self._maps.reset()
        self._densities, self._backdrops, self._axes_by_key = [], {}, {}
        self._figure.clear()
        panels = [(key, title) for key, title in self._panels() if key in self._grids]
        if not panels:
            self._canvas.draw_idle()
            return
        columns = min(3, len(panels))
        axes = self._figure.subplots(-(-len(panels) // columns), columns, squeeze=False)
        for ax in axes.ravel()[len(panels) :]:
            ax.axis("off")
        for ax, (key, title) in zip(axes.ravel(), panels, strict=False):
            grid = self._grids[key]
            w, s, e, n = grid.bounds / 1000
            ax.set(
                xlim=(w, e),
                ylim=(s, n),
                xlabel="Lambert-93 east (km)",
                ylabel="North (km)",
                facecolor="#eef0eb",
            )
            ax.set_aspect("equal")
            ax.set_autoscale_on(False)
            frame = key.rsplit("/", 1)[0]
            if frame in self._limits:
                ax.set_xlim(self._limits[frame][0])
                ax.set_ylim(self._limits[frame][1])
            self._axes_by_key[key] = ax
            if key.startswith("region/"):
                self._outline(ax, title)
            density = AdaptiveDensity(
                ax,
                grid.window,
                label="Thermal hours/km²",
                norm=self._norm,
                alpha=self._strength.value() / 100,
            )
            density.refresh()
            self._densities.append(density)

            def caption(_, ax=ax, title=title, grid=grid, density=density):
                ax.set_title(
                    f"{title} · {grid.hours:,.1f} thermal h\n"
                    f"Displayed pixels: {density._size}",
                    fontsize=10,
                )

            caption(None)
            for event in ("xlim_changed", "ylim_changed"):
                ax.callbacks.connect(event, caption)
                ax.callbacks.connect(event, lambda _: self._debounce.start())
        self._figure.colorbar(
            ScalarMappable(norm=self._norm, cmap="magma_r"),
            ax=list(self._axes_by_key.values()),
            orientation="horizontal",
            shrink=0.75,
            fraction=0.065,
            pad=0.07,
            label="Thermal hours/km² · fixed logarithmic scale",
        )
        self._toolbar.update()
        self._canvas.draw_idle()
        self._background_changed()

    @staticmethod
    def _outline(ax, name):
        west, east, south, north = thermal_regions.REGIONS[name]
        lon = np.r_[
            np.linspace(west, east, 40),
            np.full(40, east),
            np.linspace(east, west, 40),
            np.full(40, west),
        ]
        lat = np.r_[
            np.full(40, south),
            np.linspace(south, north, 40),
            np.full(40, north),
            np.linspace(north, south, 40),
        ]
        x, y = project(lon, lat)
        ax.add_patch(
            Polygon(
                np.column_stack((x, y)) / 1000,
                fill=False,
                edgecolor="#35424a",
                linewidth=0.8,
                zorder=5,
            )
        )

    def _terrain_changed(self, *_):
        for artist in self._backdrops.values():
            artist.set_alpha(self._terrain.value() / 100)
        self._canvas.draw_idle()

    def _strength_changed(self, *_):
        for density in self._densities:
            density.set_alpha(self._strength.value() / 100)
        self._canvas.draw_idle()

    def _background_changed(self, *_):
        self._map_errors.clear()
        for artist in self._backdrops.values():
            artist.remove()
        self._backdrops.clear()
        if self._maps:
            self._maps.reset()
        self._map_note = (
            "" if self._background.currentData() == "none" else "Loading map detail…"
        )
        self._update_status()
        self._debounce.start()
        self._canvas.draw_idle()

    def _request_maps(self):
        if not self._maps:
            return
        kind = self._background.currentData()
        wanted = (
            {}
            if kind == "none"
            else {
                key: view_request(kind, ax, self._canvas.devicePixelRatioF())
                for key, ax in self._axes_by_key.items()
            }
        )
        self._maps.request(wanted)

    def _map_received(self, key, result):
        if key not in self._axes_by_key:
            return
        info, pixels = result
        self._map_errors.pop(key, None)
        w, s, e, n = np.asarray(info["extent"]) / 1000
        if key in self._backdrops:
            self._backdrops[key].remove()
        ax = self._axes_by_key[key]
        self._backdrops[key] = ax.imshow(
            pixels,
            extent=(w, e, s, n),
            origin="upper",
            zorder=0.5,
            alpha=self._terrain.value() / 100,
            aspect="equal",
            interpolation="bilinear",
        )
        source = (
            "saved Thermal planes background"
            if info.get("saved_planes")
            else "new views require internet"
        )
        self._map_note = info["attribution"] + " · " + source
        self._update_status()
        self._canvas.draw_idle()

    def _map_failed(self, key, message):
        self._map_errors[key] = message
        self._update_status()

    def _update_status(self):
        if not self._grids:
            return
        source = (
            "HMM"
            if self._area.currentData() == "regions"
            else self._source.currentText()
        )
        self._status.setText(
            f"{source} · all archived dates and heights · 50 m grid · hours/km² "
            f"(not probability). {self._map_note} "
            + (
                f"{len(self._map_errors)} map(s) unavailable; "
                "previous detail retained. " + next(iter(self._map_errors.values()))
                if self._map_errors
                else ""
            )
        )

    def _scroll(self, event):
        if event.inaxes not in self._axes_by_key.values() or event.xdata is None:
            return
        ax = event.inaxes
        self._toolbar.push_current()
        factor = 0.7 if event.button == "up" else 1 / 0.7
        for limits, setter, centre in (
            (ax.get_xlim(), ax.set_xlim, event.xdata),
            (ax.get_ylim(), ax.set_ylim, event.ydata),
        ):
            setter(*(centre + (np.asarray(limits) - centre) * factor))
        self._toolbar.push_current()
        self._canvas.draw_idle()
