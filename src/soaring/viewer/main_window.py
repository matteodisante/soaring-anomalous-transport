"""The trajectory viewer's main window: wires the flight picker to the plot.

The only module besides :mod:`soaring.viewer.app` and the ``widgets`` package that
imports Qt (see the package docstring).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from soaring.reporting.style import DISCIPLINE_COLORS

from . import data, plotting
from .widgets.flight_picker import FlightPicker
from .widgets.map_view import MapView
from .widgets.plot_controls import PlotControls
from .widgets.thermal_plane import ThermalPlane

if TYPE_CHECKING:
    from mpl_toolkits.mplot3d import Axes3D

    from ..analysis.preproc.enu import LocalFrame
    from ..analysis.preproc.pipeline import FlightResult
    from ..reporting.disciplines import Discipline

# What a segmentation is called, in the combo box and in the title above its panel.
SEGMENTATION_LABELS = {
    "own": "Chapter 4 HMM (this work)",
    "vilpellet": "Vilpellet (Jérémie)",
}

# Why a segmenter left a flight unlabelled, in words a status line can carry.  The keys
# are the `phase_reason` values of both segmenters.
_REASON_TEXT = {
    "flight_shorter_than_author_guard": (
        "shorter than the author's 3600-fix minimum flight"
    ),
    "cadence_above_gate": "logged slower than the 1.2 s cadence gate",
    "non_increasing_or_repeated_time": "repeated or non-increasing times",
    "segment_shorter_than_persistence_window": (
        "every segment shorter than the 30-fix persistence window"
    ),
    "dropped_flight_tail": "discarded as flight tail",
    "run_shorter_than_minimum": "every run shorter than the configured minimum",
    "search_not_followed_by_climb": "no search run confirmed by a climb",
    "no_eligible_decisions": "no eligible decision grid",
    "outside_decision_cells": "outside every decision cell",
    "unavailable_features": "unavailable features",
    "quality_masked": "reconstructed altitude or preprocessing edges",
    "feature_edge": "window edges",
}


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
        self._vilpellet_phases: data.PhaseTrack | None = None
        self._frame: LocalFrame | None = None
        self._view_key: tuple | None = None
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
        self._controls.fullscreen_requested.connect(self._toggle_full_screen)

        self._figure = Figure(figsize=(7.5, 6.5))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._canvas.mpl_connect("motion_notify_event", self._on_canvas_drag)

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
        self._thermal_plane = ThermalPlane()
        self._tabs.addTab(self._thermal_plane, "Thermal planes")
        # The map's take-off points are only read from disk the first time this tab is
        # actually shown, not at startup: a full catalog + flights_meta read for both
        # disciplines is seconds of work the app should not pay before its window
        # even appears, for a tab the user may never open.
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._fullscreen_button = QPushButton("Full screen")
        self._fullscreen_button.setToolTip(
            "Enlarge the active view and hide the flight picker. Esc to return."
        )
        self._fullscreen_button.clicked.connect(self._toggle_full_screen)
        self._tabs.setCornerWidget(self._fullscreen_button)
        self._fullscreen_state = None
        self._escape_fullscreen = QShortcut(QKeySequence("Esc"), self)
        self._escape_fullscreen.activated.connect(self._exit_full_screen)
        self._fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self._fullscreen_shortcut.activated.connect(self._toggle_full_screen)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._picker)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 960])
        self._splitter = splitter
        self.setCentralWidget(splitter)

        self._redraw()

    def _toggle_full_screen(self):
        """Enlarge the active tab, preserving every scientific control and result."""
        if self.isFullScreen() or self._fullscreen_state is not None:
            self._exit_full_screen()
        else:
            self._fullscreen_state = (
                self.windowState(),
                self.geometry(),
                self._splitter.sizes(),
                not self._picker.isHidden(),
            )
            self.showFullScreen()

    def _exit_full_screen(self):
        """Return to the previous window size and picker layout with Escape."""
        if self.isFullScreen() or self._fullscreen_state is not None:
            state = self._fullscreen_state
            self.setWindowState(state[0] if state else Qt.WindowState.WindowNoState)
            if (
                state
                and state[1] is not None
                and not state[0] & Qt.WindowState.WindowMaximized
            ):
                self.setGeometry(state[1])
            self._restore_full_screen_layout(state)

    def _restore_full_screen_layout(self, state):
        """Restore the sidebar even if a resize already cleared the Qt window flag."""
        if state:
            self._picker.setVisible(state[3])
            self._splitter.setSizes(state[2])
        self._fullscreen_state = None
        self._fullscreen_button.setText("Full screen")

    def changeEvent(self, event):  # noqa: N802
        """Handle the button and native macOS full-screen transitions alike."""
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange or not hasattr(
            self, "_splitter"
        ):
            return
        if self.isFullScreen():
            if self._fullscreen_state is None:
                self._fullscreen_state = (
                    event.oldState(),
                    None,
                    self._splitter.sizes(),
                    not self._picker.isHidden(),
                )
            self._picker.hide()
            self._fullscreen_button.setText("Exit full screen (Esc)")
        else:
            self._restore_full_screen_layout(self._fullscreen_state)

    def _on_tab_changed(self, index: int) -> None:
        """Load a tab's own data only the first time it is actually shown."""
        if self._tabs.widget(index) is self._map_view:
            self._map_view.ensure_loaded()
        elif self._tabs.widget(index) is self._thermal_plane:
            self._thermal_plane.ensure_loaded()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Cancel archive work before Qt destroys the thermal-plane worker."""
        self._thermal_plane.shutdown()
        super().closeEvent(event)

    def _on_folders_changed(self) -> None:
        """Invalidate the map and thermal-plane caches when the archive root changes."""
        # The map cached takeoff_points() per discipline on its own (catalog_index's
        # cache was already cleared by the picker); without this it would keep
        # showing whichever root was current when it last loaded, silently stale.
        self._map_view.invalidate()
        self._thermal_plane.invalidate()
        if self._tabs.currentWidget() is self._map_view:
            self._map_view.ensure_loaded()

    def _on_flight_chosen_from_map(
        self, igc_path: Path, discipline: Discipline, flight_id: str
    ) -> None:
        """Switch to the Trajectory tab and load the flight picked on the map."""
        self._tabs.setCurrentIndex(0)
        self._on_flight_chosen(igc_path, discipline, flight_id)

    def _vilpellet_status_text(self) -> str:
        """A short status clause for the Vilpellet segmentation of the current flight.

        Returns:
            A sentence naming the classified fraction, or the reason nothing was
            classified when the flight failed the segmenter's own eligibility gate.
        """
        track = self._vilpellet_phases
        if track is None:
            return "Vilpellet configuration unavailable; that panel stays empty."
        classified = track.fixes["phase"].ne("unclassified")
        if not classified.any():
            reasons = track.fixes["phase_reason"].value_counts()
            reason = str(reasons.index[0]) if len(reasons) else "unknown"
            text = _REASON_TEXT.get(reason, reason)
            return f"Vilpellet segmentation: none classified ({text})."
        percent = 100.0 * classified.mean()
        return f"Vilpellet segmentation: {percent:.1f}% of cleaned fixes classified."

    # -- flight loading ------------------------------------------------------------
    def _on_flight_chosen(
        self, igc_path: Path, discipline: Discipline, flight_id: str
    ) -> None:
        """Load one flight's raw track, cleaned trajectory and both segmentations."""
        self._saved_views.clear()
        self._view_key = None
        self._igc_path = igc_path
        self._discipline = discipline
        self._flight_id = flight_id
        self._cleaned = None
        self._phases = None
        self._vilpellet_phases = None
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
                if self._phases is not None:
                    coverage = self._phases.coverage
                    percent = coverage.get("unclassified_fix_percent")
                    if percent is not None:
                        status += f" Unclassified: {percent:.1f}% of cleaned fixes."
                        reasons = coverage.get("fixes_by_reason", {})
                        names = {
                            "feature_edge": "window edges",
                            "quality_masked": (
                                "reconstructed altitude / preprocessing edges"
                            ),
                            "no_eligible_decisions": "no eligible decision grid",
                            "outside_decision_cells": "outside decision cells",
                            "unavailable_features": "unavailable features",
                        }
                        details = [
                            f"{names.get(k, k)}: {v}"
                            for k, v in reasons.items()
                            if k != "classified"
                        ]
                        if details:
                            status += " (" + "; ".join(details) + ")."
                    if self._phases.sequence_prior_weight:
                        status += (
                            " Search optional; climb-to-transition preferred."
                            " Names remain provisional."
                            if self._phases.search_optional
                            else " Soft phase-cycle preference active (provisional)."
                        )
            except Exception as exc:
                status += f" HMM phases could not be decoded ({exc})."

            try:
                self._vilpellet_phases = data.load_vilpellet_phases(
                    self._cleaned.fixes, discipline
                )
                status += " " + self._vilpellet_status_text()
            except Exception as exc:
                status += f" Vilpellet segmentation could not be decoded ({exc})."

        if self._frame is None:
            # No pipeline-produced frame -- either it never ran that far, or it
            # raised. Fall back to raw's own, so the ENU view still shows the full
            # raw track instead of nothing (there is never a cleaned trajectory to
            # align with in this case anyway: this early, kept is always False).
            self._frame = data.raw_only_frame(self._raw)

        self._picker.set_status(status)
        self._redraw()

    # -- drawing -----------------------------------------------------------------
    def _panel_specs(
        self, mode: str
    ) -> list[tuple[str, data.PhaseTrack | None, str]]:
        """Which segmentation(s) to draw, one ``(key, phase_track, title)`` per panel.

        Args:
            mode: ``self._controls.segmentation_source`` -- ``"own"``, ``"vilpellet"``
                or ``"compare"``.

        Returns:
            One entry for a single panel, or the two (left then right) a comparison
            draws.
        """
        if mode == "vilpellet":
            return [
                ("vilpellet", self._vilpellet_phases, SEGMENTATION_LABELS["vilpellet"])
            ]
        if mode == "compare":
            return [
                ("own", self._phases, SEGMENTATION_LABELS["own"]),
                (
                    "vilpellet",
                    self._vilpellet_phases,
                    SEGMENTATION_LABELS["vilpellet"],
                ),
            ]
        return [("own", self._phases, SEGMENTATION_LABELS["own"])]

    def _redraw(self) -> None:
        """Draw the current flight under the selected axes, phase filter and camera.

        One panel for ``"own"`` or ``"vilpellet"``; two side by side, sharing their
        limits and (in 3D) their camera, for ``"compare"``. ``climb_only`` filters
        every panel to the climb fixes before drawing, and never draws the raw track.
        """
        frame_kind = self._controls.frame_kind
        is_3d = self._controls.is_3d
        x, y = self._controls.x_column, self._controls.y_column
        z = self._controls.z_column if is_3d else None
        mode = self._controls.segmentation_source
        climb_only = self._controls.climb_only
        panel_specs = self._panel_specs(mode)
        panels = len(panel_specs)
        # Extended with `mode` and `climb_only`, both of which change what is drawn
        # and how many panels there are: restoring a saved camera from an
        # incompatible layout (a different panel count) would misplace it, so the
        # saved-view lookup below keys on the whole tuple, not just the axes.
        key = (frame_kind, x, y, z, mode, climb_only)

        if self._view_key is not None and self._figure.axes:
            old_primary = self._figure.axes[0]
            view = {"xlim": old_primary.get_xlim(), "ylim": old_primary.get_ylim()}
            if self._view_key[3] is not None:
                old_primary3d = cast("Axes3D", old_primary)
                view.update(
                    zlim=old_primary3d.get_zlim(),
                    elev=old_primary3d.elev,
                    azim=old_primary3d.azim,
                    roll=old_primary3d.roll,
                )
            self._saved_views[self._view_key] = view
        saved_view = self._saved_views.get(key)

        reused = (
            key == self._view_key
            and len(self._figure.axes) == panels
            and self._figure.axes
        )
        if reused:
            axes = list(self._figure.axes)
            for ax in axes:
                ax.clear()
        else:
            drawn = plotting.make_axes(self._figure, is_3d=is_3d, panels=panels)
            axes = drawn if isinstance(drawn, list) else [drawn]
            self._toolbar.update()
        self._view_key = key

        frame = self._frame
        self._has_3d_data = False

        if self._raw is None and self._cleaned is None:
            plotting.center_message(axes, "Pick a flight to plot.", is_3d=is_3d)
            self._canvas.draw_idle()
            return

        if frame_kind == "enu" and frame is None:
            # Only reachable when even raw's own fallback frame failed: an IGC file
            # with no decodable position fix at all (data.raw_only_frame).
            plotting.center_message(
                axes,
                "No usable position fixes in this file — switch to the geographic "
                "frame, or pick another flight.",
                is_3d=is_3d,
            )
            self._canvas.draw_idle()
            return

        raw_table = None
        if self._controls.show_raw and self._raw is not None and not climb_only:
            if frame_kind == "geographic":
                raw_table = self._raw.fixes
            else:
                # The early return above already ruled out frame_kind == "enu" with
                # frame is None.
                assert frame is not None
                raw_table = data.raw_to_enu(self._raw, frame)

        color = (
            self._discipline.color
            if self._discipline is not None
            else DISCIPLINE_COLORS["paragliders"]
        )
        drawn_any = False
        for ax, (source_key, phase_track, title) in zip(
            axes, panel_specs, strict=True
        ):
            drawn_any |= self._draw_panel(
                ax,
                source_key=source_key,
                phase_track=phase_track,
                title=title,
                panels=panels,
                raw_table=raw_table,
                x=x,
                y=y,
                z=z,
                climb_only=climb_only,
                color=color,
            )
        self._has_3d_data = is_3d and drawn_any

        # A comparison that scales its two panels differently makes the same flight
        # look like two different ones, so this runs before either camera is set --
        # a camera then orients the (now-shared) view, it never re-scales it.
        if panels > 1:
            plotting.equalise_limits(axes)
        if saved_view is not None:
            axes[0].set_xlim(saved_view["xlim"])
            axes[0].set_ylim(saved_view["ylim"])
            if is_3d:
                primary3d = cast("Axes3D", axes[0])
                primary3d.set_zlim(saved_view["zlim"])
                primary3d.view_init(
                    elev=saved_view["elev"],
                    azim=saved_view["azim"],
                    roll=saved_view["roll"],
                )
        elif is_3d:
            primary3d = cast("Axes3D", axes[0])
            primary3d.view_init(
                elev=self._controls.elev_deg, azim=self._controls.azim_deg
            )
            factor = 100.0 / self._controls.zoom_percent
            axes[0].set_xlim(self._scaled(axes[0].get_xlim(), factor))
            axes[0].set_ylim(self._scaled(axes[0].get_ylim(), factor))
            primary3d.set_zlim(self._scaled(primary3d.get_zlim(), factor))
        if panels > 1 and is_3d:
            plotting.link_3d_axes(axes, source=axes[0])
        self._last_view_controls = (
            self._controls.azim_deg,
            self._controls.elev_deg,
            self._controls.zoom_percent,
        )
        self._canvas.draw_idle()

    def _draw_panel(
        self,
        ax,
        *,
        source_key: str,
        phase_track: data.PhaseTrack | None,
        title: str,
        panels: int,
        raw_table,
        x: str,
        y: str,
        z: str | None,
        climb_only: bool,
        color: str,
    ) -> bool:
        """Draw one segmentation's trajectory on ``ax``.

        Args:
            ax: The panel's axes.
            source_key: ``"own"`` or ``"vilpellet"`` -- which segmenter this panel
                shows, for the phase-mode title wording.
            phase_track: That segmentation's decoded track, or ``None`` when it could
                not be decoded (the panel then falls back to plain segment colours,
                the same fallback the single-panel Chapter 4 view has always used).
            title: The panel's segmentation name.
            panels: Total panel count. A single panel keeps this viewer's original,
                unlabelled style; a comparison always shows both panel titles.
            raw_table: The raw track to overlay, or ``None``.
            x: Column to plot on the x-axis.
            y: Column to plot on the y-axis.
            z: Column to plot on the z-axis, or ``None`` for 2D.
            climb_only: Whether to keep only the climb fixes.
            color: The cleaned trajectory's fallback colour.

        Returns:
            Whether this panel actually plotted a non-empty trajectory.
        """
        cleaned_table = None
        color_by: str | None = "segment_id"
        group_by: str | None = None
        color_map = None
        frame_kind = self._controls.frame_kind
        frame = self._frame
        show_cleaned = self._controls.show_cleaned
        if show_cleaned and self._cleaned is not None and self._cleaned.kept:
            if climb_only:
                cleaned_fixes = (
                    data.climb_only(phase_track.fixes)
                    if phase_track is not None
                    else self._cleaned.fixes.iloc[0:0]
                )
                phase_mode = phase_track is not None
            else:
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
            if frame_kind == "geographic" and len(cleaned_fixes):
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
            elif self._controls.color_mode == "single":
                color_by = None
                group_by = "segment_id"

        has_data = bool(
            (raw_table is not None and len(raw_table))
            or (cleaned_table is not None and len(cleaned_table))
        )
        displayed_title = title
        if color_by == "phase" and phase_track is not None:
            qualifier = (
                "manual calibration"
                if phase_track.mapping_method.startswith("manual")
                else "provisional state names"
            )
            if phase_track.sequence_prior_weight:
                qualifier += (
                    "; search optional"
                    if phase_track.search_optional
                    else "; soft cycle prior"
                )
            displayed_title = (
                f"{title} — {qualifier}"
                if panels > 1
                else f"Viterbi flight-phase segmentation — {qualifier}"
                if source_key == "own"
                else f"{title} segmentation — {qualifier}"
            )
        if climb_only and cleaned_table is not None and len(cleaned_table):
            n_thermals = (
                cleaned_table["phase_run"].nunique()
                if "phase_run" in cleaned_table
                else 0
            )
            total_s = 0.0
            if {"t", "phase_run"}.issubset(cleaned_table.columns):
                total_s = float(
                    cleaned_table.groupby("phase_run")["t"]
                    .apply(lambda s: s.max() - s.min())
                    .sum()
                )
            displayed_title += f" — {n_thermals} thermals, {total_s / 60:.0f} min"
        if panels > 1 or displayed_title != title:
            ax.set_title(displayed_title)

        if climb_only and not has_data:
            plotting.center_message(
                ax, f"{title}: no climb fixes to show.", is_3d=z is not None
            )
            return False

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
        return has_data

    def _on_canvas_drag(self, event) -> None:
        """Mirror a dragged 3D camera onto the other panel while comparing.

        mplot3d has no built-in way to link two independent ``Axes3D``, so a
        comparison keeps them in sync by copying whichever panel the mouse is
        currently rotating onto the other one, on every drag step.

        Args:
            event: The Matplotlib ``motion_notify_event``.
        """
        if (
            not self._has_3d_data
            or len(self._figure.axes) != 2
            or event.inaxes is None
            or event.button is None
        ):
            return
        if event.inaxes not in self._figure.axes:
            return
        plotting.link_3d_axes(self._figure.axes, source=event.inaxes)
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
        if len(self._figure.axes) > 1:
            plotting.link_3d_axes(self._figure.axes, source=ax)
        self._canvas.draw_idle()

    @staticmethod
    def _scaled(limits: tuple[float, float], factor: float) -> tuple[float, float]:
        """``limits`` scaled by ``factor`` around its own midpoint."""
        lo, hi = limits
        center = (lo + hi) / 2.0
        half = (hi - lo) / 2.0 * factor
        return center - half, center + half

    def _on_save_pdf(self) -> None:
        """Prompt for a path and save the current figure as a vector PDF."""
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
