"""The trajectory viewer's main window: wires the flight picker to the plot.

The only module besides :mod:`soaring.viewer.app` and the ``widgets`` package that
imports Qt (see the package docstring).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import data, plotting
from .widgets.flight_picker import FlightPicker
from .widgets.map_view import MapView
from .widgets.plot_controls import PlotControls

if TYPE_CHECKING:
    from mpl_toolkits.mplot3d import Axes3D

    from ..analysis.preproc.enu import LocalFrame
    from ..analysis.preproc.pipeline import FlightResult
    from ..reporting.disciplines import Discipline


class MainWindow(QMainWindow):
    """The whole application: a flight picker beside a redrawable plot."""

    def __init__(self) -> None:
        """Build the picker/controls/canvas layout and show an empty plot."""
        super().__init__()
        self.setWindowTitle("Soaring trajectory viewer")
        self.resize(1300, 820)

        from ..analysis.config import load_preproc_config

        self._cfg = load_preproc_config()
        self._igc_path: Path | None = None
        self._discipline: Discipline | None = None
        self._flight_id: str | None = None
        self._raw: data.RawTrack | None = None
        self._cleaned: FlightResult | None = None
        self._phases: data.PhaseTrack | None = None
        self._frame: LocalFrame | None = None
        self._view_key: tuple[str, str, str, str | None] | None = None
        self._saved_views: dict[tuple, dict] = {}
        self._last_view_controls = (-60, 30, 100)
        self._has_3d_data = False

        self._picker = FlightPicker()
        self._picker.flight_chosen.connect(self._on_flight_chosen)
        self._picker.folders_changed.connect(self._on_folders_changed)
        self._picker.setMinimumWidth(320)
        self._picker.setMaximumWidth(420)

        self._controls = PlotControls()
        self._controls.changed.connect(self._redraw)
        self._controls.view_changed.connect(self._apply_view)
        self._controls.reset_view_requested.connect(self._reset_view)
        self._controls.save_pdf_requested.connect(self._on_save_pdf)

        self._figure = Figure(figsize=(7.5, 6.5))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)

        trajectory_tab = QWidget()
        trajectory_layout = QVBoxLayout(trajectory_tab)
        trajectory_layout.setContentsMargins(0, 0, 0, 0)
        trajectory_layout.addWidget(self._controls)
        trajectory_layout.addWidget(self._toolbar)
        trajectory_layout.addWidget(self._canvas, 1)

        self._map_view = MapView()
        self._map_view.flight_chosen.connect(self._on_flight_chosen_from_map)

        self._tabs = QTabWidget()
        self._tabs.addTab(trajectory_tab, "Trajectory")
        self._tabs.addTab(self._map_view, "Map")
        # The map's take-off points are only read from disk the first time this tab is
        # actually shown, not at startup: a full catalog + flights_meta read for both
        # disciplines is seconds of work the app should not pay before its window
        # even appears, for a tab the user may never open.
        self._tabs.currentChanged.connect(self._on_tab_changed)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._picker)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 960])
        self.setCentralWidget(splitter)

        self._redraw()

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.widget(index) is self._map_view:
            self._map_view.ensure_loaded()

    def _on_folders_changed(self) -> None:
        # The map cached takeoff_points() per discipline on its own (catalog_index's
        # cache was already cleared by the picker); without this it would keep
        # showing whichever root was current when it last loaded, silently stale.
        self._map_view.invalidate()
        if self._tabs.currentWidget() is self._map_view:
            self._map_view.ensure_loaded()

    def _on_flight_chosen_from_map(
        self, igc_path: Path, discipline: Discipline, flight_id: str
    ) -> None:
        self._tabs.setCurrentIndex(0)
        self._on_flight_chosen(igc_path, discipline, flight_id)

    # -- flight loading ------------------------------------------------------------
    def _on_flight_chosen(
        self, igc_path: Path, discipline: Discipline, flight_id: str
    ) -> None:
        self._saved_views.clear()
        self._view_key = None
        self._igc_path = igc_path
        self._discipline = discipline
        self._flight_id = flight_id
        self._cleaned = None
        self._phases = None
        self._frame = None

        try:
            self._raw = data.load_raw(igc_path, self._cfg)
        except Exception as exc:
            self._raw = None
            self._picker.set_status(f"Could not parse {igc_path.name}: {exc}")
            self._redraw()
            return

        status = f"{igc_path.name} — {discipline.name}, flight {flight_id}."
        try:
            self._cleaned = data.load_cleaned(
                igc_path,
                self._cfg,
                source=discipline.source,
                flight_id=flight_id,
                discipline=discipline.name,
            )
            self._frame = data.frame_from_meta(self._cleaned.meta)
            if self._cleaned.kept:
                status += " Current preprocessing: kept."
            if not self._cleaned.kept:
                meta = self._cleaned.meta
                status = (
                    f"{igc_path.name}: the pipeline dropped this flight at "
                    f"{meta.drop_stage} ({meta.drop_reason}); showing raw only."
                )
        except Exception as exc:
            status = (
                f"{igc_path.name}: the pipeline raised while cleaning it ({exc}); "
                "showing raw only."
            )

        if self._cleaned is not None and self._cleaned.kept:
            try:
                self._phases = data.load_flight_phases(self._cleaned.fixes, discipline)
                if self._phases is None:
                    status += " HMM phase model unavailable; using segment colours."
                elif not self._phases.fixes["phase"].ne("unclassified").any():
                    status += (
                        " No HMM-classifiable decision points; cleaned track in grey."
                    )
                elif self._phases.mapping_method.startswith("manual"):
                    status += " HMM phases use the manual train-set calibration."
                else:
                    status += " HMM phase names are provisional pending annotation."
            except Exception as exc:
                status += f" HMM phases could not be decoded ({exc})."

        if self._frame is None:
            # No pipeline-produced frame -- either it never ran that far, or it
            # raised. Fall back to raw's own, so the ENU view still shows the full
            # raw track instead of nothing (there is never a cleaned trajectory to
            # align with in this case anyway: this early, kept is always False).
            self._frame = data.raw_only_frame(self._raw)

        self._picker.set_status(status)
        self._redraw()

    # -- drawing -----------------------------------------------------------------
    def _redraw(self) -> None:
        frame_kind = self._controls.frame_kind
        is_3d = self._controls.is_3d
        x, y = self._controls.x_column, self._controls.y_column
        z = self._controls.z_column if is_3d else None
        key = (frame_kind, x, y, z)
        if self._view_key is not None and self._figure.axes:
            old_ax = self._figure.axes[0]
            view = {"xlim": old_ax.get_xlim(), "ylim": old_ax.get_ylim()}
            if self._view_key[-1] is not None:
                old_ax3d = cast("Axes3D", old_ax)
                view.update(
                    zlim=old_ax3d.get_zlim(),
                    elev=old_ax3d.elev,
                    azim=old_ax3d.azim,
                    roll=old_ax3d.roll,
                )
            self._saved_views[self._view_key] = view
        saved_view = self._saved_views.get(key)
        if key == self._view_key and self._figure.axes:
            ax = self._figure.axes[0]
            ax.clear()
        else:
            ax = plotting.make_axes(self._figure, is_3d=is_3d)
            self._toolbar.update()
        self._view_key = key

        # A local copy, not `self._frame` at each use below: mypy narrows a local's
        # type across a function body but not an attribute's (another method could
        # change it in between, in general), and this function never reassigns it.
        frame = self._frame
        self._has_3d_data = False

        if self._raw is None and self._cleaned is None:
            plotting.center_message(ax, "Pick a flight to plot.", is_3d=is_3d)
            self._canvas.draw_idle()
            return

        if frame_kind == "enu" and frame is None:
            # Only reachable when even raw's own fallback frame failed: an IGC file
            # with no decodable position fix at all (data.raw_only_frame).
            plotting.center_message(
                ax,
                "No usable position fixes in this file — switch to the geographic "
                "frame, or pick another flight.",
                is_3d=is_3d,
            )
            self._canvas.draw_idle()
            return

        raw_table = None
        if self._controls.show_raw and self._raw is not None:
            if frame_kind == "geographic":
                raw_table = self._raw.fixes
            else:
                # The early return above already ruled out frame_kind == "enu" with
                # frame is None.
                assert frame is not None
                raw_table = data.raw_to_enu(self._raw, frame)

        cleaned_table = None
        color_by: str | None = "segment_id"
        group_by: str | None = None
        color_map = None
        show_cleaned = self._controls.show_cleaned
        if show_cleaned and self._cleaned is not None and self._cleaned.kept:
            phase_track = self._phases
            phase_mode = (
                self._controls.color_mode == "phase"
                and phase_track is not None
                and not phase_track.fixes.empty
            )
            cleaned_fixes = (
                phase_track.fixes
                if phase_mode and phase_track is not None
                else self._cleaned.fixes
            )
            if frame_kind == "geographic":
                # cleaned.kept implies frame is not None: both are set together, at
                # (and only past) pipeline stage (v) -- see data.frame_from_meta.
                assert frame is not None
                cleaned_table = data.cleaned_to_geographic(cleaned_fixes, frame)
            else:
                cleaned_table = cleaned_fixes
            if phase_mode:
                color_by = "phase"
                group_by = "phase_run"
                color_map = plotting.PHASE_COLORS
                assert phase_track is not None
                qualifier = (
                    "manual calibration"
                    if phase_track.mapping_method.startswith("manual")
                    else "provisional state names"
                )
                ax.set_title(f"Viterbi flight-phase segmentation — {qualifier}")
            elif self._controls.color_mode == "single":
                color_by = None
                group_by = "segment_id"

        color = self._discipline.color if self._discipline is not None else "#3477a8"
        plotting.plot_trajectory(
            ax,
            raw=raw_table,
            cleaned=cleaned_table,
            x=x,
            y=y,
            z=z,
            dms=self._controls.dms,
            cleaned_color=color,
            color_by=color_by,
            group_by=group_by,
            color_map=color_map,
        )
        self._has_3d_data = is_3d and (
            raw_table is not None or cleaned_table is not None
        )
        if saved_view is not None:
            ax.set_xlim(saved_view["xlim"])
            ax.set_ylim(saved_view["ylim"])
            if is_3d:
                ax3d = cast("Axes3D", ax)
                ax3d.set_zlim(saved_view["zlim"])
                ax3d.view_init(
                    elev=saved_view["elev"],
                    azim=saved_view["azim"],
                    roll=saved_view["roll"],
                )
        elif is_3d:
            ax3d = cast("Axes3D", ax)
            ax3d.view_init(elev=self._controls.elev_deg, azim=self._controls.azim_deg)
            factor = 100.0 / self._controls.zoom_percent
            ax.set_xlim(self._scaled(ax.get_xlim(), factor))
            ax.set_ylim(self._scaled(ax.get_ylim(), factor))
            ax3d.set_zlim(self._scaled(ax3d.get_zlim(), factor))
        self._last_view_controls = (
            self._controls.azim_deg,
            self._controls.elev_deg,
            self._controls.zoom_percent,
        )
        self._canvas.draw_idle()

    def _reset_view(self) -> None:
        """Reset the camera only when the user explicitly requests it."""
        self._saved_views.clear()
        self._view_key = None
        self._redraw()

    def _apply_view(self) -> None:
        """Orient/zoom the current 3D axes to match the controls, without re-plotting.

        A no-op in 2D, and whenever there is no plotted trajectory to orient (both
        guarded by ``_has_3d_data`` -- see ``_redraw``).
        """
        if not self._has_3d_data:
            self._canvas.draw_idle()
            return
        ax = cast("Axes3D", self._figure.axes[0])
        old_azim, old_elev, old_zoom = self._last_view_controls
        azim, elev, zoom = (
            self._controls.azim_deg,
            self._controls.elev_deg,
            self._controls.zoom_percent,
        )
        # A zoom change must preserve mouse rotation; an orientation change must
        # preserve pan/zoom. Apply only the control that actually changed.
        if azim != old_azim or elev != old_elev:
            ax.view_init(
                elev=elev if elev != old_elev else ax.elev,
                azim=azim if azim != old_azim else ax.azim,
                roll=ax.roll,
            )
        if zoom != old_zoom:
            factor = old_zoom / zoom
            ax.set_xlim(self._scaled(ax.get_xlim(), factor))
            ax.set_ylim(self._scaled(ax.get_ylim(), factor))
            ax.set_zlim(self._scaled(ax.get_zlim(), factor))
        self._last_view_controls = (azim, elev, zoom)
        self._canvas.draw_idle()

    @staticmethod
    def _scaled(limits: tuple[float, float], factor: float) -> tuple[float, float]:
        """``limits`` scaled by ``factor`` around its own midpoint."""
        lo, hi = limits
        center = (lo + hi) / 2.0
        half = (hi - lo) / 2.0 * factor
        return center - half, center + half

    def _on_save_pdf(self) -> None:
        default_name = f"{self._flight_id or 'trajectory'}.pdf"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save trajectory as PDF", default_name, "PDF files (*.pdf)"
        )
        if not path_str:
            return
        try:
            plotting.save_pdf(self._figure, path_str)
        except OSError as exc:
            QMessageBox.warning(self, "Could not save PDF", str(exc))
