"""Integrity check of the `.igc` files already downloaded on disk.

The download step already validates content and writes atomically, so finalised files
should be sound. This module re-scans them on disk to catch what can still go wrong on
an external drive: interrupted writes (``*.part``), truncated/empty files, content that
is not a real IGC, and read errors (bit rot, failing medium).

It reuses the download validation logic (:func:`~.download.is_valid_igc`,
:data:`~.download.MIN_IGC_BYTES`) so "valid" means exactly the same thing as at download
time. The scan is read-only: it never modifies or deletes anything.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .download import MIN_IGC_BYTES, is_valid_igc
from .seasons import season_label

logger = logging.getLogger(__name__)

# Bytes read from the head of each file: enough for the A header + first B record of
# any real IGC. Files failing the head check are re-read in full to avoid false
# positives (e.g. an unusually long header pushing the first B record past the head).
HEAD_BYTES = 16384

# Problem categories. The first group flags genuine integrity issues (drives the exit
# code); the second is informational clutter (e.g. macOS sidecars), reported but benign.
CAT_TOO_SMALL = "too_small"
CAT_INVALID = "invalid_structure"
CAT_READ_ERROR = "read_error"
CAT_PART_LEFTOVER = "part_leftover"
CAT_SIDECAR = "sidecar"
CAT_OTHER_FILE = "other_file"

#: Categories that count as actual corruption / incomplete downloads.
INTEGRITY_FAILURES = frozenset(
    {CAT_TOO_SMALL, CAT_INVALID, CAT_READ_ERROR, CAT_PART_LEFTOVER}
)


@dataclass
class VerifyProblem:
    """A single problematic entry found during the scan.

    Attributes:
        category: One of the ``CAT_*`` constants.
        path: Path of the offending file.
        detail: Short human-readable detail (size, error message, ...).
    """

    category: str
    path: str
    detail: str = ""

    @property
    def is_integrity_failure(self) -> bool:
        """Whether this problem is a genuine integrity failure (not mere clutter)."""
        return self.category in INTEGRITY_FAILURES


@dataclass
class SeasonVerifyResult:
    """Outcome of verifying a single season.

    Attributes:
        year: Season start year.
        season: Season label (e.g. ``"2014-2015"``).
        n_igc: Number of `.igc` files checked.
        problems: Problems found (empty if the season is clean).
    """

    year: int
    season: str
    n_igc: int = 0
    problems: list[VerifyProblem] = field(default_factory=list)

    @property
    def n_failures(self) -> int:
        """Number of problems that are genuine integrity failures."""
        return sum(p.is_integrity_failure for p in self.problems)

    @property
    def ok(self) -> bool:
        """``True`` if no genuine integrity failure was found for this season."""
        return self.n_failures == 0


def check_igc_file(path: Path) -> VerifyProblem | None:
    """Validates a single `.igc` file on disk.

    Reads the head and runs :func:`~.download.is_valid_igc`; on failure re-reads the
    whole file before reporting, to avoid false positives.

    Args:
        path: Path of the `.igc` file.

    Returns:
        A :class:`VerifyProblem` if the file is problematic, otherwise ``None``.
    """
    try:
        size = path.stat().st_size
    except OSError as err:
        return VerifyProblem(CAT_READ_ERROR, str(path), str(err))
    if size < MIN_IGC_BYTES:
        return VerifyProblem(CAT_TOO_SMALL, str(path), f"{size}B")
    try:
        with path.open("rb") as fh:
            head = fh.read(HEAD_BYTES)
    except OSError as err:
        return VerifyProblem(CAT_READ_ERROR, str(path), str(err))
    if is_valid_igc(head):
        return None
    try:
        full = path.read_bytes()
    except OSError as err:
        return VerifyProblem(CAT_READ_ERROR, str(path), str(err))
    if is_valid_igc(full):
        return None
    return VerifyProblem(CAT_INVALID, str(path), f"{size}B")


def verify_season(
    year: int, cfg: Config, *, workers: int | None = None
) -> SeasonVerifyResult:
    """Verifies every `.igc` file of a season's directory.

    Non-`.igc` entries are classified too: ``*.part`` (interrupted write), ``._*``
    (macOS sidecar) and anything else (``other_file``).

    Args:
        year: Season start year.
        cfg: Configuration (provides ``igc_dir`` and the default worker count).
        workers: Override for the number of parallel workers.

    Returns:
        The :class:`SeasonVerifyResult` for the season (empty if its directory is
        absent, i.e. nothing was downloaded).
    """
    result = SeasonVerifyResult(year=year, season=season_label(year))
    season_dir = cfg.igc_dir / result.season
    if not season_dir.is_dir():
        return result

    igc_files: list[Path] = []
    for entry in season_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        if name.startswith("._"):
            result.problems.append(VerifyProblem(CAT_SIDECAR, str(entry)))
        elif name.endswith(".part"):
            result.problems.append(VerifyProblem(CAT_PART_LEFTOVER, str(entry)))
        elif name.endswith(".igc"):
            igc_files.append(entry)
        else:
            result.problems.append(VerifyProblem(CAT_OTHER_FILE, str(entry)))
    result.n_igc = len(igc_files)

    n_workers = max(1, workers if workers is not None else cfg.http.workers)
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        for problem in pool.map(check_igc_file, igc_files):
            if problem is not None:
                result.problems.append(problem)

    logger.info(
        "[%s] verified %d .igc, %d problems (%d integrity failures)",
        result.season,
        result.n_igc,
        len(result.problems),
        result.n_failures,
    )
    return result


def verify_seasons(
    years: list[int], cfg: Config, *, workers: int | None = None
) -> list[SeasonVerifyResult]:
    """Verifies several seasons in sequence.

    Args:
        years: Season start years to verify.
        cfg: Configuration.
        workers: Override for the number of parallel workers.

    Returns:
        One :class:`SeasonVerifyResult` per requested season.
    """
    return [verify_season(y, cfg, workers=workers) for y in years]
