from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src.model import Point, TaxiAvailability, TaxiDataError

FIXTURE = Path(__file__).parent / "fixtures" / "taxi_availability_sample.json"


def _geojson(
    coordinates: list[Any],
    *,
    taxi_count: Any | None = None,
    timestamp: Any = "2026-11-13T14:23:23+08:00",
    include_count: bool = True,
) -> dict[str, Any]:
    properties: dict[str, Any] = {"timestamp": timestamp}
    if include_count:
        properties["taxi_count"] = (
            taxi_count if taxi_count is not None else len(coordinates)
        )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "MultiPoint", "coordinates": coordinates},
                "properties": properties,
            }
        ],
    }


def test_from_geojson_parses_minimal_response():
    snapshot = TaxiAvailability.from_geojson(_geojson([[103.99, 1.36], [103.86, 1.32]]))
    assert snapshot.taxi_count == 2
    assert len(snapshot.points) == 2


def test_from_geojson_swaps_lon_lat_into_lat_lon():
    snapshot = TaxiAvailability.from_geojson(_geojson([[103.99, 1.36]]))
    assert snapshot.points[0] == Point(lat=1.36, lon=103.99)


def test_from_geojson_parses_timestamp():
    snapshot = TaxiAvailability.from_geojson(_geojson([[103.99, 1.36]]))
    assert snapshot.timestamp == datetime.fromisoformat("2026-11-13T14:23:23+08:00")


def test_missing_timestamp_is_none():
    snapshot = TaxiAvailability.from_geojson(_geojson([[103.99, 1.36]], timestamp=None))
    assert snapshot.timestamp is None


def test_invalid_timestamp_raises():
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(
            _geojson([[103.99, 1.36]], timestamp="not-a-date")
        )


def test_count_mismatch_raises():
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(_geojson([[103.99, 1.36]], taxi_count=99))


def test_missing_taxi_count_raises():
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(_geojson([[103.99, 1.36]], include_count=False))


def test_bool_taxi_count_rejected():
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(_geojson([[103.99, 1.36]], taxi_count=True))


def test_empty_features_raises():
    geojson = {"type": "FeatureCollection", "features": []}
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(geojson)


def test_missing_features_raises():
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson({"type": "FeatureCollection"})


def test_unswapped_position_is_rejected_as_out_of_range():
    # A raw [lat, lon] pair (lat first) puts 103.99 into the latitude slot.
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(_geojson([[1.36, 103.99]]))


def test_non_numeric_coordinate_raises():
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(_geojson([["x", "y"]]))


def test_wrong_length_position_raises():
    with pytest.raises(TaxiDataError):
        TaxiAvailability.from_geojson(_geojson([[103.99, 1.36, 5.0]]))


def test_point_rejects_out_of_range_latitude():
    with pytest.raises(TaxiDataError):
        Point(lat=91.0, lon=103.99)


def test_point_rejects_out_of_range_longitude():
    with pytest.raises(TaxiDataError):
        Point(lat=1.36, lon=181.0)


def test_real_fixture_parses_and_is_consistent():
    geojson = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot = TaxiAvailability.from_geojson(geojson)
    assert snapshot.taxi_count == len(snapshot.points)
    assert all(1.0 < p.lat < 1.6 and 103.0 < p.lon < 104.5 for p in snapshot.points)
