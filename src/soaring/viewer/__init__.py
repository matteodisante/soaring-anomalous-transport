"""Interactive trajectory viewer: a GUI, not a batch script.

Everything under this package is Qt-optional-free except :mod:`soaring.viewer.app` and
:mod:`soaring.viewer.main_window` (and the ``widgets`` it composes): ``data.py``,
``catalog_index.py`` and ``plotting.py`` import neither Qt nor matplotlib's Qt backend,
so they stay usable -- and testable -- without the ``viewer`` dependency group
installed.
"""

from __future__ import annotations
