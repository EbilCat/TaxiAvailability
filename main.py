"""Entry point: report the areas with the most available taxis in Singapore.

Wires the pipeline together: fetch the realtime GeoJSON (or read a saved snapshot
with ``--source``), pack it into a validated :class:`TaxiAvailability`, group the
points into areas using the configured strategy, reverse-geocode the busiest
areas, and print the report in the assignment's sample layout.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from src.config import load_config
from src.fetcher import fetch_taxi_data
from src.geocoding import GeocodingError, NominatimGeocoder
from src.grouping import DEFAULT_RADIUS_M, DEFAULT_STRATEGY, STRATEGIES, rank_areas
from src.model import TaxiAvailability
from src.report import LocatedArea, render_report


def main(argv: list[str] | None = None) -> None:
    """Run the full taxi-availability pipeline and print the report.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    args = parse_args(argv)
    config = load_config(
        args.config,
        strategy=args.strategy,
        top_n=args.top,
        radius_m=args.radius_m,
        precision=args.precision,
    )
    geojson = _load_source(args.source)
    snapshot = TaxiAvailability.from_geojson(geojson)

    top_areas = rank_areas(
        snapshot.points,
        strategy=config.strategy,
        top_n=config.top_n,
        radius_m=config.radius_m,
        precision=config.precision,
    )
    geocoder = NominatimGeocoder()
    located = [
        LocatedArea(area=area, address=_locate(geocoder, area.lat, area.lon))
        for area in top_areas
    ]
    print(render_report(snapshot.taxi_count, located))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Flags left unset default to ``None`` so :func:`load_config` can tell an
    explicit choice from an unset one (CLI overrides the config file and
    defaults).

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        The parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Report the top areas with the most available taxis in Singapore."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Read taxi-availability GeoJSON from a local file instead of the "
            "live API (useful offline, e.g. a saved sample fixture)."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="TOML config file of grouping settings (CLI flags override it).",
    )
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default=None,
        help=f"Grouping strategy (default {DEFAULT_STRATEGY}).",
    )
    parser.add_argument(
        "--top",
        type=_positive_int,
        default=None,
        metavar="N",
        help="Number of top areas to report (default 10).",
    )
    parser.add_argument(
        "--radius-m",
        type=_positive_float,
        default=None,
        metavar="METRES",
        help=(
            "Radius in metres of each area's footprint, hotspot strategy only "
            f"(default {DEFAULT_RADIUS_M:g})."
        ),
    )
    parser.add_argument(
        "--precision",
        type=_nonneg_int,
        default=None,
        metavar="DP",
        help="Decimal places for the reported coordinate (default 2).",
    )
    return parser.parse_args(argv)


def _load_source(source: Path | None) -> dict[str, object]:
    """Load taxi-availability GeoJSON from a file or the live API.

    Args:
        source: Path to a saved GeoJSON snapshot, or ``None`` to fetch live.

    Returns:
        The parsed GeoJSON response as a dictionary.
    """
    if source is None:
        return fetch_taxi_data()
    return json.loads(source.read_text(encoding="utf-8"))


def _locate(geocoder: NominatimGeocoder, lat: float, lon: float) -> str:
    """Reverse-geocode a coordinate, degrading to a notice rather than failing.

    A single failed lookup should not sink the whole report, so geocoding errors
    become an explicit "unavailable" note instead of an exception.

    Args:
        geocoder: The reverse geocoder.
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.

    Returns:
        The address in words, or a short notice if the lookup failed.
    """
    try:
        return geocoder.reverse_geocode(lat, lon)
    except (GeocodingError, httpx.HTTPError) as exc:
        return f"(location unavailable: {exc})"


def _positive_int(value: str) -> int:
    """Parse a strictly positive integer for argparse.

    Args:
        value: The raw argument string.

    Returns:
        The parsed integer.

    Raises:
        argparse.ArgumentTypeError: If ``value`` is not a positive integer.
    """
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}") from exc
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {number}")
    return number


def _nonneg_int(value: str) -> int:
    """Parse a non-negative integer for argparse.

    Args:
        value: The raw argument string.

    Returns:
        The parsed integer.

    Raises:
        argparse.ArgumentTypeError: If ``value`` is not a non-negative integer.
    """
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}") from exc
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {number}")
    return number


def _positive_float(value: str) -> float:
    """Parse a strictly positive float for argparse.

    Args:
        value: The raw argument string.

    Returns:
        The parsed float.

    Raises:
        argparse.ArgumentTypeError: If ``value`` is not a positive number.
    """
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a number, got {value!r}") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {number}")
    return number


if __name__ == "__main__":
    main()
