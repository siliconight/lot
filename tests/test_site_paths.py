"""A path meets a door, not the middle of a wall (Lot 0.88.0), and a walk
between two doors is drawn square to the buildings (0.89.0)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_paths as SP  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}


def _merged(bldgs, ops):
    return {"buildings": [dict(b) for b in bldgs], "openings": list(ops)}


def _site(bldgs, paths, roads=None):
    s = {"name": "t", "buildings": [dict(b) for b in bldgs], "paths": paths}
    if roads is not None:
        s["roads"] = roads
    return s


def _axis_aligned(p):
    return abs(p["a"][0] - p["b"][0]) < 1e-9 or abs(p["a"][1] - p["b"][1]) < 1e-9


def _rect(p):
    """The plan rectangle an axis-aligned leg's slab covers."""
    (ax, ay), (bx, by), h = p["a"], p["b"], p["width"] / 2.0
    if abs(ay - by) < 1e-9:
        return (min(ax, bx), ay - h, max(ax, bx), ay + h)
    return (ax - h, min(ay, by), ax + h, max(ay, by))


def _overlap_area(r, q):
    w = min(r[2], q[2]) - max(r[0], q[0])
    h = min(r[3], q[3]) - max(r[1], q[1])
    return max(w, 0.0) * max(h, 0.0)


def test_a_spur_slides_along_the_facade_to_its_door():
    """Level Factory's spur runs at the building's centre x; the south door
    is 3 m east of it. The spur moves 3 m east, its standoff untouched."""
    bldgs = [{"id": "B", "at": [10, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="B", wall="ext_0_S", story=0, x=3, y=-5)]
    site = _site(bldgs, [{"a": [10.0, -6.0], "b": [10.0, -12.0], "width": 4.0, "building": "B"}])
    findings = SP.snap_to_doors(site, _merged(bldgs, ops))
    assert findings == []
    p = site["paths"][0]
    assert p["a"] == [13.0, -6.0] and p["b"] == [13.0, -12.0] and p["width"] == 4.0
    assert p["snapped"] == {"a": "ext_0_S"}


def test_a_walk_between_offset_doors_is_three_square_legs():
    """b0's east door at y -2, b1's west door at y 2: out from each door and
    one jog on the line halfway. Every leg axis-aligned, at the walk's width,
    and no two slabs over the same ground."""
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=-2),
           dict(_DOOR, building="b0", wall="ext_0_S", story=0, x=0, y=-5),
           dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=2)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    assert SP.snap_to_doors(site, _merged(bldgs, ops)) == []
    legs = site["paths"]
    assert len(legs) == 3
    first = legs[0]
    assert first["from"] == "b0" and first["to"] == "b1" and first["route_width"] == 8.0
    assert first["snapped"] == {"a": "ext_0_E", "b": "ext_0_W"}
    w = SP.WALK_WIDTH
    # the doors' own points, a metre out: (6, -2) and (24, 2); the jog at x 15
    assert first["a"] == [6.0, -2.0] and first["b"] == [15.0 + w / 2, -2.0]
    assert legs[1]["a"] == [15.0, -2.0 + w / 2] and legs[1]["b"] == [15.0, 2.0 - w / 2]
    assert legs[2]["a"] == [15.0 - w / 2, 2.0] and legs[2]["b"] == [24.0, 2.0]
    assert all(_axis_aligned(p) and p["width"] == w for p in legs)
    assert all(p.get("leg_of") == ["b0", "b1"] for p in legs[1:])
    rects = [_rect(p) for p in legs]
    for i in range(3):
        for j in range(i + 1, 3):
            assert _overlap_area(rects[i], rects[j]) < 1e-9, (i, j)


def test_the_walk_takes_the_site_s_sidewalk_width():
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=0),
           dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=0)]
    roads = [{"a": [-50, -30], "b": [50, -30], "width": 10.0, "sidewalk": 2.5}]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}], roads)
    SP.snap_to_doors(site, _merged(bldgs, ops))
    (p,) = site["paths"]
    assert p["width"] == 2.5 and p["a"] == [6.0, 0.0] and p["b"] == [24.0, 0.0]


def test_a_shallow_offset_is_one_wider_leg_not_a_kink():
    """b1 rotated 90: its local north door (1, 5) lands at world (25, 1)
    facing west. The doors are 1 m apart across the walk -- under its width
    -- so one leg runs down the middle, widened to reach both."""
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 90, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=0),
           dict(_DOOR, building="b1", wall="ext_0_N", story=0, x=1, y=5),
           dict(_DOOR, building="b1", wall="ext_0_S", story=0, x=0, y=-5)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    assert SP.snap_to_doors(site, _merged(bldgs, ops)) == []
    (p,) = site["paths"]
    assert p["snapped"]["b"] == "ext_0_N"
    assert [round(v, 6) for v in p["a"]] == [6.0, 0.5]
    assert [round(v, 6) for v in p["b"]] == [24.0, 0.5]
    assert abs(p["width"] - (SP.WALK_WIDTH + 1.0)) < 1e-9


def test_a_blank_facade_is_said_and_the_path_stays_one_straight_band():
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=0),
           dict(_DOOR, building="b1", wall="ext_0_S", story=0, x=0, y=-5)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    findings = SP.snap_to_doors(site, _merged(bldgs, ops))
    assert len(findings) == 1 and findings[0]["code"] == "LOT_PATH_END_OFF_DOOR"
    assert "'b1'" in findings[0]["message"] and "end 'b'" in findings[0]["message"]
    (p,) = site["paths"]
    assert p["a"] == [6.0, 0.0] and p["b"] == [30.0, 0.0] and p["width"] == 8.0


def test_endpoints_prefer_the_resolved_points_and_fall_back_to_centres():
    bld = {"b0": {"at": [0, 0]}, "b1": {"at": [30, 0]}}
    assert SP.endpoints({"from": "b0", "to": "b1"}, bld) == ((0.0, 0.0), (30.0, 0.0))
    assert SP.endpoints({"from": "b0", "to": "b1", "a": [6, 0], "b": [24, 0]}, bld) == ((6.0, 0.0), (24.0, 0.0))
    assert SP.endpoints_or_none({"from": "zz", "to": "b1"}, bld) == (None, None)


def test_the_slabs_and_the_route_check_read_the_legs():
    """`path_slabs` draws one axis-aligned slab per leg, and the enterability
    route check finds each door's approach on its own leg."""
    import site_enterability as SE
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [40, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=-4),
           dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=4)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 3.0}])
    merged = _merged(bldgs, ops)
    SP.snap_to_doors(site, merged)
    slabs = lot.path_slabs(site)
    assert len(slabs) == 3
    for s in slabs:
        assert abs(s["yaw_deg"]) % 90.0 < 1e-6 or abs(abs(s["yaw_deg"]) % 90.0 - 90.0) < 1e-6, s["yaw_deg"]
    # the first leg: (6, -4) to (20 + 1.5, -4), in Godot (x, -y)
    cx, _cy, cz = slabs[0]["centre"]
    assert abs(cx - (6.0 + 21.5) / 2) < 1e-9 and abs(cz - 4.0) < 1e-9
    rep = SE.analyze(site, merged)
    assert all(b["routed_entries"] == 1 for b in rep["buildings"]), rep


def test_doors_too_close_to_run_out_keep_the_straight_band():
    """Two buildings 2 m apart: no room to leave a door and turn."""
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [14, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=-3),
           dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=3)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    SP.snap_to_doors(site, _merged(bldgs, ops))
    (p,) = site["paths"]
    assert p["a"] == [6.0, -3.0] and p["b"] == [8.0, 3.0] and p["width"] == 8.0
