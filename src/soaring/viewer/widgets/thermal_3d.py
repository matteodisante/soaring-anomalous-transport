"""Navigable GPU terrain and the complete 20 m intersection cloud of one cell."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pyqtgraph.opengl as gl
from matplotlib import colormaps
from OpenGL import GL
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QVector3D
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..thermal_3d import cell_label, load_scene
from ..thermal_daily import PARIS
from .flow_layout import FlowLayout
from .thermal_plane import _Worker


class TerrainView(gl.GLViewWidget):
    """Orbit with left drag, pan with right drag, zoom with the wheel."""

    def __init__(self, parent=None):
        """Inherit the application's shared OpenGL format and depth buffer."""
        super().__init__(parent)
        self.setBackgroundColor("#eef1f4")
        self.setMinimumSize(320, 240)

    def paintGL(self, *args, **kwargs):  # noqa: N802
        """Clear depth correctly after a frame with translucent point markers."""
        GL.glDepthMask(True)
        try:
            super().paintGL(*args, **kwargs)
        finally:
            GL.glDepthMask(True)

    def mouseMoveEvent(self, event):  # noqa: N802
        """Offer right-button panning alongside the standard GL gestures."""
        if event.buttons() == Qt.MouseButton.RightButton:
            pos = event.position()
            diff = pos - self.mousePos
            self.mousePos = pos
            self.pan(diff.x(), diff.y(), 0, relative="view")
        else:
            super().mouseMoveEvent(event)

    def wheelEvent(self, event):  # noqa: N802
        """Keep zoom usable when repeatedly scrolling a trackpad."""
        super().wheelEvent(event)
        self.opts["distance"] = float(np.clip(self.opts["distance"], 100, 100000))
        self.update()


