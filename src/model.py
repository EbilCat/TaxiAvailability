"""Typed, validated data model for the taxi-availability API response.

The data.gov.sg realtime endpoint returns an untyped GeoJSON
``FeatureCollection``. This module parses that raw dictionary into immutable
value objects at the network boundary — swapping each ``[lon, lat]`` position
into ``(lat, lon)``, validating coordinate ranges, and asserting the reported
``taxi_count`` matches the number of points — so the pure processing core
downstream can trust its inputs instead of re-checking the raw shape everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

__all__ = ["Point", "TaxiAvailability", "TaxiDataError"]

_MIN_LAT, _MAX_LAT = -90.0, 90.0
_MIN_LON, _MAX_LON = -180.0, 180.0


@dataclass(frozen=True, slots=True)
class TaxiAvailability:
    """A validated snapshot of available taxis in Singapore.

    Built from the API's GeoJSON at the boundary via :meth:`from_geojson`, after
    which every field is guaranteed consistent: ``taxi_count`` equals
    ``len(points)`` and every point is within valid WGS84 ranges.

    Attributes:
        taxi_count: Authoritative count of available taxis, as reported by LTA
            via data.gov.sg. Equals ``len(points)`` by construction.
        points: One position per available taxi, as ``(lat, lon)``.
        timestamp: Scrape time reported by data.gov.sg, or ``None`` if absent.
    """

    taxi_count: int
    points: tuple[Point, ...]
    timestamp: datetime | None

    @classmethod
    def from_geojson(cls, geojson: dict[str, Any]) -> TaxiAvailability:
        """Parse and validate a raw taxi-availability GeoJSON response.

        Args:
            geojson: The decoded JSON body from the taxi-availability endpoint —
                a ``FeatureCollection`` whose single ``MultiPoint`` feature holds
                the available-taxi coordinates (as ``[lon, lat]`` positions) plus
                a ``taxi_count`` and ``timestamp`` in its ``properties``.

        Returns:
            A fully validated ``TaxiAvailability`` snapshot.

        Raises:
            TaxiDataError: If the response is missing required fields, has the
                wrong shape, carries out-of-range coordinates, or reports a
                ``taxi_count`` that disagrees with the number of points.
        """
        feature = _first_feature(geojson)
        geometry = _require_mapping(feature.get("geometry"), "feature.geometry")
        properties = _require_mapping(feature.get("properties"), "feature.properties")

        points = tuple(
            _point_from_position(position)
            for position in _require_list(
                geometry.get("coordinates"), "geometry.coordinates"
            )
        )
        taxi_count = _require_int(properties.get("taxi_count"), "properties.taxi_count")
        if taxi_count != len(points):
            raise TaxiDataError(
                f"taxi_count ({taxi_count}) does not match number of "
                f"coordinates ({len(points)})"
            )

        return cls(
            taxi_count=taxi_count,
            points=points,
            timestamp=_parse_timestamp(properties.get("timestamp")),
        )


@dataclass(frozen=True, slots=True)
class Point:
    """A single available taxi's WGS84 position, latitude first.

    Attributes:
        lat: Latitude in decimal degrees, within ``[-90, 90]``.
        lon: Longitude in decimal degrees, within ``[-180, 180]``.
    """

    lat: float
    lon: float

    def __post_init__(self) -> None:
        """Reject out-of-range coordinates at construction.

        Raises:
            TaxiDataError: If ``lat`` or ``lon`` falls outside valid WGS84
                ranges — which also catches an un-swapped ``[lon, lat]`` pair,
                since Singapore longitudes near 104 are invalid latitudes.
        """
        if not _MIN_LAT <= self.lat <= _MAX_LAT:
            raise TaxiDataError(f"latitude out of range: {self.lat!r}")
        if not _MIN_LON <= self.lon <= _MAX_LON:
            raise TaxiDataError(f"longitude out of range: {self.lon!r}")


class TaxiDataError(ValueError):
    """Raised when a taxi-availability response cannot be parsed or validated."""


def _first_feature(geojson: dict[str, Any]) -> dict[str, Any]:
    """Return the first feature of a GeoJSON ``FeatureCollection``.

    Args:
        geojson: The decoded response body.

    Returns:
        The first feature mapping.

    Raises:
        TaxiDataError: If ``features`` is missing, not a list, or empty.
    """
    features = _require_list(geojson.get("features"), "features")
    if not features:
        raise TaxiDataError("response contains no features")
    return _require_mapping(features[0], "features[0]")


def _point_from_position(position: Any) -> Point:
    """Convert a GeoJSON ``[lon, lat]`` position into a ``(lat, lon)`` point.

    Args:
        position: A two-element ``[lon, lat]`` sequence of numbers.

    Returns:
        The corresponding ``Point``.

    Raises:
        TaxiDataError: If the position is not a pair of numbers.
    """
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        raise TaxiDataError(f"expected a [lon, lat] pair, got {position!r}")
    lon, lat = position
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        raise TaxiDataError(f"position has non-numeric coordinates: {position!r}")
    return Point(lat=float(lat), lon=float(lon))


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp string, tolerating absence.

    Args:
        value: The raw ``timestamp`` property, expected to be an ISO 8601
            string, or ``None``/absent.

    Returns:
        The parsed ``datetime``, or ``None`` if no timestamp was provided.

    Raises:
        TaxiDataError: If a value is present but is not a parseable timestamp.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TaxiDataError(f"timestamp is not a string: {value!r}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise TaxiDataError(f"invalid timestamp: {value!r}") from exc


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    """Return ``value`` if it is a mapping, else fail loudly.

    Args:
        value: The candidate value.
        field: Dotted field name, used in the error message.

    Returns:
        The value, narrowed to a dictionary.

    Raises:
        TaxiDataError: If ``value`` is not a mapping.
    """
    if not isinstance(value, dict):
        raise TaxiDataError(f"expected object for {field}, got {type(value).__name__}")
    return value


def _require_list(value: Any, field: str) -> list[Any]:
    """Return ``value`` if it is a list, else fail loudly.

    Args:
        value: The candidate value.
        field: Dotted field name, used in the error message.

    Returns:
        The value, narrowed to a list.

    Raises:
        TaxiDataError: If ``value`` is not a list.
    """
    if not isinstance(value, list):
        raise TaxiDataError(f"expected array for {field}, got {type(value).__name__}")
    return value


def _require_int(value: Any, field: str) -> int:
    """Return ``value`` if it is an integer, else fail loudly.

    Args:
        value: The candidate value.
        field: Dotted field name, used in the error message.

    Returns:
        The value as an ``int``.

    Raises:
        TaxiDataError: If ``value`` is not an integer (a ``bool`` is rejected).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TaxiDataError(f"expected integer for {field}, got {value!r}")
    return value
