"""Shared fixtures for the Qt-widget tests under tests/viewer.

A ``QApplication`` is required before any ``QWidget`` can be constructed, and only one
may exist per process; ``qapp`` creates it once (offscreen -- no display needed) and
every widget test depends on it directly or by constructing a widget.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
