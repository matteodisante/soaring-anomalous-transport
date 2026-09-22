"""Interactive height, source and UTC controls must refer to the same loaded slice."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pyproj")

from soaring.viewer.thermal_geometry import ThermalCell, project
from soaring.viewer.thermal_store import PlaneData
from soaring.viewer.widgets.thermal_plane import ThermalPlane


@pytest.fixture
def widget(qapp, monkeypatch):
    x, y = project(6, 45)
    cell = ThermalCell(int(x // 5000), int(y // 5000), "Hills", 5, 2, 500, 1500)
    day = datetime(2024, 6, 15, 12, tzinfo=UTC).timestamp()
    index = SimpleNamespace(
        disciplines=("paragliders",),
        cells=lambda: [cell],
        defaults=lambda _: (day - 43200, 500),
    )
    view = ThermalPlane()
    with monkeypatch.context() as m:
        m.setattr(view, "_start_plane", lambda: None)
        view._index_ready(index)
    view._set_busy(False)
    west, south, _, _ = cell.bounds
    edges = pd.DataFrame(
        {
            "x0": [west + 1000],
            "x1": [west + 2000],
            "y0": [south + 1000],
            "y1": [south + 2000],
            "z0": [600],
            "z1": [1400],
            "utc0": [day + 60],
            "utc1": [day + 100],
            "flight_id": ["a"],
            "discipline": ["paragliders"],
        }
    )
    view._plane_ready(PlaneData(edges, 1, 1, 0, 0, 0))
    view._set_busy(False)
    yield view
    view.shutdown()
    view.close()


def test_height_slider_updates_points_without_reloading(widget):
    assert len(widget._plane_ax.collections) == 1
    widget._slider.setValue(0)
    assert widget._height.value() == 0
    assert len(widget._plane_ax.collections) == 0
    widget._slider.setValue(50)
    assert widget._height.value() == 500
    offsets = widget._plane_ax.collections[0].get_offsets()
    assert offsets[0].tolist() == pytest.approx([1.5, 1.5])
    widget._slider.setValue(widget._slider.maximum())
    assert widget._height.value() == 1000
    assert widget._plane_ax.get_xlim() == (0, 5)
    assert widget._plane_ax.get_ylim() == (0, 5)


def test_crest_toggle_and_height_do_not_change_the_loaded_climbs(widget, monkeypatch):
    from soaring.viewer.widgets import thermal_plane

    cell = widget._cells.currentData()
    west, south, _, _ = cell.bounds
    payload = {
        "features": [
            {
                "geometry": {
                    "coordinates": [
                        [west + 1000, south + 4000],
                        [west + 1500, south + 4500],
                    ]
                },
                "properties": {"method": "transverse height maximum"},
            }
        ]
    }
    monkeypatch.setattr(thermal_plane, "load_ridges", lambda _: payload)
    widget._height.setValue(500)
    loaded = widget._plane
    edges = loaded.edges.copy()
    widget._draw_plane()

    def positions(label):
        artist = next(c for c in widget._plane_ax.collections if c.get_label() == label)
        return artist.get_offsets().tolist()

    ridge = next(
        line
        for line in widget._plane_ax.lines
        if line.get_label() == "IGN DEM-derived crests"
    )
    assert ridge.get_xydata().tolist() == [[1, 4], [1.5, 4.5]]
    climb_positions = positions("paragliders: 1")
    widget._ridges.setChecked(False)
    assert len(widget._plane_ax.collections) == 1
    assert positions("paragliders: 1") == climb_positions
    widget._ridges.setChecked(True)
    widget._height.setValue(600)
    ridge = next(
        line
        for line in widget._plane_ax.lines
        if line.get_label() == "IGN DEM-derived crests"
    )
    assert ridge.get_xydata().tolist() == [[1, 4], [1.5, 4.5]]
    assert widget._plane is loaded
    pd.testing.assert_frame_equal(widget._plane.edges, edges)


def test_source_switch_hides_old_points_and_preserves_cell_and_height_range(widget):
    cell = widget._cells.currentData()
    assert widget._source.currentData() == "vilpellet"
    widget._source.setCurrentIndex(0)
    assert widget._source.currentData() == "own"
    assert widget._plane is None
    assert widget._cells.currentData() == cell
    assert widget._height.maximum() == 1000
    assert len(widget._plane_ax.collections) == 0


def test_datetime_controls_use_real_utc_and_invalidate_cached_slice(widget):
    start, end = widget._utc_bounds()
    assert start == datetime(2024, 6, 15, tzinfo=UTC).timestamp()
    assert end == start + 86399
    widget._start.setDateTime(widget._start.dateTime().addSecs(3600))
    assert widget._utc_bounds()[0] == start + 3600
    assert widget._plane is None


def test_reversed_interval_has_no_background_request(widget):
    widget._start.setDateTime(widget._end.dateTime().addSecs(1))
    widget._start_plane()
    assert widget._worker is None
    assert "end time" in widget._status.text()


def test_archive_change_clears_four_cells_and_old_results(widget):
    widget.invalidate()
    assert widget._index is None
    assert widget._plane is None
    assert widget._cells.count() == 0
    assert not widget._load.isEnabled()


def test_twelve_category_ranks_clickable_labels_and_relief_do_not_change_points(
    widget, monkeypatch, qapp
):
    from dataclasses import replace

    import numpy as np

    from soaring.viewer.geography import TERRAIN_ORDER

    old = widget._cells.currentData()
    cells = [
        replace(old, ix=old.ix + i, terrain=band, flights=300 - rank)
        for i, band in enumerate(TERRAIN_ORDER)
        for rank in range(3)
    ]
    # Give all cells distinct geometry while deliberately keeping map markers close.
    cells = [
        replace(c, ix=old.ix + i % 4, iy=old.iy + i // 4) for i, c in enumerate(cells)
    ]
    images_read = []

    def relief(cell=None):
        images_read.append(cell)
        extent = (-5.5, 41, 10, 51.5) if cell is None else cell.bounds
        return np.full((3, 3, 3), 180, dtype=np.uint8), {"extent": extent}

    proxy = SimpleNamespace(
        disciplines=("paragliders",),
        cells=lambda: cells,
        defaults=lambda c: (widget._utc_bounds()[0], 500),
        relief=relief,
    )
    with monkeypatch.context() as m:
        m.setattr(widget, "_start_plane", lambda: None)
        widget._index_ready(proxy)
        assert widget._cells.count() == 12
        assert [widget._rank(c) for c in cells] == [1, 2, 3] * 4
        widget._canvas.draw()
        assert len(widget._map_labels) == 12
        for i in range(12):
            assert f"#{i % 3 + 1}" in widget._cells.itemText(i)
        label, target = widget._map_labels[8]
        box = label.get_bbox_patch().get_window_extent(widget._canvas.get_renderer())
        widget._map_clicked(
            SimpleNamespace(
                inaxes=widget._map_ax, x=(box.x0 + box.x1) / 2, y=(box.y0 + box.y1) / 2
            )
        )
        assert widget._cells.currentIndex() == target == 8
        assert len(widget._plane_ax.images) == 1
        assert list(widget._plane_ax.images[0].get_extent()) == [0, 5, 0, 5]
        loaded = len(images_read)
        widget._relief_strength.setValue(60)
        widget._slider.setValue(7000)
        assert len(images_read) == loaded
        assert widget._plane_ax.images[0].get_alpha() == 0.6


def test_dates_and_source_survive_other_controls_and_reload(widget, monkeypatch):
    from PyQt6.QtCore import QTime

    widget._source.setCurrentIndex(0)
    widget._start.setDateTime(widget._start.dateTime().addDays(-20))
    widget._end.setDateTime(widget._end.dateTime().addDays(20))
    bounds = widget._utc_bounds()
    with monkeypatch.context() as m:
        m.setattr(widget, "_start_plane", lambda: None)
        widget._step.setCurrentIndex(2)
        widget._height.setValue(273)
        assert widget._height.value() == 250
        widget._background.setCurrentIndex(1)
        widget._relief_strength.setValue(70)
        widget._before.setValue(3)
        widget._after.setValue(5)
        widget._bands[2].setTime(QTime(16, 0))
        widget._mode.setCurrentIndex(1)
        widget._index_ready(widget._index)
        assert widget._utc_bounds() == bounds
        assert widget._source.currentData() == "own"
        assert len(widget._plane_axes) == 3
        assert widget._bands[2].time() == QTime(16, 0)
        start, end = widget._read_bounds()
        assert end - start == pytest.approx(9 * 86400)


def test_daily_panels_share_one_row_and_focus_preserves_selection(widget, monkeypatch):
    plane = widget._plane
    dates = widget._utc_bounds()
    source, height = widget._source.currentData(), widget._height.value()
    monkeypatch.setattr(widget, "_start_plane", lambda: None)
    widget._mode.setCurrentIndex(1)
    widget._plane_ready(plane)
    widget.resize(1600, 900)
    widget._canvas.draw()
    assert widget._map_ax is None
    assert len(widget._plane_axes) == 3
    boxes = [ax.get_position() for ax in widget._plane_axes]
    assert [b.y0 for b in boxes] == pytest.approx([boxes[0].y0] * 3)
    assert boxes[0].x1 < boxes[1].x0 < boxes[1].x1 < boxes[2].x0
    assert widget._time_settings.isHidden()
    assert not widget._daily_settings.isHidden()
    for focus in ("midday", "afternoon", "france", "morning", "planes"):
        widget._view.setCurrentIndex(widget._view.findData(focus))
        assert widget._plane is plane
        assert widget._utc_bounds() == dates
        assert widget._source.currentData() == source
        assert widget._height.value() == height
        if focus == "france":
            assert len(widget._figure.axes) == 1
            assert widget._map_ax is not None
        elif focus != "planes":
            assert len(widget._figure.axes) == 1
            # The panel title's `set_title` call in thermal_plane.py names no
            # explicit `loc`, so it lands under whichever alignment the ambient
            # `axes.titlelocation` rcParam holds at the time -- 'center' by
            # matplotlib's own default, but 'left' for the rest of any process
            # where `soaring.reporting.style.paper_style()` has already run (it
            # sets that rcParam globally and never restores it). Checking every
            # slot is what makes this assertion true regardless of test order.
            ax = widget._plane_ax
            title = (
                ax.get_title(loc="left") or ax.get_title() or ax.get_title(loc="right")
            )
            assert title.startswith(focus.capitalize())
    assert widget._panel_indices == [0, 1, 2]
