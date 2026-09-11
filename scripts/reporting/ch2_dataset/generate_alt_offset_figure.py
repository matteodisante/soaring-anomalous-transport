#!/usr/bin/env python3
r"""Draw within-site and pooled scatter of raw barometric/GNSS altitude offsets.

Where ``generate_alt_offset_stats.py`` reduces the per-flight offset scan to the
\\StatAltOff* medians and spreads ``sec:altchannel`` quotes, this reads the same cached
table (``<data_root>/derived/alt_offset_scan.parquet``, one row per flight, written by
that script or by a ``--rescan`` of it) and draws the comparison those numbers argue
for: ``thesis/generated/alt_offset_hist.pdf``, one histogram per discipline of the
per-site offset scatter against a dashed line per discipline at the across-flight
scatter of the eligible raw population. Neither statistic isolates weather or sensor
effects, and the figure is not a validation of mixed-channel altitude selection.

No new pass over the archive: it is a reduction of the cache
``generate_alt_offset_stats.py`` already wrote (or would write), so it costs a fraction
of a second and, run after that script, needs neither ``--rescan`` nor the SSD's raw
tracks -- only the cached per-flight table and the flight catalogue (for the take-off
site), which does need the SSD to exist at all.

Run it after ``generate_alt_offset_stats.py``::

    uv run python scripts/reporting/ch2_dataset/generate_alt_offset_figure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_FIG = ROOT / "thesis" / "generated" / "alt_offset_hist.pdf"

#: Minimum flights per site for displaying its descriptive offset scatter;
#: matches ``SAME_DAY_MIN_FLIGHTS`` in generate_alt_offset_stats.py, kept independent
#: here so this script stays a plain reduction of the cache, not a second copy of that
#: one's config.
SAME_DAY_MIN_FLIGHTS = 3

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES  # noqa: E402

_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def _attach_site(table, discipline):
    """Merge in the take-off site, the only catalogue column this figure needs."""
    import pandas as pd

    catalog_path = discipline.catalog_path()
    if catalog_path is None or not catalog_path.is_file():
        table["site"] = pd.NA
        return table
    catalog = pd.read_csv(
        catalog_path,
        usecols=["flight_id", "takeoff"],
        dtype={"flight_id": str},
        low_memory=False,
    ).rename(columns={"takeoff": "site"})
    return table.merge(catalog, on="flight_id", how="left")


def main() -> int:
    try:
        import matplotlib
        import pandas as pd
    except ImportError:
        print(
            "matplotlib/pandas missing ('analysis' group); keeping the committed figure."
        )
        return 0
    matplotlib.use("Agg")
    from soaring.reporting.style import paper_style

    paper_style()

    from soaring.analysis.alt_offset import group_scatter, independent, sigma_mad
    from soaring.analysis.figures.alt_offset import make_alt_offset_figure

    site_sigma: dict[str, "pd.Series"] = {}
    mix_sigma: dict[str, float] = {}
    for discipline in DISCIPLINES.values():
        try:
            cfg = discipline.config()
        except (FileNotFoundError, KeyError):
            print(f"alt offset figure: no config for {discipline.name}; skipping.")
            continue
        cache = cfg.derived_dir / "alt_offset_scan.parquet"
        if not cache.is_file():
            print(
                f"alt offset figure: {cache} not found; run generate_alt_offset_stats.py first."
            )
            continue
        table = pd.read_parquet(cache)
        flights = table[independent(table)]
        flights = _attach_site(flights, discipline)
        per_site = group_scatter(flights, ["site"], min_flights=SAME_DAY_MIN_FLIGHTS)
        if per_site.empty:
            print(f"alt offset figure: no site groups for {discipline.name}; skipping.")
            continue
        site_sigma[discipline.name] = per_site["sigma"].to_numpy()
        mix_sigma[discipline.name] = sigma_mad(flights["med_offset"])
        print(
            f"[{discipline.name}] {len(flights)} paired-altitude records, "
            f"{len(per_site)} site groups"
        )

    if not site_sigma:
        print("no cached offset table reachable; alt_offset_hist.pdf not written")
        return 0

    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    make_alt_offset_figure(site_sigma, mix_sigma).savefig(
        OUT_FIG, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    print(f"Wrote {OUT_FIG.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
