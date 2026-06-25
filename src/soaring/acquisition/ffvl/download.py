"""Resumable and parallel download of `.igc` files.

Robustness guarantees (the job is large: ~186k files, hours of execution time):

* **resumable** -- already present files are skipped, so the process can be freely
  interrupted and resumed;
* **atomic writes** -- written to ``.part`` then renamed: a file with its final name is
  always complete and valid (important on exfat, which has no journaling);
* **IGC validation** -- content is accepted only if it looks like a genuine IGC file;
* **polite parallelism** -- limited thread pool, one HTTP session per worker.
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

# Minimum byte threshold below which a file cannot be a plausible IGC.
MIN_IGC_BYTES = 100

# Per-thread Fetcher: each pool worker creates and reuses its own instance.
_thread_local = threading.local()


@dataclass
class FlightFailure:
    """A failed download, recorded for a potential targeted retry.

    Attributes:
        flight_id: Flight identifier.
        season: Season label.
        igc_link: URL of the `.igc` file that could not be downloaded.
        error: Concise error message.
    """

    flight_id: str
    season: str
    igc_link: str
    error: str


@dataclass
class SeasonResult:
    """Outcome of a season download.

    Attributes:
        year: Season start year.
        season: Season label.
        n_flights: Total flights in the season.
        n_with_igc: Flights with an available `.igc` track.
        n_downloaded: Files successfully downloaded in this run.
        n_skipped: Files already present and therefore skipped.
        n_failed: Failed downloads.
        n_no_tracklog: Flights without a track (not downloadable).
        failures: Detail of failures.
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
    """Basic check that ``content`` is a plausible IGC file.

    An IGC file starts with an ``A`` record (logger identifier) and contains ``B``
    records (GPS fixes). This is sufficient to reject HTML/error responses or truncated
    files.

    Args:
        content: Bytes of the downloaded file.

    Returns:
        ``True`` if the content looks like a valid IGC.
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
                return False  # the first non-empty line must be the A record
        if line[:1] == b"B":
            has_b_record = True
            break
    return has_a_header and has_b_record


def _atomic_write(path: Path, content: bytes) -> None:
    """Writes ``content`` to ``path`` atomically (tmp ``.part`` + rename).

    Args:
        path: Final destination path.
        content: Bytes to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open("wb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def _get_fetcher(cfg: Config) -> Fetcher:
    """Returns the :class:`Fetcher` for the current thread, creating one if needed."""
    fetcher = getattr(_thread_local, "fetcher", None)
    if fetcher is None:
        fetcher = Fetcher(cfg)
        _thread_local.fetcher = fetcher
    return fetcher


def _download_one(rec: FlightRecord, cfg: Config) -> tuple[str, FlightRecord, str]:
    """Downloads a single flight.

    Args:
        rec: The flight to download.
        cfg: Configuration.

    Returns:
        A tuple ``(status, rec, detail)`` where ``status`` is one of
        ``"downloaded"``, ``"skipped"``, or ``"failed"`` and ``detail`` is an error
        message (only for ``"failed"``).
    """
    target = igc_path(cfg.igc_dir, rec.season_year, rec.date, rec.flight_id)
    if target.exists():
        return "skipped", rec, ""
    try:
        content = _get_fetcher(cfg).content(rec.igc_link)
    except FetchError as err:
        return "failed", rec, str(err)
    if not is_valid_igc(content):
        return "failed", rec, "invalid content (does not look like an IGC)"
    _atomic_write(target, content)
    return "downloaded", rec, ""


def download_season(
    year: int,
    cfg: Config,
    *,
    limit: int | None = None,
    dry_run: bool = False,
) -> SeasonResult:
    """Downloads `.igc` tracks for a season (resumable).

    Requires the season XML to have already been archived (``fetch-xml`` command).

    Args:
        year: Season start year.
        cfg: Configuration.
        limit: If provided, downloads at most this many files (useful for testing).
        dry_run: If ``True`` does not download anything: only counts what would be done.

    Returns:
        The season outcome (see :class:`SeasonResult`).
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
        # Count how many would already be present vs to download, without network access.
        for rec in to_download:
            target = igc_path(cfg.igc_dir, rec.season_year, rec.date, rec.flight_id)
            if target.exists():
                result.n_skipped += 1
            else:
                result.n_downloaded += 1  # "to download" in dry-run mode
        logger.info(
            "[%s] dry-run: %d to download, %d already present, %d without track",
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
                    "[%s] FAIL flight %s: %s", rec.season, rec.flight_id, detail
                )

    logger.info(
        "[%s] downloaded %d, skipped %d, failed %d, without track %d (out of %d flights)",
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
    """Downloads multiple seasons in sequence.

    Args:
        years: Season start years to process.
        cfg: Configuration.
        limit: File limit per season (useful for testing).
        dry_run: If ``True`` does not download anything.

    Returns:
        The list of outcomes, one per season.
    """
    return [download_season(y, cfg, limit=limit, dry_run=dry_run) for y in years]
