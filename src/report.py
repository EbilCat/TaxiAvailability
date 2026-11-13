"""Render the taxi-availability report text.

Pure formatting: given the total taxi count and the top areas already paired with
their reverse-geocoded addresses, produce the human-readable report in the
assignment's sample layout. No I/O, so the exact wording is unit-testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.geocoding import google_maps_link

if TYPE_CHECKING:
    from src.grouping import Area

__all__ = ["LocatedArea", "render_report"]


def render_report(total: int, areas: Sequence[LocatedArea]) -> str:
    """Render the report of total taxis and the top areas, in sample layout.

    Args:
        total: Total number of available taxis.
        areas: The ranked areas, each paired with its address, in display order.

    Returns:
        The formatted multi-line report string (no trailing newline).
    """
    lines = [
        f"Total available taxis: {total}",
        "",
        f"Top {len(areas)} areas with the most taxis:",
    ]
    for rank, located in enumerate(areas, start=1):
        area = located.area
        lines.append(f"{rank}. Lat: {area.lat}, Lon: {area.lon} - {area.count} taxis")
        lines.append(f"   Location: {located.address}")
        lines.append(f"   Google Maps: {google_maps_link(area.lat, area.lon)}")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class LocatedArea:
    """An area paired with its reverse-geocoded address, ready to render.

    Attributes:
        area: The grid cell and its taxi count.
        address: The address in words for the cell's coordinate.
    """

    area: Area
    address: str
