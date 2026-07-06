#!/usr/bin/env python3
"""Regenerate the pre-processing diagnostic figures for the thesis.

Writes four figures to ``thesis/generated/``:

* ``preproc_diagnostics.pdf`` -- flight-level: recorded flight duration and total flown
  path length, each with its distribution and its *marginal* retention curve (that cut
  alone), with the adopted flight-level thresholds marked;
* ``gap_diagnostics.pdf`` -- sampling regularity: the largest inter-fix gap (relative to
  that flight's own native sampling interval) and the fraction of a uniform grid left
  uncovered, each with its distribution and marginal retention curve;
* ``sampling_intervals.pdf`` -- the native sampling interval per flight;
* ``fixlevel_diagnostics.pdf`` -- fix-level: the per-fix distributions of horizontal
  speed, barometric vertical speed and barometric altitude, with the adopted fix-level
  bounds marked and the fraction of fixes each removes annotated.

The first three are computed on the **full dataset** (every downloaded track, no
sub-sampling); the fix-level distributions are pooled over a seeded random sample of
flights (millions of fixes -- ample for a distribution shape and cut fraction, far
cheaper than re-reading every fix of the census), exactly as the altitude PSD is
sampled. Every discipline present is overlaid (paragliders and hang gliders today;
sailplanes later). All quantities come from the parsed tracks, not the declared catalog
metadata. The adopted thresholds are read from ``configs/preprocessing.yaml``.

The per-flight scan is **cached** on the SSD, at each discipline's
``<data_root>/derived/track_scan.parquet`` (``Config.derived_dir`` -- never in the
repo): a second run reuses it instead of re-parsing; delete the file (or edit
``FORCE_RESCAN`` below) to force a fresh scan, e.g. after changing
``soaring.analysis.preprocessing.track_stats``. The same cache also carries the
barometric-presence fraction, so the altitude-noise figure's fallback-rate panel can
read an exact census from it instead of running its own separate scan.

The raw data lives on an external disk and may be absent (a fresh checkout, or CI); the
data roots come from ``SOARING_PARA_DATA_ROOT`` / ``SOARING_DELTA_DATA_ROOT`` or config
placeholders. A discipline whose ``igc/`` directory is missing is skipped; if none are
reachable, or matplotlib is missing, the committed figures are left untouched and the
script exits cleanly. A full census of a large archive parses hundreds of thousands of
files and takes several minutes even across processes. Run it with, e.g. (``uv run``
already includes the ``analysis`` dependency group -- matplotlib/scipy/pyarrow -- by
default, see ``pyproject.toml``)::

    SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc \
    uv run python scripts/reporting/generate_preproc_figure.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIAG = ROOT / "thesis" / "generated" / "preproc_diagnostics.pdf"
OUT_GAPS = ROOT / "thesis" / "generated" / "gap_diagnostics.pdf"
OUT_DT = ROOT / "thesis" / "generated" / "sampling_intervals.pdf"
OUT_FIX = ROOT / "thesis" / "generated" / "fixlevel_diagnostics.pdf"
N_JOBS = min(8, os.cpu_count() or 1)
FORCE_RESCAN = False  # set True (or delete <data_root>/derived/track_scan.parquet)
# Flights sampled per discipline for the fix-level distributions: a seeded random
# subsample, the same tool the altitude PSD uses. Deliberately large (tens of millions
# of fixes): resolving the sparse tail well enough to tell real dynamics from a rare
# logger/GPS artifact needs it, and it is cheap (well under two minutes total; each
# discipline is capped at its own population, so this already IS the full census for
# any discipline smaller than this number, e.g. today's hang gliders).
FIXLEVEL_SAMPLE_PER_DISCIPLINE = 15_000

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Deterministic PDF metadata -> committing the figures produces clean diffs.
_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def _resolve_config(default_config: str, env: str):
    """Load a discipline's config, or ``None`` if its ``igc/`` dir is not reachable."""
    from soaring.acquisition.ffvl.config import load_config

    try:
        cfg = load_config(default_config, data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None
    return cfg if cfg.igc_dir.is_dir() else None


def main() -> int:
    """Regenerate both figures from the full census when data and matplotlib exist."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' dependency group); keeping the figures.")
        return 0
    matplotlib.use("Agg")

    from soaring.acquisition.ffvl.config import (
        DEFAULT_CONFIG_PATH,
        DEFAULT_DELTA_CONFIG_PATH,
    )
    from soaring.analysis.altitude_noise import sample_igc_paths
    from soaring.analysis.preprocessing import (
        fix_level_distributions,
        load_or_scan_tracks,
        load_preproc_config,
        make_fixlevel_diagnostics_figure,
        make_flightlevel_diagnostics_figure,
        make_gap_diagnostics_figure,
        make_sampling_figure,
    )

    configs = {
        "paragliders": _resolve_config(
            str(DEFAULT_CONFIG_PATH), "SOARING_PARA_DATA_ROOT"
        ),
        "hang gliders": _resolve_config(
            str(DEFAULT_DELTA_CONFIG_PATH), "SOARING_DELTA_DATA_ROOT"
        ),
    }
    configs = {d: c for d, c in configs.items() if c is not None}
    if not configs:
        print("No IGC data reachable on the SSD; keeping the committed figures.")
        return 0

    scans = {}
    for disc, cfg_disc in configs.items():
        cache_path = cfg_disc.derived_dir / "track_scan.parquet"
        print(f"[{disc}] full census (cached at {cache_path})...")
        scans[disc] = load_or_scan_tracks(
            cfg_disc.igc_dir, cache_path, n_jobs=N_JOBS, force=FORCE_RESCAN
        )
        s = scans[disc]
        print(
            f"[{disc}] {len(s)} readable; median duration "
            f"{s['duration_s'].median() / 60:.0f} min, median path "
            f"{s['path_km'].median():.0f} km."
        )

    cfg = load_preproc_config()
    OUT_DIAG.parent.mkdir(parents=True, exist_ok=True)
    make_flightlevel_diagnostics_figure(scans, cfg.flight).savefig(
        OUT_DIAG, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    make_gap_diagnostics_figure(scans, cfg.sampling).savefig(
        OUT_GAPS, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    make_sampling_figure(scans).savefig(
        OUT_DT, metadata=_PDF_METADATA, bbox_inches="tight"
    )

    # Fix-level per-fix distributions, pooled over a seeded sample per discipline.
    distributions = {}
    for disc, cfg_disc in configs.items():
        t0 = time.perf_counter()
        paths = sample_igc_paths(cfg_disc.igc_dir, FIXLEVEL_SAMPLE_PER_DISCIPLINE)
        distributions[disc] = fix_level_distributions(paths, n_jobs=N_JOBS)
        elapsed = time.perf_counter() - t0
        n_fix = int(distributions[disc]["v_xy"].size)
        print(
            f"[{disc}] fix-level sample: {len(paths)} flights, {n_fix} fix pairs, "
            f"{elapsed:.0f} s."
        )
    make_fixlevel_diagnostics_figure(distributions, cfg.fix).savefig(
        OUT_FIX, metadata=_PDF_METADATA, bbox_inches="tight"
    )

    counts = ", ".join(f"{d}={len(s)}" for d, s in scans.items())
    names = f"{OUT_DIAG.name}, {OUT_GAPS.name}, {OUT_DT.name} and {OUT_FIX.name}"
    print(f"Wrote {names} ({counts}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
