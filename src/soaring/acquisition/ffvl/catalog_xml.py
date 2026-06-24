"""Recupero e parsing dell'export XML di stagione della CFD FFVL.

L'export ``.../cfd/liste/{anno}?xml=1`` restituisce, in un'unica risposta, un elemento
``<flight .../>`` per ogni volo, con tutti i metadati come attributi -- compreso il
link diretto al file `.igc`. Questo modulo lo trasforma in una lista di
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
    """Un volo della CFD, con i metadati utili all'analisi e alla provenienza.

    Attributes:
        flight_id: Identificativo univoco del volo (chiave primaria).
        season: Etichetta stagione, es. ``"1999-2000"``.
        season_year: Anno di inizio stagione, es. ``1999``.
        date: Data del volo (ISO, talvolta incompleta come ``2000-00-00``).
        pilot: Nome del pilota.
        flight_type: Tipo di volo (es. ``triangle``, ``FAI``, ``Dist 2 pts``).
        distance_km: Distanza dichiarata in km (``None`` se assente).
        points: Punteggio CFD (``None`` se assente).
        duration_s: Durata in secondi (``None`` se assente o zero non significativo).
        speed: Velocita' media dichiarata (``None`` se assente).
        takeoff: Sito di decollo.
        landing: Sito di atterraggio.
        dept: Numero di dipartimento francese.
        club: Club del pilota.
        wing: Modello di ala.
        wing_class: Classe/categoria dell'ala (es. ``"C ou 2"``).
        flight_link: URL della pagina del volo.
        igc_link: URL diretto del file `.igc` (stringa vuota se la traccia non esiste).
        tracklog_id: Identificativo interno FFVL della traccia.
        pilot_link: URL della pagina del pilota.
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
        """``True`` se il volo ha un tracciato `.igc` scaricabile.

        Molti voli (specie storici) espongono un ``igc_tracklog_link`` che e' solo la
        cartella base ``.../igcfiles/`` senza nome file: un segnaposto, non un file
        scaricabile. :func:`_clean_igc_link` lo normalizza a stringa vuota, quindi qui
        basta controllare che il link non sia vuoto.
        """
        return bool(self.igc_link)


def _clean_igc_link(value: str | None) -> str:
    """Normalizza il link al tracciato: lo tiene solo se e' un vero file `.igc`.

    Args:
        value: Valore grezzo dell'attributo ``igc_tracklog_link``.

    Returns:
        Il link se termina con ``.igc`` (un file reale), altrimenti stringa vuota
        (segnaposto: solo la cartella base, nessun tracciato scaricabile).
    """
    v = (value or "").strip()
    return v if v.lower().endswith(".igc") else ""


def _to_float(value: str | None) -> float | None:
    """Converte una stringa in float, restituendo ``None`` se vuota o non valida."""
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    """Converte una stringa in int, restituendo ``None`` se vuota o non valida."""
    if value is None or not value.strip():
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def season_xml_path(cfg: Config, year: int) -> Path:
    """Path dell'XML di stagione archiviato sull'HDD.

    Args:
        cfg: Configurazione.
        year: Anno di inizio stagione.

    Returns:
        Il path ``data_root/raw_xml/{year}.xml``.
    """
    return cfg.raw_xml_dir / f"{year}.xml"


def parse_season_xml(xml_bytes: bytes, year: int) -> list[FlightRecord]:
    """Analizza l'XML di una stagione in una lista di :class:`FlightRecord`.

    Args:
        xml_bytes: Contenuto grezzo dell'XML.
        year: Anno di inizio stagione (usato per etichetta e ``season_year``).

    Returns:
        La lista dei voli presenti nell'XML (ordine del documento).
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
    """Scarica l'XML di una stagione dal sito FFVL.

    Args:
        year: Anno di inizio stagione.
        cfg: Configurazione (origine e parametri di rete).
        fetcher: Fetcher HTTP da usare.

    Returns:
        Il contenuto grezzo dell'XML.
    """
    url = xml_url(year, cfg.base_url, cfg.list_path, cfg.xml_query)
    return fetcher.content(url)


def load_season_records(cfg: Config, year: int) -> list[FlightRecord]:
    """Carica i voli di una stagione dall'XML archiviato sull'HDD.

    Args:
        cfg: Configurazione.
        year: Anno di inizio stagione.

    Returns:
        La lista dei voli.

    Raises:
        FileNotFoundError: Se l'XML della stagione non e' stato archiviato.
    """
    path = season_xml_path(cfg, year)
    if not path.is_file():
        raise FileNotFoundError(
            f"XML della stagione {year} non trovato: {path}. Esegui prima 'fetch-xml'."
        )
    return parse_season_xml(path.read_bytes(), year)
