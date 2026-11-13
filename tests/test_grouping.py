from __future__ import annotations

import json
from pathlib import Path

from src.grouping import Area, group_into_areas
from src.model import Point, TaxiAvailability

FIXTURE = Path(__file__).parent / "fixtures" / "taxi_availability_sample.json"


def _points(*pairs: tuple[float, float]) -> list[Point]:
    return [Point(lat=lat, lon=lon) for lat, lon in pairs]


def test_empty_points_give_no_areas():
    assert group_into_areas([]) == []


def test_single_point_rounds_to_its_cell():
    areas = group_into_areas(_points((1.3627, 103.9891)))
    assert areas == [Area(lat=1.36, lon=103.99, count=1)]


def test_points_in_same_cell_are_counted_together():
    areas = group_into_areas(_points((1.361, 103.988), (1.364, 103.991)))
    assert areas == [Area(lat=1.36, lon=103.99, count=2)]


def test_points_in_different_cells_are_separate():
    areas = group_into_areas(_points((1.36, 103.99), (1.32, 103.86)))
    assert {(a.lat, a.lon) for a in areas} == {(1.36, 103.99), (1.32, 103.86)}
    assert all(a.count == 1 for a in areas)


def test_areas_sorted_by_descending_count():
    areas = group_into_areas(_points((1.36, 103.99), (1.36, 103.99), (1.32, 103.86)))
    assert [a.count for a in areas] == [2, 1]
    assert areas[0] == Area(lat=1.36, lon=103.99, count=2)


def test_ties_broken_by_lat_then_lon():
    # Three distinct cells, each with one taxi: ordered by lat, then lon.
    areas = group_into_areas(_points((1.30, 103.90), (1.30, 103.80), (1.20, 103.99)))
    assert [(a.lat, a.lon) for a in areas] == [
        (1.20, 103.99),
        (1.30, 103.80),
        (1.30, 103.90),
    ]


def test_counts_sum_to_number_of_points():
    pts = _points((1.36, 103.99), (1.36, 103.99), (1.32, 103.86), (1.30, 103.80))
    areas = group_into_areas(pts)
    assert sum(a.count for a in areas) == len(pts)


def test_lower_precision_merges_cells():
    pts = _points((1.361, 103.991), (1.369, 103.999))
    assert len(group_into_areas(pts, precision=2)) == 2
    assert group_into_areas(pts, precision=1) == [Area(lat=1.4, lon=104.0, count=2)]


def test_real_fixture_grouping_is_consistent():
    geojson = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot = TaxiAvailability.from_geojson(geojson)
    areas = group_into_areas(snapshot.points)
    assert sum(a.count for a in areas) == snapshot.taxi_count
    # Sorted strictly by the documented key.
    keys = [(-a.count, a.lat, a.lon) for a in areas]
    assert keys == sorted(keys)
    assert areas[0].count >= areas[-1].count
