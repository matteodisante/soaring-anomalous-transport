"""FFVL downloader configuration, read from a YAML file.

The configuration is a simple typed dataclass: no magic, explicit values.
Discipline-specific config paths are exposed as :data:`PARA_CONFIG_PATH` and
:data:`DELTA_CONFIG_PATH`; neither is a default — callers must choose explicitly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Configuration file paths (repository root / configs/).
_CONFIGS_DIR = Path(__file__).resolve().parents[4] / "configs"
PARA_CONFIG_PATH = _CONFIGS_DIR / "para_download.yaml"
DELTA_CONFIG_PATH = _CONFIGS_DIR / "delta_download.yaml"


@dataclass
class HttpConfig:
    """Network parameters and rate-limiting settings for the FFVL server.

    Attributes:
        impersonate: TLS fingerprint that ``curl_cffi`` should impersonate (e.g. ``"chrome"``).
        workers: Number of parallel downloads.
        timeout_s: Timeout per individual request, in seconds.
        max_retries: Maximum retry attempts per request before giving up.
        backoff_base_s: Base of the exponential backoff between attempts, in seconds.
        min_delay_s: Minimum pause (with jitter) between requests from the same worker.
    """

    impersonate: str = "chrome"
    workers: int = 4
    timeout_s: float = 60.0
    max_retries: int = 5
    backoff_base_s: float = 2.0
    min_delay_s: float = 0.05


@dataclass
class Config:
    """Complete downloader configuration.

    Attributes:
        data_root: Root directory for raw data (typically on the external HDD).
        season_start: First season year included (1999 = season 1999-2000).
        season_end: Last season year included (2025 = season 2025-2026).
        base_url: FFVL site base URL.
        list_path: URL path template for the season list (``{year}`` as placeholder).
        xml_query: Query string that enables the XML export.
        http: Network parameters (see :class:`HttpConfig`).
    """

    data_root: Path
    season_start: int 
    season_end: int 
    base_url: str 
    list_path: str = "/cfd/liste/{year}"
    xml_query: str = "?xml=1"
    http: HttpConfig = field(default_factory=HttpConfig)

    # --- subdirectories derived from data_root ---------------------------------
    # Layout: data_root/{raw/{igc,raw_xml}, catalog/{catalog.csv,seasons_index.csv},
    # logs/, derived/}. "raw" groups the untouched acquisition output (tracks + their
    # XML provenance); "catalog" groups the tables derived from it; "derived" holds
    # further byproducts of analysing the raw tracks (e.g. the pre-processing track
    # scan cache) that are not themselves raw or catalog data. All on the external
    # disk -- nothing here is ever stored in the repo.
    @property
    def raw_xml_dir(self) -> Path:
        """Directory for archived season XML files."""
        return self.data_root / "raw" / "raw_xml"

    @property
    def igc_dir(self) -> Path:
        """Root directory for `.igc` track files (one subdirectory per season)."""
        return self.data_root / "raw" / "igc"

    @property
    def logs_dir(self) -> Path:
        """Directory for logs and the failure registry."""
        return self.data_root / "logs"

    @property
    def catalog_path(self) -> Path:
        """Path to the derived CSV catalog."""
        return self.data_root / "catalog" / "catalog.csv"

    @property
    def seasons_index_path(self) -> Path:
        """Path to the per-season summary (links + counts)."""
        return self.data_root / "catalog" / "seasons_index.csv"

    @property
    def derived_dir(self) -> Path:
        """Directory for analysis byproducts of the raw tracks (e.g. scan caches)."""
        return self.data_root / "derived"

    @property
    def failures_path(self) -> Path:
        """Path to the CSV of failed downloads (for targeted retry)."""
        return self.logs_dir / "failures.csv"

    @property
    def years(self) -> range:
        """Range of configured season years (endpoints included)."""
        return range(self.season_start, self.season_end + 1)


def _expand(path_str: str) -> Path:
    """Expands ``~`` and environment variables in a path string.

    Args:
        path_str: Path potentially containing ``~`` or ``$VAR``.

    Returns:
        The absolute/expanded path as a :class:`~pathlib.Path`.
    """
    return Path(os.path.expandvars(path_str)).expanduser()


def load_config(
    path: str | os.PathLike[str],
    *,
    data_root_env: str,
) -> Config:
    """Loads the configuration from a YAML file.

    ``data_root`` can also be overridden by the environment variable named by
    ``data_root_env`` (useful on different machines without editing the file).

    Args:
        path: Path to the YAML file. Use :data:`PARA_CONFIG_PATH` for paragliders
            or :data:`DELTA_CONFIG_PATH` for hang gliders.
        data_root_env: Name of the environment variable that overrides ``data_root``
            (``"SOARING_PARA_DATA_ROOT"`` for paragliders,
            ``"SOARING_DELTA_DATA_ROOT"`` for hang gliders).

    Returns:
        The populated :class:`Config` object.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        KeyError: If the mandatory ``data_root`` key is missing.
    """
    cfg_path = Path(path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    data_root_str = os.environ.get(data_root_env) or raw.get("data_root")
    if not data_root_str:
        raise KeyError(
            "Missing 'data_root' in the configuration file "
            "(or set the SOARING_FFVL_DATA_ROOT environment variable)."
        )

    seasons = raw.get("seasons", {}) or {}
    source = raw.get("source", {}) or {}
    http_raw = raw.get("http", {}) or {}

    return Config(
        data_root=_expand(str(data_root_str)),
        season_start=int(seasons.get("start")),
        season_end=int(seasons.get("end")),
        base_url=source.get("base_url"),
        list_path=source.get("list_path", "/cfd/liste/{year}"),
        xml_query=source.get("xml_query", "?xml=1"),
        http=HttpConfig(**{
            k: cast(http_raw[k])
            for k, cast in {
                "impersonate": str,
                "workers": int,
                "timeout_s": float,
                "max_retries": int,
                "backoff_base_s": float,
                "min_delay_s": float,
            }.items()
            if k in http_raw
        }),
    )
