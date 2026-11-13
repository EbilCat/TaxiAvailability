"""Fetch data from the data.gov.sg realtime taxi-availability API.

The imperative shell for network access: one function that GETs the endpoint and
returns the parsed GeoJSON, retrying transient failures with exponential
backoff. Parsing and grouping of that GeoJSON live in pure modules elsewhere, so
this layer stays a thin, replaceable edge. The retry *decisions*
(:func:`_is_retryable`, :func:`_backoff_seconds`) are pure and unit-tested; the
loop that sleeps and calls the network is the only impure part.
"""

from __future__ import annotations

import time

import httpx

__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_TIMEOUT",
    "TAXI_AVAILABILITY_URL",
    "fetch_taxi_data",
]

TAXI_AVAILABILITY_URL = "https://api.data.gov.sg/v1/transport/taxi-availability"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_CAP_SECONDS = 10.0
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def fetch_taxi_data(
    url: str = TAXI_AVAILABILITY_URL,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, object]:
    """Fetch the current taxi-availability GeoJSON from data.gov.sg.

    Retries transient failures (connection/timeout errors and 429/5xx responses)
    with exponential backoff, up to ``max_attempts`` tries. A non-transient
    failure (e.g. a 4xx other than 429) is raised immediately.

    Args:
        url: Endpoint to query; defaults to the realtime taxi-availability API.
        timeout: Per-request timeout in seconds.
        max_attempts: Maximum number of attempts before giving up (>= 1).

    Returns:
        The parsed GeoJSON response as a dictionary (a ``FeatureCollection``
        whose single ``MultiPoint`` feature holds the available-taxi
        coordinates and a ``taxi_count`` property).

    Raises:
        ValueError: If ``max_attempts`` is less than 1.
        httpx.HTTPStatusError: On a non-2xx status that is not retryable, or
            after the final retry.
        httpx.HTTPError: On a connection/timeout error after the final retry.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.get(
                url, timeout=timeout, headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == max_attempts or not _is_retryable(exc):
                raise
            time.sleep(_backoff_seconds(attempt))

    raise RuntimeError("unreachable")  # pragma: no cover


def _is_retryable(exc: httpx.HTTPError) -> bool:
    """Return whether a failed request is worth retrying.

    Args:
        exc: The exception raised by the request.

    Returns:
        True for connection/timeout errors and for 429/5xx responses; False for
        other status errors (e.g. 4xx), which a retry would not fix.
    """
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


def _backoff_seconds(attempt: int) -> float:
    """Seconds to wait before the attempt following a failed ``attempt``.

    Exponential backoff ``base * 2**(attempt - 1)``, capped.

    Args:
        attempt: The 1-based number of the attempt that just failed.

    Returns:
        The delay in seconds.
    """
    return min(_BACKOFF_BASE_SECONDS * 2 ** (attempt - 1), _BACKOFF_CAP_SECONDS)
