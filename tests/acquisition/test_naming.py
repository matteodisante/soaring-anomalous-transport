"""Tests for the naming module (pure, no network)."""

from pathlib import Path

import pytest

from soaring.acquisition.ffvl import naming


def test_igc_filename():
    assert naming.igc_filename("2000-00-00", "20150770") == "2000-00-00_20150770.igc"
    assert naming.igc_filename("2014-07-12", 20680042) == "2014-07-12_20680042.igc"


def test_sanitize_date_empty():
    assert naming.sanitize_date("") == "0000-00-00"
    assert naming.sanitize_date("   ") == "0000-00-00"


def test_sanitize_date_strange_chars():
    # unsafe characters replaced with '-'
    assert naming.sanitize_date("2014/07/12") == "2014-07-12"


def test_roundtrip():
    name = naming.igc_filename("2000-00-00", "20150770")
    date, flight_id = naming.parse_igc_filename(name)
    assert date == "2000-00-00"
    assert flight_id == "20150770"


def test_parse_from_full_path():
    date, fid = naming.parse_igc_filename("/x/y/1999-2000/2000-00-00_20150770.igc")
    assert (date, fid) == ("2000-00-00", "20150770")


def test_parse_invalid_extension():
    with pytest.raises(ValueError):
        naming.parse_igc_filename("foo.txt")


def test_parse_invalid_scheme():
    with pytest.raises(ValueError):
        naming.parse_igc_filename("noseparator.igc")


def test_igc_path_layout():
    p = naming.igc_path(Path("/data/igc"), 1999, "2000-00-00", "20150770")
    assert p == Path("/data/igc/1999-2000/2000-00-00_20150770.igc")
