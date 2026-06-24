"""Naming "funzionale" dei file `.igc` e percorsi su disco.

Schema del nome: ``{date}_{flight_id}.igc`` (es. ``2000-00-00_20150770.igc``).

Il nome e' auto-descrittivo: il ``flight_id`` e' univoco e apre sempre la pagina del
volo (vedi :func:`~.seasons.flight_page_url`); quindi dato un file `.igc` si risale al
volo *senza* alcun dizionario.
"""

from __future__ import annotations

from pathlib import Path

from .seasons import season_label

_SAFE_DATE_CHARS = set("0123456789-")


def sanitize_date(date: str) -> str:
    """Rende una data sicura per un nome di file.

    Tiene cifre e trattini; sostituisce ogni altro carattere con ``-``. Le date FFVL
    sono gia' in forma ISO (``AAAA-MM-GG``), a volte incomplete (``2000-00-00``):
    vanno bene cosi'.

    Args:
        date: La stringa di data grezza dall'XML.

    Returns:
        Una data ripulita; ``"0000-00-00"`` se l'input e' vuoto.
    """
    date = (date or "").strip()
    if not date:
        return "0000-00-00"
    return "".join(c if c in _SAFE_DATE_CHARS else "-" for c in date)


def igc_filename(date: str, flight_id: str | int) -> str:
    """Costruisce il nome funzionale del file `.igc`.

    Args:
        date: Data del volo (idealmente ISO ``AAAA-MM-GG``).
        flight_id: Identificativo univoco del volo.

    Returns:
        Il nome del file, es. ``"2000-00-00_20150770.igc"``.
    """
    return f"{sanitize_date(date)}_{flight_id}.igc"


def parse_igc_filename(name: str) -> tuple[str, str]:
    """Operazione inversa di :func:`igc_filename`: estrae data e ``flight_id``.

    Args:
        name: Nome (o path) del file `.igc`.

    Returns:
        La coppia ``(date, flight_id)``.

    Raises:
        ValueError: Se il nome non segue lo schema ``{date}_{flight_id}.igc``.
    """
    stem = Path(name).name
    if not stem.endswith(".igc"):
        raise ValueError(f"Non e' un file .igc: {name!r}")
    stem = stem[: -len(".igc")]
    if "_" not in stem:
        raise ValueError(f"Nome file non conforme allo schema: {name!r}")
    date, flight_id = stem.rsplit("_", 1)
    return date, flight_id


def igc_path(igc_root: Path, year: int, date: str, flight_id: str | int) -> Path:
    """Percorso completo del file `.igc` di un volo.

    I file sono organizzati in ``{igc_root}/{stagione}/{nome}``, una sottocartella
    per stagione.

    Args:
        igc_root: Cartella radice dei tracciati (``data_root/igc``).
        year: Anno di inizio stagione.
        date: Data del volo.
        flight_id: Identificativo univoco del volo.

    Returns:
        Il path del file `.igc`.
    """
    return igc_root / season_label(year) / igc_filename(date, flight_id)
