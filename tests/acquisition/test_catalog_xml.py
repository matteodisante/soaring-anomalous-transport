"""Test del parsing dell'XML di stagione, su una fixture reale (stagione 1999-2000)."""

from pathlib import Path

import pytest

from soaring.acquisition.ffvl.catalog_xml import _clean_igc_link, parse_season_xml

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "ffvl_1999.xml"


@pytest.fixture
def records():
    return parse_season_xml(FIXTURE.read_bytes(), 1999)


def test_count(records):
    # La stagione 1999-2000 contiene 10 voli.
    assert len(records) == 10


def test_all_have_igc(records):
    # Tutti i 10 voli del 1999 hanno una traccia .igc.
    assert all(r.has_igc for r in records)


def test_first_record_fields(records):
    r = records[0]
    assert r.flight_id == "20150770"
    assert r.pilot == "ETIENNE GRASSART"
    assert r.season == "1999-2000"
    assert r.season_year == 1999
    assert r.flight_type == "triangle"
    assert r.takeoff == "Les Ilettes"
    assert r.landing == "Orbassy"
    assert r.distance_km == pytest.approx(35.59)
    assert "53180" in r.igc_link
    assert r.igc_link.endswith(".igc")
    assert r.flight_link == "https://parapente.ffvl.fr/cfd/liste/vol/20150770"


def test_types(records):
    r = records[0]
    assert isinstance(r.distance_km, float)
    assert r.tracklog_id == "53180"


def test_clean_igc_link():
    base = "https://parapente.ffvl.fr/sites/parapente.ffvl.fr/files/igcfiles/"
    # solo cartella base (segnaposto) -> scartato
    assert _clean_igc_link(base) == ""
    assert _clean_igc_link("") == ""
    assert _clean_igc_link(None) == ""
    # vero file .igc -> mantenuto
    real = base + "2000-00-00-igcfile-115909-53180.igc"
    assert _clean_igc_link(real) == real
