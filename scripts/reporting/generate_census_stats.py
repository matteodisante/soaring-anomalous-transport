#!/usr/bin/env python3
r"""Regenerate the census-scan statistics macros for the thesis.

Writes ``thesis/generated/census.tex``: one ``\newcommand`` per number that the thesis
quotes from the **full-census track scan** (the cached
``<data_root>/derived/track_scan.parquet``, one per discipline, produced by
``generate_preproc_figure.py``). Quoting these through macros -- exactly as
``generate_stats.py`` does for the catalog counts -- is what keeps the prose from
drifting when the archive grows and the scan is refreshed: the ``.tex`` never hard-codes
a census number.

The macros cover, per discipline: the number of scanned tracks; the barometric-absence
fraction and its all-or-nothing structure (channel exactly zero when absent, complete
when present); the median recorded duration and flown path length; the native-rate
discreteness (fraction at an exact whole second, and the per-rate breakdown quoted in
the text); the fraction of largest-gap ratios that are exact integer multiples of
the native interval; and the share of flights whose largest gap exceeds the relative
gap rule alone versus the combined two-scale split bound (thesis ``sec:uniform``),
computed with the thresholds read from ``configs/preprocessing.yaml``.

Definitions mirror the analysis code, not ad-hoc re-derivations: barometric absence is
``baro_present_frac < BARO_PRESENT_MIN`` (imported from ``soaring.analysis
.altitude_noise``, the same threshold the fallback-rate figure uses), and the rate/gap
fractions are computed over the same finite-positive filters as the sampling and gap
figures.

Best-effort, like every reporting script: it only ever *reads* the caches (a full
rescan is ``generate_preproc_figure.py``'s job), and if the SSD, a cache, or the
dependencies are missing it leaves the committed ``census.tex`` untouched and exits
cleanly -- macros for *all* disciplines are required, since a partial file would break
the thesis build. Run it after refreshing the scan caches::

    SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc \
    uv run python scripts/reporting/generate_census_stats.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "thesis" / "generated" / "census.tex"

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Macro-name prefix per discipline (matches the \StatPara/\StatHang style of stats.tex).
_DISCIPLINES = {
    "Para": ("configs/para_download.yaml", "SOARING_PARA_DATA_ROOT"),
    "Hang": ("configs/delta_download.yaml", "SOARING_DELTA_DATA_ROOT"),
}


def _fmt(value: float, decimals: int) -> str:
    """Format to ``decimals`` places, dropping a trailing all-zero fraction.

    So 100.0 -> "100" (the text reads "100 %", not "100.0 %") but 99.7 -> "99.7".
    """
    text = f"{value:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _pct(mask) -> float:
    """``100 * mean(mask)``, and 0.0 (not NaN) on an empty slice."""
    import numpy as np

    m = np.asarray(mask)
    return 100.0 * float(m.mean()) if m.size else 0.0


def _scan_macros(prefix: str, scan, sampling) -> dict[str, str]:
    """The census macros for one discipline's scan table (see module docstring)."""
    import numpy as np

    from soaring.analysis.altitude_noise import BARO_PRESENT_MIN

    frac = scan["baro_present_frac"].to_numpy()
    absent = frac < BARO_PRESENT_MIN

    dt = scan["dt_s"].to_numpy()
    dt = dt[np.isfinite(dt) & (dt > 0)]

    gap = scan["max_gap_ratio"].to_numpy()
    gap = gap[np.isfinite(gap) & (gap > 0)]

    # Gap-split shares under the sampling bound (thesis sec:uniform). Paired filtering
    # (dt AND ratio finite together), since the two-scale bound couples them.
    both = (
        np.isfinite(scan["dt_s"]).to_numpy()
        & (scan["dt_s"].to_numpy() > 0)
        & np.isfinite(scan["max_gap_ratio"]).to_numpy()
        & (scan["max_gap_ratio"].to_numpy() > 0)
    )
    dt_p = scan["dt_s"].to_numpy()[both]
    gap_s = scan["max_gap_ratio"].to_numpy()[both] * dt_p
    g_rel = sampling.max_gap_factor * dt_p
    g_comb = np.minimum(g_rel, np.maximum(sampling.max_gap_seconds, 2.0 * dt_p))

    return {
        f"StatScan{prefix}Tracks": str(len(scan)),
        f"StatScan{prefix}NoBaroPct": _fmt(_pct(absent), 1),
        f"StatScan{prefix}BaroZeroPct": _fmt(_pct(frac[absent] == 0.0), 1),
        f"StatScan{prefix}BaroFullPct": _fmt(_pct(frac[~absent] == 1.0), 0),
        f"StatScan{prefix}MedianDurH": _fmt(
            float(np.nanmedian(scan["duration_s"])) / 3600.0, 1
        ),
        f"StatScan{prefix}MedianPathKm": _fmt(float(np.nanmedian(scan["path_km"])), 0),
        f"StatScan{prefix}DtIntPct": _fmt(_pct(np.abs(dt - np.round(dt)) < 1e-9), 1),
        f"StatScan{prefix}DtOneSecPct": _fmt(_pct(dt == 1.0), 0),
        f"StatScan{prefix}DtTwoSecPct": _fmt(_pct(dt == 2.0), 0),
        f"StatScan{prefix}DtFiveSecPct": _fmt(_pct(dt == 5.0), 0),
        f"StatScan{prefix}DtTenSecPct": _fmt(_pct(dt == 10.0), 0),
        f"StatScan{prefix}GapIntPct": _fmt(_pct(np.abs(gap - np.round(gap)) < 1e-9), 0),
        f"StatScan{prefix}GapSplitRelPct": _fmt(_pct(gap_s > g_rel), 1),
        f"StatScan{prefix}GapSplitCombPct": _fmt(_pct(gap_s > g_comb), 1),
    }


def main() -> int:
    """Rewrite ``census.tex`` when every discipline's scan cache is reachable."""
    try:
        import pandas as pd

        from soaring.acquisition.ffvl.config import load_config
        from soaring.analysis.preprocessing import load_preproc_config
    except ImportError as exc:
        print(f"census stats: missing dependency ({exc}); keeping the committed file.")
        return 0

    sampling = load_preproc_config().sampling

    scans = {}
    for prefix, (config_path, env) in _DISCIPLINES.items():
        try:
            cfg = load_config(str(ROOT / config_path), data_root_env=env)
        except (FileNotFoundError, KeyError):
            print(f"census stats: no config/data root for {prefix}; keeping the file.")
            return 0
        cache = cfg.derived_dir / "track_scan.parquet"
        if not cache.is_file():
            print(f"census stats: no scan cache at {cache}; keeping the file.")
            return 0
        scans[prefix] = pd.read_parquet(cache)

    lines = [
        "% AUTO-GENERATED by scripts/reporting/generate_census_stats.py from the",
        "% cached full-census track scans (<data_root>/derived/track_scan.parquet,",
        "% one per discipline) -- DO NOT EDIT. To refresh: delete the caches, rerun",
        "% generate_preproc_figure.py (full rescan), then rerun this script.",
    ]
    for prefix, scan in scans.items():
        for name, value in _scan_macros(prefix, scan, sampling).items():
            lines.append(f"\\newcommand{{\\{name}}}{{{value}}}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    counts = ", ".join(f"{p}={len(s)}" for p, s in scans.items())
    print(f"Wrote {OUT} ({counts}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
