"""Turn a coordinate into displayable location info: an address and a map link.

Two responsibilities for one grid-cell coordinate:

- :func:`google_maps_link` — a pure, no-network formatted URL (the assignment's
  "Google Maps link" requirement is just a string, not a geocoding call).
- :class:`NominatimGeocoder` — reverse-geocode the coordinate to an address in
  words via the public Nominatim / OpenStreetMap service (the "location in
  words" requirement). No API key; it self-throttles to Nominatim's 1 req/s
  policy, sends an app-identifying ``User-Agent``, and caches results in memory
  so a repeated coordinate costs no second request.

The brittle response parsing lives in the pure :func:`parse_address`, so it is
unit-testable offline without a live request.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

__all__ = ["GeocodingError", "NominatimGeocoder", "google_maps_link", "parse_address"]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "TaxiAvailability/0.1 (AISG take-home assignment)"
MIN_REQUEST_INTERVAL = 1.0
DEFAULT_TIMEOUT = 30.0
_GOOGLE_MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query={lat},{lon}"


class NominatimGeocoder:
    """Reverse-geocode coordinates to addresses via Nominatim, throttled + cached.

    A single instance is reused across a run so its rate-limiter and cache span
    all lookups. Results are cached in memory keyed by ``(lat, lon)``.

    Args:
        url: Nominatim reverse-geocode endpoint.
        user_agent: ``User-Agent`` header identifying this app, as Nominatim's
            usage policy requires. Must not carry personal details.
        min_interval: Minimum seconds between network requests (policy: 1 req/s).
        timeout: Per-request timeout in seconds.
        fetcher: Seam for testing — a callable ``(lat, lon) -> payload`` that
            returns the decoded JSON. Defaults to the real HTTP request.
    """

    def __init__(
        self,
        *,
        url: str = NOMINATIM_URL,
        user_agent: str = USER_AGENT,
        min_interval: float = MIN_REQUEST_INTERVAL,
        timeout: float = DEFAULT_TIMEOUT,
        fetcher: Callable[[float, float], dict[str, Any]] | None = None,
    ) -> None:
        self._url = url
        self._user_agent = user_agent
        self._min_interval = min_interval
        self._timeout = timeout
        self._fetch = fetcher if fetcher is not None else self._http_fetch
        self._cache: dict[tuple[float, float], str] = {}
        self._last_request = 0.0

    def reverse_geocode(self, lat: float, lon: float) -> str:
        """Return the address in words for ``(lat, lon)``.

        Args:
            lat: Latitude in decimal degrees.
            lon: Longitude in decimal degrees.

        Returns:
            The address string (Nominatim's ``display_name``). Cached, so a
            repeated coordinate does not make a second request.

        Raises:
            GeocodingError: If the service reports an error or returns no usable
                address.
            httpx.HTTPError: On connection, timeout, or non-2xx status.
        """
        key = (lat, lon)
        if key not in self._cache:
            self._throttle()
            self._cache[key] = parse_address(self._fetch(lat, lon))
        return self._cache[key]

    def _http_fetch(self, lat: float, lon: float) -> dict[str, Any]:
        """Make the live Nominatim request and return the decoded JSON payload."""
        response = httpx.get(
            self._url,
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()

    def _throttle(self) -> None:
        """Sleep as needed so requests are spaced by at least ``min_interval``."""
        wait = self._min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()


def google_maps_link(lat: float, lon: float) -> str:
    """Build a Google Maps search URL centered on ``(lat, lon)``.

    Pure string formatting — no network, no API key. The URL opens Google Maps
    at the coordinate when followed.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.

    Returns:
        A ``https://www.google.com/maps/search/?api=1&query=<lat>,<lon>`` URL.
    """
    return _GOOGLE_MAPS_SEARCH.format(lat=lat, lon=lon)


def parse_address(payload: dict[str, Any]) -> str:
    """Extract the address string from a Nominatim reverse-geocode payload.

    Pure and offline, so the error handling is unit-testable without a request.

    Args:
        payload: The decoded JSON body from a Nominatim reverse-geocode call.

    Returns:
        The ``display_name`` address string.

    Raises:
        GeocodingError: If the payload reports an ``error`` or lacks a non-empty
            ``display_name``.
    """
    if "error" in payload:
        raise GeocodingError(f"Nominatim returned an error: {payload['error']!r}")
    display_name = payload.get("display_name")
    if not isinstance(display_name, str) or not display_name:
        raise GeocodingError(f"no usable address in response: {payload!r}")
    return display_name


class GeocodingError(Exception):
    """Raised when a coordinate cannot be reverse-geocoded to an address."""
