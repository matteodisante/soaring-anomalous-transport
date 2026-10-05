"""Controls, legend and transparent all-flight thermal time on the route DEM."""

from __future__ import annotations

import numpy as np
from matplotlib import colormaps
from matplotlib.colors import LogNorm
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...analysis.segmentation.config import load_segmentation_config
from .flow_layout import FlowLayout


class RouteDensity(QWidget):
    """Show a fixed archive population independently of selected route flights."""

    def __init__(self, parent=None):
        """Offer an overlay toggle, opacity and a quantitative logarithmic key."""
        super().__init__(parent)
        self.mesh = self.view = self._scene = None
        self.enabled = QCheckBox("Thermal hours · all flights")
        self.enabled.setChecked(True)
        self.enabled.setToolTip(
            "All available HMM-classified flights crossing this area, both "
            "disciplines, all dates and heights; independent of the route filters"
        )
        self.opacity = QSpinBox()
        self.opacity.setRange(0, 100)
        self.opacity.setValue(75)
        self.opacity.setSuffix("% opacity")
        self.resolution = QComboBox()
        self.resolution.addItem("Thermal pixels: 250 m", 250)
        self.resolution.setToolTip(
            "Sum recorded seconds into larger ground pixels, then divide by their "
            "area. This grid is independent of the 10 km departure/arrival cells."
        )
        help_button = QPushButton("What is h/km²?")
        help_button.clicked.connect(self.show_help)
        self.legend = QLabel()
        self.legend.setFixedWidth(160)
        self.range = QLabel()
        self.details = QLabel("Thermal density: waiting for a route")
        self.details.setWordWrap(True)
        flow = FlowLayout()
        for widget in (
            self.enabled,
            self.resolution,
            self.opacity,
            self.legend,
            self.range,
            help_button,
        ):
            flow.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(flow)
        layout.addWidget(self.details)
        self.enabled.toggled.connect(self.update_style)
        self.opacity.valueChanged.connect(self.update_style)
        self.resolution.currentIndexChanged.connect(self._draw_grid)
        self.clear()

    def clear(self):
        """Release the old texture before its view clears OpenGL items."""
        self._release_mesh()
        self.mesh = self.view = self._scene = None
        self.enabled.setEnabled(False)
        self.opacity.setEnabled(False)
        self.resolution.setEnabled(False)
        self.legend.clear()
        self.range.clear()
        self.details.setText("Thermal density: waiting for a route")

    def _release_mesh(self):
        """Free one resolution's texture while keeping the scene and controls."""
        if self.mesh is not None and self.view is not None:
            if self.view.isValid():
                self.view.makeCurrent()
                self.mesh.release_density()
                self.view.doneCurrent()
            self.mesh.set_density(None, self.mesh._bounds)

    def attach(self, scene, view, surface):
        """Drape a conservative density raster on the same valid DEM triangles."""
        self.clear()
        if scene.density is None:
            self.details.setText(
                "Thermal density unavailable: "
                f"{scene.density_error or 'no prepared product'}. "
                "Use Prepare / refresh index."
            )
            return
        self._scene, self.view, self.mesh = scene, view, surface
        selected = self.resolution.currentData() or 250
        self.resolution.blockSignals(True)
        self.resolution.clear()
        for step in scene.density.rasters:
            self.resolution.addItem(f"Thermal pixels: {step:g} m", step)
        self.resolution.setCurrentIndex(max(0, self.resolution.findData(selected)))
        self.resolution.blockSignals(False)
        self.resolution.setEnabled(True)
        self._draw_grid()

    def _draw_grid(self, *_):
        """Replace only the density texture, preserving the shared terrain mesh."""
        if self._scene is None:
            return
        scene = self._scene
        data = scene.density.rasters[self.resolution.currentData()]
        self._release_mesh()
        norm = LogNorm(0.01, data.maximum, clip=True)
        cmap = colormaps["magma_r"]
        key = np.ascontiguousarray(cmap(np.linspace(0, 1, 160), bytes=True)[None, :, :])
        self.legend.setPixmap(
            QPixmap.fromImage(
                QImage(
                    key.data, 160, 1, key.strides[0], QImage.Format.Format_RGBA8888
                ).copy()
            ).scaled(160, 12)
        )
        self.range.setText(f"0.01 — {data.maximum:.0f} h/km² · log")
        self.details.setText(
            f"{data.hours:,.1f} recorded climb hours in the density frame · "
            f"{data.step:g} m pixels · HMM, all dates / heights / disciplines"
        )
        self.details.setToolTip(
            "Cumulative recorded climb time divided by ground area. "
            "This is not thermal probability or thermal count. "
            "Transparent pixels have no recorded climb time; they may be unvisited. "
            "Overview pixels sum the original 50 m grid. The aligned density frame "
            "can extend less than one pixel beyond the terrain."
        )
        if scene.terrain is None:
            self.details.setText(self.details.text() + " · DEM required for overlay")
            return
        rgba = cmap(norm(np.maximum(data.values, 0.01)), bytes=True)
        rgba[data.values <= 0, 3] = 0
        self.mesh.set_density(
            np.ascontiguousarray(rgba[::-1]),
            data.bounds - np.tile(scene.origin, 2),
        )
        self.enabled.setEnabled(True)
        self.opacity.setEnabled(True)
        self.update_style()

    def update_style(self, *_):
        """Change visibility and opacity without rebuilding or filtering seconds."""
        if self.mesh is not None:
            self.mesh.density_opacity = self.opacity.value() / 100
            self.mesh.set_density_visible(self.enabled.isChecked())
            self.mesh.update()

    def show_help(self):
        """Explain accumulated flight time with a concrete area-normalised example."""
        step = load_segmentation_config().decision_step_s
        QMessageBox.information(
            self,
            "What does thermal density measure?",
            "<b>A stopwatch for each ground pixel.</b><br><br>"
            "Add the time every recorded pilot spends above this pixel while "
            "classified as climbing. Different dates and heights all contribute. "
            "Two pilots in the same thermal each add their own time.<br><br>"
            "In a 1 km² pixel, 10 + 20 + 30 minutes from three flights give "
            "1 recorded hour, hence <b>1 h/km²</b>.<br><br>"
            "The underlying grid is 50 x 50 m = 0.0025 km²: 36 seconds there "
            "give 0.01 h / 0.0025 km² = <b>4 h/km²</b>. That pixel still contains "
            "only 36 recorded seconds, not four hours.<br><br>"
            "Larger pixels sum the original seconds and divide by their new area. "
            "They do not create observations between flights.<br><br>"
            "<b>Source:</b> the same saved HMM climb decisions as Thermal density "
            f"regions, every {step:g} seconds; consecutive climb decisions only, "
            "in the same flight and segment, "
            f"with gaps above {1.5 * step:g} seconds excluded. "
            "Time is split at pixel boundaries assuming linear motion.<br><br>"
            "This measures cumulative recorded climb time, not thermal counts, "
            "probability, or yearly frequency. No recorded climb time can also "
            "mean no flight visited. Route and fastest/slowest filters never "
            "change this all-flight background.",
        )
