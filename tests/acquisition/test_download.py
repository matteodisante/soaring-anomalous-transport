"""Test delle utility di download che non richiedono rete."""

from soaring.acquisition.ffvl.download import _atomic_write, is_valid_igc

VALID_IGC = (
    b"AFLY05116\nHFDTE000000\nI013638TAS\nB0028064535412N00645033EV0202000000000\n"
)


def test_is_valid_igc_true():
    assert is_valid_igc(VALID_IGC + b"B0028114535412N00645033EV0\n" * 20)


def test_is_valid_igc_rejects_html():
    assert not is_valid_igc(b"<html><body>Just a moment...</body></html>")


def test_is_valid_igc_rejects_short():
    assert not is_valid_igc(b"AFLY\nB123\n")


def test_is_valid_igc_requires_b_record():
    # Header A presente ma nessun record B -> non valido.
    assert not is_valid_igc(b"AFLY05116\n" + b"HFDTE000000\n" * 30)


def test_atomic_write_creates_file(tmp_path):
    target = tmp_path / "sub" / "x.igc"
    _atomic_write(target, b"hello")
    assert target.read_bytes() == b"hello"
    # nessun file .part residuo
    assert not list(tmp_path.rglob("*.part"))
