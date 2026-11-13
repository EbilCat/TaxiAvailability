"""Entry point: report the areas with the most available taxis in Singapore.

Wires the imperative shell together — fetch the realtime GeoJSON (or read a saved
snapshot with ``--source``), pack it into a validated :class:`TaxiAvailability`
snapshot, then (in later steps) group the points into areas, reverse-geocode the
top ones, and render the report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.fetcher import fetch_taxi_data
from src.model import TaxiAvailability


def main(argv: list[str] | None = None) -> None:
    """Fetch (or load) the current taxi availability and print a summary.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    args = parse_args(argv)
    geojson = _load_source(args.source)
    snapshot = TaxiAvailability.from_geojson(geojson)
    print(f"Total available taxis: {snapshot.taxi_count}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        The parsed arguments namespace with a ``source`` attribute (a
        ``pathlib.Path`` to a saved GeoJSON snapshot, or ``None`` to fetch live).
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


if __name__ == "__main__":
    main()
