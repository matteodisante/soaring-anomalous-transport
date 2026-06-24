"""Test della pulizia dei file AppleDouble."""

from soaring.acquisition.ffvl import housekeeping


def test_skips_when_dot_clean_missing(tmp_path, monkeypatch):
    # Senza dot_clean (o fuori da macOS) la pulizia e' un no-op che ritorna False.
    monkeypatch.setattr(housekeeping.shutil, "which", lambda _name: None)
    assert housekeeping.clean_appledouble(tmp_path) is False


def test_missing_root_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(housekeeping.sys, "platform", "darwin")
    monkeypatch.setattr(
        housekeeping.shutil, "which", lambda _name: "/usr/sbin/dot_clean"
    )
    assert housekeeping.clean_appledouble(tmp_path / "inesistente") is False


def test_invokes_dot_clean(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(housekeeping.sys, "platform", "darwin")
    monkeypatch.setattr(
        housekeeping.shutil, "which", lambda _name: "/usr/sbin/dot_clean"
    )
    monkeypatch.setattr(housekeeping.subprocess, "run", lambda *a, **k: calls.append(a))
    assert housekeeping.clean_appledouble(tmp_path) is True
    assert calls and calls[0][0][0] == "dot_clean"
