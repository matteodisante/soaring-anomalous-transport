"""The terrain window preserves geometry and camera while appearance changes."""

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("pyqtgraph.opengl")

from soaring.viewer.thermal_3d import TerrainScene
from soaring.viewer.thermal_geometry import ThermalCell
from soaring.viewer.widgets.thermal_3d import Thermal3D
from soaring.viewer.widgets.thermal_plane import ThermalPlane


@pytest.fixture
def scene():
    return TerrainScene(
        cell=ThermalCell(193, 1309, "High mountains", 10, 2, 1500, 2500),
        x=np.array([-2500, 2500]),
        y=np.array([-2500, 2500]),
        terrain=np.array([[1000, 1500], [2000, 2500]], dtype=np.float32),
        points=np.array([[0, 0, 2020], [100, 100, 2040]], dtype=np.float32),
        reference={"grid_m": [25, 25]},
        climb_runs=20,
        contributing_flights=2,
        selected_flights=3,
        unavailable_flights=0,
        unclassified_flights=1,
        unknown_clock_flights=0,
        start=100,
        end=200,
    )


def test_opacity_size_and_terrain_toggle_keep_positions_and_camera(qapp, scene):
    view = Thermal3D()
    try:
        view.set_scene(scene)
        cloud, surface = view._cloud, view._surface
        view._view.setCameraPosition(azimuth=12, elevation=55, distance=7000)
        for strength in (0, 35, 100):
            view._point_strength.setValue(strength)
            assert cloud.color[-1] == strength / 100
        view._point_size.setValue(5)
        view._terrain.setChecked(False)
        assert cloud.size == 5 and not surface.visible()
        assert view._cloud is cloud and view._surface is surface
        np.testing.assert_array_equal(cloud.pos, scene.points)
        assert [view._view.opts[k] for k in ("azimuth", "elevation", "distance")] == [
            12,
            55,
            7000,
        ]
        view._terrain.setChecked(True)
        assert surface.visible()
        view._reset_view(top=True)
        assert view._view.opts["elevation"] == 90
    finally:
        view.close()


def test_button_captures_active_time_interval_and_reuses_window(qapp, monkeypatch):
    calls = []

    class Window:
        def __init__(self, parent):
            self.parent = parent

        def load(self, store, start, end):
            calls.append((store, start, end))

        def show(self):
            pass

        def raise_(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("soaring.viewer.widgets.thermal_3d.Thermal3D", Window)
    view = ThermalPlane()
    try:
        assert not view._terrain_3d.isEnabled()
        store = view._index = SimpleNamespace(has_climb_ranking=True)
        view._set_busy(False)
        assert view._terrain_3d.isEnabled()
        monkeypatch.setattr(view, "_read_bounds", lambda: (100, 200))
        view._terrain_3d.click()
        panel = view._terrain_3d_panel
        monkeypatch.setattr(view, "_read_bounds", lambda: (300, 400))
        view._terrain_3d.click()
        assert view._terrain_3d_panel is panel
        assert calls == [(store, 100, 200), (store, 300, 400)]
    finally:
        view.shutdown()
        view.close()
