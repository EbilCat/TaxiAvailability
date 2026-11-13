"""Group taxi positions into geographical areas by a fixed lat/lon grid.

The pure processing core: bin each taxi's ``(lat, lon)`` into a grid cell by
rounding to a fixed number of decimals, count the taxis per cell, and return the
cells ordered by taxi count. No I/O — it operates on the validated
:class:`~src.model.Point` values produced at the network boundary, so it is
fully unit-testable offline.

At ``precision=2`` each cell is ~1.1 km square near the equator, which is why
"most taxis per cell" equals "highest concentration": every cell covers the same
area. The reported coordinate is the rounded grid label (not a centroid), which
matches the assignment's sample output.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.model import Point

__all__ = ["DEFAULT_PRECISION", "Area", "group_into_areas"]

DEFAULT_PRECISION = 2


def group_into_areas(
    points: Sequence[Point], precision: int = DEFAULT_PRECISION
) -> list[Area]:
    """Group taxi positions into grid cells, ordered by descending taxi count.

    Each point is binned by rounding its latitude and longitude to ``precision``
    decimal places; the rounded pair becomes the cell's label and representative
    coordinate. Cells are returned sorted by taxi count (highest first), with
    ties broken by latitude then longitude so the ordering is deterministic.

    Args:
        points: Validated taxi positions (``(lat, lon)``).
        precision: Decimal places to round coordinates to when forming cells.
            ``2`` (the default) gives ~1.1 km cells. Lower is coarser.

    Returns:
        All occupied cells as :class:`Area` values, sorted by ``(-count, lat,
        lon)``. The total of every area's ``count`` equals ``len(points)``.
    """
    counts = Counter(
        (round(point.lat, precision), round(point.lon, precision)) for point in points
    )
    areas = [
        Area(lat=lat, lon=lon, count=count) for (lat, lon), count in counts.items()
    ]
    areas.sort(key=lambda area: (-area.count, area.lat, area.lon))
    return areas


@dataclass(frozen=True, slots=True)
class Area:
    """A grid cell and the number of available taxis within it.

    Attributes:
        lat: Cell latitude label (a rounded grid coordinate), in decimal degrees.
        lon: Cell longitude label (a rounded grid coordinate), in decimal degrees.
        count: Number of available taxis whose position falls in this cell.
    """

    lat: float
    lon: float
    count: int
