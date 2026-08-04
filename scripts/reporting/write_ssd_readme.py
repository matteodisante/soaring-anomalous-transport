#!/usr/bin/env python3
r"""Write a README at the root of the data disk, describing what is on it.

The disk outlives any one working session and is the only copy of the data. Somebody
-- the author in a year, a successor, an examiner asking where a number came from --
will mount it without this repository at hand, and needs to be able to tell what each
directory is, which files are inputs and which are derived, and which of them can be
deleted and rebuilt. That is what this writes.

It is generated rather than typed, and generated *from the disk itself*: the file
sizes, the row counts, the column lists and the pipeline version are read off the
tables as they are, so the README cannot describe a layout the disk no longer has. Re-
run it after every processing run; it takes seconds, since it reads Parquet metadata
rather than data.

The one thing it does not do is duplicate the column-by-column documentation, which
lives in ``docs/guide/data-on-disk.md`` in the repository and is far longer than a
README should be. The README points at it, names the repository, and gives the
environment variables that connect the two.

Usage::

    SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... \\
    uv run python scripts/reporting/write_ssd_readme.py [--root /Volumes/SSD_DISANTE]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DISCIPLINES = {
    "paragliders": ("SOARING_PARA_DATA_ROOT", "PARA_CONFIG_PATH"),
    "hang gliders": ("SOARING_DELTA_DATA_ROOT", "DELTA_CONFIG_PATH"),
}

# What each derived table is, in one line. The full column documentation is in the repo.
_TABLES = {
    "fixes.parquet": "the trajectories: one row per grid point of every "
    "retained segment",
    "flights_meta.parquet": "one row per flight *attempted*, kept or dropped, with the "
    "reason and every per-stage counter",
    "segments.parquet": "one row per segment the splitting produced, retained or not",
    "suspect_intervals.parquet": "slow-and-flat stints too short to excise, for the "
    "psi(tau) sensitivity check",
    "track_scan.parquet": "the raw-archive census: one scalar row per parsed flight, "
    "cached so a threshold can be re-queried without re-reading the archive",
}


def _human(size: float) -> str:
    """A byte count a person can read."""
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _tree_size(path: Path) -> tuple[int, int]:
    """``(bytes, files)`` under a directory, or ``(0, 0)`` if it is not there."""
    if not path.is_dir():
        return 0, 0
    total = count = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
            count += 1
    return total, count


def _describe(discipline: str) -> list[str]:
    """The section of the README for one discipline's root."""
    from soaring.acquisition.ffvl import config as cfgmod

    env, attr = DISCIPLINES[discipline]
    try:
        cfg = cfgmod.load_config(str(getattr(cfgmod, attr)), data_root_env=env)
    except (FileNotFoundError, KeyError):
        return [
            f"## {discipline}\n\nNot reachable from this machine's configuration.\n"
        ]

    root = cfg.data_root
    lines = [f"## {discipline}", "", f"`{root}`  — environment variable `{env}`", ""]

    raw_bytes, raw_files = _tree_size(cfg.igc_dir)
    lines += [
        "| directory | what it is | size |",
        "|---|---|---|",
        f"| `raw/igc/<season>/` | **the input.** One `.igc` tracklog per flight, plain "
        f"text, named `<date>_<flight_id>.igc`. {raw_files:,} files. Irreplaceable: "
        f"everything else on the disk is rebuilt from these | {_human(raw_bytes)} |",
        f"| `catalog/` | the season XML the flights were listed from, as downloaded | "
        f"{_human(_tree_size(root / 'catalog')[0])} |",
        f"| `derived/` | **rebuildable.** The processed tables below, written by "
        f"`scripts/preprocess.py` | {_human(_tree_size(cfg.derived_dir)[0])} |",
        f"| `logs/` | acquisition logs | {_human(_tree_size(root / 'logs')[0])} |",
        "",
    ]

    derived = cfg.derived_dir
    if not derived.is_dir():
        lines += ["No `derived/` yet: run `scripts/preprocess.py`.", ""]
        return lines

    lines += [
        "### `derived/`",
        "",
        "| file | rows | size | what it holds |",
        "|---|---|---|---|",
    ]
    for name, what in _TABLES.items():
        path = derived / name
        if not path.is_file():
            continue
        rows = ""
        try:
            import pyarrow.parquet as pq

            rows = f"{pq.ParquetFile(path).metadata.num_rows:,}"
        except Exception:  # a table we cannot read is still worth listing
            rows = "?"
        lines.append(f"| `{name}` | {rows} | {_human(path.stat().st_size)} | {what} |")
    lines.append("")

    try:
        import pandas as pd

        meta = pd.read_parquet(
            derived / "flights_meta.parquet",
            columns=["drop_reason", "pipeline_version"],
        )
        kept = int(meta["drop_reason"].isna().sum())
        version = str(meta["pipeline_version"].iloc[0])
        lines += [
            f"Written by pipeline version **{version}**: {len(meta):,} flights "
            f"attempted, ",
            f"{kept:,} retained ({100 * kept / max(len(meta), 1):.1f} %). The "
            f"reason for ",
            "every drop is in `flights_meta.drop_reason`.",
            "",
        ]
    except Exception:
        pass
    return lines


