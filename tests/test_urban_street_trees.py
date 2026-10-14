"""An urban street plants a city block's trees (Lot 0.123.0, factory roadmap 241).

The urban comps show street trees in pits along both sidewalks; Lot planted a tree halfway between lamps 25 m
apart, a Delco strip's spacing. Philadelphia's own siting guidelines (the factory root's
`docs/reference/STREET_TREES.md`: PHS / TreeVitalize, 2010) say 15 to 30 ft between trees by mature size and
30 ft from a street corner. On a site that says it is urban, each sidewalk now plants a tree every 30 ft, each
block's row centred between corners kept 30 ft clear; a strip plants as it did.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_furniture  # noqa: E402
import site_streets  # noqa: E402

#: 9233's block, reduced, as `test_lane_lamps.py` holds it: the main street and two side streets
STREETS = [{"a": [-90.0, -21.665], "b": [90.0, -21.665], "width": 10.0, "sidewalk": 3.0},
           {"a": [-20.0, -21.665], "b": [-20.0, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [75.0, -21.665], "b": [75.0, 32.0], "width": 10.0, "sidewalk": 3.0}]
ROW = [{"id": "b1", "at": [4.0, -2.51], "rot": 0}, {"id": "b2", "at": [48.0, 0.49], "rot": 0}]


def _plan(**kw):
    roads = site_streets.roads({"name": "trees", "buildings": ROW, "roads": STREETS, "paths": [],
                                "ground": {"size_x": 200.0, "size_y": 120.0}})
    return roads, site_furniture.plan_furniture(roads, ROW, [], [], **kw)


def _trees(pieces, road=0):
    return sorted((p for p in pieces if p["road"] == road and p["species"] in site_furniture.TREES),
                  key=lambda p: (p["kerb"], p["t"]))


def test_a_strip_plants_as_it_did():
    _roads, strip = _plan(urban=False)
    _roads, default = _plan()
    assert strip == default


def test_an_urban_street_plants_a_tree_every_thirty_feet():
    roads, urban = _plan(urban=True)
    _roads, strip = _plan(urban=False)
    assert abs(site_furniture.URBAN_TREE_SPACING - 30 * 0.3048) < 1e-9
    trees = _trees(urban)
    assert len(trees) >= 2.5 * len(_trees(strip)), (len(trees), len(_trees(strip)))
    for kerb in roads[0].kerbs:
        row = [p["t"] for p in trees if p["kerb"] == kerb.side]
        stations = site_furniture.urban_tree_stations(roads[0], kerb)
        assert row == [round(s, 3) for s in stations], (kerb.side, row, stations)   # `_piece` keeps t to 3 places
        for a, b in zip(stations, stations[1:]):
            gap = b - a
            assert abs(gap - site_furniture.URBAN_TREE_SPACING) < 1e-6 or gap > site_furniture.URBAN_TREE_SPACING, gap


def test_a_tree_keeps_thirty_feet_from_a_corner():
    roads, _urban = _plan(urban=True)
    for kerb in roads[0].kerbs:
        corners = [(c.t - c.span / 2.0, c.t + c.span / 2.0) for c in kerb.cuts if c.kind == "road"]
        for t in site_furniture.urban_tree_stations(roads[0], kerb):
            for c0, c1 in corners:
                assert t <= c0 - site_furniture.URBAN_TREE_CORNER + 1e-6 or t >= c1 + site_furniture.URBAN_TREE_CORNER - 1e-6, \
                    (kerb.side, t, c0, c1)


def test_the_poles_and_the_corner_hydrants_still_stand():
    _roads, urban = _plan(urban=True)
    _roads, strip = _plan(urban=False)
    for species in ("utility_pole", "fire_hydrant"):
        u = [p for p in urban if p["species"] == species or p.get("form") == species]
        s = [p for p in strip if p["species"] == species or p.get("form") == species]
        assert len(u) == len(s), (species, len(u), len(s))
