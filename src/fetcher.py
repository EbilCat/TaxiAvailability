"""Fetch data from the data.gov.sg realtime taxi-availability API.

The imperative shell for network access: one function that GETs the endpoint and
returns the parsed GeoJSON. Parsing and grouping of that GeoJSON live in pure
modules elsewhere, so this layer stays a thin, replaceable edge.
"""

from __future__ import annotations

import httpx

__all__ = ["DEFAULT_TIMEOUT", "TAXI_AVAILABILITY_URL", "fetch_taxi_data"]

TAXI_AVAILABILITY_URL = "https://api.data.gov.sg/v1/transport/taxi-availability"
DEFAULT_TIMEOUT = 30.0


def fetch_taxi_data(
    url: str = TAXI_AVAILABILITY_URL, *, timeout: float = DEFAULT_TIMEOUT
) -> dict[str, object]:
    """Fetch the current taxi-availability GeoJSON from data.gov.sg.

    Args:
        url: Endpoint to query; defaults to the realtime taxi-availability API.
        timeout: Per-request timeout in seconds.

    Returns:
        The parsed GeoJSON response as a dictionary (a ``FeatureCollection``
        whose single ``MultiPoint`` feature holds the available-taxi
        coordinates and a ``taxi_count`` property).

    Raises:
        httpx.HTTPStatusError: If the endpoint returns a non-2xx status.
        httpx.HTTPError: On connection, timeout, or protocol errors.
    """
    response = httpx.get(url, timeout=timeout, headers={"Accept": "application/json"})
    response.raise_for_status()
    return response.json()