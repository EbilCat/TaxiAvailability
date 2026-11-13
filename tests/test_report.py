from __future__ import annotations

from src.grouping import Area
from src.report import LocatedArea, render_report


def test_render_report_matches_sample_layout():
    areas = [
        LocatedArea(Area(1.36, 103.99, 83), "Jewel Changi Basement, Singapore"),
        LocatedArea(Area(1.32, 103.86, 31), "107, Towner Road, Kallang, Singapore"),
    ]
    report = render_report(2003, areas)
    assert report == (
        "Total available taxis: 2003\n"
        "\n"
        "Top 2 areas with the most taxis:\n"
        "1. Lat: 1.36, Lon: 103.99 - 83 taxis\n"
        "   Location: Jewel Changi Basement, Singapore\n"
        "   Google Maps: https://www.google.com/maps/search/?api=1&query=1.36,103.99\n"
        "2. Lat: 1.32, Lon: 103.86 - 31 taxis\n"
        "   Location: 107, Towner Road, Kallang, Singapore\n"
        "   Google Maps: https://www.google.com/maps/search/?api=1&query=1.32,103.86"
    )


def test_render_report_header_reflects_area_count():
    areas = [LocatedArea(Area(1.3, 103.8, 5), "Somewhere, Singapore")]
    report = render_report(5, areas)
    assert "Top 1 areas with the most taxis:" in report
    assert report.startswith("Total available taxis: 5\n")


def test_render_report_with_no_areas():
    report = render_report(0, [])
    assert report == ("Total available taxis: 0\n\nTop 0 areas with the most taxis:")
