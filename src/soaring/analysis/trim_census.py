"""Per-flight trimming census: how much time each end gives up, separately.

Thesis sec:trimming. ``flights_meta.parquet`` keeps ``trimmed_fraction``, the
*combined* share of the recorded span outside ``[t_on, t_off]``
(:mod:`soaring.analysis.preproc.trimming`), and
``ground_phase_start_s`` / ``ground_phase_end_s`` (``t_on``, ``t_off`` themselves), but
not the record's own first and last fix -- the two numbers needed to split that one
fraction into a takeoff duration and a landing duration. That split is not recoverable
from the cached table, so this module reruns stages (i)-(iii)
(:func:`~soaring.analysis.preproc.altchannel.adopt_alt_channel`,
:func:`~soaring.analysis.preproc.cleaning.clean_flight`,
:func:`~soaring.analysis.preproc.trimming.trim_flight`) exactly as the pipeline does,
and keeps the three numbers the combined fraction discards: the takeoff-trimmed and
landing-trimmed durations, and (for free, from the same pass) ``n_interior_excised``,
so the mid-flight-landing count quoted beside them is read off the identical run rather
than a second, possibly stale, source.

A full census (every ``.igc`` file) is cheap relative to the full pipeline: no
resampling, local-frame conversion or smoothing, so it costs roughly the fix-level
cleaning pass alone -- a few minutes for the paraglider archive across several worker
processes, not the tens of minutes :func:`soaring.analysis.census.scan_tracks` or the
full :mod:`scripts.preprocess` run need. The result is cached the same way,
at ``<data_root>/derived/trim_scan.parquet``.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import pandas as pd

_SCAN_COLUMNS = ("takeoff_trimmed_s", "landing_trimmed_s", "n_interior_excised")


def trim_split_one(path: Path, discipline: str) -> tuple | None:
    """Worker: run stages (i)-(iii) on one flight, or ``None`` if none applies.

    ``None`` covers exactly the two gates upstream of trimming that leave no
    ``[t_on, t_off]`` to split a duration around: the GNSS presence/range gate
    (``adopt_alt_channel``) and a flight with no sustained fast stretch at all
    (``trim_flight``'s ``DROP_NO_FLIGHT``). Both are already censused elsewhere
    (thesis, secs. altchannel and trimming); this module measures only the flights
    that reach a defined window.

    A top-level function (not a closure) so it can be pickled for
    :class:`~concurrent.futures.ProcessPoolExecutor`.
    """
    from .config import load_preproc_config
    from .igc import parse_igc
    from .preproc.altchannel import adopt_alt_channel
    from .preproc.cleaning import clean_flight
    from .preproc.trimming import trim_flight

    global _CFG
    try:
        cfg = _CFG
    except NameError:
        cfg = _CFG = load_preproc_config()

    fixes = parse_igc(path)
    if len(fixes) < 2:
        return None
    with_alt, channel = adopt_alt_channel(fixes, cfg.alt_channel)
    if channel.drop_reason is not None:
        return None
    cleaned = clean_flight(
        with_alt, cfg.fix, discipline=discipline, baro_witness=channel.baro_witness
    )
    t = cleaned.fixes["t"].to_numpy(dtype=float)
    if t.size < 2:
        return None
    trimmed = trim_flight(
        cleaned.fixes,
        cfg.trimming,
        suspect_min_span_s=cfg.fix.frozen_tau_s,
        max_drift_mps=cfg.fix.frozen_delta_z_m / cfg.fix.frozen_tau_s,
        baro_witness=channel.baro_witness,
    )
    if trimmed.drop_reason is not None:
        return None
    takeoff_trimmed_s = trimmed.t_on - float(t[0])
    landing_trimmed_s = float(t[-1]) - trimmed.t_off
    return (takeoff_trimmed_s, landing_trimmed_s, trimmed.n_interior_excised)


def scan_trim_split(
    paths: list[Path], discipline: str, *, n_jobs: int = 1
) -> pd.DataFrame:
    """Run :func:`trim_split_one` over a set of IGC files and tabulate the result.

    Args:
        paths: IGC file paths (a full census, or a sample).
        discipline: ``"paragliders"`` / ``"hang gliders"`` -- the fix-level speed bound
            to clean against.
        n_jobs: Worker processes; ``1`` runs serially in-process.

    Returns:
        A DataFrame with one row per flight that reached a defined trim window and
        columns :data:`_SCAN_COLUMNS`.
    """
    worker = partial(trim_split_one, discipline=discipline)
    if n_jobs > 1 and len(paths) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            results = list(ex.map(worker, paths, chunksize=200))
    else:
        results = [worker(p) for p in paths]
    rows = [r for r in results if r is not None]
    return pd.DataFrame(rows, columns=_SCAN_COLUMNS)


def load_or_scan_trim_split(
    igc_dir: Path,
    discipline: str,
    cache_path: Path,
    *,
    n_jobs: int = 1,
    force: bool = False,
) -> pd.DataFrame:
    """Load a cached trim-split census, or run :func:`scan_trim_split` and cache it.

    Args:
        igc_dir: The discipline's ``igc/`` root (scanned recursively for ``*.igc``).
        discipline: Passed through to :func:`scan_trim_split`.
        cache_path: Where to read/write the cached scan.
        n_jobs: Worker processes for a fresh scan.
        force: Rescan even if ``cache_path`` already exists.

    Returns:
        The per-flight trim-split table (:data:`_SCAN_COLUMNS`).
    """
    if cache_path.is_file() and not force:
        print(f"Using cached scan at {cache_path} (delete it to force a rescan).")
        return pd.read_parquet(cache_path)
    paths = sorted(igc_dir.rglob("*.igc"))
    print(
        f"No cache at {cache_path}; scanning {len(paths)} tracks, {n_jobs} workers..."
    )
    scan = scan_trim_split(paths, discipline, n_jobs=n_jobs)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    scan.to_parquet(cache_path)
    print(f"Cached scan to {cache_path} ({len(scan)} rows).")
    return scan
