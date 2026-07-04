#!/usr/bin/env python3
"""Regenerate the flight-level filtering and sampling-interval figures for the thesis.

Writes two figures to ``thesis/generated/``:

* ``preproc_diagnostics.pdf`` -- recorded flight duration and total flown path length,
  each with its distribution and its *marginal* retention curve (that cut alone), with
  the adopted flight-level thresholds marked;
* ``sampling_intervals.pdf`` -- the native sampling interval per flight.

Both are computed on the **full dataset** (every downloaded track, no sub-sampling) and
for **every discipline** present (paragliders and hang gliders today; sailplanes later),
overlaid per discipline. All quantities come from the parsed tracks, not the declared
catalog metadata. The adopted thresholds are read from ``configs/preprocessing.yaml``.

The raw data lives on an external disk and may be absent (a fresh checkout, or CI); the
data roots come from ``SOARING_PARA_DATA_ROOT`` / ``SOARING_DELTA_DATA_ROOT`` or config
placeholders. A discipline whose ``igc/`` directory is missing is skipped; if none are
reachable, or matplotlib is missing, the committed figures are left untouched and the
script exits cleanly. A full paraglider census parses ~186k files and takes several
minutes even across processes. Run it with, e.g.::

    SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc \
    uv run --with matplotlib python scripts/reporting/generate_preproc_figure.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIAG = ROOT / "thesis" / "generated" / "preproc_diagnostics.pdf"
OUT_DT = ROOT / "thesis" / "generated" / "sampling_intervals.pdf"
N_JOBS = min(8, os.cpu_count() or 1)

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Deterministic PDF metadata -> committing the figures produces clean diffs.
_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def _igc_dir(default_config: str, env: str):
    """Locate a discipline's ``igc/`` directory, or ``None`` if it is not reachable."""
    from soaring.acquisition.ffvl.config import load_config

    try:
        cfg = load_config(default_config, data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None
    return cfg.igc_dir if cfg.igc_dir.is_dir() else None


def main() -> int:
    """Regenerate both figures from the full census when data and matplotlib exist."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing (extra 'analysis'); keeping the committed figures.")
        return 0
    matplotlib.use("Agg")

    from soaring.acquisition.ffvl.config import (
        DEFAULT_CONFIG_PATH,
        DEFAULT_DELTA_CONFIG_PATH,
    )
    from soaring.analysis.preprocessing import (
        load_preproc_config,
        make_diagnostics_figure,
        make_sampling_figure,
        scan_tracks,
    )

    dirs = {
        "paragliders": _igc_dir(str(DEFAULT_CONFIG_PATH), "SOARING_PARA_DATA_ROOT"),
        "hang gliders": _igc_dir(
            str(DEFAULT_DELTA_CONFIG_PATH), "SOARING_DELTA_DATA_ROOT"
        ),
    }
    dirs = {d: p for d, p in dirs.items() if p is not None}
    if not dirs:
        print("No IGC data reachable on the SSD; keeping the committed figures.")
        return 0

    scans = {}
    for disc, igc_dir in dirs.items():
        paths = sorted(igc_dir.rglob("*.igc"))
        print(f"[{disc}] full census: parsing {len(paths)} tracks, {N_JOBS} workers...")
        scans[disc] = scan_tracks(paths, n_jobs=N_JOBS)
        s = scans[disc]
        print(
            f"[{disc}] {len(s)} readable; median duration "
            f"{s['duration_s'].median() / 60:.0f} min, median path "
            f"{s['path_km'].median():.0f} km."
        )

    cfg = load_preproc_config()
    OUT_DIAG.parent.mkdir(parents=True, exist_ok=True)
    make_diagnostics_figure(scans, cfg.flight).savefig(
        OUT_DIAG, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    make_sampling_figure(scans).savefig(
        OUT_DT, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    counts = ", ".join(f"{d}={len(s)}" for d, s in scans.items())
    print(f"Wrote {OUT_DIAG.name} and {OUT_DT.name} from full census ({counts}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
