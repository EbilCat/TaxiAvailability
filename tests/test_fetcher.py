from __future__ import annotations

import httpx
import pytest

from src.fetcher import (
    TAXI_AVAILABILITY_URL,
    _backoff_seconds,
    _is_retryable,
    fetch_taxi_data,
)


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", TAXI_AVAILABILITY_URL)
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"HTTP {code}", request=request, response=response)


def test_transport_errors_are_retryable():
    assert _is_retryable(httpx.ConnectError("boom"))
    assert _is_retryable(httpx.ReadTimeout("slow"))


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_retryable_status_codes(code: int):
    assert _is_retryable(_status_error(code))


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_errors_are_not_retryable(code: int):
    assert not _is_retryable(_status_error(code))


def test_backoff_is_exponential_and_capped():
    assert _backoff_seconds(1) == 1.0
    assert _backoff_seconds(2) == 2.0
    assert _backoff_seconds(3) == 4.0
    assert _backoff_seconds(10) == 10.0  # capped


def test_zero_max_attempts_raises():
    with pytest.raises(ValueError):
        fetch_taxi_data(max_attempts=0)
