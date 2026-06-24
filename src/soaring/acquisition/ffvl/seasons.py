"""Mapping anno<->stagione e costruzione dei link FFVL.

Una "stagione" e' identificata dall'anno di inizio: l'anno ``1999`` corrisponde alla
stagione ``1999-2000``. Il modulo e' puro (nessuna rete), quindi facile da testare.
"""

from __future__ import annotations

# Valori canonici del sito FFVL (sovrascrivibili dalla configurazione).
BASE_URL = "https://parapente.ffvl.fr"
LIST_PATH = "/cfd/liste/{year}"
XML_QUERY = "?xml=1"
FLIGHT_PATH = "/cfd/liste/vol/{flight_id}"


def season_label(year: int) -> str:
    """Etichetta leggibile della stagione che inizia in ``year``.

    Args:
        year: Anno di inizio stagione (es. ``1999``).

    Returns:
        L'etichetta ``"AAAA-AAAA"`` (es. ``"1999-2000"``), usata anche come nome
        della sottocartella dei tracciati.
    """
    return f"{year}-{year + 1}"


def list_url(year: int, base_url: str = BASE_URL, list_path: str = LIST_PATH) -> str:
    """URL della pagina-lista (umana) dei voli di una stagione.

    Args:
        year: Anno di inizio stagione.
        base_url: Origine del sito.
        list_path: Template del path con segnaposto ``{year}``.

    Returns:
        L'URL completo della lista (es. ``https://parapente.ffvl.fr/cfd/liste/1999``).
    """
    return base_url + list_path.format(year=year)


def xml_url(
    year: int,
    base_url: str = BASE_URL,
    list_path: str = LIST_PATH,
    xml_query: str = XML_QUERY,
) -> str:
    """URL dell'export XML completo di una stagione.

    E' la fonte canonica da cui scarichiamo: restituisce tutti i voli in una sola
    risposta.

    Args:
        year: Anno di inizio stagione.
        base_url: Origine del sito.
        list_path: Template del path con segnaposto ``{year}``.
        xml_query: Query string che attiva l'export XML.

    Returns:
        L'URL completo dell'export XML (es. ``.../cfd/liste/1999?xml=1``).
    """
    return list_url(year, base_url, list_path) + xml_query


def flight_page_url(flight_id: str | int, base_url: str = BASE_URL) -> str:
    """URL della pagina del singolo volo a partire dal suo ``flight_id``.

    E' la relazione deterministica che permette di risalire dal nome del file `.igc`
    (che contiene il ``flight_id``) alla pagina del volo, senza alcun dizionario.

    Args:
        flight_id: Identificativo numerico del volo.
        base_url: Origine del sito.

    Returns:
        L'URL della pagina del volo (es. ``.../cfd/liste/vol/20150770``).
    """
    return base_url + FLIGHT_PATH.format(flight_id=flight_id)


def parse_seasons_arg(value: str, default_start: int, default_end: int) -> list[int]:
    """Interpreta l'argomento ``--seasons`` della CLI in una lista di anni.

    Formati accettati:

    * ``"all"`` -> tutte le stagioni configurate ``[default_start, default_end]``;
    * un singolo anno, es. ``"2014"``;
    * un intervallo, es. ``"2010-2015"`` (estremi inclusi);
    * un elenco separato da virgole, es. ``"2010,2012,2015"``.

    Args:
        value: Stringa dell'argomento.
        default_start: Primo anno usato per ``"all"``.
        default_end: Ultimo anno usato per ``"all"``.

    Returns:
        Lista ordinata e deduplicata di anni di stagione.

    Raises:
        ValueError: Se la stringa non e' in un formato riconosciuto.
    """
    value = value.strip().lower()
    if value == "all":
        return list(range(default_start, default_end + 1))

    years: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", 1)
            start, end = int(start_str), int(end_str)
            if start > end:
                start, end = end, start
            years.update(range(start, end + 1))
        else:
            years.add(int(token))

    if not years:
        raise ValueError(f"Argomento --seasons non valido: {value!r}")
    return sorted(years)
