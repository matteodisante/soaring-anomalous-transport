"""Robust HTTP fetching for FFVL, capable of bypassing the Cloudflare challenge.

The FFVL site is protected by Cloudflare: a 'normal' HTTP request receives 403 with a
challenge page. ``curl_cffi`` mimics the TLS fingerprint of a real browser and bypasses
the filter.

The :class:`Fetcher` class wraps a ``curl_cffi`` session with:

* retry with exponential backoff,
* challenge page detection (and session renewal),
* a small jittered pause between requests (courtesy towards the server).

A :class:`Fetcher` is not thread-safe: each worker must use its own instance.
"""

from __future__ import annotations

import contextlib
import random
import time

from curl_cffi import requests as cffi_requests

from .config import Config, HttpConfig

# Typical markers of a Cloudflare challenge page ("Just a moment...").
CHALLENGE_MARKERS = (
    b"Just a moment",
    b"_cf_chl_opt",
    b"challenge-platform",
    b"cf-browser-verification",
)

# HTTP statuses that typically indicate blocking/overload -> worth retrying.
RETRY_STATUS = frozenset({403, 429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    """Fetch failed after exhausting all retry attempts."""


def new_session(http_cfg: HttpConfig) -> cffi_requests.Session:
    """Creates a new ``curl_cffi`` session with browser impersonation.

    Args:
        http_cfg: Network parameters (in particular the ``impersonate`` fingerprint).

    Returns:
        A ready-to-use session.
    """
    return cffi_requests.Session(impersonate=http_cfg.impersonate)


def looks_like_challenge(body: bytes) -> bool:
    """Indicates whether the response body is a Cloudflare challenge page.

    Args:
        body: Response bytes.

    Returns:
        ``True`` if a challenge marker appears in the first KB.
    """
    head = body[:4096]
    return any(marker in head for marker in CHALLENGE_MARKERS)


class Fetcher:
    """HTTP fetching with a ``curl_cffi`` session, retry logic and challenge handling.

    Attributes:
        cfg: Complete configuration.
        http: Shortcut to ``cfg.http``.
    """

    def __init__(self, cfg: Config) -> None:
        """Initialises the fetcher by creating the first session.

        Args:
            cfg: Complete configuration.
        """
        self.cfg = cfg
        self.http: HttpConfig = cfg.http
        self._session = new_session(cfg.http)

    def _renew_session(self) -> None:
        """Closes and recreates the session (useful after a Cloudflare challenge)."""
        with contextlib.suppress(Exception):
            self._session.close()
        self._session = new_session(self.http)

    def _polite_pause(self) -> None:
        """Short jittered pause before each request (courtesy towards the server)."""
        delay = self.http.min_delay_s
        if delay > 0:
            time.sleep(delay + random.uniform(0, delay))

    def content(self, url: str) -> bytes:
        """Downloads a URL and returns its bytes, with retry and challenge handling.

        Args:
            url: URL to download.

        Returns:
            The response body as bytes.

        Raises:
            FetchError: If all retry attempts fail.
        """
        last_error: Exception | None = None
        for attempt in range(1, self.http.max_retries + 1):
            self._polite_pause()
            try:
                resp = self._session.get(url, timeout=self.http.timeout_s)
                body = resp.content
                if looks_like_challenge(body):
                    self._renew_session()
                    raise FetchError(f"Cloudflare challenge at {url}")
                if resp.status_code in RETRY_STATUS:
                    raise FetchError(f"HTTP {resp.status_code} at {url}")
                if resp.status_code != 200:
                    # Non-retryable status (e.g. 404): no point retrying.
                    raise FetchError(
                        f"HTTP {resp.status_code} at {url} (non-retryable)"
                    )
                return body
            except FetchError as err:
                last_error = err
                if "non-retryable" in str(err):
                    break
            except Exception as err:
                last_error = err
            # Exponential backoff with jitter before the next attempt.
            if attempt < self.http.max_retries:
                backoff = self.http.backoff_base_s**attempt
                time.sleep(backoff + random.uniform(0, backoff))
        raise FetchError(
            f"fetch failed ({self.http.max_retries} attempts): {last_error}"
        )

    def text(self, url: str, encoding: str = "utf-8") -> str:
        """Like :meth:`content`, but decodes the bytes into a string.

        Args:
            url: URL to download.
            encoding: Encoding used for decoding (default UTF-8).

        Returns:
            The response body as a string.
        """
        return self.content(url).decode(encoding, errors="replace")

    def close(self) -> None:
        """Closes the underlying session."""
        with contextlib.suppress(Exception):
            self._session.close()
