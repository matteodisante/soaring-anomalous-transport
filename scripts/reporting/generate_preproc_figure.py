#!/usr/bin/env python3
"""Regenerate the pre-processing diagnostics figure for the thesis.

Reads the paraglider flight catalog ``data/paragliders/catalog.csv`` and writes

* ``thesis/generated/preproc_diagnostics.pdf`` -- the distributions of flight
  duration, declared distance and track length, each marked with the flight-level
  filtering threshold adopted in the thesis.

Unlike ``generate_stats.py``, the catalog is large and *not* versioned, so it may be
absent (a fresh checkout, or CI). In that case the script leaves the committed figure
untouched and exits successfully. It also needs the ``analysis`` extra
(``matplotlib``); if that is missing it likewise exits without failing. The figure is
therefore refreshed on demand -- on a machine that has the catalog -- and committed as
an asset. PDF metadata is pinned so re-runs on unchanged data give clean diffs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "data" / "paragliders" / "catalog.csv"
OUT_PATH = ROOT / "thesis" / "generated" / "preproc_diagnostics.pdf"

# Make ``soaring`` importable from the source tree even when it is not installed in the
# active environment (``uv`` does not reinstall the editable package when switching
# extras). This keeps the script runnable with, e.g.,
# ``uv run --with matplotlib python scripts/reporting/generate_preproc_figure.py``.
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Deterministic PDF metadata -> committing the figure produces clean diffs.
_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def main() -> int:
    """Regenerate the figure when the catalog and matplotlib are both available."""
    if not CATALOG_PATH.is_file():
        print(f"Catalog not found ({CATALOG_PATH}); keeping the committed figure.")
        return 0
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing (extra 'analysis'); keeping the committed figure.")
        return 0
    matplotlib.use("Agg")

    from soaring.analysis.preprocessing import load_catalog, make_diagnostics_figure

    catalog = load_catalog(CATALOG_PATH)
    fig = make_diagnostics_figure(catalog)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, metadata=_PDF_METADATA, bbox_inches="tight")
    print(f"Wrote {OUT_PATH} from {len(catalog)} catalog rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
