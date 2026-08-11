"""
MediaMTX Monitor - Control API client.

Provides the technical HTTP boundary for reading raw MediaMTX JSON data.

Responsibilities:
- Build Control API URLs and execute GET requests with a fixed timeout.
- Translate transport, HTTP, and JSON decoding failures into client errors.

Does not:
- Interpret streams, protocols, metrics, health, or persistence.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import requests


DEFAULT_TIMEOUT_SECONDS = 3.0


class MediaMTXError(Exception):
    """Base class for technical MediaMTX Control API failures."""


class MediaMTXRequestError(MediaMTXError):
    """Raised when the Control API cannot be reached."""


class MediaMTXHTTPError(MediaMTXError):
    """Raised when the Control API returns an unsuccessful HTTP status."""

    def __init__(self, url: str, status_code: int) -> None:
        super().__init__(f"HTTP {status_code} for {url}")
        self.url = url
        self.status_code = status_code


class MediaMTXDecodeError(MediaMTXError):
    """Raised when a successful response does not contain valid JSON."""


class MediaMTXClient:
    """Read raw JSON responses from one MediaMTX Control API."""

    def __init__(
        self,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session: Optional[Any] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session if session is not None else requests.Session()

    def build_url(self, endpoint: str) -> str:
        """Combine the configured base URL with a Control API endpoint."""
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def get_json(
        self,
        endpoint: str,
        params: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Return decoded JSON or raise a technical client error."""
        url = self.build_url(endpoint)
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else 0
            raise MediaMTXHTTPError(url, status_code) from exc
        except requests.RequestException as exc:
            raise MediaMTXRequestError(f"Request failed for {url}: {exc}") from exc

        try:
            return response.json()
        except (ValueError, requests.RequestException) as exc:
            raise MediaMTXDecodeError(f"Invalid JSON from {url}: {exc}") from exc
