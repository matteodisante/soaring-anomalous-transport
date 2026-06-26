"""Command-line interface ``soaring-ffvl``.

Subcommands:

* ``fetch-xml``     -- downloads and archives the season XML exports;
* ``download``      -- downloads `.igc` files (resumable);
* ``build-catalog`` -- regenerates ``catalog.csv`` and ``seasons_index.csv``;
* ``status``        -- per-season summary: declared / with-igc / downloaded;
* ``verify``        -- integrity check of the `.igc` files already on disk.

Examples::

    soaring-ffvl fetch-xml --seasons all
    soaring-ffvl download --seasons 1999
    soaring-ffvl download --seasons 2024 --limit 50 --workers 6
    soaring-ffvl build-catalog
    soaring-ffvl status
    soaring-ffvl verify
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter

import pandas as pd

from . import catalog as catalog_mod
from .catalog_xml import fetch_season_xml, load_season_records, season_xml_path
from .config import Config, load_config
from .download import download_seasons
from .housekeeping import clean_appledouble
from .http import Fetcher
from .naming import igc_path
from .seasons import parse_seasons_arg, season_label
from .verify import verify_seasons

logger = logging.getLogger("soaring.ffvl")


def _setup_logging(cfg: Config) -> None:
    """Configures logging to console and file (``logs/download.log``).

    Args:
        cfg: Configuration (used to locate the log directory).
    """
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)s %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers.append(
        logging.FileHandler(cfg.logs_dir / "download.log", encoding="utf-8")
    )
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers, force=True)


def _resolve_seasons(cfg: Config, seasons_arg: str) -> list[int]:
    """Translates ``--seasons`` into a list of years, using the configuration limits."""
    return parse_seasons_arg(seasons_arg, cfg.season_start, cfg.season_end)


def cmd_fetch_xml(cfg: Config, args: argparse.Namespace) -> int:
    """Downloads and archives the season XMLs.

    Args:
        cfg: Configuration.
        args: Subcommand arguments.

    Returns:
        Process exit code.
    """
    years = _resolve_seasons(cfg, args.seasons)
    cfg.raw_xml_dir.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(cfg)
    try:
        for year in years:
            xml_bytes = fetch_season_xml(year, cfg, fetcher)
            path = season_xml_path(cfg, year)
            path.write_bytes(xml_bytes)
            logger.info(
                "[%s] XML archived: %s (%d KB)",
                season_label(year),
                path,
                len(xml_bytes) // 1024,
            )
    finally:
        fetcher.close()
    clean_appledouble(cfg.raw_xml_dir)
    return 0


def cmd_download(cfg: Config, args: argparse.Namespace) -> int:
    """Downloads `.igc` files for the requested seasons.

    Args:
        cfg: Configuration.
        args: Subcommand arguments.

    Returns:
        Process exit code.
    """
    if args.workers is not None:
        cfg.http.workers = args.workers
    years = _resolve_seasons(cfg, args.seasons)
    results = download_seasons(years, cfg, limit=args.limit, dry_run=args.dry_run)

    failures = [f for r in results for f in r.failures]
    if failures and not args.dry_run:
        cfg.failures_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([vars(f) for f in failures]).to_csv(cfg.failures_path, index=False)
        logger.warning("%d failures recorded in %s", len(failures), cfg.failures_path)

    tot_dl = sum(r.n_downloaded for r in results)
    tot_skip = sum(r.n_skipped for r in results)
    tot_fail = sum(r.n_failed for r in results)
    verb = "to download" if args.dry_run else "downloaded"
    logger.info("TOTAL: %d %s, %d skipped, %d failed", tot_dl, verb, tot_skip, tot_fail)
    if not args.dry_run:
        clean_appledouble(cfg.data_root)
        logger.info("Hint: now run 'soaring-ffvl build-catalog'.")
    return 1 if tot_fail else 0


def cmd_clean(cfg: Config, args: argparse.Namespace) -> int:
    """Removes ``._*`` sidecar files created by macOS on exfat volumes.

    Args:
        cfg: Configuration.
        args: Subcommand arguments (unused).

    Returns:
        Process exit code.
    """
    done = clean_appledouble(cfg.data_root)
    if not done:
        logger.info("Cleanup skipped (dot_clean not available or directory missing).")
    return 0


def cmd_build_catalog(cfg: Config, args: argparse.Namespace) -> int:
    """Regenerates the catalog and the season index.

    Args:
        cfg: Configuration.
        args: Subcommand arguments.

    Returns:
        Process exit code.
    """
    years = _resolve_seasons(cfg, args.seasons) if args.seasons != "all" else None
    catalog, index = catalog_mod.build(cfg, years)
    logger.info(
        "Done: %d flights in the catalog, %d seasons in the index.",
        len(catalog),
        len(index),
    )
    return 0


def cmd_status(cfg: Config, args: argparse.Namespace) -> int:
    """Shows the download status per season.

    Args:
        cfg: Configuration.
        args: Subcommand arguments.

    Returns:
        Process exit code.
    """
    years = _resolve_seasons(cfg, args.seasons)
    header = (
        f"{'season':<12}{'flights':>8}{'with_igc':>9}{'downloaded':>11}{'missing':>10}"
    )
    print(header)
    print("-" * len(header))
    tot_f = tot_igc = tot_dl = 0
    for year in years:
        path = season_xml_path(cfg, year)
        if not path.is_file():
            print(f"{season_label(year):<12}(XML missing: run 'fetch-xml')")
            continue
        records = load_season_records(cfg, year)
        n_f = len(records)
        with_igc = [r for r in records if r.has_igc]
        n_dl = sum(
            igc_path(cfg.igc_dir, r.season_year, r.date, r.flight_id).is_file()
            for r in with_igc
        )
        n_missing = len(with_igc) - n_dl
        tot_f += n_f
        tot_igc += len(with_igc)
        tot_dl += n_dl
        print(
            f"{season_label(year):<12}{n_f:>8}{len(with_igc):>9}{n_dl:>11}{n_missing:>10}"
        )
    print("-" * len(header))
    print(f"{'TOTAL':<12}{tot_f:>8}{tot_igc:>9}{tot_dl:>11}{tot_igc - tot_dl:>10}")
    return 0


def cmd_verify(cfg: Config, args: argparse.Namespace) -> int:
    """Checks the integrity of the `.igc` files already on disk.

    Prints a per-season summary and, if any problem is found, writes the details to
    ``logs/verify_problems.csv``. Exits non-zero only on genuine integrity failures
    (truncated/invalid files, ``*.part`` leftovers, read errors); macOS sidecars and
    stray files are reported but do not fail the run.

    Args:
        cfg: Configuration.
        args: Subcommand arguments.

    Returns:
        Process exit code (1 if integrity failures were found, else 0).
    """
    years = _resolve_seasons(cfg, args.seasons)
    results = verify_seasons(years, cfg, workers=args.workers)

    header = f"{'season':<12}{'igc':>9}{'problems':>10}{'failures':>10}"
    print(header)
    print("-" * len(header))
    tot_igc = tot_prob = tot_fail = 0
    for r in results:
        tot_igc += r.n_igc
        tot_prob += len(r.problems)
        tot_fail += r.n_failures
        flag = "" if r.ok else "  <-- CHECK"
        print(
            f"{r.season:<12}{r.n_igc:>9}{len(r.problems):>10}{r.n_failures:>10}{flag}"
        )
    print("-" * len(header))
    print(f"{'TOTAL':<12}{tot_igc:>9}{tot_prob:>10}{tot_fail:>10}")

    problems = [
        {"season": r.season, "category": p.category, "path": p.path, "detail": p.detail}
        for r in results
        for p in r.problems
    ]
    if problems:
        cfg.logs_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.logs_dir / "verify_problems.csv"
        pd.DataFrame(problems).to_csv(out, index=False)
        counts = Counter(p["category"] for p in problems)
        for category, n in counts.most_common():
            logger.warning("  %s: %d", category, n)
        logger.warning("%d problems written to %s", len(problems), out)
    else:
        logger.info("All %d .igc files passed validation.", tot_igc)
    return 1 if tot_fail else 0


def build_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser.

    Returns:
        The parser configured with all subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="soaring-ffvl",
        description="Download of .igc tracks from the CFD FFVL.",
    )
    parser.add_argument(
        "--config", default=None, help="Path to the YAML configuration file."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch-xml", help="Download and archive the season XMLs.")
    p_fetch.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_fetch.set_defaults(func=cmd_fetch_xml)

    p_dl = sub.add_parser("download", help="Download .igc files (resumable).")
    p_dl.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_dl.add_argument(
        "--workers", type=int, default=None, help="Override the number of workers."
    )
    p_dl.add_argument(
        "--limit", type=int, default=None, help="Max files per season (for testing)."
    )
    p_dl.add_argument(
        "--dry-run", action="store_true", help="Do not download: count only."
    )
    p_dl.set_defaults(func=cmd_download)

    p_cat = sub.add_parser(
        "build-catalog", help="Regenerate catalog.csv and seasons_index.csv."
    )
    p_cat.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_cat.set_defaults(func=cmd_build_catalog)

    p_st = sub.add_parser("status", help="Download status per season.")
    p_st.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_st.set_defaults(func=cmd_status)

    p_vfy = sub.add_parser("verify", help="Integrity check of the .igc files on disk.")
    p_vfy.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_vfy.add_argument(
        "--workers", type=int, default=None, help="Override the number of workers."
    )
    p_vfy.set_defaults(func=cmd_verify)

    p_clean = sub.add_parser("clean", help="Remove '._*' sidecar files (macOS/exfat).")
    p_clean.set_defaults(func=cmd_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``soaring-ffvl`` CLI.

    Args:
        argv: Arguments (for testing); if ``None`` uses ``sys.argv``.

    Returns:
        The process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    _setup_logging(cfg)
    logger.info("data_root = %s", cfg.data_root)
    return int(args.func(cfg, args))


if __name__ == "__main__":
    raise SystemExit(main())
