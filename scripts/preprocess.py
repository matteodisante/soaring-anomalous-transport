#!/usr/bin/env python3
r"""Run the pre-processing pipeline over an archive and write the three tables.

Stages (i)-(vii) of the thesis chapter "The dataset" (sec:preproc), chained by
``soaring.analysis.preproc.pipeline.run_flight``, applied to every ``.igc`` file of a
discipline. Three Parquet tables land in ``<data_root>/derived/``:

* ``fixes.parquet`` -- one row per grid point of every retained segment, keyed
  ``(source, flight_id, segment_id)``. Written incrementally, one row group per batch of
  flights, because the whole archive does not fit in memory: ~10^9 rows at the native
  cadence. Stored as ``float32``, which is ~10^-7 relative on a coordinate of tens of
  kilometres, far below the GPS noise on it.
* ``segments.parquet`` -- one row per segment the splitting produced, retained or not,
  with the reason for every drop.
* ``flights_meta.parquet`` -- one row per flight *attempted*, including the ones the
  pipeline dropped: the census of what was removed is as much a result as what was kept,
  and it is what the removal audit of sec:fixlevel reads.

The raw data lives on an external disk and may be absent (a fresh checkout, or CI); the
roots come from ``SOARING_PARA_DATA_ROOT`` / ``SOARING_DELTA_DATA_ROOT``. A discipline
whose ``igc/`` directory is missing is skipped. Run it with, e.g.::

    SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc \\
    uv run python scripts/preprocess.py --limit 20000

``--limit`` takes a seeded random sample rather than the first N files, so a partial run
is still an unbiased sample of the archive; ``--limit 0`` processes everything.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# discipline key (the config's, and the per-discipline speed bound's) -> source value
DISCIPLINES = {
    "paragliders": ("paraglider", "SOARING_PARA_DATA_ROOT", "PARA_CONFIG_PATH"),
    "hang gliders": ("hangglider", "SOARING_DELTA_DATA_ROOT", "DELTA_CONFIG_PATH"),
}

# Flights per row group. Large enough that the Parquet footer stays small, small enough
# that a batch of trajectories is a few hundred megabytes rather than a few hundred
# gigabytes.
BATCH_FLIGHTS = 400

# The stored precision of the trajectory columns (blueprint: `fixes` is float32).
_FIX_FLOAT32 = ["t", "E", "N", "z", "v_E", "v_N", "v_z", "a_E", "a_N", "a_z"]


def _process_one(job):
    """Worker: parse one IGC file and run the seven stages over it."""
    path, source, discipline = job
    from soaring.acquisition.ffvl.naming import parse_igc_filename
    from soaring.analysis.igc import parse_igc
    from soaring.analysis.preproc.pipeline import run_flight
    from soaring.analysis.config import load_preproc_config

    global _CFG
    try:
        cfg = _CFG
    except NameError:
        cfg = _CFG = load_preproc_config()

    try:
        _, flight_id = parse_igc_filename(Path(path).name)
    except ValueError:
        flight_id = Path(path).stem
    try:
        result = run_flight(
            parse_igc(path),
            cfg,
            source=source,
            flight_id=flight_id,
            discipline=discipline,
        )
    except Exception as exc:  # one bad file must not stop the archive
        from soaring.analysis.preproc.pipeline import DROP_ERROR, FlightRecord

        # A fixed reason, not the exception text. A free-form string is a drop reason
        # the pipeline census has never heard of, so such a flight is counted in
        # `attempted`, appears in no row of the cascade, and the table quietly stops
        # summing -- with the guard written to prevent exactly that unable to see it,
        # since it compares against the DROP_* constants. The message is kept, in its
        # own column, because it is the only thing that says which file to look at.
        meta = FlightRecord(source=source, flight_id=flight_id)
        meta.drop_stage, meta.drop_reason = "error", DROP_ERROR
        meta.error_detail = f"{type(exc).__name__}: {exc}"[:400]
        return asdict(meta), None, None, None
    return (
        asdict(result.meta),
        result.fixes,
        result.segments,
        result.suspect_intervals,
    )


def _resolve(discipline: str):
    """The discipline's acquisition config, or ``None`` if its data is not reachable."""
    from soaring.acquisition.ffvl import config as cfgmod

    _, env, attr = DISCIPLINES[discipline]
    try:
        cfg = cfgmod.load_config(str(getattr(cfgmod, attr)), data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None
    return cfg if cfg.igc_dir.is_dir() else None


def _write_batch(writer, table_path, frames, schema_ref):
    """Append a batch of per-fix rows as one Parquet row group."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    frame = pd.concat(frames, ignore_index=True)
    for column in _FIX_FLOAT32:
        frame[column] = frame[column].astype("float32")
    frame["segment_id"] = frame["segment_id"].astype("int16")
    table = pa.Table.from_pandas(frame, preserve_index=False)
    if writer is None:
        schema_ref["schema"] = table.schema
        writer = pq.ParquetWriter(table_path, table.schema, compression="zstd")
    writer.write_table(table.cast(schema_ref["schema"]))
    return writer


def run_discipline(discipline: str, limit: int, jobs: int, seed: int) -> int:
    """Process one discipline's archive; returns the number of flights kept."""
    import pandas as pd

    acq = _resolve(discipline)
    if acq is None:
        print(f"[{discipline}] no IGC data reachable; skipped.")
        return 0
    source = DISCIPLINES[discipline][0]

    paths = sorted(acq.igc_dir.rglob("*.igc"))
    if limit and len(paths) > limit:
        paths = random.Random(seed).sample(paths, limit)
        paths.sort()
    out_dir = acq.derived_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    fixes_path = out_dir / "fixes.parquet"
    print(f"[{discipline}] {len(paths)} tracks -> {out_dir} ({jobs} workers)")

    metas: list[dict] = []
    segments: list[pd.DataFrame] = []
    # Stage (iii) exists partly to produce these: slow-and-flat stints too short to
    # excise, which the psi(tau) fits are to be re-run with and without as a sensitivity
    # check (sec:trimming). The driver used to drop them on the floor, so the check the
    # thesis promises had no data behind it.
    suspects: list[pd.DataFrame] = []
    batch: list[pd.DataFrame] = []
    writer = None
    schema_ref: dict = {}
    kept = 0
    t0 = time.perf_counter()
    jobs_iter = ((str(p), source, discipline) for p in paths)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for i, (meta, fixes, segs, stints) in enumerate(
            pool.map(_process_one, jobs_iter, chunksize=8), start=1
        ):
            metas.append(meta)
            if segs is not None and len(segs):
                segments.append(segs)
            if stints is not None and len(stints):
                suspects.append(stints)
            if fixes is not None and len(fixes):
                kept += 1
                batch.append(fixes)
            if len(batch) >= BATCH_FLIGHTS:
                writer = _write_batch(writer, fixes_path, batch, schema_ref)
                batch = []
            if i % 5000 == 0:
                rate = i / (time.perf_counter() - t0)
                print(f"[{discipline}] {i}/{len(paths)} ({rate:.0f} flights/s)")
    if batch:
        writer = _write_batch(writer, fixes_path, batch, schema_ref)
    if writer is not None:
        writer.close()

    pd.DataFrame(metas).to_parquet(out_dir / "flights_meta.parquet", compression="zstd")
    if segments:
        pd.concat(segments, ignore_index=True).to_parquet(
            out_dir / "segments.parquet", compression="zstd"
        )
    # Written even when empty, so that its absence means "this run predates the table"
    # rather than "no flight had one" -- two things a consumer must be able to tell
    # apart.
    (
        pd.concat(suspects, ignore_index=True)
        if suspects
        else pd.DataFrame(columns=["source", "flight_id", "t_start", "t_end"])
    ).to_parquet(out_dir / "suspect_intervals.parquet", compression="zstd")
    elapsed = time.perf_counter() - t0
    print(
        f"[{discipline}] {kept}/{len(paths)} flights kept "
        f"({100 * kept / max(1, len(paths)):.1f} %) in {elapsed / 60:.1f} min"
    )
    return kept


def main(argv=None) -> int:
    """Parse the arguments and run each requested discipline."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--discipline",
        choices=[*DISCIPLINES, "all"],
        default="all",
        help="which archive to process (default: every one reachable)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="process a seeded random sample of this many flights (0 = all)",
    )
    parser.add_argument(
        "--jobs", type=int, default=min(8, os.cpu_count() or 1), help="worker processes"
    )
    parser.add_argument("--seed", type=int, default=20260803, help="sampling seed")
    args = parser.parse_args(argv)

    chosen = list(DISCIPLINES) if args.discipline == "all" else [args.discipline]
    for discipline in chosen:
        run_discipline(discipline, args.limit, args.jobs, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
