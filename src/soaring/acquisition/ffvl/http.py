"""Recupero HTTP robusto verso FFVL, capace di superare il challenge Cloudflare.

Il sito FFVL e' protetto da Cloudflare: una richiesta HTTP "normale" riceve 403
con una pagina di challenge. ``curl_cffi`` imita il fingerprint TLS di un browser
reale e supera il filtro.

La classe :class:`Fetcher` incapsula una sessione ``curl_cffi`` con:

* retry con backoff esponenziale,
* rilevamento della pagina di challenge (e rigenerazione della sessione),
* piccola pausa con jitter tra richieste (cortesia verso il server).

Una :class:`Fetcher` non e' thread-safe: ogni worker deve usarne una propria.
"""

from __future__ import annotations

import contextlib
import random
import time

from curl_cffi import requests as cffi_requests

from .config import Config, HttpConfig

# Marcatori tipici della pagina di challenge Cloudflare ("Just a moment...").
CHALLENGE_MARKERS = (
    b"Just a moment",
    b"_cf_chl_opt",
    b"challenge-platform",
    b"cf-browser-verification",
)

# Stati HTTP che tipicamente indicano blocco/sovraccarico -> conviene ritentare.
RETRY_STATUS = frozenset({403, 429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    """Recupero fallito dopo aver esaurito i tentativi."""


def new_session(http_cfg: HttpConfig) -> cffi_requests.Session:
    """Crea una nuova sessione ``curl_cffi`` con impersonation del browser.

    Args:
        http_cfg: Parametri di rete (in particolare il fingerprint ``impersonate``).

    Returns:
        Una sessione pronta all'uso.
    """
    return cffi_requests.Session(impersonate=http_cfg.impersonate)


def looks_like_challenge(body: bytes) -> bool:
    """Indica se il corpo della risposta e' una pagina di challenge Cloudflare.

    Args:
        body: Byte della risposta.

    Returns:
        ``True`` se nei primi KB compare un marcatore di challenge.
    """
    head = body[:4096]
    return any(marker in head for marker in CHALLENGE_MARKERS)


class Fetcher:
    """Recupero HTTP con sessione ``curl_cffi``, retry e gestione del challenge.

    Attributes:
        cfg: Configurazione completa.
        http: Scorciatoia a ``cfg.http``.
    """

    def __init__(self, cfg: Config) -> None:
        """Inizializza il fetcher creando la prima sessione.

        Args:
            cfg: Configurazione completa.
        """
        self.cfg = cfg
        self.http: HttpConfig = cfg.http
        self._session = new_session(cfg.http)

    def _renew_session(self) -> None:
        """Chiude e ricrea la sessione (utile dopo un challenge Cloudflare)."""
        with contextlib.suppress(Exception):
            self._session.close()
        self._session = new_session(self.http)

    def _polite_pause(self) -> None:
        """Breve pausa con jitter prima di ogni richiesta (cortesia verso il server)."""
        delay = self.http.min_delay_s
        if delay > 0:
            time.sleep(delay + random.uniform(0, delay))

    def content(self, url: str) -> bytes:
        """Scarica un URL e ne restituisce i byte, con retry e gestione del challenge.

        Args:
            url: URL da scaricare.

        Returns:
            Il corpo della risposta in byte.

        Raises:
            FetchError: Se tutti i tentativi falliscono.
        """
        last_error: Exception | None = None
        for attempt in range(1, self.http.max_retries + 1):
            self._polite_pause()
            try:
                resp = self._session.get(url, timeout=self.http.timeout_s)
                body = resp.content
                if looks_like_challenge(body):
                    self._renew_session()
                    raise FetchError(f"challenge Cloudflare su {url}")
                if resp.status_code in RETRY_STATUS:
                    raise FetchError(f"HTTP {resp.status_code} su {url}")
                if resp.status_code != 200:
                    # Stato non ritentabile (es. 404): inutile insistere.
                    raise FetchError(
                        f"HTTP {resp.status_code} su {url} (non ritentabile)"
                    )
                return body
            except FetchError as err:
                last_error = err
                if "non ritentabile" in str(err):
                    break
            except Exception as err:
                last_error = err
            # Backoff esponenziale con jitter prima del prossimo tentativo.
            if attempt < self.http.max_retries:
                backoff = self.http.backoff_base_s**attempt
                time.sleep(backoff + random.uniform(0, backoff))
        raise FetchError(
            f"recupero fallito ({self.http.max_retries} tentativi): {last_error}"
        )

    def text(self, url: str, encoding: str = "utf-8") -> str:
        """Come :meth:`content`, ma decodifica i byte in stringa.

        Args:
            url: URL da scaricare.
            encoding: Codifica usata per la decodifica (default UTF-8).

        Returns:
            Il corpo della risposta come stringa.
        """
        return self.content(url).decode(encoding, errors="replace")

    def close(self) -> None:
        """Chiude la sessione sottostante."""
        with contextlib.suppress(Exception):
            self._session.close()
