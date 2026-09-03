#!/usr/bin/env python3
r"""The dataset statistics of Sec.~\ref{sec:prelim}: what was discarded, and what survived.

Three questions the existing census answers only partly.

**Which cut does the work.** ``tab:pipecensus`` lists how many flights each criterion
removed, which leaves the reader to compute the thing that matters -- how much of what was
*still standing* each criterion took. The cascade table here carries the running remainder,
so the answer is legible rather than derivable, and on this archive it is not the obvious
one: the resampling sparsity rule removes an order of magnitude more flights than any
threshold the text argues for.

**Whether the pipeline discards uniformly in time.** Logger technology changed over the two
decades the archive spans, so a cascade resolved by season is a real check and not a
formality: a cut that eats one era is a cut that has silently reshaped the ensemble.

**What survived.** Per season and per stratum, the statistics every later chapter refers
to when it says "within a stratum".

Writes ``thesis/generated/dataset_stats.tex``. Numbers already generated elsewhere
(``\StatPipe*``, ``\StatPrelim*``) are not recomputed here: two generators disagreeing
about one quantity is the failure the macro contract exists to prevent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)

OUT_TEX = ROOT / "thesis" / "generated" / "dataset_stats.tex"
OUT_FIG = ROOT / "thesis" / "generated" / "dataset_seasons.pdf"

# The criteria in the order the pipeline applies them. The order is the point of the
# table: a flight counted against one criterion was still standing when that criterion
# tested it, so the counts are conditional and do not add up to what each cut would
# remove on its own.
CASCADE = [
    ("fewer_than_two_fixes", "unreadable track", "parse"),
    ("no_sustained_flight", "never airborne", "trimming"),
    ("cleaning_rebuilt_too_much", "integrity gate", "cleaning"),
    ("duration_below_minimum", "shorter than the duration cut", "flight filter"),
    ("duration_above_maximum", "longer than the duration cut", "flight filter"),
    ("path_below_minimum", "path below the floor", "flight filter"),
    ("altitude_range_below_minimum", "altitude activity below the floor", "flight filter"),
    (
        "mean_ground_speed_above_the_fix_level_bound",
        "mean ground speed over the bound",
        "flight filter",
    ),
    ("extent_out_of_reach_of_the_first_fix", "out of reach of its own first fix", "flight filter"),
    ("no_native_cadence", "no native cadence", "resampling"),
    ("no_segment_survived", "no segment survived resampling", "resampling"),
    ("shorter_than_smoothing_window", "no segment carries the smoothing window", "smoothing"),
]

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def _tex_int(value: int | float) -> str:
    """A thousands-separated integer that siunitx will not re-parse."""
    return f"{int(value):,}".replace(",", "{,}")


def load(discipline: str):
    """The flight table joined to the catalogue, or ``None`` if unreachable."""
    glider = DISCIPLINES[discipline]
    derived = glider.derived_dir("flights_meta.parquet")
    if derived is None:
        return None

    meta = pd.read_parquet(derived / "flights_meta.parquet")
    raw_catalog = glider.catalog_path()
    catalog_path = Path(raw_catalog) if raw_catalog else None
    if catalog_path is not None and catalog_path.is_file():
        catalog = pd.read_csv(catalog_path, low_memory=False)
        catalog["flight_id"] = catalog["flight_id"].astype(str)
        keep = [c for c in ("flight_id", "season", "season_year", "wing_class") if c in catalog]
        meta = meta.merge(catalog[keep], on="flight_id", how="left")
    return meta


def cascade(meta: pd.DataFrame) -> pd.DataFrame:
    """One row per criterion, in pipeline order, with the running remainder.

    ``standing`` is how many flights had survived every earlier criterion when this one
    ran, and ``share`` is the removal as a fraction of those -- not of the archive. The
    distinction is the reason the table exists: a cut late in the cascade tests a
    population the earlier cuts have already thinned, so a percentage of the archive
    understates it.
    """
    rows = []
    standing = len(meta)
    for reason, label, stage in CASCADE:
        removed = int((meta["drop_reason"] == reason).sum())
        if removed == 0:
            continue
        rows.append(
            {
                "stage": stage,
                "reason": reason,
                "label": label,
                "standing": standing,
                "removed": removed,
                "share_of_standing": 100.0 * removed / standing,
                "remaining": standing - removed,
            }
        )
        standing -= removed
    return pd.DataFrame(rows)


def per_season(meta: pd.DataFrame) -> pd.DataFrame:
    """Attempted, retained and the survivors' basic statistics, one row per season."""
    if "season" not in meta:
        return pd.DataFrame()
    kept = meta["drop_reason"].isna()
    grouped = meta.assign(kept=kept).groupby("season", dropna=True)
    out = grouped.agg(
        attempted=("flight_id", "size"),
        retained=("kept", "sum"),
    )
    survivors = meta[kept].groupby("season", dropna=True)
    out["retention_pct"] = 100.0 * out["retained"] / out["attempted"]
    out["median_duration_h"] = survivors["duration_flight_s"].median() / 3600.0
    out["median_path_km"] = survivors["path_km"].median()
    out["median_dt_s"] = survivors["dt_native_s"].median()
    out["one_hertz_pct"] = 100.0 * survivors["dt_native_s"].apply(
        lambda s: s == 1
    ).groupby(level=0).mean() if False else 100.0 * survivors["dt_native_s"].agg(
        lambda s: float((s == 1).mean())
    )
    out["split_pct"] = 100.0 * survivors["n_segments_kept"].agg(
        lambda s: float((s > 1).mean())
    )
    return out.reset_index()


