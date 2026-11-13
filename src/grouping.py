"""Group taxi positions into areas, ranked by taxi count.

Two interchangeable strategies, dispatched by :func:`rank_areas`:

- **grid** (:func:`group_into_areas`) — bin each taxi onto a fixed lat/lon grid
  by rounding its coordinate. Pure, zero extra dependencies, and the reported
  point is the grid-cell label. Simple, but a crowd that straddles a cell
  boundary is split across cells.
- **hotspot** (:func:`find_hotspots`) — grow each area from the densest taxi
  outward within a fixed radius (a greedy, non-overlapping search), so a crowd is
  captured whole regardless of where it sits. Uses numpy; the reported point is
  the member centroid.

Both are pure (no I/O), deterministic, and return ranked :class:`Area` values, so
they are unit-testable offline and freely swappable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.model import Point

__all__ = [
    "DEFAULT_PRECISION",
    "DEFAULT_RADIUS_M",
    "DEFAULT_STRATEGY",
    "STRATEGIES",
    "Area",
    "find_hotspots",
    "group_into_areas",
    "rank_areas",
]

EARTH_RADIUS_M = 6_371_000.0
DEFAULT_RADIUS_M = 500.0
DEFAULT_PRECISION = 2
DEFAULT_STRATEGY = "hotspot"
STRATEGIES = ("grid", "hotspot")
_NEIGHBOUR_CHUNK = 512


def rank_areas(
    points: Sequence[Point],
    *,
    strategy: str = DEFAULT_STRATEGY,
    top_n: int = 10,
    radius_m: float = DEFAULT_RADIUS_M,
    precision: int = DEFAULT_PRECISION,
) -> list[Area]:
    """Rank the top ``top_n`` areas using the chosen grouping strategy.

    Args:
        points: Validated taxi positions (``(lat, lon)``).
        strategy: ``"grid"`` or ``"hotspot"`` (see module docstring).
        top_n: Maximum number of areas to return.
        radius_m: Hotspot footprint radius in metres (``"hotspot"`` only).
        precision: Decimal places for the reported coordinate (grid cell size
            for ``"grid"``; centroid rounding for ``"hotspot"``).

    Returns:
        The top areas, highest taxi count first.

    Raises:
        ValueError: If ``strategy`` is not one of :data:`STRATEGIES` (or a
            strategy's own argument is invalid).
    """
    if strategy == "grid":
        return group_into_areas(points, precision=precision)[:top_n]
    if strategy == "hotspot":
        return find_hotspots(
            points, radius_m=radius_m, top_n=top_n, precision=precision
        )
    raise ValueError(f"unknown strategy {strategy!r}; expected one of {STRATEGIES}")


def group_into_areas(
    points: Sequence[Point], precision: int = DEFAULT_PRECISION
) -> list[Area]:
    """Group taxis onto a fixed lat/lon grid, ordered by descending taxi count.

    Each point is binned by rounding its latitude and longitude to ``precision``
    decimals; the rounded pair is the cell's label and representative coordinate.
    Cells are sorted by count (highest first), ties broken by latitude then
    longitude for determinism.

    Args:
        points: Validated taxi positions (``(lat, lon)``).
        precision: Decimal places to round coordinates to when forming cells.
            ``2`` (the default) gives ~1.1 km cells.

    Returns:
        All occupied cells as :class:`Area` values, sorted by ``(-count, lat,
        lon)``. The areas' counts sum to ``len(points)``.
    """
    counts = Counter(
        (round(point.lat, precision), round(point.lon, precision)) for point in points
    )
    areas = [
        Area(lat=lat, lon=lon, count=count) for (lat, lon), count in counts.items()
    ]
    areas.sort(key=lambda area: (-area.count, area.lat, area.lon))
    return areas


def find_hotspots(
    points: Sequence[Point],
    *,
    radius_m: float = DEFAULT_RADIUS_M,
    top_n: int = 10,
    precision: int = DEFAULT_PRECISION,
    min_taxis: int = 1,
) -> list[Area]:
    """Find the ``top_n`` non-overlapping areas with the most taxis.

    Grows each area from the densest still-unassigned taxi outward within
    ``radius_m``. Every area is the same circular footprint, so counts are
    directly comparable as concentration. The reported coordinate is the member
    centroid, rounded to ``precision`` decimals.

    Distances use an equirectangular projection to local metres — at Singapore's
    latitude over a ~50 km extent this is accurate to well under 1%, far below
    the precision of "approximate area".

    Args:
        points: Validated taxi positions (``(lat, lon)``).
        radius_m: Radius of each area's circular footprint, in metres.
        top_n: Maximum number of areas to return.
        precision: Decimal places to round the reported centroid to.
        min_taxis: Stop once the best remaining area has fewer taxis than this,
            so lone taxis are not reported as "areas".

    Returns:
        Areas sorted by taxi count (highest first); fewer than ``top_n`` if taxis
        run out or ``min_taxis`` cuts it short. Member sets are disjoint, so the
        areas' counts sum to at most ``len(points)``.

    Raises:
        ValueError: If ``radius_m`` or ``top_n`` is not positive.
    """
    if radius_m <= 0:
        raise ValueError(f"radius_m must be positive, got {radius_m}")
    if top_n <= 0:
        raise ValueError(f"top_n must be positive, got {top_n}")
    if not points:
        return []

    lat = np.array([p.lat for p in points], dtype=float)
    lon = np.array([p.lon for p in points], dtype=float)
    # Sort by (lat, lon) so ties resolve identically regardless of API order.
    order = np.lexsort((lon, lat))
    lat, lon = lat[order], lon[order]
    xy = _project_to_metres(lat, lon)
    neighbours = _neighbours_within(xy, radius_m)

    counts = np.array([len(cell) for cell in neighbours], dtype=np.int64)
    alive = np.ones(len(points), dtype=bool)

    areas: list[Area] = []
    while len(areas) < top_n and alive.any():
        candidate_counts = np.where(alive, counts, -1)
        seed = int(np.argmax(candidate_counts))  # lowest index wins ties
        if candidate_counts[seed] < min_taxis:
            break

        members = neighbours[seed][alive[neighbours[seed]]]
        alive[members] = False
        for member in members:
            counts[neighbours[member]] -= 1

        areas.append(
            Area(
                lat=round(float(lat[members].mean()), precision),
                lon=round(float(lon[members].mean()), precision),
                count=int(members.size),
            )
        )

    return areas


@dataclass(frozen=True, slots=True)
class Area:
    """An area of taxi concentration and the number of taxis within it.

    Attributes:
        lat: Representative latitude (grid-cell label or member centroid).
        lon: Representative longitude (grid-cell label or member centroid).
        count: Number of available taxis assigned to this area.
    """

    lat: float
    lon: float
    count: int


def _project_to_metres(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Project latitude/longitude degrees to local ``(x, y)`` metres.

    Uses an equirectangular projection centred on the data's mean latitude.

    Args:
        lat: Latitudes in decimal degrees.
        lon: Longitudes in decimal degrees.

    Returns:
        An ``(n, 2)`` array of ``(x, y)`` positions in metres.
    """
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    x = EARTH_RADIUS_M * lon_rad * np.cos(lat_rad.mean())
    y = EARTH_RADIUS_M * lat_rad
    return np.column_stack((x, y))


def _neighbours_within(xy: np.ndarray, radius_m: float) -> list[np.ndarray]:
    """List, for each point, the indices within ``radius_m`` metres (incl. self).

    Computes squared distances in row chunks to bound memory for large inputs,
    avoiding a full ``n x n`` distance matrix.

    Args:
        xy: An ``(n, 2)`` array of projected ``(x, y)`` metre positions.
        radius_m: Neighbour radius in metres.

    Returns:
        A list of ``n`` index arrays; entry ``i`` holds the indices of all points
        within ``radius_m`` of point ``i``.
    """
    radius_sq = radius_m * radius_m
    neighbours: list[np.ndarray] = []
    for start in range(0, len(xy), _NEIGHBOUR_CHUNK):
        block = xy[start : start + _NEIGHBOUR_CHUNK]
        diff = block[:, None, :] - xy[None, :, :]
        dist_sq = np.einsum("bnk,bnk->bn", diff, diff)
        neighbours.extend(np.nonzero(row <= radius_sq)[0] for row in dist_sq)
    return neighbours
