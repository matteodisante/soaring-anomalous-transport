"""Four metric cells and a movable horizontal cross-section through their climbs."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, timedelta
from itertools import pairwise
from threading import Event

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.patches import Polygon
from PyQt6.QtCore import QDate, QDateTime, Qt, QThread, QTime, QTimeZone, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .. import geography
from ..thermal_daily import height_levels, local_bounds
from ..thermal_geometry import plane_intersections, unproject
from ..thermal_ridges import draw_ridges, load_ridges
from ..thermal_store import CancelledError, PlaneData, ThermalStore, load_store
from .thermal_info import ThermalInfo


class _Worker(QThread):
    """Run one cancellable I/O/decoding operation outside the GUI thread."""

    progress = pyqtSignal(str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation, parent):
        """Keep the operation and a cooperative cancellation flag."""
        super().__init__(parent)
        self.operation = operation
        self.cancel = Event()

    def run(self):
        """Publish only complete results; leave cancelled/failed caches untouched."""
        try:
            result = self.operation(progress=self.progress.emit, cancel=self.cancel)
            if not self.cancel.is_set():
                self.succeeded.emit(result)
        except CancelledError:
            self.failed.emit("Cancelled. No partial result is displayed.")
        except Exception as exc:
            self.failed.emit(f"Could not load thermal cells: {exc}")


class ThermalPlane(QWidget):
    """An all-time crossing census followed by a selected UTC climb-plane view."""

    def __init__(self, parent=None):
        """Build controls without reading any archive at application startup."""
        super().__init__(parent)
        self._index: ThermalStore | None = None
        self._plane: PlaneData | None = None
        self._worker: _Worker | None = None
        self._reliefs = OrderedDict()
        self._map_labels = []
        self._tried_cache = False
        self._auto_load = False
        self._dates_initialized = False
        self._daily_info = ""
        self._daily_days = {}
        self._build = QPushButton("Reload SSD data")
        self._build.setToolTip(
            "Read the completed thermal-planes.sqlite3 file from the SSD."
        )
        self._cells = QComboBox()
        self._cells.setMinimumContentsLength(20)
        self._source = QComboBox()
        self._source.addItem("This work (HMM)", "own")
        self._source.addItem("Jérémie (Vilpellet)", "vilpellet")
        self._source.setCurrentIndex(1)
        self._start, self._end = QDateTimeEdit(), QDateTimeEdit()
        for edit in (self._start, self._end):
            edit.setTimeZone(QTimeZone(b"Europe/Paris"))
            edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss 'Paris'")
            edit.setCalendarPopup(True)
            edit.setKeyboardTracking(False)
        self._load = QPushButton("Load climb intersections")
        self._cancel = QPushButton("Cancel")
        self._cancel.setEnabled(False)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._levels = np.array([0.0])
        self._step = QComboBox()
        for step in (10, 20, 50, 100, 200):
            self._step.addItem(f"{step} m", step)
        self._height = QDoubleSpinBox()
        self._height.setDecimals(2)
        self._height.setSuffix(" m AGL")
        self._height.setRange(0, 0)
        self._height.setSingleStep(10)
        self._background = QComboBox()
        self._background.addItem("Colour map · IGN", "colour")
        self._background.addItem("Aerial photo · IGN", "aerial")
        self._background.addItem("Shaded relief", "relief")
        self._background.addItem("None", "none")
        self._background.setCurrentIndex(0)
        self._ridges = QCheckBox("Crests · IGN DEM")
        self._ridges.setChecked(True)
        self._ridges.setToolTip(
            "Show approximate crest lines derived from IGN terrain, "
            "including secondary ridges. "
            "These ground locations do not change with the plane height."
        )
        self._image_info = QLabel()
        self._image_info.setWordWrap(True)
        self._mode = QComboBox()
        self._mode.addItems(["Whole interval", "Morning / midday / afternoon"])
        self._day = QDateEdit(QDate.currentDate())
        self._day.setDisplayFormat("yyyy-MM-dd")
        self._day.setCalendarPopup(True)
        self._day.setKeyboardTracking(False)
        self._best_day = QPushButton("Busiest summer day")
        self._before, self._after = QSpinBox(), QSpinBox()
        for spin in (self._before, self._after):
            spin.setRange(0, 365)
        self._bands = [QTimeEdit(QTime(h, 0)) for h in (8, 11, 15, 18)]
        for edit, tooltip in zip(
            self._bands,
            (
                "Morning starts (Paris time)",
                "Morning ends / midday starts",
                "Midday ends / afternoon starts",
                "Afternoon ends",
            ),
            strict=True,
        ):
            edit.setDisplayFormat("HH:mm")
            edit.setToolTip(tooltip)
            edit.setKeyboardTracking(False)
        self._relief_strength = QDoubleSpinBox()
        self._relief_strength.setRange(0, 100)
        self._relief_strength.setDecimals(0)
        self._relief_strength.setSingleStep(5)
        self._relief_strength.setValue(35)
        self._relief_strength.setSuffix("% background")
        self._relief_strength.setToolTip(
            "Strength of the saved terrain backdrop on both maps"
        )
        self._summary = QLabel(
            "Metropolitan France · both available disciplines · "
            "5 x 5 km Lambert-93 cells.\n"
            "Ranked by all-time distinct crossing flights. Ground: median raw GNSS "
            "launch altitude of flights starting inside the cell."
        )
        self._summary.setWordWrap(True)
        self._status = QLabel(
            "Connect the SSD to read the prepared cells and both segmentations."
        )
        self._status.setWordWrap(True)
        self._view = QComboBox()
        self._view.addItem("France + horizontal plane", "overview")
        self._view.addItem("France only", "france")
        self._view.addItem("Horizontal plane only", "planes")
        self._view.setToolTip(
            "Choose the maps to enlarge; use Full screen at the top right"
        )
        self._details = QPushButton("Cell details")
        self._details.setCheckable(True)
        self._details.toggled.connect(self._summary.setVisible)
        self._info = QPushButton("Info")
        self._info.setToolTip("How the cells, ground altitude and AGL are obtained")
        self._info_panel: ThermalInfo | None = None
        self._info.clicked.connect(self._show_info)
        self._summary.hide()
        top = QHBoxLayout()
        for widget in (self._mode, self._cells, self._source):
            top.addWidget(widget)
        self._time_settings = QWidget()
        times = QHBoxLayout(self._time_settings)
        times.setContentsMargins(0, 0, 0, 0)
        for label, widget in (("From", self._start), ("To", self._end)):
            times.addWidget(QLabel(label))
            times.addWidget(widget)
        heights = QHBoxLayout()
        heights.addWidget(QLabel("Horizontal plane"))
        heights.addWidget(self._slider, 1)
        heights.addWidget(QLabel("Step"))
        heights.addWidget(self._step)
        heights.addWidget(self._height)
        heights.addWidget(self._background)
        heights.addWidget(self._relief_strength)
        heights.addWidget(self._ridges)
        self._figure = Figure(figsize=(10, 5), layout="constrained")
        self._map_ax, self._plane_ax = self._figure.subplots(
            1, 2, width_ratios=[1, 1.5]
        )
        self._plane_axes = [self._plane_ax]
        self._panel_indices = [0]
        self._canvas = FigureCanvasQTAgg(self._figure)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._summary)
        layout.setSpacing(4)
        layout.addWidget(self._time_settings)
        self._daily_settings = QWidget()
        daily = QHBoxLayout(self._daily_settings)
        daily.setContentsMargins(0, 0, 0, 0)
        for item in (
            self._day,
            self._best_day,
            QLabel("Days before"),
            self._before,
            QLabel("after"),
            self._after,
            QLabel("Paris hours"),
        ):
            daily.addWidget(item)
        for edit in self._bands:
            daily.addWidget(edit)
        layout.addWidget(self._daily_settings)
        self._daily_settings.hide()
        layout.addLayout(heights)
        layout.addWidget(self._image_info)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        navigation = QHBoxLayout()
        navigation.addWidget(self._toolbar)
        navigation.addWidget(QLabel("View"))
        navigation.addWidget(self._view)
        navigation.addStretch(1)
        for button in (
            self._info,
            self._details,
            self._build,
            self._load,
            self._cancel,
        ):
            navigation.addWidget(button)
        layout.addLayout(navigation)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._status)
        self._build.clicked.connect(self._start_index)
        self._cells.currentIndexChanged.connect(self._cell_changed)
        self._source.currentIndexChanged.connect(self._invalidate_plane)
        self._start.dateTimeChanged.connect(self._invalidate_plane)
        self._end.dateTimeChanged.connect(self._invalidate_plane)
        self._load.clicked.connect(self._start_plane)
        self._cancel.clicked.connect(self._cancel_work)
        self._step.currentIndexChanged.connect(self._step_changed)
        self._background.currentIndexChanged.connect(self._relief_changed)
        self._mode.currentIndexChanged.connect(self._mode_changed)
        self._view.currentIndexChanged.connect(self._layout_changed)
        self._best_day.clicked.connect(self._select_best_day)
        self._day.dateChanged.connect(self._daily_changed)
        self._before.valueChanged.connect(self._daily_changed)
        self._after.valueChanged.connect(self._daily_changed)
        for edit in self._bands:
            edit.timeChanged.connect(self._draw_plane)
        self._slider.valueChanged.connect(self._slider_changed)
        self._height.valueChanged.connect(self._height_changed)
        self._relief_strength.valueChanged.connect(self._relief_changed)
        self._ridges.toggled.connect(self._draw_plane)
        self._canvas.mpl_connect("button_press_event", self._map_clicked)
        self._set_busy(False)
        self._draw_map()
        self._draw_plane()

    def ensure_loaded(self):
        """Read saved data only; opening a tab never starts expensive preparation."""
        if not self._tried_cache and self._worker is None:
            self._tried_cache = True
            self._run(lambda **_: load_store(), self._saved_index_ready)

    def _saved_index_ready(self, index):
        """Offer explicit preparation when there is no current saved census."""
        if index is None:
            self._index = self._plane = None
            self._cells.clear()
            self._draw_map()
            self._draw_plane()
            self._status.setText(
                "Prepared thermal-planes.sqlite3 not found. Connect the SSD. "
                "Prepare separately with scripts/pipeline/prepare_thermal_planes.py."
            )
        else:
            self._index_ready(index)

    def invalidate(self):
        """Drop results after the application's archive folders change."""
        self.shutdown()
        self._index = self._plane = None
        self._tried_cache = False
        self._cells.clear()
        self._set_busy(False)
        self._draw_map()
        self._draw_plane()
        self._status.setText("Archive folders changed. Reload the prepared SSD data.")

    def shutdown(self):
        """Join the cooperative worker before Qt destroys its owning widget."""
        self._auto_load = False
        if self._worker is not None:
            self._worker.cancel.set()
            # Disconnect queued results: a completed old archive must never replace
            # the state after a folder change or widget shutdown.
            self._worker.succeeded.disconnect()
            self._worker.wait()
            self._worker = None

    def _cancel_work(self):
        """Request cancellation at the next archive/flight boundary."""
        if self._worker is not None:
            self._worker.cancel.set()
            self._status.setText("Cancelling after the current flight/block…")

    def _set_busy(self, busy):
        """Prevent controls from changing the meaning of an in-flight request."""
        self._build.setEnabled(not busy)
        self._cancel.setEnabled(busy)
        for widget in (
            self._cells,
            self._source,
            self._start,
            self._end,
            self._load,
            self._day,
            self._best_day,
            self._before,
            self._after,
        ):
            widget.setEnabled(
                not busy and self._index is not None and self._cells.count() > 0
            )
        for widget in (self._slider, self._height, self._step):
            widget.setEnabled(not busy and self._plane is not None)

    def _run(self, operation, on_success):
        """Connect a worker result to this widget's GUI-thread slot."""
        if self._worker is not None:
            return
        self._set_busy(True)
        self._worker = _Worker(operation, self)
        self._on_success = on_success
        self._worker.progress.connect(self._progress)
        self._worker.failed.connect(self._progress)
        self._worker.succeeded.connect(self._receive_result)
        self._worker.finished.connect(self._finished)
        self._worker.start()

    def _progress(self, message):
        """Ignore queued messages from an invalidated archive request."""
        if self.sender() is self._worker:
            self._status.setText(message)

    def _receive_result(self, result):
        """Accept only the live, uncancelled request's result on the GUI thread."""
        if self.sender() is self._worker and not self._worker.cancel.is_set():
            self._on_success(result)

    def _finished(self):
        """Restore controls once the worker has fully exited."""
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
            self._set_busy(False)
            if self._auto_load:
                self._auto_load = False
                self._start_plane()
        worker.deleteLater()

    def _start_index(self):
        """Reload only the standalone prepared file; never prepare inside the GUI."""
        self._plane = None
        self._draw_plane()
        self._run(lambda **_: load_store(), self._saved_index_ready)

    def _index_ready(self, index):
        """Expose the four winning cells with their distinct crossing counts."""
        self._index = index
        self._reliefs.clear()
        previous = self._cells.currentData()
        ranks = {}
        self._cells.blockSignals(True)
        self._cells.clear()
        for cell in index.cells():
            ranks[cell.terrain] = ranks.get(cell.terrain, 0) + 1
            self._cells.addItem(
                f"{cell.terrain} #{ranks[cell.terrain]} · {cell.flights:,} flights "
                f"· ground {cell.ground_m:g} m",
                cell,
            )
        if previous is not None:
            for i in range(self._cells.count()):
                c = self._cells.itemData(i)
                if (c.ix, c.iy) == (previous.ix, previous.iy):
                    self._cells.setCurrentIndex(i)
                    break
        self._cells.blockSignals(False)
        if not self._dates_initialized and self._cells.count():
            if hasattr(index, "time_extent"):
                start, end = index.time_extent()
            else:
                start, _ = index.defaults(self._cells.currentData())
                end = start + 86399
            for edit, stamp in (
                (self._start, np.floor(start)),
                (self._end, np.ceil(end)),
            ):
                edit.blockSignals(True)
                edit.setDateTime(
                    QDateTime.fromSecsSinceEpoch(int(stamp), QTimeZone(b"Europe/Paris"))
                )
                edit.blockSignals(False)
            self._dates_initialized = True
        self._cell_changed()
        bands = {self._cells.itemData(i).terrain for i in range(self._cells.count())}
        missing = [name for name in geography.TERRAIN_ORDER if name not in bands]
        self._status.setText(
            f"Indexed archives: {', '.join(index.disciplines)}. "
            + (
                f"No cell with a ground reference for: {', '.join(missing)}. "
                if missing
                else ""
            )
            + "Select an interval in Paris local time to read saved intersections."
        )

    def _cell_changed(self, *_):
        """Set a useful one-day window and the cell's fixed all-time height range."""
        cell = self._cells.currentData()
        self._plane = None
        if cell is not None and self._index is not None:
            _, height = self._index.defaults(cell)
            if hasattr(self._index, "summer_days"):
                days = self._index.summer_days(cell)
                if days:
                    self._day.blockSignals(True)
                    self._day.setDate(
                        self._daily_days.get(
                            (cell.ix, cell.iy),
                            QDate.fromString(days[0][0], "yyyy-MM-dd"),
                        )
                    )
                    self._day.blockSignals(False)
                    self._daily_info = (
                        f"Busiest summer day: {days[0][0]} · "
                        f"{days[0][1]} crossing flights"
                    )
            self._levels = height_levels(cell.max_agl_m, self._step.currentData())
            height = self._levels[np.argmin(abs(self._levels - height))]
            self._height.blockSignals(True)
            self._height.setRange(0, cell.max_agl_m)
            self._height.setValue(height)
            self._height.blockSignals(False)
            origin_kind = (
                "screened raw"
                if getattr(self._index, "quality_summary", None)
                else "raw"
            )
            self._summary.setText(
                f"{cell.terrain} #{self._rank(cell)} · 5 x 5 km (Lambert-93) · "
                f"{cell.flights:,} distinct "
                f"crossing flights, all dates. Ground: {cell.ground_m:.1f} m "
                f"(median of {cell.launches:,} {origin_kind} GNSS starts inside). "
                f"Maximum inside cell: {cell.max_agl_m:.1f} m AGL.\n"
                "Bands use the ground median: <300 / 300-800 / 800-1500 / ≥1500 m. "
                "AGL uses this fixed reference; shaded terrain is a separate backdrop."
                + (
                    " Few starts: altitude category has limited support."
                    if cell.launches < 10
                    else ""
                )
            )
            if hasattr(self._index, "reference_audit"):
                audit = self._index.reference_audit(cell)
                if audit is not None:
                    self._summary.setText(
                        self._summary.text() + f" Raw start audit: {audit[0]} starts, "
                        f"median {audit[1]:g} m; "
                        f"{audit[0] - cell.launches} excluded by origin screen."
                    )
        self._set_busy(self._worker is not None)
        self._height_changed()
        self._draw_map()
        if cell is not None:
            if self._worker is None:
                self._start_plane()
            else:
                self._auto_load = True

    def _invalidate_plane(self, *_):
        """Hide stale results immediately when the UTC interval or decoder changes."""
        self._plane = None
        self._set_busy(self._worker is not None)
        self._status.setText(
            "Selection changed. Load climb intersections for this interval."
        )
        self._draw_plane()

    def _start_plane(self):
        """Read the saved climb edges for the selected source/window."""
        cell = self._cells.currentData()
        start, end = self._read_bounds()
        if cell is None or self._index is None:
            return
        if end < start:
            self._status.setText("The end time must be at or after the start time.")
            return
        index, source = self._index, self._source.currentData()
        self._plane = None
        self._draw_plane()
        self._run(
            lambda **kwargs: index.read_plane(cell, start, end, source, **kwargs),
            self._plane_ready,
        )

    def _plane_ready(self, plane):
        """Report absent models/UTC explicitly, including an entirely empty slice."""
        self._plane = plane
        if plane.points is not None and not plane.points.empty:
            clock = pd.to_datetime(plane.points.utc, unit="s", utc=True).dt.tz_convert(
                "Europe/Paris"
            )
            plane.points["local_hour"] = (
                clock.dt.hour
                + clock.dt.minute / 60
                + clock.dt.second / 3600
                + clock.dt.microsecond / 3.6e9
            )
        self._status.setText(
            f"{plane.selected} flights overlap the interval; "
            f"{plane.cached} read from the prepared SSD file; "
            f"{plane.unclassified} entirely unclassified; "
            f"{plane.unavailable} unavailable. "
            f"{plane.unknown_clock} all-time visitors lack a recoverable UTC origin. "
            "Points are climb crossings; several may belong to the same thermal."
        )
        self._draw_plane()

    def _utc_bounds(self):
        """UTC epoch seconds, independent of the computer's local timezone."""
        return (
            self._start.dateTime().toSecsSinceEpoch(),
            self._end.dateTime().toSecsSinceEpoch(),
        )

    def _read_bounds(self):
        """Comparison dates are independent of the user's full interval."""
        if not self._mode.currentIndex():
            return self._utc_bounds()
        day = date.fromisoformat(self._day.date().toString("yyyy-MM-dd"))
        return (
            local_bounds(day - timedelta(days=self._before.value()))[0],
            local_bounds(day + timedelta(days=self._after.value()))[1] - 1e-6,
        )

    def _select_best_day(self):
        cell = self._cells.currentData()
        if (
            self._index is not None
            and cell is not None
            and hasattr(self._index, "summer_days")
        ):
            days = self._index.summer_days(cell)
            if days:
                self._day.setDate(QDate.fromString(days[0][0], "yyyy-MM-dd"))

    def _daily_changed(self, *_):
        cell = self._cells.currentData()
        if cell is not None:
            self._daily_days[(cell.ix, cell.iy)] = self._day.date()
        if self._mode.currentIndex():
            self._invalidate_plane()
            self._start_plane()

    def _mode_changed(self, *_):
        """Change time selection independently from the visual layout."""
        daily = bool(self._mode.currentIndex())
        previous = self._view.currentData()
        self._view.blockSignals(True)
        self._view.clear()
        if daily:
            for label, value in (
                ("Three time periods", "planes"),
                ("France only", "france"),
                ("Morning only", "morning"),
                ("Midday only", "midday"),
                ("Afternoon only", "afternoon"),
            ):
                self._view.addItem(label, value)
        else:
            for label, value in (
                ("France + horizontal plane", "overview"),
                ("France only", "france"),
                ("Horizontal plane only", "planes"),
            ):
                self._view.addItem(label, value)
        if previous == "france":
            self._view.setCurrentIndex(self._view.findData(previous))
        self._view.blockSignals(False)
        self._time_settings.setVisible(not daily)
        self._daily_settings.setVisible(daily)
        self._plane = None
        self._layout_changed()
        self._invalidate_plane()
        self._start_plane()

    def _layout_changed(self, *_):
        """Allocate the figure to the chosen maps without loading or changing data."""
        self._figure.clear()
        self._map_ax = None
        self._plane_axes = []
        self._panel_indices = []
        view = self._view.currentData()
        if view == "france":
            self._map_ax = self._figure.subplots()
        elif view == "overview":
            self._map_ax, ax = self._figure.subplots(1, 2, width_ratios=[1, 1.5])
            self._plane_axes = [ax]
            self._panel_indices = [0]
        elif view == "planes" and self._mode.currentIndex():
            self._plane_axes = list(
                self._figure.subplots(1, 3, sharex=True, sharey=True)
            )
            self._panel_indices = [0, 1, 2]
        else:
            self._plane_axes = [self._figure.subplots()]
            self._panel_indices = [
                {"morning": 0, "midday": 1, "afternoon": 2}.get(view, 0)
            ]
        self._plane_ax = self._plane_axes[0] if self._plane_axes else None
        self._toolbar.update()
        self._draw_map()
        self._draw_plane()

    def _step_changed(self, *_):
        cell = self._cells.currentData()
        if cell is not None:
            self._levels = height_levels(cell.max_agl_m, self._step.currentData())
            self._height.setSingleStep(self._step.currentData())
            self._height_changed()

    def _slider_changed(self, value):
        """Choose one saved plane; no interpolation or segmentation at runtime."""
        self._height.setValue(self._levels[value])

    def _height_changed(self, *_):
        index = int(np.argmin(abs(self._levels - self._height.value())))
        self._height.blockSignals(True)
        self._height.setValue(self._levels[index])
        self._height.blockSignals(False)
        self._slider.blockSignals(True)
        self._slider.setRange(0, len(self._levels) - 1)
        self._slider.setValue(index)
        self._slider.blockSignals(False)
        self._draw_plane()

    def _show_info(self):
        """Open the explanatory panel, creating it on first use."""
        if self._info_panel is None:
            self._info_panel = ThermalInfo(self)
        self._info_panel.show()
        self._info_panel.raise_()

    def _rank(self, cell):
        """Population rank is local to an altitude category, never across categories."""
        peers = [
            self._cells.itemData(i)
            for i in range(self._cells.count())
            if self._cells.itemData(i).terrain == cell.terrain
        ]
        return peers.index(cell) + 1

    def _saved_relief(self, cell=None):
        """Decode each SSD image once; slider redraws use only in-memory arrays."""
        kind = self._background.currentData()
        if kind == "none":
            return None
        key = (kind, "france" if cell is None else (cell.ix, cell.iy))
        if key not in self._reliefs and self._index is not None:
            self._reliefs[key] = (
                self._index.background(cell, kind)
                if hasattr(self._index, "background")
                else self._index.relief(cell)
                if hasattr(self._index, "relief")
                else None
            )
        if key in self._reliefs:
            self._reliefs.move_to_end(key)
        while len(self._reliefs) > 4:
            self._reliefs.popitem(last=False)
        return self._reliefs.get(key)

    def _relief_changed(self, *_):
        """Adjust background strength without changing any scientific result."""
        self._draw_map()
        self._draw_plane()

    def _draw_map(self):
        """Show numbered, category-coloured cells and separated ranking callouts."""
        ax = self._map_ax
        self._map_labels = []
        if ax is None:
            return
        ax.clear()
        basemap = geography.load_basemap()
        if basemap:
            geography.draw_land(ax, basemap["france"]["rings"], geography.FRANCE_EXTENT)
        else:
            ax.set_xlim(-5.5, 10)
            ax.set_ylim(41, 51.5)
        saved = self._saved_relief()
        if saved is not None:
            pixels, info = saved
            w, s, e, n = info["extent"]
            ax.imshow(
                pixels,
                extent=(w, e, s, n),
                origin="upper",
                alpha=self._relief_strength.value() / 100,
                zorder=0.5,
                aspect=1 / np.cos(np.deg2rad(46.25)),
            )
        current = self._cells.currentData()
        colors = dict(
            zip(
                geography.TERRAIN_ORDER,
                ("#197548", "#ad6412", "#7444a6", "#1d609a"),
                strict=True,
            )
        )
        codes = dict(zip(geography.TERRAIN_ORDER, ("P", "H", "L", "M"), strict=True))
        for i in range(self._cells.count()):
            cell = self._cells.itemData(i)
            rank = self._rank(cell)
            west, south, east, north = cell.bounds
            lon, lat = unproject([west, east, east, west], [south, south, north, north])
            color = colors[cell.terrain]
            selected = cell == current
            ax.add_patch(
                Polygon(
                    np.column_stack([lon, lat]),
                    facecolor=color,
                    edgecolor="black" if selected else color,
                    linewidth=2 if selected else 0.8,
                    alpha=0.85,
                    zorder=3,
                )
            )
            cx, cy = unproject((west + east) / 2, (south + north) / 2)
            ax.plot(
                cx,
                cy,
                "o",
                color=color,
                markersize=7 if selected else 4,
                markeredgecolor="black" if selected else "white",
                markeredgewidth=0.7,
                zorder=4,
            )
            # Callouts have fixed distinct rows even when 5 km cells are neighbours.
            # P/H on the west, L/M on the east; each retains its category and rank.
            band = geography.TERRAIN_ORDER.index(cell.terrain)
            tx = 0.01 if band < 2 else 0.59
            ty = 0.93 - (band % 2) * 0.32 - (rank - 1) * 0.073
            annotation = ax.annotate(
                f"{codes[cell.terrain]}{rank} · {cell.flights:,} · {cell.ground_m:g} m",
                (cx, cy),
                xytext=(tx, ty),
                textcoords="axes fraction",
                fontsize=8,
                color=color,
                fontweight="bold" if selected else "normal",
                bbox={
                    "boxstyle": "round,pad=0.25",
                    "fc": "white",
                    "ec": color if selected else "none",
                    "alpha": 0.94,
                },
                arrowprops={
                    "arrowstyle": "-",
                    "color": color,
                    "lw": 1.2 if selected else 0.55,
                    "alpha": 0.7,
                },
                zorder=6 if selected else 5,
            )
            self._map_labels.append((annotation, i))
        ax.text(
            0.02,
            0.02,
            "P: Plains   H: Hills\nL: Low mountains   M: High mountains\n"
            "1 / 2 / 3 = rank within category; m = median launch altitude",
            transform=ax.transAxes,
            fontsize=7,
            va="bottom",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9},
            zorder=7,
        )
        ax.set_title("Top 3 cells per altitude category", fontsize=11)
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
        self._canvas.draw_idle()

    def _map_clicked(self, event):
        """Select a winning cell by clicking its map marker as well as the dropdown."""
        if (
            self._map_ax is None
            or event.inaxes is not self._map_ax
            or self._worker is not None
        ):
            return
        renderer = self._canvas.get_renderer()
        for annotation, i in self._map_labels:
            if (
                annotation.get_bbox_patch()
                .get_window_extent(renderer)
                .contains(event.x, event.y)
            ):
                self._cells.setCurrentIndex(i)
                return
        for i in range(self._cells.count()):
            cell = self._cells.itemData(i)
            west, south, east, north = cell.bounds
            center = unproject((west + east) / 2, (south + north) / 2)
            px, py = self._map_ax.transData.transform(center)
            if np.hypot(px - event.x, py - event.y) < 12:
                self._cells.setCurrentIndex(i)
                return

    def _draw_plane(self, *_):
        """Filter saved points by level and Paris hour; keep all panels aligned."""
        cell = self._cells.currentData()
        saved = (
            self._saved_relief(cell if self._plane_axes else None)
            if cell is not None
            else None
        )
        info = saved[1] if saved else {}
        if (
            self._background.currentData() == "aerial"
            and saved
            and not self._plane_axes
        ):
            self._image_info.setText(
                "France overview: IGN mosaic with multiple acquisition dates. "
                "Select a horizontal plane to see its cell's acquisition dates. "
                f"Downloaded: {info.get('retrieved', '')[:10]}."
            )
        elif self._background.currentData() == "aerial" and saved:
            dates = info.get("acquisition_dates", [])
            acquisition = ", ".join(dates) if dates else "not supplied by IGN"
            self._image_info.setText(
                f"IGN aerial acquisition dates in this cell: {acquisition}. "
                "Dates differ from flight dates; France is a multi-date mosaic. "
                f"Downloaded: {info.get('retrieved', '')[:10]} · 1.25 m/pixel."
            )
        elif saved:
            self._image_info.setText(info.get("attribution", "Saved relief"))
        else:
            self._image_info.setText(
                "Background not prepared"
                if self._background.currentData() != "none"
                else ""
            )
        ridges = None
        if self._ridges.isChecked() and cell is not None and self._plane_axes:
            try:
                ridges = load_ridges(cell)
                ridge_info = (
                    f"Red crest lines: {len(ridges['features'])} pieces "
                    "derived from terrain · "
                    "© IGN RGE ALTI · Licence Ouverte 2.0"
                    if ridges is not None
                    else "IGN crest lines not prepared for this cell"
                )
            except (OSError, ValueError, KeyError) as exc:
                ridge_info = f"IGN crest overlay unavailable: {exc}"
            self._image_info.setText(
                " · ".join(filter(None, (self._image_info.text(), ridge_info)))
            )
        points = None
        if self._plane is not None and cell is not None and self._plane_axes:
            if self._plane.points is not None:
                level = int(
                    np.argmin(abs(height_levels(cell.max_agl_m) - self._height.value()))
                )
                points = self._plane.points.loc[self._plane.points.level == level]
            else:
                points = plane_intersections(
                    self._plane.edges, cell, self._height.value(), *self._read_bounds()
                )
                if not points.empty:
                    clock = pd.to_datetime(
                        points.utc, unit="s", utc=True
                    ).dt.tz_convert("Europe/Paris")
                    points["local_hour"] = (
                        clock.dt.hour + clock.dt.minute / 60 + clock.dt.second / 3600
                    )
        bands = [e.time().hour() + e.time().minute() / 60 for e in self._bands]
        valid_bands = all(a < b for a, b in pairwise(bands))
        labels = ("Morning", "Midday", "Afternoon")
        for i, ax in zip(self._panel_indices, self._plane_axes, strict=True):
            ax.clear()
            ax.set(xlim=(0, 5), ylim=(0, 5), xlabel="East (km)", ylabel="North (km)")
            ax.set_aspect("equal")
            ax.grid(alpha=0.15)
            if saved is not None:
                pixels, info = saved
                w, s, e, n = info["extent"]
                west, south, _, _ = cell.bounds
                ax.imshow(
                    pixels,
                    extent=(
                        (w - west) / 1000,
                        (e - west) / 1000,
                        (s - south) / 1000,
                        (n - south) / 1000,
                    ),
                    origin="upper",
                    alpha=self._relief_strength.value() / 100,
                    zorder=0,
                )
                ax.text(
                    0.01,
                    0.01,
                    info.get("attribution", "Relief: Esri / contributors"),
                    transform=ax.transAxes,
                    fontsize=6,
                    zorder=4,
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8},
                )
            selected = points
            if ridges is not None:
                draw_ridges(ax, cell, ridges)
            if (
                self._mode.currentIndex()
                and selected is not None
                and not selected.empty
            ):
                selected = (
                    selected.loc[
                        (selected.local_hour >= bands[i])
                        & (selected.local_hour < bands[i + 1])
                    ]
                    if valid_bands
                    else selected.iloc[:0]
                )
            count = len(selected) if selected is not None else 0
            flights = 0
            if count:
                flights = len(selected[["discipline", "flight_id"]].drop_duplicates())
                west, south, _, _ = cell.bounds
                for discipline, group in selected.groupby("discipline"):
                    from ...reporting.disciplines import DISCIPLINES

                    ax.scatter(
                        (group.x - west) / 1000,
                        (group.y - south) / 1000,
                        s=23,
                        alpha=0.95,
                        edgecolors="white",
                        linewidths=0.6,
                        zorder=3,
                        color=DISCIPLINES[discipline].color,
                        label=f"{discipline}: {len(group):,}",
                    )
                ax.legend(
                    fontsize=7,
                    loc="upper center",
                    bbox_to_anchor=(0.5, -0.13),
                    ncol=3,
                    columnspacing=0.8,
                    handletextpad=0.3,
                    borderaxespad=0,
                )
            else:
                message = (
                    "No intersections at this height and time"
                    if points is not None
                    else "Load saved intersections"
                )
                if self._mode.currentIndex() and not valid_bands:
                    message = "Hour boundaries must increase from left to right"
                ax.text(
                    0.5,
                    0.5,
                    message,
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=9,
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85},
                )
            prefix = ""
            if self._mode.currentIndex():
                prefix = (
                    f"{labels[i]} {self._bands[i].time().toString('HH:mm')}-"
                    f"{self._bands[i + 1].time().toString('HH:mm')} Paris\n"
                )
            ax.set_title(
                f"{prefix}z = {self._height.value():g} m AGL · "
                f"{count:,} points · {flights:,} flights",
                fontsize=10,
            )
        if self._mode.currentIndex():
            day = self._day.date()
            first = day.addDays(-self._before.value()).toString("yyyy-MM-dd")
            last = day.addDays(self._after.value()).toString("yyyy-MM-dd")
            self._figure.suptitle(
                f"{first} → {last} · "
                f"{1 + self._before.value() + self._after.value()} days pooled · "
                f"{self._daily_info}",
                fontsize=10,
            )
        else:
            self._figure.suptitle("")
        self._canvas.draw_idle()
