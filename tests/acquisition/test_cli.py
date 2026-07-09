"""Tests for the CLI data_root guard (no network)."""

from pathlib import Path

import pytest

from soaring.acquisition.ffvl.cli import _check_data_root
from soaring.acquisition.ffvl.config import Config


def _cfg(data_root: Path) -> Config:
    # season_start/season_end/base_url are required but irrelevant to the
    # data_root guard: use inert dummies.
    return Config(
        data_root=data_root,
        season_start=2014,
        season_end=2015,
        base_url="https://ffvl.invalid",
    )


def test_check_data_root_passes_when_parent_exists(tmp_path):
    # data_root itself need not exist yet, but its parent (the mounted disk) must.
    _check_data_root(_cfg(tmp_path / "ffvl_cfd_igc"))


def test_check_data_root_aborts_when_parent_missing(tmp_path):
    cfg = _cfg(tmp_path / "unmounted-disk" / "ffvl_cfd_igc")
    with pytest.raises(SystemExit):
        _check_data_root(cfg)
