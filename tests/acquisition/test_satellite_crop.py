"""Tests for local-hour selection and the atomic, space-guarded output."""

import json
from dataclasses import replace

import numpy as np
import pytest

# Satellite dependencies are opt-in; CI runs with --group satellite.
pytest.importorskip("blosc2")
pytest.importorskip("pyproj")
pytest.importorskip("requests")

from soaring.acquisition.satellite.config import load_config
from soaring.acquisition.satellite.crop import Crop, local_mask, write_crops
from soaring.acquisition.satellite.grid import Box


def test_local_mask_follows_paris_summer_and_winter_time():
    times = np.array(
        [
            "2020-07-15T05:55",
            "2020-07-15T06:00",
            "2020-07-15T17:55",
            "2020-07-15T18:00",
            "2020-01-15T06:55",
            "2020-01-15T07:00",
        ],
        dtype="datetime64[ns]",
    )
    assert local_mask(times, "Europe/Paris", (8, 20)).tolist() == [
        False,
        True,
        True,
        False,
        False,
        True,
    ]


def _crop():
    return Crop(
        time=np.array(["2020-07-15T12:00"], dtype="datetime64[ns]"),
        variables=("VIS006",),
        units={"VIS006": "%"},
        boxes={"c001_0001": Box(0, 2, 0, 3)},
        x={"c001_0001": np.arange(3.0)},
        y={"c001_0001": np.arange(2.0)},
        data={"c001_0001": np.ones((1, 2, 3, 1), np.float16)},
    )


def test_write_crops_is_readable(tmp_path):
    cfg = replace(load_config(), output_root=tmp_path, min_free_gib=0)
    path = write_crops(tmp_path / "m.npz", cfg, {"nonhrv": _crop()}, {"days": []})
    with np.load(path) as f:
        assert f["c001_0001__nonhrv"].shape == (1, 2, 3, 1)
        meta = json.loads(str(f["meta"]))
        assert meta["physical_units"] == {"nonhrv": {"VIS006": "%"}}
        assert meta["scaling"]["nonhrv"]["VIS006"] == [-1.1009827, 93.786545]
    assert not list(tmp_path.glob("*.partial*"))


def test_write_crops_stops_before_filling_the_disk(tmp_path):
    cfg = replace(load_config(), output_root=tmp_path, min_free_gib=1e9)
    with pytest.raises(RuntimeError, match="stopping before writing"):
        write_crops(tmp_path / "m.npz", cfg, {"nonhrv": _crop()}, {})
    assert not list(tmp_path.iterdir())