def cross_tab(meta: pd.DataFrame, column: str, top: int = 6) -> pd.DataFrame:
    """Discard reason against another variable, as a share of what that group attempted."""
    if column not in meta:
        return pd.DataFrame()
    frame = meta.dropna(subset=[column]).copy()
    if column == "dt_native_s":
        frame = frame[frame[column].isin(frame[column].value_counts().head(top).index)]
    reasons = [r for r, _, _ in CASCADE if (frame["drop_reason"] == r).any()]
    table = pd.crosstab(frame[column], frame["drop_reason"])
    for r in reasons:
        if r not in table:
            table[r] = 0
    table = table[reasons]
    attempted = frame.groupby(column).size()
    return 100.0 * table.div(attempted, axis=0)


def draw_seasons(seasons: dict[str, pd.DataFrame]):
    """Retention and the survivors' character over the archive's two decades."""
    import matplotlib.pyplot as plt

    fig, (top, mid, bottom) = plt.subplots(3, 1, figsize=(9.6, 7.4), sharex=True)

    # One shared axis for both disciplines. Their season lists differ -- the paraglider
    # ladder opens three years earlier -- so each frame is reindexed onto the union
    # before it is drawn. Indexing each by its own position would slide one discipline's
    # bars along the other's labels.
    labels = sorted({s for f in seasons.values() if not f.empty for s in f.season.astype(str)})
    position = {s: i for i, s in enumerate(labels)}

    for discipline, frame in seasons.items():
        if frame.empty:
            continue
        colour = DISCIPLINES[discipline].color
        offset = 0.2 if discipline.startswith("hang") else -0.2
        x = np.array([position[s] for s in frame.season.astype(str)], dtype=float)
        top.bar(x + offset, frame.attempted, width=0.4, color=colour, alpha=0.35,
                label=f"{discipline}, attempted")
        top.bar(x + offset, frame.retained, width=0.4, color=colour,
                label=f"{discipline}, retained")
        # A season of a handful of flights carries a retention rate that is noise; the
        # open markers say which points are not to be read as a trend.
        big = frame.attempted >= 1000
        for axis, values in ((mid, frame.retention_pct), (bottom, frame.median_duration_h)):
            axis.plot(x, values, "-", color=colour, lw=1, label=discipline)
            axis.plot(x[big], values[big], "o", color=colour, ms=3.5)
            axis.plot(x[~big], values[~big], "o", color=colour, ms=3.5,
                      markerfacecolor="white")

    top.set_yscale("log")
    top.set_ylabel("flights")
    top.set_title("(a) attempted and retained, per season", fontsize=10, loc="left")
    top.legend(frameon=False, fontsize=7, ncol=2)
    mid.set_ylabel("retention (%)")
    mid.set_title("(b) retention rate; open markers are seasons under 1000 flights",
                  fontsize=10, loc="left")
    mid.set_ylim(0, 100)
    bottom.set_ylabel("median duration (h)")
    bottom.set_title("(c) median airborne duration of the survivors", fontsize=10, loc="left")
    bottom.set_xticks(np.arange(len(labels)))
    bottom.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)
    for ax in (mid, bottom):
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def macros(discipline: str, meta: pd.DataFrame) -> dict[str, str]:
    tag = DISCIPLINES[discipline].tag
    out: dict[str, str] = {}

    def put(name, value):
        out[f"StatData{tag}{name}"] = value

    casc = cascade(meta)
    kept = meta[meta["drop_reason"].isna()]

    # The cascade as a ready-made tabular body, so the thesis cannot re-order it.
    rows = "\n".join(
        f"{r.label} & {_tex_int(r.standing)} & {_tex_int(r.removed)} & "
        f"{r.share_of_standing:.2f} & {_tex_int(r.remaining)} \\\\"
        for r in casc.itertuples()
    )
    out[f"DataCascade{tag}Rows"] = "%\n" + rows

    by_share = casc.sort_values("share_of_standing", ascending=False)
    worst = by_share.iloc[0]
    put("WorstCutLabel", str(worst.label))
    put("WorstCutPct", f"{worst.share_of_standing:.1f}")
    put("WorstCutRemoved", _tex_int(worst.removed))
    if len(by_share) > 1:
        second = by_share.iloc[1]
        put("SecondCutLabel", str(second.label))
        put("SecondCutPct", f"{second.share_of_standing:.1f}")
        put("SecondCutRemoved", _tex_int(second.removed))
        put("WorstToSecondRatio", f"{worst.share_of_standing / second.share_of_standing:.1f}")
    put("Criteria", str(len(casc)))
    put("Attempted", _tex_int(len(meta)))
    put("Retained", _tex_int(len(kept)))
    put("RetainedPct", f"{100.0 * len(kept) / len(meta):.1f}")

    seasons = per_season(meta)
    if not seasons.empty:
        put("Seasons", str(len(seasons)))
        put("SeasonFirst", str(seasons.season.iloc[0]))
        put("SeasonLast", str(seasons.season.iloc[-1]))
        put("RetentionMinPct", f"{seasons.retention_pct.min():.1f}")
        put("RetentionMaxPct", f"{seasons.retention_pct.max():.1f}")
        put("RetentionSpreadPct", f"{seasons.retention_pct.max() - seasons.retention_pct.min():.1f}")
        big = seasons[seasons.attempted >= 1000]
        if not big.empty:
            put("RetentionMinBigPct", f"{big.retention_pct.min():.1f}")
            put("RetentionMaxBigPct", f"{big.retention_pct.max():.1f}")
            put("SeasonsBig", str(len(big)))

    # The cadence cross-tabulation: the sparsity rule is known to fall unevenly.
    by_cadence = cross_tab(meta, "dt_native_s")
    if not by_cadence.empty and "no_segment_survived" in by_cadence:
        column = by_cadence["no_segment_survived"]
        put("SparsityByCadenceMinPct", f"{column.min():.1f}")
        put("SparsityByCadenceMaxPct", f"{column.max():.1f}")
        put("SparsityWorstCadenceS", f"{column.idxmax():.0f}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")

    values: dict[str, str] = {}
    seasons: dict[str, pd.DataFrame] = {}
    missing = []
    for discipline in DISCIPLINES:
        meta = load(discipline)
        if meta is None:
            missing.append(discipline)
            continue
        values.update(macros(discipline, meta))
        seasons[discipline] = per_season(meta)
    if not values:
        print("no dataset reachable; dataset_stats.tex not written")
        return 1
    refusal = partial_write_refusal(
        missing, OUT_TEX.name, allow_partial=args.allow_partial,
        reasons=[
            unreachable_reason(DISCIPLINES[d], "flights_meta.parquet")
            for d in missing
        ],
    )
    if refusal:
        print(refusal)
        return 1

    if seasons:
        draw_seasons(seasons).savefig(OUT_FIG, metadata=_PDF_METADATA)

    write_macros(
        OUT_TEX, values, generator="scripts/reporting/ch2_dataset/generate_dataset_stats.py"
    )
    print(f"wrote {OUT_TEX.name}, {OUT_FIG.name} ({len(values)} macros)")
    for k, v in values.items():
        if not k.startswith("DataCascade"):
            print(f"  {k:40s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
