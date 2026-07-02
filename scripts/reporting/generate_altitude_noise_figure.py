#!/usr/bin/env python3
r"""Regenerate the barometric-vs-GNSS altitude noise figure for the thesis.

Computes the altitude noise diagnostics (Welch PSD + barometric availability) from raw
IGC tracks on the external SSD and writes ``thesis/generated/altitude_noise.pdf``.

The three panels have different precision needs, so they use different data volumes (see
``soaring.analysis.altitude_noise`` for the full rationale):

* Panel (d), the barometric-presence fraction, is a headline number, so its precision is
  justified rather than asserted. A population up to ``CENSUS_MAX_POPULATION`` files is
  censused exactly (fast enough to just do it); a larger one (the paraglider archive,
  ~186,000 files) is instead estimated from a simple random sample whose size is
  computed by ``required_sample_size`` for a stated 95%-confidence margin of error
  (``TARGET_MARGIN_OF_ERROR``) -- a few thousand files, parsed in well under a minute.
* Panels (a)/(b), the PSD and the representative flight, use a smaller, fixed-size
  random subsample (``PSD_SAMPLE_PER_DISCIPLINE``): an ensemble-average spectral shape,
  not a headline statistic, so a moderate sample is the standard and adequate tool.

Like ``generate_preproc_figure.py``, the raw data lives on an external disk and may be
absent (a fresh checkout, or CI). The data roots come from the same environment
variables used by the downloaders (``SOARING_PARA_DATA_ROOT`` /
``SOARING_DELTA_DATA_ROOT``) or the config placeholders; a discipline whose ``igc/``
directory is missing is skipped, and if no data at all is reachable the committed figure
is left untouched and the script exits cleanly. It also needs the ``analysis`` extra
(``matplotlib`` + ``scipy``); if either is missing it also exits without failing. Run it
with, e.g.::

    uv run --with matplotlib --with scipy \
        python scripts/reporting/generate_altitude_noise_figure.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "thesis" / "generated" / "altitude_noise.pdf"

# Flights sampled per discipline for the PSD / representative-flight panels: an
# ensemble-average spectral shape, not a headline statistic, so a moderate seeded random
# subsample is standard practice here (see the module docstring above).
PSD_SAMPLE_PER_DISCIPLINE = 400
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


def _igc_dir(default_config: str, env: str) -> Path | None:
    """Locate a discipline's ``igc/`` directory, or ``None`` if it is not reachable."""
    from soaring.acquisition.ffvl.config import load_config

    try:
        cfg = load_config(default_config, data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None
    return cfg.igc_dir if cfg.igc_dir.is_dir() else None


def main() -> int:
    """Regenerate the figure when the raw data and the analysis extra are available."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing (extra 'analysis'); keeping the committed figure.")
        return 0
    try:
        import scipy  # noqa: F401
    except ImportError:
        print("scipy missing (extra 'analysis'); keeping the committed figure.")
        return 0
    matplotlib.use("Agg")

    from soaring.acquisition.ffvl.config import (
        DEFAULT_CONFIG_PATH,
        DEFAULT_DELTA_CONFIG_PATH,
    )
    from soaring.analysis.altitude_noise import (
        collect,
        proportion_ci,
        render_altitude_noise_figure,
        required_sample_size,
        sample_igc_paths,
    )

    para_dir = _igc_dir(str(DEFAULT_CONFIG_PATH), "SOARING_PARA_DATA_ROOT")
    hang_dir = _igc_dir(str(DEFAULT_DELTA_CONFIG_PATH), "SOARING_DELTA_DATA_ROOT")
    disciplines = {"paragliders": para_dir, "hang gliders": hang_dir}
    disciplines = {d: p for d, p in disciplines.items() if p is not None}
    if not disciplines:
        print("No IGC data reachable on the SSD; keeping the committed figure.")
        return 0

    stat_samples: dict[str, list[Path]] = {}
    for disc, igc_dir in disciplines.items():
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

    acc = collect(samples, stat_samples=stat_samples, stat_n_jobs=STAT_N_JOBS)
    for disc in disciplines:
        p_hat, half_width = proportion_ci(acc.baro_absent[disc], acc.n_flights[disc])
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
