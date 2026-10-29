"""What stands outside a shop's door (Lot 0.137.0)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_frontage as SF  # noqa: E402
import site_streets  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}
#: Level Factory stands a building's face FRONTAGE (2 m) back from its sidewalk: the wall at y -5, the band's back
#: edge at -7 (road centre -15, half width 5, sidewalk 3)
_SOUTH_ROAD = {"a": [-40, -15], "b": [40, -15], "width": 10.0, "sidewalk": 3.0}


def _site(bldgs, roads=(), paths=()):
    return {"name": "t", "buildings": [dict(b) for b in bldgs], "roads": list(roads), "paths": list(paths)}


def _plan(archetype, ops=None, **kw):
    """A site spec's building as Lot holds it: the site's id `b0`, the library's name as its `archetype`."""
    bid = "b0"
    b = {"id": bid, "archetype": archetype, "at": [0, 0], "rot": 0, "_footprint": [20, 10],
         "front": {"wall": "S"}}
    ops = [dict(o, building=bid) for o in ops] if ops is not None else [
        dict(_DOOR, building=bid, wall="ext_0_S", story=0, x=0, y=-5)]
    site = _site([b], [_SOUTH_ROAD])
    findings = []
    got = SF.plan_frontage(site, {"buildings": [b], "openings": ops}, site_streets.roads(site),
                           findings=findings, **kw)
    return got, findings


def test_a_shop_keeps_a_soda_machine_crates_and_a_news_box_beside_its_door():
    """FAILS ON 0.136.0: no site_frontage. Against the street face, to one side of the door, nearest first, facing
    out, a gap off the wall, every piece clear of the door's approach point."""
    got, findings = _plan("gas_station_a02")
    assert findings == []
    assert [p["species"] for p in got] == ["vending_machine", "milk_crate_stack", "newspaper_box"]
    xs = [p["at"][0] for p in got]
    assert all(x > 0 for x in xs) or all(x < 0 for x in xs)          # one side of the door
    assert [abs(x) for x in xs] == sorted(abs(x) for x in xs)        # the machine nearest
    for p in got:
        assert p["wall"] == "S" and p["yaw"] == 0.0 and p["base"] == "plate"     # front to the street
        w, d, _h = p["dims"]
        assert abs(p["at"][1] - (-5.0 - SF.WALL_GAP - d / 2)) < 1e-6
        # the door's approach point is 1.5 m out from its centre: clear of it by APPROACH_CLEAR
        near = abs(p["at"][0]) - w / 2
        assert near >= 0.6 + SF.DOOR_CLEAR - 1e-9


def test_a_bank_and_a_house_keep_a_clear_front():
    for bid in ("bank_branch_a02", "credit_union_a01", "gs_empty_rowhome_a", "train_yard_a01"):
        assert _plan(bid)[0] == [], bid
    assert SF.is_shop("card_shop_a01") and SF.is_shop("primos_pizza_a01") and not SF.is_shop("bank_job")


def test_no_way_in_on_a_street_face_is_said_and_gets_nothing():
    ops = [dict(_DOOR, wall="ext_0_N", story=0, x=0, y=5)]
    got, findings = _plan("deli_a01", ops)
    assert got == [] and any(f.startswith("LOT_FRONTAGE_NO_ROOM") for f in findings)


def test_a_walk_beside_the_door_pushes_the_group_along_and_never_into_it():
    """A walk 1 m either side of the door's edges: every piece steps clear of it."""
    walk = (-4.0, -8.0, 4.0, -5.0)
    got, _f = _plan("video_store_a01", keep_out=[walk])
    assert got
    for p in got:
        w, d, _h = p["dims"]
        assert abs(p["at"][0]) - w / 2 >= 4.0 - 1e-9, p["at"]
