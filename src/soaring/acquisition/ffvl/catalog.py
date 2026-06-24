"""Costruzione del catalogo CSV derivato (metadati + path locali).

Il catalogo e' un *derivato* rigenerabile, non una fonte di verita': si ottiene
riparsando gli XML archiviati e collegando ogni volo al file `.igc` presente su disco
(colonne ``local_path``, ``downloaded``, ``file_size``).

Produce due file:

* ``catalog.csv`` -- una riga per volo (tutte le stagioni archiviate);
* ``seasons_index.csv`` -- una riga per stagione, con i link e i conteggi.
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

# Colonne del catalogo, in ordine (metadati del volo + collegamento al file fisico).
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
    """Anni di stagione il cui XML risulta archiviato sull'HDD.

    Args:
        cfg: Configurazione.

    Returns:
        Lista ordinata di anni per cui esiste ``raw_xml/{year}.xml``.
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
    """Costruisce il catalogo dei voli e lo scrive in ``catalog.csv``.

    Args:
        cfg: Configurazione.
        years: Anni da includere; se ``None`` usa tutte le stagioni archiviate.

    Returns:
        Il catalogo come :class:`~pandas.DataFrame`.
    """
    use_years = years if years is not None else archived_years(cfg)
    rows: list[dict] = []
    for year in use_years:
        for rec in load_season_records(cfg, year):
            row = asdict(rec)
            row.pop(
                "has_igc", None
            )  # proprieta', non campo: non e' in asdict ma per sicurezza
            target = igc_path(cfg.igc_dir, rec.season_year, rec.date, rec.flight_id)
            exists = target.is_file()
            row["local_path"] = str(target) if exists else ""
            row["downloaded"] = exists
            row["file_size"] = target.stat().st_size if exists else 0
            rows.append(row)

    df = pd.DataFrame(rows, columns=CATALOG_COLUMNS)
    cfg.catalog_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cfg.catalog_path, index=False)
    logger.info("Catalogo scritto: %s (%d voli)", cfg.catalog_path, len(df))
    return df


def build_seasons_index(cfg: Config, catalog: pd.DataFrame) -> pd.DataFrame:
    """Costruisce il riepilogo per stagione e lo scrive in ``seasons_index.csv``.

    Args:
        cfg: Configurazione.
        catalog: Il catalogo gia' costruito (vedi :func:`build_catalog`).

    Returns:
        Il riepilogo per stagione come :class:`~pandas.DataFrame`.
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
        "Indice stagioni scritto: %s (%d stagioni)", cfg.seasons_index_path, len(df)
    )
    return df


def build(
    cfg: Config, years: list[int] | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rigenera catalogo e indice stagioni.

    Args:
        cfg: Configurazione.
        years: Anni da includere; se ``None`` usa tutte le stagioni archiviate.

    Returns:
        La coppia ``(catalogo, indice_stagioni)``.
    """
    catalog = build_catalog(cfg, years)
    index = build_seasons_index(cfg, catalog)
    return catalog, index
