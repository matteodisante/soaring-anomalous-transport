"""Interfaccia a riga di comando ``soaring-ffvl``.

Sottocomandi:

* ``fetch-xml``     -- scarica e archivia gli export XML di stagione;
* ``download``      -- scarica i file `.igc` (resumibile);
* ``build-catalog`` -- rigenera ``catalog.csv`` e ``seasons_index.csv``;
* ``status``        -- riepilogo per stagione: dichiarati / con-igc / scaricati.

Esempi::

    soaring-ffvl fetch-xml --seasons all
    soaring-ffvl download --seasons 1999
    soaring-ffvl download --seasons 2024 --limit 50 --workers 6
    soaring-ffvl build-catalog
    soaring-ffvl status
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from . import catalog as catalog_mod
from .catalog_xml import fetch_season_xml, load_season_records, season_xml_path
from .config import Config, load_config
from .download import download_seasons
from .housekeeping import clean_appledouble
from .http import Fetcher
from .naming import igc_path
from .seasons import parse_seasons_arg, season_label

logger = logging.getLogger("soaring.ffvl")


def _setup_logging(cfg: Config) -> None:
    """Configura il logging su console e su file (``logs/download.log``).

    Args:
        cfg: Configurazione (per individuare la cartella dei log).
    """
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)s %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers.append(
        logging.FileHandler(cfg.logs_dir / "download.log", encoding="utf-8")
    )
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers, force=True)


def _resolve_seasons(cfg: Config, seasons_arg: str) -> list[int]:
    """Traduce ``--seasons`` in lista di anni, usando i limiti di configurazione."""
    return parse_seasons_arg(seasons_arg, cfg.season_start, cfg.season_end)


def cmd_fetch_xml(cfg: Config, args: argparse.Namespace) -> int:
    """Scarica e archivia gli XML di stagione.

    Args:
        cfg: Configurazione.
        args: Argomenti del sottocomando.

    Returns:
        Codice di uscita del processo.
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
                "[%s] XML archiviato: %s (%d KB)",
                season_label(year),
                path,
                len(xml_bytes) // 1024,
            )
    finally:
        fetcher.close()
    clean_appledouble(cfg.raw_xml_dir)
    return 0


def cmd_download(cfg: Config, args: argparse.Namespace) -> int:
    """Scarica i file `.igc` delle stagioni richieste.

    Args:
        cfg: Configurazione.
        args: Argomenti del sottocomando.

    Returns:
        Codice di uscita del processo.
    """
    if args.workers is not None:
        cfg.http.workers = args.workers
    years = _resolve_seasons(cfg, args.seasons)
    results = download_seasons(years, cfg, limit=args.limit, dry_run=args.dry_run)

    failures = [f for r in results for f in r.failures]
    if failures and not args.dry_run:
        cfg.failures_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([vars(f) for f in failures]).to_csv(cfg.failures_path, index=False)
        logger.warning(
            "%d fallimenti registrati in %s", len(failures), cfg.failures_path
        )

    tot_dl = sum(r.n_downloaded for r in results)
    tot_skip = sum(r.n_skipped for r in results)
    tot_fail = sum(r.n_failed for r in results)
    verb = "da scaricare" if args.dry_run else "scaricati"
    logger.info(
        "TOTALE: %d %s, %d saltati, %d falliti", tot_dl, verb, tot_skip, tot_fail
    )
    if not args.dry_run:
        clean_appledouble(cfg.data_root)
        logger.info("Suggerimento: ora esegui 'soaring-ffvl build-catalog'.")
    return 1 if tot_fail else 0


def cmd_clean(cfg: Config, args: argparse.Namespace) -> int:
    """Rimuove i file sidecar ``._*`` creati da macOS su exfat.

    Args:
        cfg: Configurazione.
        args: Argomenti del sottocomando (non usati).

    Returns:
        Codice di uscita del processo.
    """
    done = clean_appledouble(cfg.data_root)
    if not done:
        logger.info("Pulizia saltata (dot_clean non disponibile o cartella assente).")
    return 0


def cmd_build_catalog(cfg: Config, args: argparse.Namespace) -> int:
    """Rigenera il catalogo e l'indice delle stagioni.

    Args:
        cfg: Configurazione.
        args: Argomenti del sottocomando.

    Returns:
        Codice di uscita del processo.
    """
    years = _resolve_seasons(cfg, args.seasons) if args.seasons != "all" else None
    catalog, index = catalog_mod.build(cfg, years)
    logger.info(
        "Fatto: %d voli nel catalogo, %d stagioni nell'indice.",
        len(catalog),
        len(index),
    )
    return 0


def cmd_status(cfg: Config, args: argparse.Namespace) -> int:
    """Mostra lo stato del download per stagione.

    Args:
        cfg: Configurazione.
        args: Argomenti del sottocomando.

    Returns:
        Codice di uscita del processo.
    """
    years = _resolve_seasons(cfg, args.seasons)
    header = (
        f"{'stagione':<12}{'voli':>8}{'con_igc':>9}{'scaricati':>11}{'mancanti':>10}"
    )
    print(header)
    print("-" * len(header))
    tot_f = tot_igc = tot_dl = 0
    for year in years:
        path = season_xml_path(cfg, year)
        if not path.is_file():
            print(f"{season_label(year):<12}(XML mancante: esegui 'fetch-xml')")
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
    print(f"{'TOTALE':<12}{tot_f:>8}{tot_igc:>9}{tot_dl:>11}{tot_igc - tot_dl:>10}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Costruisce il parser degli argomenti della CLI.

    Returns:
        Il parser configurato con tutti i sottocomandi.
    """
    parser = argparse.ArgumentParser(
        prog="soaring-ffvl",
        description="Download dei tracciati .igc dalla CFD FFVL.",
    )
    parser.add_argument(
        "--config", default=None, help="Path del file di configurazione YAML."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser(
        "fetch-xml", help="Scarica e archivia gli XML di stagione."
    )
    p_fetch.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_fetch.set_defaults(func=cmd_fetch_xml)

    p_dl = sub.add_parser("download", help="Scarica i file .igc (resumibile).")
    p_dl.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_dl.add_argument(
        "--workers", type=int, default=None, help="Override del numero di worker."
    )
    p_dl.add_argument(
        "--limit", type=int, default=None, help="Max file per stagione (test)."
    )
    p_dl.add_argument(
        "--dry-run", action="store_true", help="Non scarica: conta soltanto."
    )
    p_dl.set_defaults(func=cmd_download)

    p_cat = sub.add_parser(
        "build-catalog", help="Rigenera catalog.csv e seasons_index.csv."
    )
    p_cat.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_cat.set_defaults(func=cmd_build_catalog)

    p_st = sub.add_parser("status", help="Stato del download per stagione.")
    p_st.add_argument(
        "--seasons", default="all", help="all | 1999 | 1999-2025 | 2010,2012"
    )
    p_st.set_defaults(func=cmd_status)

    p_clean = sub.add_parser(
        "clean", help="Rimuove i file sidecar '._*' (macOS/exfat)."
    )
    p_clean.set_defaults(func=cmd_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto di ingresso della CLI ``soaring-ffvl``.

    Args:
        argv: Argomenti (per i test); se ``None`` usa ``sys.argv``.

    Returns:
        Il codice di uscita del processo.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    _setup_logging(cfg)
    logger.info("data_root = %s", cfg.data_root)
    return int(args.func(cfg, args))


if __name__ == "__main__":
    raise SystemExit(main())
