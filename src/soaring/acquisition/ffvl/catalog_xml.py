"""Retrieval and parsing of the FFVL CFD season XML export.

The export ``.../cfd/liste/{year}?xml=1`` returns, in a single response, a
``<flight .../>`` element for each flight, with all metadata as attributes -- including
the direct link to the `.igc` file. This module transforms it into a list of
:class:`FlightRecord`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .http import Fetcher
from .seasons import season_label, xml_url


@dataclass
class FlightRecord:
    """A CFD flight, with metadata useful for analysis and provenance tracking.

    Attributes:
        flight_id: Unique flight identifier (primary key).
        season: Season label, e.g. ``"1999-2000"``.
        season_year: Season start year, e.g. ``1999``.
        date: Flight date (ISO format, sometimes incomplete such as ``2000-00-00``).
        pilot: Pilot name.
        flight_type: Flight type (e.g. ``triangle``, ``FAI``, ``Dist 2 pts``).
        distance_km: Declared distance in km (``None`` if absent).
        points: CFD score (``None`` if absent).
        duration_s: Duration in seconds (``None`` if absent or meaningless zero).
        speed: Declared average speed (``None`` if absent).
        takeoff: Takeoff site.
        landing: Landing site.
        dept: French department number.
        club: Pilot's club.
        wing: Wing model.
        wing_class: Wing class/category (e.g. ``"C ou 2"``).
        flight_link: URL of the flight page.
        igc_link: Direct URL of the `.igc` file (empty string if no track exists).
        tracklog_id: FFVL internal track identifier.
        pilot_link: URL of the pilot's page.
    """

    flight_id: str
    season: str
    season_year: int
    date: str
    pilot: str
    flight_type: str
    distance_km: float | None
    points: float | None
    duration_s: int | None
    speed: float | None
    takeoff: str
    landing: str
    dept: str
    club: str
    wing: str
    wing_class: str
    flight_link: str
    igc_link: str
    tracklog_id: str
    pilot_link: str

    @property
    def has_igc(self) -> bool:
        """``True`` if the flight has a downloadable `.igc` track.

        Many flights (especially historical ones) expose an ``igc_tracklog_link`` that is
        only the base folder ``.../igcfiles/`` without a filename: a placeholder, not a
        downloadable file. :func:`_clean_igc_link` normalises it to an empty string, so
        here it is sufficient to check that the link is not empty.
        """
        return bool(self.igc_link)


def _clean_igc_link(value: str | None) -> str:
    """Normalises the track link: keeps it only if it is a real `.igc` file.

    Args:
        value: Raw value of the ``igc_tracklog_link`` attribute.

    Returns:
        The link if it ends with ``.igc`` (a real file), otherwise an empty string
        (placeholder: only the base folder, no downloadable track).
    """
    v = (value or "").strip()
    return v if v.lower().endswith(".igc") else ""


def _to_float(value: str | None) -> float | None:
    """Converts a string to float, returning ``None`` if empty or invalid."""
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    """Converts a string to int, returning ``None`` if empty or invalid."""
    if value is None or not value.strip():
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def season_xml_path(cfg: Config, year: int) -> Path:
    """Path of the season XML archived on the HDD.

    Args:
        cfg: Configuration.
        year: Season start year.

    Returns:
        The path ``data_root/raw_xml/{year}.xml``.
    """
    return cfg.raw_xml_dir / f"{year}.xml"


def parse_season_xml(xml_bytes: bytes, year: int) -> list[FlightRecord]:
    """Parses a season's XML into a list of :class:`FlightRecord`.

    Args:
        xml_bytes: Raw XML content.
        year: Season start year (used for the label and ``season_year``).

    Returns:
        The list of flights present in the XML (document order).
    """
    root = ET.fromstring(xml_bytes)
    label = season_label(year)
    records: list[FlightRecord] = []
    for el in root.iter("flight"):
        a = el.attrib
        records.append(
            FlightRecord(
                flight_id=a.get("id", "").strip(),
                season=label,
                season_year=year,
                date=a.get("date", "").strip(),
                pilot=a.get("pilot", "").strip(),
                flight_type=a.get("flight_type", "").strip(),
                distance_km=_to_float(a.get("distance")),
                points=_to_float(a.get("points")),
                duration_s=_to_int(a.get("duration")),
                speed=_to_float(a.get("speed")),
                takeoff=a.get("takeOff", "").strip(),
                landing=a.get("landing", "").strip(),
                dept=a.get("depNum", "").strip(),
                club=a.get("club", "").strip(),
                wing=a.get("aile", "").strip(),
                wing_class=a.get("aile_class", "").strip(),
                flight_link=a.get("flight_link", "").strip(),
                igc_link=_clean_igc_link(a.get("igc_tracklog_link")),
                tracklog_id=a.get("igc_tracklog", "").strip(),
                pilot_link=a.get("pilot_link", "").strip(),
            )
        )
    return records


def fetch_season_xml(year: int, cfg: Config, fetcher: Fetcher) -> bytes:
    """Downloads a season's XML from the FFVL site.

    Args:
        year: Season start year.
        cfg: Configuration (base URL and network parameters).
        fetcher: HTTP Fetcher to use.

    Returns:
        The raw XML content.
    """
    url = xml_url(year, cfg.base_url, cfg.list_path, cfg.xml_query)
    return fetcher.content(url)


def load_season_records(cfg: Config, year: int) -> list[FlightRecord]:
    """Loads the flights of a season from the archived XML on the HDD.

    Args:
        cfg: Configuration.
        year: Season start year.

    Returns:
        The list of flights.

    Raises:
        FileNotFoundError: If the season's XML has not been archived yet.
    """
    path = season_xml_path(cfg, year)
    if not path.is_file():
        raise FileNotFoundError(
            f"Season {year} XML not found: {path}. Run 'fetch-xml' first."
        )
    return parse_season_xml(path.read_bytes(), year)
