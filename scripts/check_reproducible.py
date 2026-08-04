#!/usr/bin/env python3
r"""Check that the stored dataset is what the current code produces.

Every row of ``flights_meta`` carries a ``pipeline_version``, and that claim is worth
exactly what it can be checked against. A stored table can disagree with the code that
names it for reasons none of the other checks can see: the run was interrupted and
restarted from a different commit, a rule was edited while the archive was being
written, or the version was bumped without re-running. ``verify_dataset.py`` asks
whether the tables satisfy the invariants of Chapter 2; this script asks the different
and equally necessary question of whether they are the tables *this code* would write.

The method is the direct one. Draw a seeded sample of retained flights, find their raw
IGC files, run them through ``run_flight`` as it stands now, and compare the result
with the stored rows column by column. Anything but agreement is a finding: a different
row count, a flight now dropped, a boolean flag that moved, a coordinate that shifted by
more than the storage precision allows.

That last tolerance is the one judgement here. The tables store the trajectory as
``float32`` while the pipeline computes in ``float64``, so a coordinate of order
:math:`10^5` metres round-trips with an error of order :math:`10^{-2}` metres -- a part
in :math:`10^7`, orders below the GPS noise on it, and it appears on every flight rather
than on a few. The bound scales with the coordinate for that reason instead of being an
absolute number, so it stays a statement about *precision* and cannot quietly absorb a
real disagreement on a flight that happens to stay near its origin.

Run it after ``preprocess.py``, with the same data roots::

    SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... \\
    uv run python scripts/check_reproducible.py [--sample 250]

Exits non-zero if any flight disagrees.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from preprocess import DISCIPLINES, _process_one, _resolve

# The kinematic columns, compared numerically, and the flags, compared exactly. A flag
# is a decision the pipeline made, so it either agrees or the code has changed.
_NUMERIC = ["t", "E", "N", "z", "v_E", "v_N", "v_z", "a_E", "a_N", "a_z"]
_FLAGS = [
    "interpolated",
    "z_reconstructed",
    "edge",
    "hampel_flagged",
    "alt_invalidated",
]

# Storage precision: float32 carries about seven significant digits, so a coordinate of
# magnitude R round-trips to about R * 1e-7. Doubled, for the difference of two such.
_FLOAT32_RELATIVE = 2e-7


def _stored(derived: Path, wanted: set[str]):
    """The stored rows of the wanted flights, keyed by ``flight_id``."""
    import pandas as pd
    import pyarrow.parquet as pq

    out: dict[str, pd.DataFrame] = {}
    parquet = pq.ParquetFile(derived / "fixes.parquet")
    for group in range(parquet.metadata.num_row_groups):
        frame = parquet.read_row_group(group).to_pandas()
        hit = frame[frame["flight_id"].isin(wanted)]
        for flight_id, part in hit.groupby("flight_id", sort=False):
            key = str(flight_id)
            out[key] = pd.concat([out[key], part]) if key in out else part
    return out


def _disagreement(old, new) -> str | None:
    """Why these two tables of the same flight differ, or ``None`` if they do not."""
    if len(new) != len(old):
        return f"{len(new)} rows now, {len(old)} stored"
    for column in _FLAGS:
        if not np.array_equal(
            new[column].to_numpy(dtype=bool), old[column].to_numpy(dtype=bool)
        ):
            moved = int(
                (
                    new[column].to_numpy(dtype=bool) != old[column].to_numpy(dtype=bool)
                ).sum()
            )
            return f"{moved} rows differ in `{column}`"
    for column in _NUMERIC:
        a = old[column].to_numpy(dtype=float)
        b = new[column].to_numpy(dtype=float)
        scale = max(1.0, float(np.nanmax(np.abs(a))) if a.size else 1.0)
        worst = float(np.nanmax(np.abs(a - b))) if a.size else 0.0
        if worst > 10.0 * _FLOAT32_RELATIVE * scale:
            return f"`{column}` differs by {worst:.4g} (scale {scale:.4g})"
    return None


def check(discipline: str, sample: int, seed: int) -> list[str]:
    """Recompute a sample of one discipline's flights; returns the disagreements."""
    import pandas as pd

    acq = _resolve(discipline)
    if acq is None:
        print(f"[{discipline}] no processed dataset; skipped.")
        return []
    derived = acq.derived_dir
    meta = pd.read_parquet(derived / "flights_meta.parquet")
    kept = meta[meta["drop_reason"].isna()]
    if kept.empty:
        return [f"{discipline}: no retained flight to check"]

    rng = np.random.default_rng(seed)
    pick = rng.choice(len(kept), size=min(sample, len(kept)), replace=False)
    wanted = {str(f) for f in kept["flight_id"].to_numpy()[pick]}
    stored = _stored(derived, wanted)

    paths = {p.stem.split("_")[-1]: p for p in acq.igc_dir.rglob("*.igc")}
    source = DISCIPLINES[discipline][0]
    jobs = [
        (str(paths[flight_id]), source, discipline)
        for flight_id in sorted(stored)
        if flight_id in paths
    ]
    with ProcessPoolExecutor(max_workers=8) as pool:
        fresh = list(pool.map(_process_one, jobs, chunksize=4))

    problems, agreed = [], 0
    for (path, _, _), (_meta, fixes, _segments, _stints) in zip(
        jobs, fresh, strict=True
    ):
        flight_id = Path(path).stem.split("_")[-1]
        old = stored[flight_id].sort_values(["segment_id", "t"]).reset_index(drop=True)
        if fixes is None or not len(fixes):
            problems.append(f"{flight_id}: retained on disk, dropped by this code")
            continue
        new = fixes.sort_values(["segment_id", "t"]).reset_index(drop=True)
        why = _disagreement(old, new)
        if why:
            problems.append(f"{flight_id}: {why}")
        else:
            agreed += 1
    print(
        f"[{discipline}] {len(jobs)} flights recomputed: {agreed} identical, "
        f"{len(problems)} disagree"
    )
    return problems


def main(argv=None) -> int:
    """Check every reachable discipline; non-zero exit if any flight disagrees."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sample", type=int, default=250, help="flights per discipline"
    )
    parser.add_argument("--seed", type=int, default=19, help="sampling seed")
    args = parser.parse_args(argv)

    total = 0
    for discipline in DISCIPLINES:
        problems = check(discipline, args.sample, args.seed)
        for problem in problems[:10]:
            print(f"  DISAGREES  {problem}")
        if len(problems) > 10:
            print(f"  ... and {len(problems) - 10} more")
        total += len(problems)
    if total:
        print(
            f"\n{total} flights do not reproduce. The stored tables were not "
            "written by this code: re-run scripts/preprocess.py."
        )
        return 1
    print("\nthe stored dataset is what this code produces.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
