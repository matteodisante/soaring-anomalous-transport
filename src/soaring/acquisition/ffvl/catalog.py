"""Construction of the derived CSV catalog (metadata + local paths).

The catalog is a *regenerable derivative*, not a source of truth: it is obtained by
re-parsing the archived XMLs and linking each flight to the `.igc` file present on disk
(columns ``local_path``, ``downloaded``, ``file_size``).

Produces two files:

* ``catalog.csv`` -- one row per flight (all archived seasons);
* ``seasons_index.csv`` -- one row per season, with links and counts.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

import pandas as pd

from .catalog_xml import load_season_records
from .config import Config
from .naming import igc_path
from .seasons import list_url, season_label, xml_url

logger = logging.getLogger(__name__)

# Catalog columns, in order (flight metadata + link to the physical file).
CATALOG_COLUMNS = [
    "flight_id",
    "season",
    "season_year",
    "date",
    "pilot",
    "flight_type",
    "distance_km",
    "points",
    "duration_s",
    "speed",
    "takeoff",
    "landing",
    "dept",
    "club",
    "wing",
    "wing_class",
    "flight_link",
    "igc_link",
    "tracklog_id",
    "pilot_link",
    "local_path",
    "downloaded",
    "file_size",
]

SEASONS_INDEX_COLUMNS = [
    "season_year",
    "season",
    "list_url",
    "xml_url",
    "n_flights",
    "n_with_igc",
    "n_downloaded",
]


def archived_years(cfg: Config) -> list[int]:
    """Season years whose XML is archived on the HDD.

    Args:
        cfg: Configuration.

    Returns:
        Sorted list of years for which ``raw_xml/{year}.xml`` exists.
    """
    if not cfg.raw_xml_dir.is_dir():
        return []
    years: list[int] = []
    for path in cfg.raw_xml_dir.glob("*.xml"):
        try:
            years.append(int(path.stem))
        except ValueError:
            continue
    return sorted(years)


def build_catalog(cfg: Config, years: list[int] | None = None) -> pd.DataFrame:
    """Builds the flight catalog and writes it to ``catalog.csv``.

    Args:
        cfg: Configuration.
        years: Years to include; if ``None`` uses all archived seasons.

    Returns:
        The catalog as a :class:`~pandas.DataFrame`.
    """
    use_years = years if years is not None else archived_years(cfg)
    rows: list[dict] = []
    for year in use_years:
        for rec in load_season_records(cfg, year):
            row = asdict(rec)
            row.pop(
                "has_igc", None
            )  # property, not a field: not in asdict but removed for safety
            target = igc_path(cfg.igc_dir, rec.season_year, rec.date, rec.flight_id)
            exists = target.is_file()
            row["local_path"] = str(target) if exists else ""
            row["downloaded"] = exists
            row["file_size"] = target.stat().st_size if exists else 0
            rows.append(row)

    df = pd.DataFrame(rows, columns=CATALOG_COLUMNS)
    cfg.catalog_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cfg.catalog_path, index=False)
    logger.info("Catalog written: %s (%d flights)", cfg.catalog_path, len(df))
    return df


def build_seasons_index(cfg: Config, catalog: pd.DataFrame) -> pd.DataFrame:
    """Builds the per-season summary and writes it to ``seasons_index.csv``.

    Args:
        cfg: Configuration.
        catalog: The already-built catalog (see :func:`build_catalog`).

    Returns:
        The per-season summary as a :class:`~pandas.DataFrame`.
    """
    rows: list[dict] = []
    if not catalog.empty:
        for year, group in catalog.groupby("season_year", sort=True):
            year = int(year)
            rows.append(
                {
                    "season_year": year,
                    "season": season_label(year),
                    "list_url": list_url(year, cfg.base_url, cfg.list_path),
                    "xml_url": xml_url(
                        year, cfg.base_url, cfg.list_path, cfg.xml_query
                    ),
                    "n_flights": len(group),
                    "n_with_igc": int(
                        (group["igc_link"].astype(str).str.len() > 0).sum()
                    ),
                    "n_downloaded": int(group["downloaded"].sum()),
                }
            )

    df = pd.DataFrame(rows, columns=SEASONS_INDEX_COLUMNS)
    cfg.seasons_index_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cfg.seasons_index_path, index=False)
    logger.info(
        "Season index written: %s (%d seasons)", cfg.seasons_index_path, len(df)
    )
    return df


def build(
    cfg: Config, years: list[int] | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Regenerates the catalog and the season index.

    Args:
        cfg: Configuration.
        years: Years to include; if ``None`` uses all archived seasons.

    Returns:
        The pair ``(catalog, season_index)``.
    """
    catalog = build_catalog(cfg, years)
    index = build_seasons_index(cfg, catalog)
    return catalog, index
