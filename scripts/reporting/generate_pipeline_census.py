#!/usr/bin/env python3
r"""Census of what the pre-processing pipeline kept and what it removed, and why.

Reads the ``flights_meta.parquet`` that ``scripts/preprocess.py`` writes -- one row per
flight *attempted*, dropped ones included -- and emits
``thesis/generated/pipeline_census.tex``: the ``\StatPipe*`` macros the thesis quotes,
plus a per-discipline table of the drop reasons.

This is a different census from the ``\StatScan*`` family of
``generate_census_stats.py``. Those come from a scan of *parsed* tracks and answer "what
would this cut remove if it acted alone on the raw population"; these come from the
pipeline itself and answer "what did the cascade actually remove, at which stage, and
for what stated reason". Neither replaces the other: the marginal numbers justify a
threshold, the cascade numbers report the dataset.

Run it after ``scripts/preprocess.py``, with the same data roots::

    SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... \
    uv run python scripts/reporting/generate_pipeline_census.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "thesis" / "generated" / "pipeline_census.tex"

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

DISCIPLINES = {
    "paragliders": ("Para", "SOARING_PARA_DATA_ROOT", "PARA_CONFIG_PATH"),
    "hang gliders": ("Hang", "SOARING_DELTA_DATA_ROOT", "DELTA_CONFIG_PATH"),
}

# Drop reasons in pipeline order, with the label the table prints for each. A reason the
# run never produced is left out of the table rather than shown as a row of zeros.
#
# It must list *every* reason a flight can carry: the thesis quotes one macro per entry,
# so a reason missing here is a macro the thesis asks for and never gets, which is a
# build failure at best and a silently absent row of the cascade at worst. That is what
# happened to the two whole-flight sanity bounds, which reached the thesis before they
# reached this list; `_check_labels_cover_the_code` below now makes it impossible.
DROP_LABELS = [
    ("pipeline_raised", "the pipeline raised on this file"),
    ("fewer_than_two_fixes", "unreadable track"),
    ("no_sustained_flight", "never airborne"),
    ("cleaning_rebuilt_too_much", "integrity gate"),
    ("duration_below_minimum", "shorter than the duration cut"),
    ("duration_above_maximum", "longer than the duration cut"),
    ("path_below_minimum", "path below the floor"),
    ("altitude_range_below_minimum", "altitude activity below the floor"),
    ("mean_ground_speed_above_the_fix_level_bound", "mean ground speed implausible"),
    ("extent_out_of_reach_of_the_first_fix", "out of reach of its own first fix"),
    ("no_native_cadence", "no cadence to resample onto"),
    ("no_segment_survived", "no segment survived resampling"),
    ("shorter_than_smoothing_window", "no segment carries the smoothing window"),
]


def _check_labels_cover_the_code() -> None:
    """Fail loudly if a stage can produce a reason this table does not know about."""
    from soaring.analysis.preproc import (
        cleaning,
        flightfilter,
        pipeline,
        resample,
        smoothing,
        trimming,
    )

    known = {reason for reason, _ in DROP_LABELS}
    produced = {
        value
        for module in (cleaning, trimming, flightfilter, resample, smoothing, pipeline)
        for name, value in vars(module).items()
        if name.startswith("DROP_") and isinstance(value, str)
    }
    # The per-segment reasons live in the segments table, not in flights_meta.
    produced -= {
        resample.DROP_TOO_SHORT,
        resample.DROP_TOO_SPARSE,
        resample.DROP_INCOMPLETE,
    }
    missing = sorted(produced - known)
    if missing:
        raise SystemExit(
            "generate_pipeline_census.py: DROP_LABELS does not cover "
            + ", ".join(missing)
            + " -- add them, or the thesis quotes a macro that is never written."
        )


def _meta_path(discipline: str) -> Path | None:
    """The discipline's ``flights_meta.parquet``, or ``None`` if it is not reachable."""
    from soaring.acquisition.ffvl import config as cfgmod

    _, env, attr = DISCIPLINES[discipline]
    try:
        cfg = cfgmod.load_config(str(getattr(cfgmod, attr)), data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None
    path = cfg.derived_dir / "flights_meta.parquet"
    return path if path.is_file() else None


def _macros(tag: str, meta) -> dict[str, str]:
    r"""The ``\StatPipe*`` numbers for one discipline."""
    import numpy as np

    total = len(meta)
    kept = meta[meta["drop_reason"].isna()]
    out = {
        f"StatPipe{tag}Attempted": f"{total}",
        f"StatPipe{tag}Kept": f"{len(kept)}",
        f"StatPipe{tag}KeptPct": f"{100.0 * len(kept) / max(total, 1):.1f}",
        f"StatPipe{tag}BaroPct": f"{100.0 * (meta['alt_source'] == 'baro').mean():.1f}",
    }
    if not len(kept):
        return out

    for reason, _ in DROP_LABELS:
        name = "".join(part.title() for part in reason.split("_"))
        out[f"StatPipe{tag}Drop{name}"] = (
            f"{int((meta['drop_reason'] == reason).sum())}"
        )

    raw_fixes = kept["n_fix_raw"].sum()
    deleted = 1.0 - kept["n_fix_clean"].sum() / raw_fixes
    invalidated = (kept["n_alt_out_of_band"] + kept["n_alt_vz_spike"]).sum() / raw_fixes
    flagged_kept = kept["n_flagged_kept"].sum() / raw_fixes
    return out | {
        f"StatPipe{tag}MedianDurationMin": (
            f"{kept['duration_flight_s'].median() / 60:.0f}"
        ),
        f"StatPipe{tag}MedianPathKm": f"{kept['path_km'].median():.0f}",
        f"StatPipe{tag}MedianDtS": f"{np.nanmedian(kept['dt_native_s']):.0f}",
        f"StatPipe{tag}SplitPct": f"{100.0 * (kept['n_segments'] > 1).mean():.1f}",
        f"StatPipe{tag}MedianSegments": f"{kept['n_segments_kept'].median():.0f}",
        f"StatPipe{tag}InterpPct": f"{100.0 * kept['frac_interpolated'].mean():.2f}",
        f"StatPipe{tag}TrimmedPct": f"{100.0 * kept['trimmed_fraction'].median():.2f}",
        f"StatPipe{tag}RemovedPct": f"{100.0 * deleted:.2f}",
        f"StatPipe{tag}AltInvalidPct": f"{100.0 * invalidated:.3f}",
        f"StatPipe{tag}FlaggedKeptPct": f"{100.0 * flagged_kept:.2f}",
        f"StatPipe{tag}FrozenFlightsPct": (
            f"{100.0 * (kept['n_removed_frozen'] > 0).mean():.1f}"
        ),
        # How often the impossible-step postcondition had to add a boundary the scan
        # had not: the audit of a rule that would otherwise repair in silence.
        f"StatPipe{tag}BoundariedFlightsPct": (
            f"{100.0 * (kept['n_boundaried'] > 0).mean():.2f}"
            if "n_boundaried" in kept
            else "n/a"
        ),
        f"StatPipe{tag}BoundariedTotal": (
            f"{int(kept['n_boundaried'].sum())}" if "n_boundaried" in kept else "n/a"
        ),
    }


def _thousands(value: int) -> str:
    """A count with LaTeX-safe thousands separators (``{,}`` keeps the spacing)."""
    return f"{value:,}".replace(",", "{,}")


def _drop_table(metas: dict) -> list[str]:
    """A LaTeX table of the drop reasons, one column per discipline."""
    disciplines = list(metas)
    lines = [
        "\\newcommand{\\PipeCensusTable}{%",
        "\\begin{tabular}{|l|" + "r|" * len(disciplines) + "}",
        "\\hline",
        " & ".join(["\\textbf{Why the flight was dropped}", *disciplines]) + " \\\\",
        "\\hline",
    ]
    for reason, label in DROP_LABELS:
        counts = [int((meta["drop_reason"] == reason).sum()) for meta in metas.values()]
        if any(counts):
            lines.append(f"{label} & " + " & ".join(map(_thousands, counts)) + " \\\\")
    kept = [int(meta["drop_reason"].isna().sum()) for meta in metas.values()]
    total = [len(meta) for meta in metas.values()]
    retained = " & ".join(
        f"\\textbf{{{_thousands(k)}}} ({100 * k / max(t, 1):.1f}\\%)"
        for k, t in zip(kept, total, strict=True)
    )
    lines += [
        "\\hline",
        f"\\textbf{{retained}} & {retained} \\\\",
        "\\hline",
        "\\end{tabular}}",
    ]
    return lines


def main() -> int:
    """Read every reachable ``flights_meta`` and write the macros and the table."""
    import pandas as pd

    _check_labels_cover_the_code()
    metas, lines = {}, []
    for discipline, (tag, _, _) in DISCIPLINES.items():
        path = _meta_path(discipline)
        if path is None:
            print(f"[{discipline}] no processed dataset; skipped.")
            continue
        meta = pd.read_parquet(path)
        metas[discipline] = meta
        for name, value in _macros(tag, meta).items():
            lines.append(f"\\newcommand{{\\{name}}}{{{value}}}")
        kept = int(meta["drop_reason"].isna().sum())
        share = 100.0 * kept / max(len(meta), 1)
        print(f"[{discipline}] {kept}/{len(meta)} retained ({share:.1f} %)")

    if not metas:
        print("No processed dataset reachable; nothing to do.")
        return 0

    lines += _drop_table(metas)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "% Generated by scripts/reporting/generate_pipeline_census.py -- do not edit.\n"
        + "\n".join(lines)
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
