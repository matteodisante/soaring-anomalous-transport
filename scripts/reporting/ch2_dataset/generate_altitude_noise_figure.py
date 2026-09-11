#!/usr/bin/env python3
r"""Regenerate paired altitude spectra and GNSS-presence diagnostics.

Writes ``thesis/generated/altitude_noise.pdf`` and ``altitude_noise.tex``. Raw PSDs
use a seeded sample of 3000 paths per discipline and the longest uninterrupted paired
interval of valid altitude readings. Versioned NPZ caches preserve the spectra; pass
``--rescan`` to force collection. The GNSS-presence distribution independently reuses
the full raw track census when available, otherwise an explicit census/sample fallback.
High-frequency power is a statistic of logged channels, not an identified error source.

Entry point: ``scripts/reporting/ch2_dataset/generate_altitude_noise_figure.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

GENERATED_OUTPUTS = ("altitude_noise.pdf", "altitude_noise.tex")

ROOT = Path(__file__).resolve().parents[3]
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
STAT_N_JOBS = max(
    1, min(int(os.environ.get("SOARING_MAX_WORKERS", "1")), os.cpu_count() or 1)
)

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    bare_cli,
    partial_write_refusal,
    unreachable_reason,
)

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


def main(argv: list[str] | None = None) -> int:
    """Regenerate the figure when the raw data and the analysis group are available."""
    argv = sys.argv[1:] if argv is None else argv
    rescan = "--rescan" in argv
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
    from soaring.reporting.style import paper_style

    paper_style()

    from soaring.acquisition.ffvl.config import (
        DELTA_CONFIG_PATH,
        PARA_CONFIG_PATH,
    )
    from soaring.analysis.altitude_noise import (
        BARO_PRESENT_MIN,
        collect,
        gnss_presence_from_scan,
        proportion_ci,
        render_altitude_noise_figure,
        required_sample_size,
        sample_igc_paths,
    )

    configs = {
        "paragliders": _resolve_config(str(PARA_CONFIG_PATH), "SOARING_PARA_DATA_ROOT"),
        "hang gliders": _resolve_config(
            str(DELTA_CONFIG_PATH), "SOARING_DELTA_DATA_ROOT"
        ),
    }
    configs = {d: c for d, c in configs.items() if c is not None}
    disciplines = {d: c.igc_dir for d, c in configs.items()}
    if not disciplines:
        print("No IGC data reachable on the SSD; keeping the committed figure.")
        return 0
    refusal = partial_write_refusal(
        [d for d in DISCIPLINES if d not in disciplines],
        OUT_PATH.name,
        allow_partial="--allow-partial" in sys.argv[1:],
        reasons=[
            unreachable_reason(DISCIPLINES[d], "fixes.parquet")
            for d in DISCIPLINES
            if d not in disciplines
        ],
    )
    if refusal:
        print(refusal)
        return 1

    # Prefer generate_preproc_figure.py's cached full-census scan for panel (d): an
    # EXACT population distribution at zero extra parsing, in place of a sampled one.
    precomputed_gnss_stats = {}
    for disc, cfg_disc in configs.items():
        cache_path = cfg_disc.derived_dir / "track_scan.parquet"
        if cache_path.is_file():
            import pandas as pd

            scan = pd.read_parquet(cache_path)
            precomputed_gnss_stats[disc] = gnss_presence_from_scan(scan)
            print(
                f"[{disc}] using cached full-census scan at {cache_path} for the "
                f"GNSS-presence distribution (exact, no sampling here)."
            )

    stat_samples: dict[str, list[Path]] = {}
    for disc, igc_dir in disciplines.items():
        if disc in precomputed_gnss_stats:
            continue  # The cached census already supplies this distribution.
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

    psd_cache_paths = {
        disc: configs[disc].derived_dir / "psd_sample.npz" for disc in samples
    }
    acc = collect(
        samples,
        stat_samples=stat_samples or None,
        stat_n_jobs=STAT_N_JOBS,
        precomputed_gnss_stats=precomputed_gnss_stats,
        psd_cache_paths=psd_cache_paths,
        force_psd_rescan=rescan,
    )
    for disc in disciplines:
        frac = acc.gnss_present_frac[disc]
        k = int((frac < BARO_PRESENT_MIN).sum())
        p_hat, half_width = proportion_ci(k, acc.n_flights[disc])
        if disc in precomputed_gnss_stats:
            print(
                f"[{disc}] below-cutoff GNSS-presence fraction: {p_hat * 100:.1f}% "
                f"(exact, full census, n={acc.n_flights[disc]})."
            )
        else:
            print(
                f"[{disc}] below-cutoff GNSS-presence fraction: "
                f"{p_hat * 100:.1f}% +/- {half_width * 100:.1f} pts "
                f"(95% CI, n={acc.n_flights[disc]})."
            )

    fig = render_altitude_noise_figure(acc, list(samples))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, metadata=_PDF_METADATA, bbox_inches="tight")
    counts = ", ".join(f"{d}={len(p)}" for d, p in samples.items())
    print(f"Wrote {OUT_PATH} from PSD sample ({counts}).")

    _write_hf_floor_macros(acc)
    return 0


def _write_hf_floor_macros(acc) -> None:
    r"""Write ``\StatAltNoise*``: the measured size of the noisy-GNSS minority.

    Pooled over every discipline the PSD sample reached, matching the pooling
    :func:`~soaring.analysis.altitude_noise._Accumulator.pooled_band_psd` already does
    for panel (c) -- one number, not a per-discipline family, since the claim is about
    the channel and the receiver, not the glider (thesis, sec:altchannel).
    """
    from soaring.analysis.altitude_noise import hf_floor_excess_fraction
    from soaring.reporting.macros import MacroWriter, write_macros

    gnss_floor = acc.hf_floor("gnss")
    baro_floor = acc.hf_floor("baro")
    if gnss_floor.size == 0 or baro_floor.size == 0:
        print("No paired baro/GNSS spectra in the sample; skipping altitude_noise.tex.")
        return

    import numpy as np

    w = MacroWriter("StatAltNoise")
    w.put("PsdSampleFlights", int(gnss_floor.size))
    factor_names = {3: "ThreeX", 10: "TenX"}  # spelled out: \newcommand reads a
    # leading digit in the trailing text as an argument count (see check_name).
    for factor, name in factor_names.items():
        pct = 100.0 * hf_floor_excess_fraction(gnss_floor, baro_floor, float(factor))
        w.put(f"GnssExcess{name}Pct", f"{pct:.1f}")
    for label, arr in (("Baro", baro_floor), ("Gnss", gnss_floor)):
        for q, name in ((50, "Median"), (90, "PNinety"), (99, "PNinetyNine")):
            w.put(f"{label}Floor{name}", f"{np.percentile(arr, q):.2e}")

    out = OUT_PATH.parent / "altitude_noise.tex"
    n = write_macros(
        out,
        w,
        generator="scripts/reporting/ch2_dataset/generate_altitude_noise_figure.py",
        extra_header=[
            "The GNSS high-frequency-floor excess: how many flights carry a floor a",
            "given multiple of the barometric channel's typical (median) one, measured",
            "per flight rather than inferred from where the two ensemble medians sit.",
        ],
    )
    print(f"Wrote {out} ({n} macros).")


if __name__ == "__main__":
    bare_cli(__doc__, known=["--allow-partial", "--rescan"])

    raise SystemExit(main())
