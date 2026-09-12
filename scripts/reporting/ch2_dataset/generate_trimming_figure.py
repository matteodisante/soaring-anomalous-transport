#!/usr/bin/env python3
r"""Regenerate the takeoff/landing trim-split and interior-excision figures.

Writes two figures to ``thesis/generated/``:

* ``trim_split_seconds.pdf`` -- per discipline, the distribution of the time cut from
  the start of the record to the estimated onset :math:`t_{\mathrm{on}}`, and
  separately the time cut from the estimated end :math:`t_{\mathrm{off}}` to the end of
  the record (sec:trimming). The cached ``flights_meta.parquet`` keeps only their
  *combined* fraction of the recorded span, so this figure needs its own scan.
* ``trim_interior_excisions.pdf`` -- the discrete distribution of how many interior
  ground stints (mid-flight landings) the same stage excised, per flight.

Both come from one full-census pass of :func:`soaring.analysis.trim_census
.scan_trim_split`, which reruns stages (i)-(iii)
(:mod:`soaring.analysis.preproc.altchannel`/``cleaning``/``trimming``) on every raw
``.igc`` file -- cheaper than the full pipeline (no resampling, local-frame conversion
or smoothing), but still a real pass over the archive: a few minutes for the paraglider
population across several worker processes. The result is cached at each discipline's
``<data_root>/derived/trim_scan.parquet``; pass ``--rescan`` to force a fresh one, e.g.
after changing :mod:`soaring.analysis.preproc.trimming`.

The raw data lives on an external disk and may be absent (a fresh checkout, or CI); the
data roots come from ``SOARING_PARA_DATA_ROOT`` / ``SOARING_DELTA_DATA_ROOT``. A
discipline whose ``igc/`` directory is missing is skipped; if none are reachable, or
matplotlib is missing, the committed figures are left untouched. Run it with::

    SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc \
    uv run python scripts/reporting/ch2_dataset/generate_trimming_figure.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

GENERATED_OUTPUTS = (
    "trim_split_seconds.pdf",
    "trim_interior_excisions.pdf",
    "trim.tex",
)

ROOT = Path(__file__).resolve().parents[3]
OUT_SPLIT = ROOT / "thesis" / "generated" / "trim_split_seconds.pdf"
OUT_INTERIOR = ROOT / "thesis" / "generated" / "trim_interior_excisions.pdf"
OUT_MACROS = ROOT / "thesis" / "generated" / "trim.tex"
N_JOBS = max(
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


def _write_macros(scans: dict) -> None:
    r"""Write ``\StatTrim*``: the trim-split medians and the interior-excision tail."""
    import numpy as np

    from soaring.reporting.macros import MacroWriter, write_macros

    tag = {"paragliders": "Para", "hang gliders": "Hang"}
    w = MacroWriter("StatTrim")
    for disc, s in scans.items():
        t = tag.get(disc, disc.capitalize())
        w.put(f"{t}ScanCount", len(s))
        w.put(f"{t}TakeoffMedianS", f"{np.median(s['takeoff_trimmed_s']):.0f}")
        w.put(f"{t}LandingMedianS", f"{np.median(s['landing_trimmed_s']):.0f}")
        n_interior = s["n_interior_excised"].to_numpy(dtype=int)
        nonzero = int((n_interior > 0).sum())
        w.put(f"{t}InteriorNonzeroCount", nonzero)
        # pct_of's usual one-decimal rounding reads as a flat "0.0" for the smaller
        # hang-glider population (3 of 6580); two decimals keep the nonzero count
        # visible in the macro the prose quotes, matching the point of the figure.
        pct = 100.0 * nonzero / len(n_interior) if len(n_interior) else 0.0
        w.put(f"{t}InteriorNonzeroPct", f"{pct:.2f}")
        w.put(f"{t}InteriorMax", int(n_interior.max()) if n_interior.size else 0)

    n = write_macros(
        OUT_MACROS,
        w,
        generator="scripts/reporting/ch2_dataset/generate_trimming_figure.py",
        extra_header=[
            "The takeoff/landing trim-split census (thesis, sec:trimming): medians of",
            "the two durations flights_meta.parquet keeps only combined, and how often",
            "the interior-ground rule excises more than zero mid-flight stints.",
        ],
    )
    print(f"Wrote {OUT_MACROS} ({n} macros).")


def main(argv: list[str] | None = None) -> int:
    """Regenerate both figures from a full trim-split census."""
    argv = sys.argv[1:] if argv is None else argv
    rescan = "--rescan" in argv
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' dependency group); keeping the figures.")
        return 0
    matplotlib.use("Agg")

    from soaring.acquisition.ffvl.config import DELTA_CONFIG_PATH, PARA_CONFIG_PATH
    from soaring.analysis.figures.trimming import (
        make_interior_excision_figure,
        make_trim_split_figure,
    )
    from soaring.analysis.trim_census import load_or_scan_trim_split

    configs = {
        "paragliders": _resolve_config(str(PARA_CONFIG_PATH), "SOARING_PARA_DATA_ROOT"),
        "hang gliders": _resolve_config(
            str(DELTA_CONFIG_PATH), "SOARING_DELTA_DATA_ROOT"
        ),
    }
    configs = {d: c for d, c in configs.items() if c is not None}
    if not configs:
        print("No IGC data reachable on the SSD; keeping the committed figures.")
        return 0
    refusal = partial_write_refusal(
        [d for d in DISCIPLINES if d not in configs],
        "the trim-split figures",
        allow_partial="--allow-partial" in argv,
        reasons=[
            unreachable_reason(DISCIPLINES[d], "trim_scan.parquet")
            for d in DISCIPLINES
            if d not in configs
        ],
    )
    if refusal:
        print(refusal)
        return 1

    scans = {}
    for disc, cfg_disc in configs.items():
        cache_path = cfg_disc.derived_dir / "trim_scan.parquet"
        scans[disc] = load_or_scan_trim_split(
            cfg_disc.igc_dir, disc, cache_path, n_jobs=N_JOBS, force=rescan
        )

    fig = make_trim_split_figure(scans)
    OUT_SPLIT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_SPLIT, metadata=_PDF_METADATA, bbox_inches="tight")
    print(f"Wrote {OUT_SPLIT}.")

    fig = make_interior_excision_figure(scans)
    fig.savefig(OUT_INTERIOR, metadata=_PDF_METADATA, bbox_inches="tight")
    print(f"Wrote {OUT_INTERIOR}.")

    _write_macros(scans)
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=["--allow-partial", "--rescan"])

    raise SystemExit(main())
