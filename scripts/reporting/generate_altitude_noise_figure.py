#!/usr/bin/env python3
r"""Regenerate the barometric-vs-GNSS altitude noise figure for the thesis.

Computes the altitude noise diagnostics (Welch PSD + barometric availability) from raw
IGC tracks on the external SSD and writes ``thesis/generated/altitude_noise.pdf``.

The three panels have different precision needs, so they use different data volumes (see
``soaring.analysis.altitude_noise`` for the full rationale):

* Panel (d), the barometric-presence fraction, is a headline number, so its precision is
  justified rather than asserted. **Preferred path**: if
  ``generate_preproc_figure.py`` has already cached a full-dataset scan at
  ``<data_root>/derived/track_scan.parquet`` (on the SSD), this reuses it -- an *exact*
  population fraction, no scanning here at all. **Fallback** (no cache yet): a
  population up to ``CENSUS_MAX_POPULATION`` files is censused exactly (fast enough); a
  larger one (the paraglider archive, ~186,000 files) is instead estimated from a simple
  random sample whose size is computed by ``required_sample_size`` for a stated
  95%-confidence margin of error (``TARGET_MARGIN_OF_ERROR``).
* Panels (a)/(b), the PSD and the representative flight, use a smaller, fixed-size
  random subsample (``PSD_SAMPLE_PER_DISCIPLINE``): an ensemble-average spectral shape,
  not a headline statistic, so a moderate sample is the standard and adequate tool. This
  always needs an actual scan (the cache only carries summary stats, not full spectra).

Like ``generate_preproc_figure.py``, the raw data lives on an external disk and may be
absent (a fresh checkout, or CI). The data roots come from the same environment
variables used by the downloaders (``SOARING_PARA_DATA_ROOT`` /
``SOARING_DELTA_DATA_ROOT``) or the config placeholders; a discipline whose ``igc/``
directory is missing is skipped, and if no data at all is reachable the committed figure
is left untouched and the script exits cleanly. It also needs the ``analysis``
dependency group (``matplotlib`` + ``scipy``; on by default in ``uv run``, see
``pyproject.toml``); if either is missing it also exits without failing. Run it with,
e.g.::

    uv run python scripts/reporting/generate_altitude_noise_figure.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "thesis" / "generated" / "altitude_noise.pdf"

# Flights sampled per discipline for the PSD / representative-flight panels. The PSD
# ensemble spectral shape, not a headline statistic, but the sample must still be large
# enough for the high-frequency barometric curve to converge: at ~400 flights that curve
# is visibly under-averaged (ragged), and it smooths out with more. A few thousand keeps
# the parse cheap while giving a stable curve (the ensemble is reduced with the robust
# per-frequency median, see `soaring.analysis.altitude_noise`, so a few noisy flights do
# not dominate, but the median still needs enough flights to be smooth).
PSD_SAMPLE_PER_DISCIPLINE = 3000
# Populations up to this size are censused exactly for panel (d) rather than sampled
# (a couple of minutes at most; the hang-glider archive, ~6,700 files, falls under it).
CENSUS_MAX_POPULATION = 10_000
# Target 95%-confidence margin of error for the sampled panel-(d) estimate
# (paragliders): +/-2 percentage points, ample precision to tell "a negligible
# minority" from "a substantial minority" of flights, all this is used for.
TARGET_MARGIN_OF_ERROR = 0.02
STAT_N_JOBS = min(8, os.cpu_count() or 1)

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Deterministic PDF metadata -> committing the figure produces clean diffs.
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
    """Regenerate the figure when the raw data and the analysis group are available."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' dependency group); keeping the figure.")
        return 0
    try:
        import scipy  # noqa: F401
    except ImportError:
        print("scipy missing ('analysis' dependency group); keeping the figure.")
        return 0
    matplotlib.use("Agg")

    from soaring.acquisition.ffvl.config import (
        DEFAULT_CONFIG_PATH,
        DEFAULT_DELTA_CONFIG_PATH,
    )
    from soaring.analysis.altitude_noise import (
        baro_presence_from_scan,
        collect,
        proportion_ci,
        render_altitude_noise_figure,
        required_sample_size,
        sample_igc_paths,
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
    disciplines = {d: c.igc_dir for d, c in configs.items()}
    if not disciplines:
        print("No IGC data reachable on the SSD; keeping the committed figure.")
        return 0

    # Prefer generate_preproc_figure.py's cached full-census scan for panel (d): an
    # EXACT population fraction at zero extra parsing, in place of a sampled estimate.
    precomputed_baro_stats: dict[str, tuple[int, int]] = {}
    for disc, cfg_disc in configs.items():
        cache_path = cfg_disc.derived_dir / "track_scan.parquet"
        if cache_path.is_file():
            import pandas as pd

            scan = pd.read_parquet(cache_path)
            precomputed_baro_stats[disc] = baro_presence_from_scan(scan)
            print(
                f"[{disc}] using cached full-census scan at {cache_path} for the "
                f"barometric-presence fraction (exact, no sampling here)."
            )

    stat_samples: dict[str, list[Path]] = {}
    for disc, igc_dir in disciplines.items():
        if disc in precomputed_baro_stats:
            continue  # exact count already in hand from the cache; no scan needed
        population = sorted(igc_dir.rglob("*.igc"))
        n_pop = len(population)
        if n_pop <= CENSUS_MAX_POPULATION:
            stat_samples[disc] = population
            print(f"[{disc}] full-population census: N={n_pop}.")
        else:
            n = required_sample_size(TARGET_MARGIN_OF_ERROR)
            stat_samples[disc] = sample_igc_paths(igc_dir, n)
            print(
                f"[{disc}] N={n_pop} exceeds the census threshold; sampling n={n} "
                f"for a target 95% margin of error of "
                f"+/-{TARGET_MARGIN_OF_ERROR * 100:.0f} percentage points."
            )

    samples = {
        disc: sample_igc_paths(igc_dir, PSD_SAMPLE_PER_DISCIPLINE)
        for disc, igc_dir in disciplines.items()
    }
    samples = {d: paths for d, paths in samples.items() if paths}
    if not samples:
        print("No IGC data reachable on the SSD; keeping the committed figure.")
        return 0

    acc = collect(
        samples,
        stat_samples=stat_samples or None,
        stat_n_jobs=STAT_N_JOBS,
        precomputed_baro_stats=precomputed_baro_stats,
    )
    for disc in disciplines:
        p_hat, half_width = proportion_ci(acc.baro_absent[disc], acc.n_flights[disc])
        if disc in precomputed_baro_stats:
            print(
                f"[{disc}] barometric-absent fraction: {p_hat * 100:.1f}% "
                f"(exact, full census, n={acc.n_flights[disc]})."
            )
        else:
            print(
                f"[{disc}] barometric-absent fraction: "
                f"{p_hat * 100:.1f}% +/- {half_width * 100:.1f} pts "
                f"(95% CI, n={acc.n_flights[disc]})."
            )

    fig = render_altitude_noise_figure(acc, list(samples))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, metadata=_PDF_METADATA, bbox_inches="tight")
    counts = ", ".join(f"{d}={len(p)}" for d, p in samples.items())
    print(f"Wrote {OUT_PATH} from PSD sample ({counts}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
