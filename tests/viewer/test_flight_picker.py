"""Tests for the discipline-selection logic in soaring.viewer.widgets.flight_picker.

Qt widget tests: need ``qapp`` (tests/viewer/conftest.py). ``Discipline.config()`` is
monkeypatched the same way tests/viewer/test_catalog_index.py does, pointing at
tmp_path roots instead of the real archive. A picker is ``.show()``n before any
visibility assertion: an un-shown top-level widget reports every descendant as
invisible regardless of ``setVisible()``, so that alone would make every assertion
below pass by accident.
"""

from __future__ import annotations

import os

import pytest

from soaring.acquisition.ffvl.config import Config
from soaring.reporting import disciplines as disciplines_mod
from soaring.viewer import catalog_index
from soaring.viewer.widgets.flight_picker import FlightPicker


def _fake_config_for(root_by_name: dict):
    def fake_config(self):
        root = root_by_name.get(self.name)
        if root is None:
            raise FileNotFoundError("not configured in this test")
        return Config(
            data_root=root, season_start=2020, season_end=2021, base_url="https://x"
        )

    return fake_config


def _make_root(tmp_path, name):
    root = tmp_path / name
    (root / "raw" / "igc").mkdir(parents=True)
    return root


@pytest.fixture(autouse=True)
def _clear_caches():
    catalog_index._catalog_cache.clear()
    catalog_index._flights_meta_cache.clear()
    yield
    catalog_index._catalog_cache.clear()
    catalog_index._flights_meta_cache.clear()


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    # _on_set_folder writes SOARING_*_DATA_ROOT into the real process environment;
    # isolate that from whatever this shell happens to have set.
    monkeypatch.delenv("SOARING_PARA_DATA_ROOT", raising=False)
    monkeypatch.delenv("SOARING_DELTA_DATA_ROOT", raising=False)


def test_discipline_choice_hidden_when_only_paragliders_reachable(
    qapp, tmp_path, monkeypatch
):
    para_root = _make_root(tmp_path, "para")
    monkeypatch.setattr(
        disciplines_mod.Discipline,
        "config",
        _fake_config_for({"paragliders": para_root}),
    )
    picker = FlightPicker()
    picker.show()
    assert picker._discipline_combo.isVisible() is False
    assert picker._discipline_label.isVisible() is True
    assert "Paragliders" in picker._discipline_label.text()
    assert picker.current_discipline().name == "paragliders"


def test_discipline_choice_shown_when_both_reachable(qapp, tmp_path, monkeypatch):
    para_root = _make_root(tmp_path, "para")
    hang_root = _make_root(tmp_path, "hang")
    monkeypatch.setattr(
        disciplines_mod.Discipline,
        "config",
        _fake_config_for({"paragliders": para_root, "hang gliders": hang_root}),
    )
    picker = FlightPicker()
    picker.show()
    assert picker._discipline_combo.isVisible() is True
    assert picker._discipline_label.isVisible() is False


def test_discipline_choice_shown_when_neither_reachable(qapp, monkeypatch):
    def raising_config(self):
        raise FileNotFoundError("nothing configured")

    monkeypatch.setattr(disciplines_mod.Discipline, "config", raising_config)
    picker = FlightPicker()
    picker.show()
    # Still a real choice here: an arbitrary browsed file still needs a discipline
    # for the pipeline's speed threshold, and nothing can guess it from no archive.
    assert picker._discipline_combo.isVisible() is True
    assert picker._discipline_label.isVisible() is False


def test_set_folder_points_the_env_var_and_updates_the_selector(
    qapp, tmp_path, monkeypatch
):
    from unittest.mock import patch

    def env_only_config(self):
        # A reduced stand-in for the real Discipline.config(), which also checks the
        # env var first -- isolated from both the real SSD (which may well be
        # mounted in this dev environment) and the checked-in YAML defaults, so the
        # "before" state below is deterministic: nothing set, nothing reachable.
        root = os.environ.get(self.env)
        if root is None:
            raise FileNotFoundError("not configured in this test")
        from pathlib import Path

        return Config(
            data_root=Path(root), season_start=2020, season_end=2021,
            base_url="https://x",
        )

    monkeypatch.setattr(disciplines_mod.Discipline, "config", env_only_config)
    picker = FlightPicker()
    picker.show()
    assert picker._discipline_combo.isVisible() is True  # neither reachable yet

    para_root = _make_root(tmp_path, "para")
    with patch(
        "soaring.viewer.widgets.flight_picker.QFileDialog.getExistingDirectory",
        return_value=str(para_root),
    ):
        picker._on_set_folder(disciplines_mod.PARAGLIDERS)

    assert os.environ["SOARING_PARA_DATA_ROOT"] == str(para_root)
    # env_only_config() now resolves paragliders (the env var is set) and still
    # raises for hang gliders (its own env var never was) -- only one reachable.
    assert picker._discipline_combo.isVisible() is False
    assert picker._discipline_label.isVisible() is True
    assert picker.current_discipline().name == "paragliders"
    assert str(para_root) in picker._btn_set_folder["paragliders"].text()


def test_set_folder_emits_folders_changed(qapp, tmp_path, monkeypatch):
    from unittest.mock import patch

    monkeypatch.setattr(
        disciplines_mod.Discipline,
        "config",
        _fake_config_for({}),  # nothing reachable up front; irrelevant to this test
    )
    picker = FlightPicker()
    received = []
    picker.folders_changed.connect(lambda: received.append(1))

    para_root = _make_root(tmp_path, "para")
    with patch(
        "soaring.viewer.widgets.flight_picker.QFileDialog.getExistingDirectory",
        return_value=str(para_root),
    ):
        picker._on_set_folder(disciplines_mod.PARAGLIDERS)

    # A sibling widget with its own cache (MapView) needs this to know a discipline's
    # root just changed -- catalog_index's own cache being cleared isn't enough,
    # since that cache is invisible to whatever a widget cached on its own.
    assert received == [1]

    # Cancelling the folder dialog must not emit: nothing actually changed.
    received.clear()
    with patch(
        "soaring.viewer.widgets.flight_picker.QFileDialog.getExistingDirectory",
        return_value="",
    ):
        picker._on_set_folder(disciplines_mod.PARAGLIDERS)
    assert received == []
