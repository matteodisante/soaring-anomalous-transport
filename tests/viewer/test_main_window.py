"""Camera regressions: display changes must preserve interactive navigation."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from soaring.viewer.main_window import MainWindow
from soaring.viewer.widgets.flight_picker import FlightPicker


@pytest.fixture
def window(qapp, monkeypatch):
    monkeypatch.setattr(FlightPicker, "_repopulate_filter_combos", lambda self: None)
    win = MainWindow()
    win._igc_path = Path("test.igc")
    win._raw = SimpleNamespace(
        fixes=pd.DataFrame(
            {
                "lon": np.linspace(3, 4, 20),
                "lat": np.linspace(43, 44, 20),
                "alt": np.linspace(1000, 1500, 20),
            }
        )
    )
    win._redraw()
    yield win
    win.close()


def test_colour_and_visibility_preserve_2d_zoom_and_toolbar_history(window):
    ax = window._figure.axes[0]
    window._toolbar.push_current()
    ax.set_xlim(3.2, 3.3)
    ax.set_ylim(43.4, 43.5)
    window._toolbar.push_current()
    for change in (
        lambda: window._controls._color_combo.setCurrentIndex(1),
        lambda: window._controls._chk_raw.setChecked(False),
        lambda: window._controls._chk_raw.setChecked(True),
        lambda: window._controls._chk_dms.setChecked(True),
    ):
        change()
        assert window._figure.axes[0] is ax
        assert ax.get_xlim() == pytest.approx((3.2, 3.3))
        assert ax.get_ylim() == pytest.approx((43.4, 43.5))
    window._toolbar.back()
    assert ax.get_xlim()[0] < 3.1
    window._toolbar.forward()
    assert ax.get_xlim() == pytest.approx((3.2, 3.3))


def test_3d_zoom_preserves_mouse_rotation_and_orientation_preserves_pan(window):
    window._controls._chk_3d.setChecked(True)
    ax = window._figure.axes[0]
    ax.set_xlim(3.2, 3.3)
    ax.set_ylim(43.4, 43.5)
    ax.set_zlim(1100, 1200)
    ax.view_init(elev=12, azim=78, roll=9)
    window._controls._color_combo.setCurrentIndex(2)
    assert window._figure.axes[0] is ax
    assert (ax.elev, ax.azim, ax.roll) == (12, 78, 9)
    assert ax.get_xlim() == pytest.approx((3.2, 3.3))
    window._controls._slider_zoom.setValue(200)
    assert (ax.elev, ax.azim, ax.roll) == (12, 78, 9)
    assert ax.get_xlim() == pytest.approx((3.225, 3.275))
    assert ax.get_zlim() == pytest.approx((1125, 1175))
    window._controls._slider_azim.setValue(40)
    assert (ax.elev, ax.azim, ax.roll) == (12, 40, 9)
    assert ax.get_xlim() == pytest.approx((3.225, 3.275))
    window._controls._chk_3d.setChecked(False)
    window._controls._chk_3d.setChecked(True)
    ax = window._figure.axes[0]
    assert (ax.elev, ax.azim, ax.roll) == (12, 40, 9)
    assert ax.get_xlim() == pytest.approx((3.225, 3.275))
    window._controls._btn_reset_view.click()
    assert window._figure.axes[0].get_xlim()[0] < 3.1


def test_fullscreen_hides_picker_and_restores_layout_without_redraw(
    window, qapp, monkeypatch
):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    window.show()
    qapp.processEvents()
    geometry = window.geometry()
    sizes = window._splitter.sizes()
    axes = window._figure.axes[0]
    monkeypatch.setattr(window, "_redraw", lambda: pytest.fail("fullscreen redraw"))
    window._fullscreen_button.click()
    qapp.processEvents()
    assert window.isFullScreen()
    assert window._picker.isHidden()
    assert not window._controls.isHidden()
    assert "Exit" in window._fullscreen_button.text()
    QTest.keyClick(window, Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not window.isFullScreen()
    assert not window._picker.isHidden()
    assert window.geometry() == geometry
    assert window._splitter.sizes() == sizes
    assert window._figure.axes[0] is axes
    assert window._fullscreen_button.text() == "Full screen"


def test_fullscreen_exit_after_resize_and_single_map_focus(window, qapp, monkeypatch):
    view = window._thermal_plane
    monkeypatch.setattr(view, "ensure_loaded", lambda: None)
    window._tabs.setCurrentWidget(view)
    view._mode.setCurrentIndex(1)
    window.show()
    qapp.processEvents()
    window._fullscreen_button.click()
    qapp.processEvents()
    view._view.setCurrentIndex(view._view.findData("midday"))
    window.resize(1920, 1080)
    qapp.processEvents()
    # Qt can clear its fullscreen flag on resize without a WindowStateChange event.
    window._fullscreen_button.click()
    qapp.processEvents()
    assert not window.isFullScreen()
    assert not window._picker.isHidden()
    assert window._fullscreen_state is None
    assert view._view.currentData() == "midday"
    assert view._panel_indices == [1]
