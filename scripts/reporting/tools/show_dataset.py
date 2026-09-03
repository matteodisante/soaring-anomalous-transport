#!/usr/bin/env python3
r"""Print what every file on the data disk actually looks like.

The data dictionary of ``docs/guide/data-on-disk.md`` is written from this script's
output, so the page shows the tables as they are rather than as they were once
described. Re-run it after a pipeline run and paste the blocks back, or read it directly
when you want to know what a column holds without opening a 43 GB Parquet.

For each artefact it prints the shape, the dtypes and the first rows -- the three things
you would ask a DataFrame yourself. Wide tables are shown in two halves rather than
truncated with an ellipsis, and ``flights_meta`` is transposed: forty-odd columns across
is unreadable, the same list read downward is one you can check off.

    SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... \
    uv run python scripts/reporting/tools/show_dataset.py --discipline "hang gliders"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES  # noqa: E402

def _root(discipline: str) -> Path | None:
    """The discipline's data root, or ``None`` if it is not reachable."""
    try:
        cfg = DISCIPLINES[discipline].config()
    except (FileNotFoundError, KeyError):
        return None
    return cfg.data_root if cfg.data_root.is_dir() else None


def _banner(title: str) -> None:
    """A heading that survives being pasted into a fenced code block."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# Columns that carry a person rather than a measurement. The catalog is a public
# listing, but a repository page is not the place to reproduce names, so the dictionary
# shows the shape of these fields and not their contents. (Some rows already arrive
# anonymised at source, as a bcrypt-looking token -- that quirk is worth seeing, so the
# redaction says which kind each value was.)
_PERSONAL = {"pilot", "pilot_link"}


def _redact(frame):
    """Replace personal fields by a description of what they hold."""
    import pandas as pd

    out = frame.copy()
    for column in _PERSONAL & set(out.columns):
        out[column] = [
            "<anonymised at source>"
            if isinstance(v, str) and v.startswith("$2")
            else ("<pilot name>" if column == "pilot" else "<pilot URL>")
            if pd.notna(v)
            else v
            for v in out[column]
        ]
    return out


def _frame(
    frame,
    name: str,
    rows: int = 4,
    split_at: int | None = None,
    total: int | None = None,
) -> None:
    """Shape, dtypes and head of one table, in halves if it is too wide to read."""
    frame = _redact(frame)
    n_rows = frame.shape[0] if total is None else total
    print(f"\n{name}   shape = {n_rows:,} rows x {frame.shape[1]} columns\n")
    print("dtypes:")
    print("  " + "\n  ".join(f"{c:<22}{t}" for c, t in frame.dtypes.items()))
    head = frame.head(rows)
    if split_at is None:
        print(f"\nhead({rows}):\n{head.to_string(index=False)}")
        return
    print(f"\nhead({rows}), columns 1-{split_at}:")
    print(head.iloc[:, :split_at].to_string(index=False))
    print(f"\nhead({rows}), columns {split_at + 1}-{frame.shape[1]}:")
    print(head.iloc[:, split_at:].to_string(index=False))


def show(discipline: str) -> None:
    """Print every artefact of one discipline's data root."""
    import pandas as pd
    import pyarrow.parquet as pq

    root = _root(discipline)
    if root is None:
        print(f"[{discipline}] data root not reachable; skipped.")
        return
    pd.set_option("display.width", 200, "display.max_columns", 60)
    print(f"\n\n{'#' * 78}\n#  {discipline}: {root}\n{'#' * 78}")

    _banner("raw/igc/<season>/<date>_<flight_id>.igc  -- one track, plain text")
    seasons = sorted(p for p in (root / "raw" / "igc").iterdir() if p.is_dir())
    if not seasons:
        print("no season directories under raw/igc.")
        return
    # A representative season rather than the newest, which is usually part-collected --
    # but indexed from whichever end the archive actually has, since a fresh or partial
    # download has fewer than three and `seasons[-3]` would simply raise on it.
    sample = seasons[-3] if len(seasons) >= 3 else seasons[-1]
    tracks = sorted(sample.glob("*.igc"))
    print(
        f"seasons: {len(seasons)} directories, {seasons[0].name} .. {seasons[-1].name}"
    )
    if tracks:
        print(f"{sample.name}/ holds {len(tracks)} files, e.g. {tracks[0].name}\n")
        lines = tracks[0].read_text(errors="replace").splitlines()
        for line in [ln for ln in lines if not ln.startswith("B")][:6]:
            print("  " + line)
        print("  ...")
        for line in [ln for ln in lines if ln.startswith("B")][:3]:
            print("  " + line)
        print("\nparsed by soaring.analysis.igc.parse_igc into:")
        from soaring.analysis.igc import parse_igc

        _frame(parse_igc(tracks[0]), "fixes (in memory, one track)", rows=4)

    for name, kwargs in (
        ("catalog/catalog.csv", {"split_at": 12}),
        ("catalog/seasons_index.csv", {}),
        ("logs/failures.csv", {"rows": 2}),
    ):
        path = root / name
        if path.is_file():
            _banner(f"{name}")
            _frame(pd.read_csv(path), name, **kwargs)

    for name, kwargs in (
        ("derived/track_scan.parquet", {"split_at": 7}),
        ("derived/fixes.parquet", {"split_at": 9}),
        ("derived/segments.parquet", {}),
    ):
        path = root / name
        if not path.is_file():
            continue
        _banner(f"{name}")
        parquet = pq.ParquetFile(path)
        print(
            f"{parquet.metadata.num_rows:,} rows in "
            f"{parquet.metadata.num_row_groups} row groups, "
            f"{path.stat().st_size / 1e6:,.1f} MB on disk, "
            f"{parquet.metadata.row_group(0).column(0).compression}"
        )
        _frame(
            parquet.read_row_group(0).to_pandas(),
            name,
            total=parquet.metadata.num_rows,
            **kwargs,
        )

    path = root / "derived" / "flights_meta.parquet"
    if path.is_file():
        meta = pd.read_parquet(path)
        _banner(
            "derived/flights_meta.parquet  -- transposed: "
            f"{len(meta.columns)} columns read down"
        )
        kept = meta[meta["drop_reason"].isna()]
        dropped = meta[meta["drop_reason"].notna()]
        print(
            f"{len(meta):,} rows x {len(meta.columns)} columns "
            f"({len(kept):,} retained, {len(dropped):,} dropped)\n"
        )
        sample = pd.concat([kept.head(1), dropped.head(1)]).T
        sample.columns = ["a retained flight", "a dropped one"]
        print(sample.to_string())


def main(argv=None) -> int:
    """Print one discipline, or every reachable one."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--discipline", choices=[*DISCIPLINES, "all"], default="all")
    args = parser.parse_args(argv)
    for discipline in DISCIPLINES if args.discipline == "all" else [args.discipline]:
        show(discipline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
