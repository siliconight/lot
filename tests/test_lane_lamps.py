"""A lane lights its own length (Lot 0.116.0): a road without a sidewalk stood no furniture, lamps
included, so the `block` grammar's service lane read black at dusk between two lit streets. Its
lamps are the street's own, on the side the buildings it runs behind stand, spread along its
slab no farther apart than `LANE_LAMP_SPACING`, beyond its paved edge and clear of the paths that
reach it; each becomes a light like any street lamp."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_cover  # noqa: E402
import site_furniture  # noqa: E402
import site_streets  # noqa: E402

#: 9233's block, reduced: the main street, two side streets and the lane between them
STREETS = [{"a": [-90.0, -21.665], "b": [90.0, -21.665], "width": 10.0, "sidewalk": 3.0},
           {"a": [-20.0, -21.665], "b": [-20.0, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [75.0, -21.665], "b": [75.0, 32.0], "width": 10.0, "sidewalk": 3.0}]
LANE = {"a": [-20.0, 27.185], "b": [75.0, 27.185], "width": 5.0, "sidewalk": 0.0,
        "kind": "service_lane", "serves": ["b1", "b2"]}
ROW = [{"id": "b1", "at": [4.0, -2.51], "rot": 0}, {"id": "b2", "at": [48.0, 0.49], "rot": 0}]


def _spec(paths=()):
    return {"name": "lane", "buildings": ROW, "roads": STREETS + [LANE], "paths": list(paths),
            "ground": {"size_x": 200.0, "size_y": 120.0}}


def _lane_lamps(spec, markers=()):
    roads = site_streets.roads(spec)
    findings = []
    pieces = site_furniture.plan_furniture(roads, spec["buildings"], list(markers), findings,
                                           keep_out=site_furniture.path_corridors(spec))
    return roads[3], [p for p in pieces if p["road"] == 3], pieces, findings


def _offset(lane, p):
    return (p["at"][0] - lane.a[0]) * lane.perp[0] + (p["at"][1] - lane.a[1]) * lane.perp[1]


def test_the_lane_stands_its_own_lamps_on_the_side_its_row_backs_onto():
    lane, lamps, _all, findings = _lane_lamps(_spec())
    s0, s1 = lane.slab
    want = max(1, round((s1 - s0) / site_furniture.LANE_LAMP_SPACING))
    assert len(lamps) == want >= 2, (len(lamps), lane.slab)
    assert not [f for f in findings if f.startswith("LOT_LANE_LAMP")], findings
    for p in lamps:
        assert p["species"] == "streetlight" and p["base"] == "ground" and p["lane"] is True
        # beyond the paved edge, on the row's side (the row is south: -y, right of travel)
        off = _offset(lane, p)
        assert off < 0 and abs(abs(off) - (2.5 + site_furniture.LANE_LAMP_OUT)) < 1e-3, off
        assert s0 < p["t"] < s1
    ts = sorted(p["t"] for p in lamps)
    # one pool ends before the next begins: farther apart than two 14 m reaches
    assert all(b - a > 28.0 for a, b in zip(ts, ts[1:])), ts


def test_a_rear_spur_that_stops_short_of_the_lane_keeps_its_mouth_clear():
    """Cold run 9237's spurs end 0.5 m short of the lane's paved edge, so they
    never cross the lane and its crossings cannot see them: only the spur's
    corridor says where it is. A lamp drafted without it stood on the spur's
    end, in front of a rear door's way to the lane."""
    lane, before, _a, _f = _lane_lamps(_spec())
    t = before[0]["t"]
    x = lane.a[0] + lane.along[0] * t
    spur = {"a": [x, 7.6], "b": [x, 24.185], "width": 2.0}
    _lane2, after, _a2, findings = _lane_lamps(_spec([spur]))
    assert len(after) == len(before), (after, before)
    assert not [f for f in findings if f.startswith("LOT_LANE_LAMP")], findings
    corridor = site_furniture.path_corridors(_spec([spur]))
    for p in after:
        rect = site_cover._grow(site_furniture._piece_rect(p), site_furniture.CUT_CLEARANCE)
        assert not any(site_furniture._rects_overlap(rect, k) for k in corridor), p["at"]
    near = min(after, key=lambda p: abs(p["t"] - t))
    assert abs(near["t"] - t) >= 1.0 + site_furniture.CUT_CLEARANCE, (near["t"], t)


def test_every_lane_lamp_becomes_a_light_on_its_pole_at_grade():
    _lane, lamps, _all, _f = _lane_lamps(_spec())
    anchors = lot._streetlight_anchors({"cover": lamps})
    assert len(anchors) == len(lamps)
    for a, p in zip(anchors, lamps):
        assert a["type"] == "streetlight" and a["pos"][:2] == p["at"]
        assert abs(a["pos"][2] - (p["dims"][2] - lot.STREETLIGHT_LENS_DROP)) < 1e-6   # no kerb under it


def test_the_streets_keep_their_bands_and_the_names_stay_the_sites():
    _lane, _lamps, pieces, _f = _lane_lamps(_spec())
    street = [p for p in pieces if p["road"] != 3]
    assert street and all(p.get("base") == "sidewalk" for p in street if p["species"] == "streetlight")
    names = [p["name"] for p in pieces]
    assert len(names) == len(set(names))


def test_a_lane_with_no_building_in_reach_lights_its_left():
    spec = _spec()
    spec["buildings"] = []
    lane, lamps, _all, _f = _lane_lamps(spec)
    assert lamps and all(_offset(lane, p) > 0 for p in lamps)
