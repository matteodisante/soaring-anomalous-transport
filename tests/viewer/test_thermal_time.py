"""Thermal time maps conserve duration across clipping, sampling and zoom."""

import numpy as np
import pandas as pd
import pytest

from soaring.viewer.thermal_time import TimeGrid, duration_bins, load_grids, save_grids


def test_crossed_pixels_receive_elapsed_time_and_outside_portions_are_clipped():
    flat, seconds = duration_bins([[-50, 25]], [[150, 25]], [20], (0, 0, 100, 100))
    assert flat.tolist() == [0, 1]
    assert seconds.tolist() == pytest.approx([5, 5])


def test_stationary_and_downward_climb_edges_keep_their_time():
    flat, seconds = duration_bins(
        [[25, 25], [25, 25]], [[25, 25], [25, 75]], [10, 20], (0, 0, 100, 100)
    )
    assert flat.tolist() == [0, 2]
    assert seconds.tolist() == pytest.approx([20, 10])


def test_diagonal_corner_and_subdivision_conserve_identical_weights():
    args = ((0, 0, 100, 100),)
    first = duration_bins([[0, 0]], [[100, 100]], [20], *args)
    second = duration_bins([[0, 0], [25, 25]], [[25, 25], [100, 100]], [5, 15], *args)
    assert first[0].tolist() == second[0].tolist() == [0, 3]
    np.testing.assert_allclose(first[1], second[1])
    assert first[1].sum() == pytest.approx(20)


def test_no_mass_on_upper_boundary_or_from_invalid_edges():
    flat, seconds = duration_bins(
        [[100, 0], [0, 100], [0, 0], [0, 0]],
        [[100, 50], [50, 100], [50, 0], [np.nan, 1]],
        [5, 5, 0, 5],
        (0, 0, 100, 100),
    )
    assert len(flat) == len(seconds) == 0


def test_hour_units_and_coarsening_include_partial_edge_pixel_area(tmp_path):
    grid = TimeGrid((0, 0, 150, 100))
    grid.add([[0, 25]], [[150, 25]], [3600])
    grid.flush()
    assert grid.hours == pytest.approx(1)
    for bins in (100, 1):
        values, xe, ye, _ = grid.window(0, 0.15, 0, 0.1, bins=bins)
        assert (
            values * np.diff(ye)[:, None] * np.diff(xe)[None, :]
        ).sum() == pytest.approx(1)
    path = tmp_path / "duration.npz"
    save_grids({"test": grid}, path, {"complete": True})
    loaded, _ = load_grids(path)
    assert loaded["test"].hours == pytest.approx(1)


def test_phase_edges_do_not_connect_nonclimb_gaps_or_flights(monkeypatch):
    pytest.importorskip("pyproj")
    from soaring.viewer.thermal_time_prepare import phase_edges

    monkeypatch.setattr(
        "soaring.viewer.thermal_time_prepare.enu_to_geodetic",
        lambda e, n, z, f: (n.to_numpy(), e.to_numpy()),
    )
    monkeypatch.setattr(
        "soaring.viewer.thermal_time_prepare.project", lambda x, y: (x, y)
    )
    frame = pd.DataFrame(
        {
            "flight_id": ["a"] * 6 + ["b"] * 2,
            "segment_id": [0] * 8,
            "t": [0, 10, 20, 30, 100, 110, 120, 130],
            "phase": [
                "climb",
                "climb",
                "search",
                "climb",
                "climb",
                "climb",
                "climb",
                "climb",
            ],
            "E": np.arange(8),
            "N": 0.0,
            "z": 1000.0,
        }
    )
    a, b, dt = phase_edges(frame, {"a": (0, 0, 0), "b": (0, 0, 0)}, 15)
    assert a[:, 0].tolist() == [0, 4, 6]
    assert b[:, 0].tolist() == [1, 5, 7]
    assert dt.tolist() == [10, 10, 10]


def test_grid_origin_need_not_be_a_multiple_of_the_pixel_size():
    flat, seconds = duration_bins([[25, 50]], [[175, 50]], [30], (25, 25, 175, 125))
    assert flat.tolist() == [0, 1, 2]
    assert seconds.tolist() == pytest.approx([10, 10, 10])


def test_incomplete_benchmark_cannot_be_displayed_as_the_full_archive(tmp_path):
    path = tmp_path / "benchmark.npz"
    save_grids({"test": TimeGrid((0, 0, 100, 100))}, path, {"complete": False})
    with pytest.raises(ValueError, match="Incomplete"):
        load_grids(path)
