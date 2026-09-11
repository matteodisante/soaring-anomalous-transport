"""Shared fixtures for the Qt-widget tests under tests/viewer.

A ``QApplication`` is required before any ``QWidget`` can be constructed, and only one
may exist per process; ``qapp`` creates it once (offscreen -- no display needed) and
every widget test depends on it directly or by constructing a widget.

PyQt6 sits in the opt-in ``viewer`` dependency group (pyproject.toml), so it is absent
wherever the interactive viewer is not wanted, CI included. The three modules listed
below import a widget at module scope, which pytest reports as a collection error --
not a skip -- and one collection error fails the whole run. Drop them from collection
when the binding is missing, so an install without the viewer gives a smaller suite
rather than a red one. They are a real part of the suite: run them with
``uv sync --group viewer``, which is what a local checkout already has.
"""

from __future__ import annotations

import importlib.util
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

_WIDGET_MODULES = ["test_flight_picker.py", "test_main_window.py", "test_map_view.py"]
collect_ignore = (
    [] if importlib.util.find_spec("PyQt6") is not None else list(_WIDGET_MODULES)
)


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
