from __future__ import annotations

import pytest

from src.geocoding import (
    GeocodingError,
    NominatimGeocoder,
    google_maps_link,
    parse_address,
)


def test_google_maps_link_format():
    assert (
        google_maps_link(1.36, 103.99)
        == "https://www.google.com/maps/search/?api=1&query=1.36,103.99"
    )


def test_parse_address_returns_display_name():
    payload = {
        "display_name": "107, Towner Road, Kallang, Singapore, 321107, Singapore"
    }
    assert parse_address(payload) == payload["display_name"]


def test_parse_address_raises_on_error_payload():
    with pytest.raises(GeocodingError):
        parse_address({"error": "Unable to geocode"})


def test_parse_address_raises_on_missing_display_name():
    with pytest.raises(GeocodingError):
        parse_address({})


def test_parse_address_raises_on_empty_display_name():
    with pytest.raises(GeocodingError):
        parse_address({"display_name": ""})


def test_reverse_geocode_uses_fetcher_and_returns_address():
    geocoder = NominatimGeocoder(
        min_interval=0.0,
        fetcher=lambda lat, lon: {"display_name": f"addr {lat},{lon}"},
    )
    assert geocoder.reverse_geocode(1.36, 103.99) == "addr 1.36,103.99"


def test_reverse_geocode_caches_repeated_coordinate():
    calls: list[tuple[float, float]] = []

    def fetcher(lat: float, lon: float) -> dict[str, str]:
        calls.append((lat, lon))
        return {"display_name": "cached place"}

    geocoder = NominatimGeocoder(min_interval=0.0, fetcher=fetcher)
    first = geocoder.reverse_geocode(1.36, 103.99)
    second = geocoder.reverse_geocode(1.36, 103.99)

    assert first == second == "cached place"
    assert calls == [(1.36, 103.99)]  # second lookup served from cache


def test_reverse_geocode_propagates_geocoding_error():
    geocoder = NominatimGeocoder(
        min_interval=0.0,
        fetcher=lambda lat, lon: {"error": "Unable to geocode"},
    )
    with pytest.raises(GeocodingError):
        geocoder.reverse_geocode(1.0, 103.0)
