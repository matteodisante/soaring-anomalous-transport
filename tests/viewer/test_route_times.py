"""Route dates must restore the trim offset and retain civil-day/DST boundaries."""

from datetime import date, time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("PyQt6")

from soaring.acquisition.ffvl.naming import igc_path
from soaring.viewer.route_times import (
    DepartureWindow,
    filter_departures,
    with_flight_times,
)
from soaring.viewer.widgets.route_comparison import _flight_datetime


@pytest.fixture
def flight(tmp_path):
    cfg = SimpleNamespace(
        derived_dir=tmp_path / "derived",
        catalog_path=tmp_path / "catalog.csv",
        igc_dir=tmp_path / "igc",
    )
    cfg.derived_dir.mkdir()
    pd.DataFrame({"flight_id": ["0001"], "ground_phase_start_s": [50.0]}).to_parquet(
        cfg.derived_dir / "flights_meta.parquet"
    )
    # The catalogue date only locates the file; it deliberately differs from IGC.
    pd.DataFrame(
        {"flight_id": ["0001"], "season_year": [2024], "date": ["2024-01-01"]}
    ).to_csv(cfg.catalog_path, index=False)
    path = igc_path(cfg.igc_dir, 2024, "2024-01-01", "0001")
    path.parent.mkdir(parents=True)
    path.write_text("HFDTE150624\nB2159004432469N00542796EA010000010000\n")
    selected = pd.DataFrame(
        {
            "discipline": ["para"],
            "flight_id": ["0001"],
            "t0": [5.0],
            "t1": [65.0],
            "duration_s": [60.0],
        },
        index=[7],
    )
    return SimpleNamespace(config=lambda: cfg, name="para"), selected, path


@pytest.mark.parametrize(
    "day,clock,departure,arrival",
    [
        ("150624", "215900", "15/06/2024 23:59:55 CEST", "16/06/2024 00:00:55 CEST"),
        ("150124", "105900", "15/01/2024 11:59:55 CET", "15/01/2024 12:00:55 CET"),
        ("310324", "005900", "31/03/2024 01:59:55 CET", "31/03/2024 03:00:55 CEST"),
        ("271024", "005900", "27/10/2024 02:59:55 CEST", "27/10/2024 02:00:55 CET"),
    ],
)
def test_dates_restore_trim_and_endpoint_offsets(
    flight, day, clock, departure, arrival
):
    disc, selected, path = flight
    path.write_text(f"HFDTE{day}\nB{clock}4432469N00542796EA010000010000\n")
    result = with_flight_times(selected, [disc])
    row = result.loc[7]
    assert _flight_datetime(row.departure_utc) == departure
    assert _flight_datetime(row.arrival_utc) == arrival
    assert row.arrival_utc - row.departure_utc == row.duration_s == 60
    pd.testing.assert_frame_equal(result[selected.columns], selected)


@pytest.mark.parametrize("missing", ["header", "file", "catalog", "trim"])
def test_missing_clock_is_unavailable_without_catalogue_fallback(flight, missing):
    disc, selected, path = flight
    if missing == "header":
        path.write_text("B2159004432469N00542796EA010000010000\n")
    elif missing == "file":
        path.unlink()
    elif missing == "catalog":
        disc.config().catalog_path.unlink()
    else:
        pd.DataFrame(
            {"flight_id": ["0001"], "ground_phase_start_s": [np.nan]}
        ).to_parquet(disc.config().derived_dir / "flights_meta.parquet")
    result = with_flight_times(selected, [disc])
    assert result[["departure_utc", "arrival_utc"]].isna().all().all()
    assert _flight_datetime(result.loc[7, "departure_utc"]) == "Unavailable"
    assert _flight_datetime(None) == "Unavailable"


def test_departure_window_uses_paris_day_and_half_open_boundary():
    times = pd.to_datetime(
        [
            "2024-06-15T09:59:59Z",
            "2024-06-15T10:00:00Z",
            "2024-06-15T10:29:59.500Z",
            "2024-06-15T10:30:00Z",
            "2024-06-16T10:10:00Z",
            "2024-06-14T10:10:00Z",
        ],
        format="ISO8601",
        utc=True,
    )
    flights = pd.DataFrame({"departure_utc": [t.timestamp() for t in times] + [np.nan]})
    flights["arrival_utc"] = flights.departure_utc + 86400  # arrivals may be next day
    window = DepartureWindow(date(2024, 6, 15), time(12), 30)
    assert filter_departures(flights, window).index.tolist() == [1, 2]
    assert filter_departures(flights, None) is flights


def test_departure_window_handles_midnight_and_repeated_autumn_hour():
    times = pd.to_datetime(
        [
            "2024-10-27T00:15:00Z",
            "2024-10-27T01:15:00Z",  # 02:15 CEST and CET
            "2024-10-27T23:00:00Z",
            "2024-10-27T22:59:59Z",
        ],
        utc=True,
    )
    flights = pd.DataFrame({"departure_utc": [t.timestamp() for t in times]})
    assert filter_departures(
        flights, DepartureWindow(date(2024, 10, 27), time(2), 30)
    ).index.tolist() == [0, 1]
    end = DepartureWindow(date(2024, 10, 27), time(23, 30), 30)
    assert end.end_label == "24:00"
    assert filter_departures(flights, end).index.tolist() == [3]
    with pytest.raises(ValueError, match=r"same|selected day"):
        DepartureWindow(date(2024, 10, 27), time(23, 45), 30)


def test_departure_controls_list_all_days_preview_and_capture_request(
    qapp, monkeypatch
):
    from PyQt6.QtCore import QTime

    from soaring.viewer.widgets import route_comparison as widget_module

    widget = widget_module.RouteComparison()
    pair = (90, 650, 100, 650)
    widget._pairs.addItem("Test pair", pair)
    widget._index = object()
    widget._flights = pd.DataFrame()
    utc = pd.to_datetime(
        [
            "2024-06-15T10:05:00Z",
            "2024-06-15T10:29:59Z",
            "2024-06-15T10:30:00Z",
            "2024-06-16T10:15:00Z",
        ],
        utc=True,
    )
    cohort = pd.DataFrame({"departure_utc": [t.timestamp() for t in utc] + [np.nan]})
    control = widget._departure
    try:
        control.set_cohort(cohort)
        assert control._day.count() == 2
        assert control._day.currentData() == date(2024, 6, 15)
        assert control._minutes.value() == 30
        widget._scene = object()
        widget._table.setRowCount(1)
        control._active.setChecked(True)
        control._start.setTime(QTime(12, 0))
        assert widget._scene is None and widget._table.rowCount() == 0
        assert "2 / 5 departures" in control._note.text()
        assert "unavailable dates: 1" in control._note.text()
        operations = []
        monkeypatch.setattr(
            widget, "_start", lambda operation, kind: operations.append(operation)
        )
        monkeypatch.setattr(
            widget_module, "load_scene", lambda *a, **kw: kw["departure_window"]
        )
        widget._mode.setCurrentIndex(1)
        control._apply.click()
        captured = operations[-1]()
        assert captured == DepartureWindow(date(2024, 6, 15), time(12), 30)
        assert widget._mode.currentData() == "all"
        control._start.setTime(QTime(13, 0))
        assert "0 / 5 departures" in control._note.text()
        assert not control._apply.isEnabled()
        assert operations[-1]() == captured
        control._active.setChecked(False)
        control._apply.click()
        assert operations[-1]() is None
        widget._pair_changed()
        assert control._day.count() == 0 and not control._active.isChecked()
    finally:
        widget.shutdown()
        widget.close()
