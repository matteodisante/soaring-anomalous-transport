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
  speed, windowed GNSS vertical speed and GNSS altitude, with the adopted fix-level
  bounds marked and bound-exceedance fractions annotated.

The first three are computed on the **full dataset** (every downloaded track, no
sub-sampling); the fix-level distributions are pooled over a seeded random sample of
flights (millions of fixes -- ample for a distribution shape and cut fraction, far
cheaper than re-reading every fix of the census), exactly as the altitude PSD is
sampled. Every discipline present is overlaid (paragliders and hang gliders today;
sailplanes later). All quantities come from the parsed tracks, not the declared catalog
metadata. The adopted thresholds are read from ``configs/preprocessing.yaml``.

The per-flight scan is **cached** on the SSD, at each discipline's
``<data_root>/derived/track_scan.parquet`` (``Config.derived_dir`` -- never in the
repo): a second run reuses it instead of re-parsing. Pass ``--rescan`` to refresh
both raw diagnostic caches after changing
``soaring.analysis.census.track_stats``. The same cache also carries the
barometric-presence fraction, so the altitude-noise figure's fallback-rate panel can
read an exact census from it instead of running its own separate scan. The fix-level
sample is cached the same way, at ``<data_root>/derived/fixlevel_scan.parquet``
(:func:`soaring.analysis.census.load_or_scan_fixlevel`): sampling and parsing tens of
thousands of files off the external disk, not the plotting, is what makes a cold run of
this script slow, so a change to ``fixlevel_diagnostics.pdf``'s styling alone -- unlike
a change to ``FIXLEVEL_SAMPLE_PER_DISCIPLINE`` or ``vz_window_s``, which needs a fresh
sample -- costs the same fraction of a second the cached scan already does.

The raw data lives on an external disk and may be absent (a fresh checkout, or CI); the
data roots come from ``SOARING_PARA_DATA_ROOT`` / ``SOARING_DELTA_DATA_ROOT`` or config
placeholders. A discipline whose ``igc/`` directory is missing is skipped; if none are
reachable, or matplotlib is missing, the committed figures are left untouched and the
script exits cleanly. A full census of a large archive parses hundreds of thousands of
files and takes several minutes even across processes. Run it with, e.g. (``uv run``
already includes the ``analysis`` dependency group -- matplotlib/scipy/pyarrow -- by
default, see ``pyproject.toml``)::

    SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc \
    uv run python scripts/reporting/ch2_dataset/generate_preproc_figure.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_DIAG = ROOT / "thesis" / "generated" / "preproc_diagnostics.pdf"
OUT_GAPS = ROOT / "thesis" / "generated" / "gap_diagnostics.pdf"
OUT_DT = ROOT / "thesis" / "generated" / "sampling_intervals.pdf"
OUT_FIX = ROOT / "thesis" / "generated" / "fixlevel_diagnostics.pdf"
N_JOBS = max(
    1, min(int(os.environ.get("SOARING_MAX_WORKERS", "1")), os.cpu_count() or 1)
)
FORCE_RESCAN = False  # set True to force both caches below to redo their pass -- edit
# <data_root>/derived/{track_scan,fixlevel_scan}.parquet directly to redo just one.
# Flights sampled per discipline for the fix-level distributions: a seeded random
# subsample, the same tool the altitude PSD uses. Deliberately large (tens of millions
# of fixes): resolving the sparse tail well enough to tell real dynamics from a rare
# logger/GPS artifact needs it. That many individually-opened files on the external
# disk is not cheap (tens of minutes, not the "well under two" once assumed here) --
# which is exactly why the sample is cached rather than merely fast.
FIXLEVEL_SAMPLE_PER_DISCIPLINE = 15_000

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


