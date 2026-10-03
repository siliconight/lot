"""A dumpster at each building's service side (Lot 0.90.0)."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_dumpsters as SD  # noqa: E402
import site_streets  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}
_WINDOW = {"kind": "window", "width": 1.6, "height": 1.2, "sill": 1.1}
W, D, H = SD.DIMS


def _site(bldgs, roads=(), paths=()):
    return {"name": "t", "buildings": [dict(b) for b in bldgs], "roads": list(roads), "paths": list(paths)}


def _merged(bldgs, ops):
    return {"buildings": [dict(b) for b in bldgs], "openings": list(ops)}


def _plan(site, ops, **kw):
    findings = []
    got = SD.plan_dumpsters(site, _merged(site["buildings"], ops), site_streets.roads(site),
                            findings=findings, **kw)
    return got, findings


_B = {"id": "b0", "at": [0, 0], "rot": 0, "_footprint": [20, 10]}
_SOUTH_ROAD = {"a": [-40, -14], "b": [40, -14], "width": 10.0, "sidewalk": 3.0}
_FRONT = dict(_DOOR, building="b0", wall="ext_0_S", story=0, x=0, y=-5)


def test_it_stands_at_the_back_facing_away_a_gap_off_the_wall():
    (p,), findings = _plan(_site([_B], [_SOUTH_ROAD]), [_FRONT])
    assert findings == []
    assert p["species"] == "dumpster" and p["wall"] == "N" and p["building"] == "b0"
    assert p["yaw"] == 180.0                               # the front faces north, away from the wall
    assert abs(p["at"][1] - (5.0 + 0.25 + D / 2)) < 1e-6          # a quarter metre off the wall
    # toward a corner: its near side CORNER_IN from the wall's end
    assert abs(abs(p["at"][0]) - (10.0 - SD.CORNER_IN - W / 2)) < 1e-6
    assert p["dims"] == [W, D, H] and p["size"] == [W, H, D] and p["base"] == "plate"
    assert 0 <= p["variant"] < SD.VARIANTS


def test_never_against_a_street_face():
    """Roads front and back: both long walls are street faces, so it goes to
    a side, turned to run along it."""
    north = {"a": [-40, 14], "b": [40, 14], "width": 10.0, "sidewalk": 3.0}
    (p,), _f = _plan(_site([_B], [_SOUTH_ROAD, north]), [_FRONT])
    assert p["wall"] in ("E", "W")
    assert p["yaw"] == (90.0 if p["wall"] == "E" else 270.0)
    assert p["size"] == [D, H, W]
    assert abs(abs(p["at"][0]) - (10.0 + 0.25 + D / 2)) < 1e-6


def test_it_keeps_clear_of_a_back_door_and_stays_out_from_under_a_window():
    """Back doors at x -8 and 8, right where the corner stations are: it
    steps in along the back until its near side is 2.5 m from the door's
    edge. The literals are the rule; a constant read back from the module
    would pass whatever it said."""
    ops = [_FRONT,
           dict(_DOOR, building="b0", wall="ext_0_N", story=0, x=-8.0, y=5),
           dict(_DOOR, building="b0", wall="ext_0_N", story=0, x=8.0, y=5)]
    (p,), _f = _plan(_site([_B], [_SOUTH_ROAD]), ops)
    assert p["wall"] == "N"
    for door_x in (-8.0, 8.0):
        assert abs(p["at"][0] - door_x) - W / 2 - 0.6 >= 2.5 - 1e-9, p["at"]
    # the first station that clears: five steps in from the corner
    assert abs(abs(p["at"][0]) - (10.0 - 0.6 - W / 2 - 5.0)) < 1e-6, p["at"]
    # a window on the centre line: half a metre from its edge, at least
    ops.append(dict(_WINDOW, building="b0", wall="ext_0_N", story=0, x=p["at"][0], y=5))
    (q,), _f = _plan(_site([_B], [_SOUTH_ROAD]), ops)
    assert not (q["wall"] == "N" and abs(q["at"][0] - p["at"][0]) - W / 2 - 0.8 < 0.5 - 1e-9), q


def test_a_neighbour_s_door_is_never_boxed_in():
    """Roads front and back, a walk down the west side, and a neighbour 4 m
    to the east whose west doors' approach points line the gap: every
    station on b0's east wall stands within a body's staging depth of one,
    so b0 gets none and says so."""
    north = {"a": [-40, 14], "b": [60, 14], "width": 10.0, "sidewalk": 3.0}
    south = dict(_SOUTH_ROAD, b=[60, -14])
    b1 = {"id": "b1", "at": [19, 0], "rot": 0, "_footprint": [10, 10]}
    ops = [_FRONT] + [dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=y) for y in (-3.4, 0.0, 3.4)]
    west_walk = (-13.0, -6.0, -10.0, 6.0)
    got, findings = _plan(_site([_B, b1], [south, north]), ops, keep_out=[west_walk])
    assert [p for p in got if p["building"] == "b0"] == [], got
    assert any(f.startswith("LOT_DUMPSTER_NO_ROOM") and "b0" in f for f in findings), findings


def test_it_stays_off_walks_what_stands_and_the_plate_s_edge():
    site = _site([_B], [_SOUTH_ROAD])
    back = (-12.0, 5.0, 12.0, 8.0)                 # a walk along the whole back
    (p,), _f = _plan(site, [_FRONT], keep_out=[back])
    assert p["wall"] in ("E", "W")
    (q,), _f = _plan(site, [_FRONT], standing=[back])
    assert q["wall"] in ("E", "W")
    # a plate that ends a metre behind the building: no room at the back
    (r,), _f = _plan(site, [_FRONT], ground=(-40.0, -30.0, 40.0, 6.0))
    assert r["wall"] in ("E", "W")


def test_no_room_is_said_and_nothing_is_stood():
    """Roads on all four sides."""
    roads = [_SOUTH_ROAD, {"a": [-40, 14], "b": [40, 14], "width": 10.0, "sidewalk": 3.0},
             {"a": [-24, -40], "b": [-24, 40], "width": 10.0, "sidewalk": 3.0},
             {"a": [24, -40], "b": [24, 40], "width": 10.0, "sidewalk": 3.0}]
    got, findings = _plan(_site([_B], roads), [_FRONT])
    assert got == []
    assert len(findings) == 1 and findings[0].startswith("LOT_DUMPSTER_NO_ROOM") and "b0" in findings[0]


def test_a_row_of_buildings_gets_one_each_and_they_do_not_share_a_station():
    bldgs = [dict(_B, id=f"b{i}", at=[i * 30, 0]) for i in range(4)]
    ops = [dict(_FRONT, building=b["id"]) for b in bldgs]
    got, findings = _plan(_site(bldgs, [dict(_SOUTH_ROAD, a=[-40, -14], b=[130, -14])]), ops)
    assert findings == [] and [p["building"] for p in got] == ["b0", "b1", "b2", "b3"]
    assert len({(p["at"][0], p["at"][1]) for p in got}) == 4
    # which corner and which hauler are the building's own id's
    again, _f = _plan(_site(bldgs, [dict(_SOUTH_ROAD, a=[-40, -14], b=[130, -14])]), ops)
    assert again == got


def test_the_slot_carries_the_hauler_and_the_module_s_name_does(tmp_path):
    site = _site([_B], [_SOUTH_ROAD])
    (p,), _f = _plan(site, [_FRONT])
    p["variant"] = 2
    site["cover"] = [p]
    out = tmp_path / "t.slots.json"
    assert lot.write_site_slots(site, str(out)) == 1
    (slot,) = json.loads(out.read_text(encoding="utf-8"))["slots"]
    assert slot["species"] == "dumpster" and slot["variant"] == 2
    assert slot["material"] == "metal_painted" and slot["fit"]["dims"] == [W, D, H]
    assert slot["transform"]["rot_y"] == 180.0
    assert slot["transform"]["translation"][2] == round(H / 2, 4)          # on the plate
    assert lot.cover_module_stem("dumpster", "delco_1997", 1, [W, D, H], variant=2) \
        == "prop_dumpster_delco_1997_01_w183_d110_h130_n2"


def test_lot_knows_the_species():
    import site_furniture
    assert site_furniture.SPECIES["dumpster"] == SD.DIMS
    assert lot.COVER_MATERIALS["dumpster"] == "metal_painted"