def main(argv=None) -> int:
    """Write the README at the disk root."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/Volumes/SSD_DISANTE"),
        help="where to write the README (default: the disk root)",
    )
    args = parser.parse_args(argv)

    lines = [
        "# Soaring flight data",
        "",
        "The data behind *Anomalous Transport in Soaring Flights* (MSc, Physics of "
        "Complex Systems, University of Pisa). This file is **generated** "
        "from the disk ",
        "itself by `scripts/reporting/write_ssd_readme.py`; re-run it after a "
        "processing ",
        f"run rather than editing it. Last written {date.today().isoformat()}.",
        "",
        "## Reading this disk",
        "",
        "One root per discipline, identically laid out. Nothing here is "
        "referenced by an ",
        "absolute path: the code finds each root through an environment "
        "variable, so the ",
        "disk can be mounted anywhere.",
        "",
        "```bash",
        "export SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc",
        "export "
        "SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc",
        "```",
        "",
        "**What is irreplaceable and what is not.** `raw/igc/` and `catalog/` are the "
        "downloaded record and cannot be regenerated if the source withdraws a flight; "
        "back those up. Everything under `derived/` is a pure function of them "
        "and of the ",
        "code, and can be deleted and rebuilt with `scripts/preprocess.py` — which is "
        "checked, not assumed: `scripts/check_reproducible.py` re-runs a sample of "
        "flights through the current code and compares them with what is stored.",
        "",
        "**Column-by-column documentation** — every field of every table, with example "
        "rows — is `docs/guide/data-on-disk.md` in the repository, which also explains "
        "the conventions a reader has to know (the clock is zero at take-off, segments "
        "keep their parent's clock and origin, coordinates are a local ENU frame).",
        "",
    ]
    for discipline in DISCIPLINES:
        lines += _describe(discipline)

    lines += [
        "## Reading `fixes.parquet`",
        "",
        "It is tens of gigabytes and must be streamed. Do **not** iterate Parquet row "
        "groups directly: a row group is a unit of storage and cuts across flights, so "
        "grouping its rows by `flight_id` yields fragments at each boundary. Use the "
        "reader that reassembles them:",
        "",
        "```python",
        "from soaring.analysis.derived import stream_flights",
        "",
        "for flight in stream_flights(root / 'derived' / 'fixes.parquet',",
        "                             ['segment_id', 't', 'E', 'N']):",
        "    ...  # one whole flight per iteration",
        "```",
        "",
    ]

    args.root.mkdir(parents=True, exist_ok=True)
    out = args.root / "README.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(lines)} lines).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
