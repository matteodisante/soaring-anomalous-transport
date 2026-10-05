"""Route dates must restore the trim offset and retain civil-day/DST boundaries."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("PyQt6")

from soaring.acquisition.ffvl.naming import igc_path
from soaring.viewer.route_times import with_flight_times
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
