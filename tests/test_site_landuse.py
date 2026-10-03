"""The land-use census (`site_landuse`): what the ground is for, measured."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_extent  # noqa: E402
import site_landuse as LU  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}


def _site(buildings, roads=()):
    return {"name": "t", "ground": {"size_x": 60, "size_y": 60},
            "buildings": [dict(b) for b in buildings], "roads": list(roads), "paths": []}


def test_every_cell_has_exactly_one_use_and_the_building_is_its_footprint():
    site = _site([{"id": "B", "at": [0, 0], "rot": 0, "_footprint": [10, 10]}])
    c = LU.census(site)
    assert c["ok"]
    assert abs(sum(c["shares"].values()) - 1.0) < 1e-3
    assert abs(sum(c["areas"].values()) - c["plate_area"]) < 1.0
    assert abs(c["areas"]["building"] - 100.0) <= 10.5            # one cell row of slack a side
    assert c["areas"]["remainder"] == c["plate_area"] - c["areas"]["building"]
    assert c["remainder_largest_blob"] == c["areas"]["remainder"]  # one piece, round the building
    x0, y0, x1, y1 = site_extent.resolve(site).rect
    assert c["plate"] == [round(v, 2) for v in (x0, y0, x1, y1)]


def test_a_road_and_its_sidewalks_are_counted_as_theirs():
    road = {"a": [-40, -20], "b": [40, -20], "width": 10.0, "sidewalk": 3.0}
    c = LU.census(_site([{"id": "B", "at": [0, 0], "rot": 0, "_footprint": [10, 10]}], [road]))
    # the road's own 80 m, not the plate's width: the plate runs on past its
    # ends by the extent's clearance (the first draft of this test assumed
    # otherwise and the census was right)
    assert abs(c["areas"]["road"] + c["areas"]["kerbcut"] - 10.0 * 80.0) <= 0.5 * 80.0
    assert c["plate"][2] - c["plate"][0] > 80.0
    assert c["areas"]["sidewalk"] > 0.0
    assert c["shares"]["remainder"] < 1.0 - c["shares"]["building"] - c["shares"]["road"] + 1e-6


def test_the_building_line_and_door_facing_are_read_per_road():
    """Two buildings on one road, one 2 m and one 9 m behind its back of
    walk; the first has a door on its road face, the second on its back."""
    road = {"a": [-40, -20], "b": [40, -20], "width": 10.0, "sidewalk": 3.0}
    back = -20 + 5.0 + 3.0                      # y of the back of walk
    a = {"id": "A", "at": [-15, back + 2.0 + 5.0], "rot": 0, "_footprint": [10, 10]}
    b = {"id": "C", "at": [15, back + 9.0 + 5.0], "rot": 0, "_footprint": [10, 10]}
    site = _site([a, b], [road])
    merged = {"buildings": [dict(a), dict(b)],
              "openings": [dict(_DOOR, building="A", wall="ext_0_S", story=0, x=0, y=-5),
                           dict(_DOOR, building="C", wall="ext_0_N", story=0, x=0, y=5)]}
    c = LU.census(site, merged)
    (r,) = c["roads"]
    by = {f["building"]: f for f in r["fronting"]}
    assert abs(by["A"]["setback"] - 2.0) < 1e-6 and abs(by["C"]["setback"] - 9.0) < 1e-6
    assert r["setback_spread"] == 7.0
    assert by["A"]["door_faces_road"] is True and by["C"]["door_faces_road"] is False
    # 20 m of building along an 80 m road's one side
    side = "left" if by["A"]["side"] > 0 else "right"
    assert abs(r["frontage_occupancy"][side] - 20.0 / r["length"]) < 1e-3


def test_separation_is_exterior_to_exterior():
    site = _site([{"id": "A", "at": [-9, 0], "rot": 0, "_footprint": [10, 10]},
                  {"id": "C", "at": [9, 0], "rot": 0, "_footprint": [10, 10]}])
    c = LU.census(site)
    assert c["nearest_building_gap"] == {"A": 8.0, "C": 8.0}


def test_a_surface_family_it_does_not_know_is_said():
    assert LU.census(_site([]))["unknown_families"] == []
