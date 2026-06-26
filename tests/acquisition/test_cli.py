"""Tests for the CLI data_root guard (no network)."""

import pytest

from soaring.acquisition.ffvl.cli import _check_data_root
from soaring.acquisition.ffvl.config import Config


def test_check_data_root_passes_when_parent_exists(tmp_path):
    # data_root itself need not exist yet, but its parent (the mounted disk) must.
    _check_data_root(Config(data_root=tmp_path / "ffvl_cfd_igc"))


def test_check_data_root_aborts_when_parent_missing(tmp_path):
    cfg = Config(data_root=tmp_path / "unmounted-disk" / "ffvl_cfd_igc")
    with pytest.raises(SystemExit):
        _check_data_root(cfg)
