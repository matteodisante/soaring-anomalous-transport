"""Tests for the integrity verification (no network, operates on a tmp tree)."""

from pathlib import Path

from soaring.acquisition.ffvl.config import Config
from soaring.acquisition.ffvl.verify import (
    CAT_INVALID,
    CAT_PART_LEFTOVER,
    CAT_SIDECAR,
    CAT_TOO_SMALL,
    check_igc_file,
    verify_season,
)

VALID_IGC = (
    b"AFLY05116\nHFDTE000000\nI013638TAS\n"
    + b"B0028064535412N00645033EV0202000000000\n" * 5
)


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_check_igc_file_accepts_valid(tmp_path):
    assert check_igc_file(_write(tmp_path / "ok.igc", VALID_IGC)) is None


def test_check_igc_file_flags_too_small(tmp_path):
    problem = check_igc_file(_write(tmp_path / "tiny.igc", b"AB"))
    assert problem is not None and problem.category == CAT_TOO_SMALL


def test_check_igc_file_flags_invalid_structure(tmp_path):
    html = b"<html><body>Just a moment...</body></html>" * 5
    problem = check_igc_file(_write(tmp_path / "bad.igc", html))
    assert problem is not None and problem.category == CAT_INVALID


def test_verify_season_clean(tmp_path):
    cfg = Config(data_root=tmp_path)
    season_dir = cfg.igc_dir / "2014-2015"
    _write(season_dir / "a.igc", VALID_IGC)
    _write(season_dir / "b.igc", VALID_IGC)

    result = verify_season(2014, cfg)

    assert result.n_igc == 2
    assert result.ok
    assert result.problems == []


def test_verify_season_reports_problems_and_failures(tmp_path):
    cfg = Config(data_root=tmp_path)
    season_dir = cfg.igc_dir / "2014-2015"
    _write(season_dir / "good.igc", VALID_IGC)
    _write(season_dir / "broken.igc", b"<html>nope</html>" * 10)  # integrity failure
    _write(season_dir / "half.igc.part", b"partial")  # integrity failure
    _write(season_dir / "._good.igc", b"sidecar")  # clutter, not a failure

    result = verify_season(2014, cfg)
    cats = {p.category for p in result.problems}

    assert result.n_igc == 2  # good.igc + broken.igc (.part and ._ are not .igc)
    assert CAT_INVALID in cats
    assert CAT_PART_LEFTOVER in cats
    assert CAT_SIDECAR in cats
    assert result.n_failures == 2  # invalid + part leftover; sidecar excluded
    assert not result.ok


def test_verify_season_missing_dir_is_empty(tmp_path):
    cfg = Config(data_root=tmp_path)
    result = verify_season(2099, cfg)
    assert result.n_igc == 0 and result.ok
