"""Test del modulo seasons (puro, senza rete)."""

import pytest

from soaring.acquisition.ffvl import seasons


def test_season_label():
    assert seasons.season_label(1999) == "1999-2000"
    assert seasons.season_label(2025) == "2025-2026"


def test_url_builders():
    assert seasons.list_url(1999) == "https://parapente.ffvl.fr/cfd/liste/1999"
    assert seasons.xml_url(1999) == "https://parapente.ffvl.fr/cfd/liste/1999?xml=1"
    assert seasons.flight_page_url(20150770) == (
        "https://parapente.ffvl.fr/cfd/liste/vol/20150770"
    )


def test_parse_seasons_all():
    assert seasons.parse_seasons_arg("all", 1999, 2001) == [1999, 2000, 2001]


def test_parse_seasons_single():
    assert seasons.parse_seasons_arg("2014", 1999, 2025) == [2014]


def test_parse_seasons_range():
    assert seasons.parse_seasons_arg("2010-2012", 1999, 2025) == [2010, 2011, 2012]


def test_parse_seasons_range_reversed():
    assert seasons.parse_seasons_arg("2012-2010", 1999, 2025) == [2010, 2011, 2012]


def test_parse_seasons_list_dedup_sorted():
    assert seasons.parse_seasons_arg("2015,2010,2010", 1999, 2025) == [2010, 2015]


def test_parse_seasons_invalid():
    with pytest.raises(ValueError):
        seasons.parse_seasons_arg(",", 1999, 2025)