def _write_fixlevel_cache(igc_dir, cache_path, vz_window_s):
    """Build the existing long-form cache without retaining all sampled flights."""
    from concurrent.futures import ProcessPoolExecutor
    from functools import partial

    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    from soaring.analysis.altitude_noise import sample_igc_paths
    from soaring.analysis.census import _fix_level_one

    paths = sample_igc_paths(igc_dir, FIXLEVEL_SAMPLE_PER_DISCIPLINE)
    schema = pa.schema([("quantity", pa.int8()), ("value", pa.float32())])
    temporary = cache_path.with_suffix(".parquet.pending")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    worker = partial(_fix_level_one, vz_window_s=vz_window_s)
    try:
        with (
            pq.ParquetWriter(temporary, schema, compression="zstd") as writer,
            ProcessPoolExecutor(max_workers=N_JOBS) as pool,
        ):
            for begin in range(0, len(paths), 100):
                tables = []
                for result in pool.map(worker, paths[begin : begin + 100], chunksize=5):
                    for code, values in enumerate(result):
                        if len(values):
                            tables.append(
                                pa.table(
                                    {
                                        "quantity": np.full(
                                            len(values), code, dtype=np.int8
                                        ),
                                        "value": values.astype(np.float32),
                                    },
                                    schema=schema,
                                )
                            )
                if tables:
                    writer.write_table(pa.concat_tables(tables))
        temporary.replace(cache_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    print(f"Cached {len(paths)} raw diagnostic flights to {cache_path}.", flush=True)


def _stream_fixlevel_histograms(cache_path, discipline, fix):
    """Exact finite counts and fixed-range histograms from the long-form cache."""
    import numpy as np
    import pyarrow.parquet as pq

    specs = {
        "v_xy": (
            0,
            np.linspace(0, 120, 61),
            (-np.inf, fix.max_horizontal_speed_mps[discipline]),
        ),
        "v_z_local": (2, np.linspace(0, 60, 61), (-np.inf, fix.max_vertical_speed_mps)),
        "altitude": (
            3,
            np.linspace(-200, 10000, 61),
            (fix.min_altitude_m, fix.max_altitude_m),
        ),
    }
    out = {
        name: {
            "edges": edges,
            "counts": np.zeros(len(edges) - 1, dtype=np.int64),
            "n_finite": 0,
            "n_outside": 0,
        }
        for name, (_, edges, _) in specs.items()
    }
    for batch in pq.ParquetFile(cache_path).iter_batches(
        batch_size=262144, columns=["quantity", "value"]
    ):
        codes = batch.column(0).to_numpy()
        values = batch.column(1).to_numpy(zero_copy_only=False)
        for name, (code, edges, (lo, hi)) in specs.items():
            v = values[(codes == code) & np.isfinite(values)]
            out[name]["counts"] += np.histogram(v, bins=edges)[0]
            out[name]["n_finite"] += len(v)
            out[name]["n_outside"] += int(np.count_nonzero((v < lo) | (v > hi)))
    return out


def main() -> int:
    """Regenerate both figures from the full census when data and matplotlib exist."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' dependency group); keeping the figures.")
        return 0
    matplotlib.use("Agg")
    from soaring.reporting.style import paper_style

    paper_style()

    from soaring.acquisition.ffvl.config import (
        DELTA_CONFIG_PATH,
        PARA_CONFIG_PATH,
    )
    from soaring.analysis.census import (
        load_or_scan_tracks,
    )
    from soaring.analysis.config import load_preproc_config
    from soaring.analysis.figures.preproc import (
        make_flightlevel_diagnostics_figure,
        make_gap_diagnostics_figure,
        make_sampling_figure,
    )

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
        "the pre-processing diagnostic figures",
        allow_partial="--allow-partial" in sys.argv[1:],
        reasons=[
            unreachable_reason(DISCIPLINES[d], "fixes.parquet")
            for d in DISCIPLINES
            if d not in configs
        ],
    )
    if refusal:
        print(refusal)
        return 1

    scans = {}
    for disc, cfg_disc in configs.items():
        cache_path = cfg_disc.derived_dir / "track_scan.parquet"
        print(f"[{disc}] full census (cached at {cache_path})...")
        scans[disc] = load_or_scan_tracks(
            cfg_disc.igc_dir,
            cache_path,
            n_jobs=N_JOBS,
            force=FORCE_RESCAN or "--rescan" in sys.argv[1:],
        )
        s = scans[disc]
        print(
            f"[{disc}] {len(s)} readable; median duration "
            f"{s['duration_s'].median() / 60:.0f} min, median path "
            f"{s['path_km'].median():.0f} km."
        )

    cfg = load_preproc_config()
    OUT_DIAG.parent.mkdir(parents=True, exist_ok=True)
    make_flightlevel_diagnostics_figure(scans, cfg.flight, cfg.alt_channel).savefig(
        OUT_DIAG, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    make_gap_diagnostics_figure(scans, cfg.sampling).savefig(
        OUT_GAPS, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    make_sampling_figure(scans).savefig(
        OUT_DT, metadata=_PDF_METADATA, bbox_inches="tight"
    )

    # Reduce the long-form sample in bounded-memory batches, including on a warm run.
    # The historical all-array loader can exceed the RAM of an 8 GB laptop.
    histograms = {}
    for disc, cfg_disc in configs.items():
        cache_path = cfg_disc.derived_dir / "fixlevel_scan.parquet"
        if not cache_path.is_file() or FORCE_RESCAN or "--rescan" in sys.argv[1:]:
            _write_fixlevel_cache(cfg_disc.igc_dir, cache_path, cfg.fix.vz_window_s)
        histograms[disc] = _stream_fixlevel_histograms(cache_path, disc, cfg.fix)
    from soaring.analysis.figures.preproc import make_fixlevel_histogram_figure

    make_fixlevel_histogram_figure(histograms, cfg.fix).savefig(
        OUT_FIX, metadata=_PDF_METADATA, bbox_inches="tight"
    )

    counts = ", ".join(f"{d}={len(s)}" for d, s in scans.items())
    names = f"{OUT_DIAG.name}, {OUT_GAPS.name}, {OUT_DT.name} and {OUT_FIX.name}"
    print(f"Wrote {names} ({counts}).")
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=["--allow-partial", "--rescan"])

    raise SystemExit(main())
