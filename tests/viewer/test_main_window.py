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