class Thermal3D(QDialog):
    """A modeless, cancellable snapshot of Thermal planes' selected interval."""

    def __init__(self, parent=None):
        """Create controls and defer all saved-data reads to an explicit request."""
        super().__init__(parent)
        self.setWindowTitle("3D terrain · Vilpellet")
        self.resize(1200, 850)
        self._worker = None
        self._scene = None
        self._cloud = self._surface = None
        self._request = None
        self._heading = QLabel("Vilpellet · planes every 20 m")
        self._heading.setWordWrap(True)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._status = QLabel()
        self._status.setWordWrap(True)
        self._point_strength = QDoubleSpinBox()
        self._point_strength.setRange(0, 100)
        self._point_strength.setDecimals(0)
        self._point_strength.setSingleStep(5)
        self._point_strength.setValue(30)
        self._point_strength.setSuffix("% points")
        self._point_size = QDoubleSpinBox()
        self._point_size.setRange(1, 12)
        self._point_size.setSingleStep(0.5)
        self._point_size.setDecimals(1)
        self._point_size.setValue(2)
        self._point_size.setSuffix(" px points")
        self._terrain = QCheckBox("Terrain")
        self._terrain.setChecked(True)
        self._terrain.setToolTip("Hide the surface to inspect every recorded point")
        reset = QPushButton("Reset view")
        top = QPushButton("Top view")
        self._fullscreen = QPushButton("Full screen")
        self._cancel = QPushButton("Cancel loading")
        self._cancel.setEnabled(False)
        controls = FlowLayout()
        for widget in (
            self._point_strength,
            self._point_size,
            self._terrain,
            reset,
            top,
            self._fullscreen,
            self._cancel,
        ):
            controls.addWidget(widget)
        self._view = TerrainView(self)
        navigation = QLabel(
            "Left drag: rotate · Right drag or Ctrl + drag: pan · Wheel: zoom · "
            "Blue: Vilpellet intersections · Scale 1:1 (metres on all axes)"
        )
        navigation.setWordWrap(True)
        self._source = QLabel()
        self._source.setWordWrap(True)
        self._source.setOpenExternalLinks(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._heading)
        layout.addWidget(self._summary)
        layout.addLayout(controls)
        layout.addWidget(navigation)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._source)
        layout.addWidget(self._status)
        self._point_strength.valueChanged.connect(self._style_changed)
        self._point_size.valueChanged.connect(self._style_changed)
        self._terrain.toggled.connect(self._style_changed)
        reset.clicked.connect(self._reset_view)
        top.clicked.connect(lambda: self._reset_view(top=True))
        self._fullscreen.clicked.connect(self._toggle_fullscreen)
        self._cancel.clicked.connect(self._cancel_loading)

    def _set_heading(self, label, start, end):
        """Identify the displayed cell and dates in the window and scene titles."""
        self.setWindowTitle(f"3D terrain · {label} · Vilpellet")
        dates = [
            datetime.fromtimestamp(t, PARIS).strftime("%Y-%m-%d %H:%M:%S")
            for t in (start, end)
        ]
        self._heading.setText(
            f"{label} · Vilpellet · planes every 20 m\n"
            f"{dates[0]} → {dates[1]} · Europe/Paris"
        )

    def load(self, store, cell, start, end):
        """Replace the displayed snapshot with an explicit cell and date selection."""
        self.shutdown()
        self._view.clear()
        self._cloud = self._surface = self._scene = None
        self._request = (cell, start, end)
        self._set_heading(cell_label(store, cell), start, end)
        self._summary.setText("Loading the selected interval from the SSD…")
        self._source.clear()
        self._status.clear()
        self._cancel.setEnabled(True)
        worker = self._worker = _Worker(
            lambda **kw: load_scene(store, cell, start, end, **kw), self
        )
        worker.progress.connect(self._progress)
        worker.succeeded.connect(self._loaded)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()

    def _progress(self, message):
        """Ignore progress queued by a superseded request."""
        if self.sender() is self._worker:
            self._status.setText(message)

    def _failed(self, message):
        """Show unavailable data without leaving a previous scene visible."""
        if self.sender() is self._worker:
            self._summary.setText("No 3D scene loaded")
            self._status.setText(message)

    def _loaded(self, scene):
        """Upload the mesh and all points only on the GUI thread."""
        if self.sender() is self._worker and not self._worker.cancel.is_set():
            self.set_scene(scene)

    def _finished(self):
        """Release the completed worker after all its queued results."""
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            self._cancel.setEnabled(False)
            if worker.cancel.is_set() and self._scene is None:
                self._summary.setText("Loading cancelled")
                self._status.setText("No partial intersection cloud is displayed.")
        worker.deleteLater()

    def set_scene(self, scene):
        """Render exact metric positions without vertical exaggeration or thinning."""
        self._scene = scene
        self._set_heading(
            scene.label
            or f"{scene.cell.terrain} · cell {scene.cell.ix}/{scene.cell.iy}",
            scene.start,
            scene.end,
        )
        self._view.clear()
        terrain = scene.terrain
        lo, hi = float(terrain.min()), float(terrain.max())
        colours = colormaps["terrain"](
            0.25 + 0.7 * (terrain.T - lo) / max(hi - lo, 1)
        ).astype(np.float32)
        self._surface = gl.GLSurfacePlotItem(
            x=scene.x,
            y=scene.y,
            z=terrain.T,
            colors=colours,
            shader="shaded",
            smooth=True,
            glOptions="opaque",
        )
        self._view.addItem(self._surface)
        self._cloud = gl.GLScatterPlotItem(
            pos=scene.points,
            size=self._point_size.value(),
            pxMode=True,
            color=(0.08, 0.35, 0.72, self._point_strength.value() / 100),
            glOptions="translucent",
        )
        # Keep terrain occlusion; transparent dots must not hide later dots.
        self._cloud.updateGLOptions({"glDepthMask": (False,)})
        self._cloud.setDepthValue(10)
        self._view.addItem(self._cloud)
        self._add_axes(lo)
        self._style_changed()
        self._reset_view()
        self._summary.setText(
            f"Cell {scene.cell.ix}/{scene.cell.iy} · 5 x 5 km · "
            f"{scene.climb_runs:,} Vilpellet climbs in the all-date ranking\n"
            f"{len(scene.points):,} intersections · "
            f"{scene.contributing_flights:,} contributing flights · "
            f"H = {scene.cell.ground_m:.2f} m + 0, 20, 40, … m"
        )
        self._source.setText(
            '<a href="https://www.data.gouv.fr/datasets/rge-alti-r">'
            "© IGN RGE ALTI · Licence Ouverte 2.0</a> · "
            f"DEM sampling {scene.reference['grid_m'][0]:g} m · "
            f"terrain {lo:.0f}-{hi:.0f} m ASL. "
            "Recorder GNSS heights are not harmonised with IGN terrain heights."
        )
        message = "All saved intersections at 20 m levels are included; no subsampling."
        if not len(scene.points):
            message = (
                "No intersections at 20 m levels in this interval. "
                "Terrain remains visible."
            )
        if scene.unavailable_flights or scene.unclassified_flights:
            message += (
                f" {scene.unavailable_flights:,} unavailable flights; "
                f"{scene.unclassified_flights:,} unclassified flights."
            )
        if scene.unknown_clock_flights:
            message += f" {scene.unknown_clock_flights:,} flights have no usable UTC."
        self._status.setText(message)

    def _add_axes(self, minimum):
        """Add a kilometre grid and labelled east, north and absolute altitude."""
        floor = 500 * np.floor(minimum / 500)
        grid = gl.GLGridItem(color=(90, 105, 120, 85), glOptions="translucent")
        grid.setSize(5000, 5000)
        grid.setSpacing(1000, 1000)
        grid.translate(0, 0, floor)
        grid.setDepthValue(20)
        self._view.addItem(grid)
        labels = [((2700, -2500, floor), "E · 1 km grid"), ((-2500, 2700, floor), "N")]
        ceiling = max(self._scene.cell.max_alt_m, self._scene.terrain.max())
        for height in np.arange(floor, ceiling + 1, 500):
            labels.append(((-2600, -2600, height), f"{height:.0f} m ASL"))
        for pos, text in labels:
            item = gl.GLTextItem(pos=pos, text=text, color="#334155")
            item.setDepthValue(30)
            self._view.addItem(item)

    def _style_changed(self, *_):
        """Update appearance without reloading arrays or resetting the camera."""
        if self._surface is not None:
            self._surface.setVisible(self._terrain.isChecked())
        if self._cloud is not None:
            self._cloud.setData(
                color=(0.08, 0.35, 0.72, self._point_strength.value() / 100),
                size=self._point_size.value(),
            )

    def _reset_view(self, *_, top=False):
        """Frame the full cell and all displayed altitudes."""
        if self._scene is None:
            return
        scene = self._scene
        low = float(scene.terrain.min())
        high = max(
            float(scene.terrain.max()),
            float(scene.points[:, 2].max()) if len(scene.points) else low,
        )
        aspect = max(1, self._view.width() / max(self._view.height(), 1))
        half_angle = np.arctan(np.tan(np.deg2rad(30)) / aspect)
        radius = 0.5 * np.sqrt(2 * 5000**2 + (high - low) ** 2)
        distance = 1.1 * radius / np.sin(half_angle)
        self._view.opts["fov"] = 60
        self._view.setCameraPosition(
            pos=QVector3D(0, 0, (low + high) / 2),
            distance=float(distance),
            elevation=90 if top else 35,
            azimuth=-90 if top else -55,
        )

    def _toggle_fullscreen(self):
        """Enlarge the 3D window independently of the parent viewer."""
        if self.isFullScreen():
            self.showNormal()
            self._fullscreen.setText("Full screen")
        else:
            self.showFullScreen()
            self._fullscreen.setText("Exit full screen")

    def keyPressEvent(self, event):  # noqa: N802
        """Escape first exits full screen, then closes the ordinary dialog."""
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self._toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def _cancel_loading(self):
        """Cancel at the next saved flight boundary."""
        if self._worker is not None:
            self._worker.cancel.set()
            self._status.setText("Cancelling the saved-data read…")

    def shutdown(self):
        """Join before closing or replacing a request and discard queued results."""
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.cancel.set()
            worker.wait()
        self._cancel.setEnabled(False)

    def reject(self):
        """Stop loading when Escape closes the dialog."""
        self.shutdown()
        super().reject()

    def closeEvent(self, event):  # noqa: N802
        """Stop loading before the window is hidden."""
        self.shutdown()
        super().closeEvent(event)
