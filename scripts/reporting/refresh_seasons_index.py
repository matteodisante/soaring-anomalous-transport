#!/usr/bin/env python3
"""Refresh the committed ``seasons_index.csv`` snapshots from the SSD.

The canonical per-season index lives on the SSD, next to the catalog, and is (re)written
by ``soaring-<para|delta> build-catalog``. The thesis, however, must build its dataset
statistics **offline** -- on a fresh checkout, a co-author's machine, or CI, with no SSD
mounted -- so a small versioned snapshot of each index is kept in the repo under
``data/<discipline>/seasons_index.csv`` and read by ``generate_stats.py``.

This script is the one explicit, scripted step that keeps that snapshot from silently
drifting: it copies each reachable SSD index into its repo location. It is best-effort:
a discipline whose SSD copy is not mounted is skipped and the script never fails, so the
pre-commit hook can call it unconditionally. On a machine with the SSD it auto-refreshes
the snapshot; elsewhere it is a no-op that leaves the committed copies untouched.

Run it directly after a catalog rebuild, or let the pre-commit hook run it::

    uv run python scripts/reporting/refresh_seasons_index.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def main() -> int:
    """Copy each reachable SSD ``seasons_index.csv`` into the repo; best-effort."""
    from soaring.acquisition.ffvl.config import (
        PARA_CONFIG_PATH,
        DELTA_CONFIG_PATH,
        load_config,
    )

    # (discipline, config file, env override, repo sub-directory)
    disciplines = [
        ("paragliders", PARA_CONFIG_PATH, "SOARING_PARA_DATA_ROOT", "paragliders"),
        (
            "hang gliders",
            DELTA_CONFIG_PATH,
            "SOARING_DELTA_DATA_ROOT",
            "hang_gliders",
        ),
    ]

    refreshed = 0
    for disc, cfg_path, env, folder in disciplines:
        try:
            cfg = load_config(str(cfg_path), data_root_env=env)
        except (FileNotFoundError, KeyError):
            continue
        src = cfg.seasons_index_path
        if not src.is_file():
            print(
                f"[{disc}] SSD index not reachable ({src}); committed copy left as-is."
            )
            continue
        dst = ROOT / "data" / folder / "seasons_index.csv"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"[{disc}] refreshed {dst.relative_to(ROOT)} from the SSD.")
        refreshed += 1

    if refreshed == 0:
        print("No SSD index reachable; the committed snapshots are unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
