"""Download resumibile e parallelo dei file `.igc`.

Garanzie di robustezza (il job e' grande: ~186k file, ore di esecuzione):

* **resumibile** -- i file gia' presenti vengono saltati, quindi si puo' interrompere e
  riprendere liberamente;
* **scrittura atomica** -- si scrive su ``.part`` e poi si rinomina: un file con il
  nome definitivo e' sempre completo e valido (importante su exfat, senza journaling);
* **validazione IGC** -- il contenuto viene accettato solo se sembra un vero file IGC;
* **parallelismo cortese** -- pool di thread limitato, una sessione HTTP per worker.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from .catalog_xml import FlightRecord, load_season_records
from .config import Config
from .http import Fetcher, FetchError
from .naming import igc_path
from .seasons import season_label

logger = logging.getLogger(__name__)

# Soglia minima di byte sotto la quale un file non puo' essere un IGC plausibile.
MIN_IGC_BYTES = 100

# Fetcher per-thread: ogni worker del pool ne crea e riusa uno proprio.
_thread_local = threading.local()


@dataclass
class FlightFailure:
    """Un download fallito, registrato per un eventuale retry mirato.

    Attributes:
        flight_id: Identificativo del volo.
        season: Etichetta della stagione.
        igc_link: URL del file `.igc` che non si e' riusciti a scaricare.
        error: Messaggio d'errore sintetico.
    """

    flight_id: str
    season: str
    igc_link: str
    error: str


@dataclass
class SeasonResult:
    """Esito del download di una stagione.

    Attributes:
        year: Anno di inizio stagione.
        season: Etichetta della stagione.
        n_flights: Voli totali nella stagione.
        n_with_igc: Voli con traccia `.igc` disponibile.
        n_downloaded: File scaricati con successo in questa esecuzione.
        n_skipped: File gia' presenti e quindi saltati.
        n_failed: Download falliti.
        n_no_tracklog: Voli senza traccia (non scaricabili).
        failures: Dettaglio dei fallimenti.
    """

    year: int
    season: str
    n_flights: int = 0
    n_with_igc: int = 0
    n_downloaded: int = 0
    n_skipped: int = 0
    n_failed: int = 0
    n_no_tracklog: int = 0
    failures: list[FlightFailure] = field(default_factory=list)


def is_valid_igc(content: bytes) -> bool:
    """Verifica sommaria che ``content`` sia un file IGC plausibile.

    Un IGC inizia con un record ``A`` (identificativo del logger) e contiene record
    ``B`` (i fix GPS). Questo basta a scartare risposte HTML/errore o file troncati.

    Args:
        content: Byte del file scaricato.

    Returns:
        ``True`` se il contenuto sembra un IGC valido.
    """
    if len(content) < MIN_IGC_BYTES:
        return False
    has_a_header = False
    has_b_record = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not has_a_header:
            has_a_header = line[:1] == b"A"
            if not has_a_header:
                return False  # la prima riga utile deve essere il record A
        if line[:1] == b"B":
            has_b_record = True
            break
    return has_a_header and has_b_record


def _atomic_write(path: Path, content: bytes) -> None:
    """Scrive ``content`` in ``path`` in modo atomico (tmp ``.part`` + rename).

    Args:
        path: Path di destinazione finale.
        content: Byte da scrivere.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open("wb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def _get_fetcher(cfg: Config) -> Fetcher:
    """Restituisce il :class:`Fetcher` del thread corrente, creandolo se serve."""
    fetcher = getattr(_thread_local, "fetcher", None)
    if fetcher is None:
        fetcher = Fetcher(cfg)
        _thread_local.fetcher = fetcher
    return fetcher


def _download_one(rec: FlightRecord, cfg: Config) -> tuple[str, FlightRecord, str]:
    """Scarica un singolo volo.

    Args:
        rec: Il volo da scaricare.
        cfg: Configurazione.

    Returns:
        Una tupla ``(status, rec, detail)`` dove ``status`` e' uno tra
        ``"downloaded"``, ``"skipped"`` o ``"failed"`` e ``detail`` e' un messaggio
        d'errore (solo per ``"failed"``).
    """
    target = igc_path(cfg.igc_dir, rec.season_year, rec.date, rec.flight_id)
    if target.exists():
        return "skipped", rec, ""
    try:
        content = _get_fetcher(cfg).content(rec.igc_link)
    except FetchError as err:
        return "failed", rec, str(err)
    if not is_valid_igc(content):
        return "failed", rec, "contenuto non valido (non sembra un IGC)"
    _atomic_write(target, content)
    return "downloaded", rec, ""


def download_season(
    year: int,
    cfg: Config,
    *,
    limit: int | None = None,
    dry_run: bool = False,
) -> SeasonResult:
    """Scarica i tracciati `.igc` di una stagione (resumibile).

    Richiede che l'XML della stagione sia gia' stato archiviato (comando ``fetch-xml``).

    Args:
        year: Anno di inizio stagione.
        cfg: Configurazione.
        limit: Se indicato, scarica al massimo questo numero di file (utile per test).
        dry_run: Se ``True`` non scarica nulla: conta soltanto cosa farebbe.

    Returns:
        L'esito della stagione (vedi :class:`SeasonResult`).
    """
    records = load_season_records(cfg, year)
    result = SeasonResult(year=year, season=season_label(year), n_flights=len(records))

    to_download: list[FlightRecord] = []
    for rec in records:
        if rec.has_igc:
            result.n_with_igc += 1
            to_download.append(rec)
        else:
            result.n_no_tracklog += 1
    if limit is not None:
        to_download = to_download[:limit]

    if dry_run:
        # Conta quanti sarebbero gia' presenti vs da scaricare, senza rete.
        for rec in to_download:
            target = igc_path(cfg.igc_dir, rec.season_year, rec.date, rec.flight_id)
            if target.exists():
                result.n_skipped += 1
            else:
                result.n_downloaded += 1  # "da scaricare" in modalita' dry-run
        logger.info(
            "[%s] dry-run: %d da scaricare, %d gia' presenti, %d senza traccia",
            result.season,
            result.n_downloaded,
            result.n_skipped,
            result.n_no_tracklog,
        )
        return result

    workers = max(1, cfg.http.workers)
    desc = f"{result.season}"
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_download_one, rec, cfg) for rec in to_download]
        for fut in tqdm(
            as_completed(futures), total=len(futures), desc=desc, unit="igc"
        ):
            status, rec, detail = fut.result()
            if status == "downloaded":
                result.n_downloaded += 1
            elif status == "skipped":
                result.n_skipped += 1
            else:
                result.n_failed += 1
                result.failures.append(
                    FlightFailure(rec.flight_id, rec.season, rec.igc_link, detail)
                )
                logger.warning(
                    "[%s] FAIL volo %s: %s", rec.season, rec.flight_id, detail
                )

    logger.info(
        "[%s] scaricati %d, saltati %d, falliti %d, senza traccia %d (su %d voli)",
        result.season,
        result.n_downloaded,
        result.n_skipped,
        result.n_failed,
        result.n_no_tracklog,
        result.n_flights,
    )
    return result


def download_seasons(
    years: list[int],
    cfg: Config,
    *,
    limit: int | None = None,
    dry_run: bool = False,
) -> list[SeasonResult]:
    """Scarica piu' stagioni in sequenza.

    Args:
        years: Anni di inizio stagione da elaborare.
        cfg: Configurazione.
        limit: Limite di file per stagione (utile per test).
        dry_run: Se ``True`` non scarica nulla.

    Returns:
        La lista degli esiti, una per stagione.
    """
    return [download_season(y, cfg, limit=limit, dry_run=dry_run) for y in years]
