"""Configurazione del downloader FFVL, letta da un file YAML.

La configurazione e' una semplice dataclass tipizzata: nessuna magia, valori espliciti.
Il path di default e' ``configs/ffvl_download.yaml`` nella radice del progetto.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Path di default del file di configurazione, relativo alla radice del repo.
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "ffvl_download.yaml"
)


@dataclass
class HttpConfig:
    """Parametri di rete e di cortesia verso il server FFVL.

    Attributes:
        impersonate: Fingerprint TLS che ``curl_cffi`` deve imitare (es. ``"chrome"``).
        workers: Numero di download paralleli.
        timeout_s: Timeout per singola richiesta, in secondi.
        max_retries: Tentativi massimi per richiesta prima di arrendersi.
        backoff_base_s: Base del backoff esponenziale tra i tentativi, in secondi.
        min_delay_s: Pausa minima (con jitter) tra richieste dello stesso worker.
    """

    impersonate: str = "chrome"
    workers: int = 4
    timeout_s: float = 60.0
    max_retries: int = 5
    backoff_base_s: float = 2.0
    min_delay_s: float = 0.05


@dataclass
class Config:
    """Configurazione completa del downloader.

    Attributes:
        data_root: Cartella radice dei dati grezzi (tipicamente sull'HDD esterno).
        season_start: Primo anno di stagione incluso (1999 = stagione 1999-2000).
        season_end: Ultimo anno di stagione incluso (2025 = stagione 2025-2026).
        base_url: Origine del sito FFVL.
        list_path: Template del path della lista per anno (``{year}`` come segnaposto).
        xml_query: Query string che attiva l'export XML.
        http: Parametri di rete (vedi :class:`HttpConfig`).
    """

    data_root: Path
    season_start: int = 1999
    season_end: int = 2025
    base_url: str = "https://parapente.ffvl.fr"
    list_path: str = "/cfd/liste/{year}"
    xml_query: str = "?xml=1"
    http: HttpConfig = field(default_factory=HttpConfig)

    # --- sottocartelle derivate da data_root ---------------------------------
    @property
    def raw_xml_dir(self) -> Path:
        """Cartella degli XML di stagione archiviati."""
        return self.data_root / "raw_xml"

    @property
    def igc_dir(self) -> Path:
        """Cartella radice dei tracciati `.igc` (una sottocartella per stagione)."""
        return self.data_root / "igc"

    @property
    def logs_dir(self) -> Path:
        """Cartella dei log e del registro dei fallimenti."""
        return self.data_root / "logs"

    @property
    def catalog_path(self) -> Path:
        """Path del catalogo CSV derivato."""
        return self.data_root / "catalog.csv"

    @property
    def seasons_index_path(self) -> Path:
        """Path del riepilogo per stagione (link + conteggi)."""
        return self.data_root / "seasons_index.csv"

    @property
    def failures_path(self) -> Path:
        """Path del CSV dei download falliti (per retry mirato)."""
        return self.logs_dir / "failures.csv"

    @property
    def years(self) -> range:
        """Intervallo di anni di stagione configurati (estremi inclusi)."""
        return range(self.season_start, self.season_end + 1)


def _expand(path_str: str) -> Path:
    """Espande ``~`` e le variabili d'ambiente in una stringa di path.

    Args:
        path_str: Path eventualmente contenente ``~`` o ``$VAR``.

    Returns:
        Il path assoluto/espanso come :class:`~pathlib.Path`.
    """
    return Path(os.path.expandvars(path_str)).expanduser()


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Carica la configurazione da YAML.

    ``data_root`` puo' anche essere sovrascritto dalla variabile d'ambiente
    ``SOARING_FFVL_DATA_ROOT`` (utile su macchine diverse senza toccare il file).

    Args:
        path: Path del file YAML. Se ``None`` usa :data:`DEFAULT_CONFIG_PATH`.

    Returns:
        L'oggetto :class:`Config` popolato.

    Raises:
        FileNotFoundError: Se il file di configurazione non esiste.
        KeyError: Se manca la chiave obbligatoria ``data_root``.
    """
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not cfg_path.is_file():
        raise FileNotFoundError(f"File di configurazione non trovato: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    data_root_str = os.environ.get("SOARING_FFVL_DATA_ROOT") or raw.get("data_root")
    if not data_root_str:
        raise KeyError(
            "Manca 'data_root' nel file di configurazione "
            "(oppure imposta la variabile SOARING_FFVL_DATA_ROOT)."
        )

    seasons = raw.get("seasons", {}) or {}
    source = raw.get("source", {}) or {}
    http_raw = raw.get("http", {}) or {}

    return Config(
        data_root=_expand(str(data_root_str)),
        season_start=int(seasons.get("start", 1999)),
        season_end=int(seasons.get("end", 2025)),
        base_url=source.get("base_url", "https://parapente.ffvl.fr"),
        list_path=source.get("list_path", "/cfd/liste/{year}"),
        xml_query=source.get("xml_query", "?xml=1"),
        http=HttpConfig(
            impersonate=http_raw.get("impersonate", "chrome"),
            workers=int(http_raw.get("workers", 4)),
            timeout_s=float(http_raw.get("timeout_s", 60.0)),
            max_retries=int(http_raw.get("max_retries", 5)),
            backoff_base_s=float(http_raw.get("backoff_base_s", 2.0)),
            min_delay_s=float(http_raw.get("min_delay_s", 0.05)),
        ),
    )
