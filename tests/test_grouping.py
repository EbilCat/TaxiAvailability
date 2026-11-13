from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.grouping import Area, find_hotspots, group_into_areas, rank_areas
from src.model import Point, TaxiAvailability

FIXTURE = Path(__file__).parent / "fixtures" / "taxi_availability_sample.json"


def _points(*pairs: tuple[float, float]) -> list[Point]:
    return [Point(lat=lat, lon=lon) for lat, lon in pairs]


def test_empty_points_give_no_areas():
    assert find_hotspots([]) == []


def test_non_positive_radius_raises():
    with pytest.raises(ValueError):
        find_hotspots(_points((1.3, 103.8)), radius_m=0)


def test_non_positive_top_n_raises():
    with pytest.raises(ValueError):
        find_hotspots(_points((1.3, 103.8)), top_n=0)


def test_single_point_is_one_area():
    areas = find_hotspots(_points((1.3627, 103.9891)))
    assert areas == [Area(lat=1.36, lon=103.99, count=1)]


def test_tight_crowd_collapses_to_one_area():
    # Four taxis within a few metres of each other -> one area of 4.
    crowd = _points(
        (1.3600, 103.9900),
        (1.36001, 103.99001),
        (1.35999, 103.98999),
        (1.36002, 103.99002),
    )
    areas = find_hotspots(crowd, radius_m=100)
    assert len(areas) == 1
    assert areas[0].count == 4
    assert areas[0] == Area(lat=1.36, lon=103.99, count=4)


def test_two_separated_crowds_ranked_by_size():
    # A crowd of 3 near Changi and a crowd of 2 far away in the west.
    points = _points(
        (1.3600, 103.9900),
        (1.36001, 103.99001),
        (1.35999, 103.98999),
        (1.3000, 103.6300),
        (1.30001, 103.63001),
    )
    areas = find_hotspots(points, radius_m=200)
    assert [a.count for a in areas] == [3, 2]
    assert areas[0].lon > areas[1].lon  # Changi (east) ranked first


def test_member_sets_are_disjoint():
    points = _points(
        (1.3600, 103.9900),
        (1.36001, 103.99001),
        (1.35999, 103.98999),
        (1.3000, 103.6300),
        (1.30001, 103.63001),
    )
    areas = find_hotspots(points, radius_m=200)
    assert sum(a.count for a in areas) == len(points)  # no taxi double-counted


def test_top_n_limits_results():
    # Five far-apart lone taxis; ask for only the top 2.
    points = _points(
        (1.30, 103.70),
        (1.32, 103.75),
        (1.34, 103.80),
        (1.36, 103.85),
        (1.38, 103.90),
    )
    areas = find_hotspots(points, radius_m=100, top_n=2)
    assert len(areas) == 2


def test_result_is_deterministic():
    points = _points((1.30, 103.80), (1.30, 103.81), (1.31, 103.80))
    first = find_hotspots(points, radius_m=2000)
    second = find_hotspots(points, radius_m=2000)
    assert first == second


def test_real_fixture_hotspots_are_sensible():
    geojson = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot = TaxiAvailability.from_geojson(geojson)
    areas = find_hotspots(snapshot.points, top_n=10)
    assert len(areas) == 10
    # Ranked by descending count, counts positive, members disjoint.
    assert [a.count for a in areas] == sorted((a.count for a in areas), reverse=True)
    assert all(a.count > 0 for a in areas)
    assert sum(a.count for a in areas) <= snapshot.taxi_count
    # Busiest area is around Changi Airport.
    top = areas[0]
    assert 1.34 <= top.lat <= 1.37 and 103.98 <= top.lon <= 104.00


# --- grid strategy -----------------------------------------------------------


def test_grid_single_point_rounds_to_its_cell():
    assert group_into_areas(_points((1.3627, 103.9891))) == [
        Area(lat=1.36, lon=103.99, count=1)
    ]


def test_grid_same_cell_counted_together_and_sorted():
    areas = group_into_areas(
        _points((1.361, 103.988), (1.364, 103.991), (1.32, 103.86))
    )
    assert areas[0] == Area(lat=1.36, lon=103.99, count=2)
    assert sum(a.count for a in areas) == 3


def test_grid_ties_broken_by_lat_then_lon():
    areas = group_into_areas(_points((1.30, 103.90), (1.30, 103.80), (1.20, 103.99)))
    assert [(a.lat, a.lon) for a in areas] == [
        (1.20, 103.99),
        (1.30, 103.80),
        (1.30, 103.90),
    ]


def test_grid_returns_all_cells_unsliced():
    # Grid returns every occupied cell; the caller slices the top N.
    areas = group_into_areas(_points((1.30, 103.80), (1.31, 103.81), (1.32, 103.82)))
    assert len(areas) == 3


# --- strategy dispatch -------------------------------------------------------


def test_rank_areas_grid_slices_to_top_n():
    points = _points((1.30, 103.80), (1.31, 103.81), (1.32, 103.82))
    assert len(rank_areas(points, strategy="grid", top_n=2)) == 2


def test_rank_areas_hotspot_matches_find_hotspots():
    points = _points((1.3600, 103.9900), (1.36001, 103.99001), (1.30, 103.63))
    dispatched = rank_areas(points, strategy="hotspot", top_n=5, radius_m=200)
    direct = find_hotspots(points, radius_m=200, top_n=5)
    assert dispatched == direct


def test_rank_areas_unknown_strategy_raises():
    with pytest.raises(ValueError):
        rank_areas(_points((1.3, 103.8)), strategy="nope")
