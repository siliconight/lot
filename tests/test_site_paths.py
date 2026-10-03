"""A path meets a door, not the middle of a wall (Lot 0.88.0)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_paths as SP  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}


def _merged(bldgs, ops):
    return {"buildings": [dict(b) for b in bldgs], "openings": list(ops)}


def _site(bldgs, paths):
    return {"name": "t", "buildings": [dict(b) for b in bldgs], "paths": paths}


def test_a_spur_slides_along_the_facade_to_its_door():
    """Level Factory's spur runs at the building's centre x; the south door
    is 3 m east of it. The spur moves 3 m east, its standoff untouched."""
    bldgs = [{"id": "B", "at": [10, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="B", wall="ext_0_S", story=0, x=3, y=-5)]
    site = _site(bldgs, [{"a": [10.0, -6.0], "b": [10.0, -12.0], "width": 4.0, "building": "B"}])
    findings = SP.snap_to_doors(site, _merged(bldgs, ops))
    assert findings == []
    p = site["paths"][0]
    assert p["a"] == [13.0, -6.0] and p["b"] == [13.0, -12.0]
    assert p["snapped"] == {"a": "ext_0_S"}


def test_a_building_path_ends_in_front_of_the_facing_doors():
    """b0's east door at local (5, -2), b1's west door at local (-5, 2), b1
    rotated 180 so its local west face is its world east... no: rot 0 here,
    and the rotated case is below. Each end lands DOOR_STANDOFF out from its
    door, and the ids stay on the record."""
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=-2),
           dict(_DOOR, building="b0", wall="ext_0_S", story=0, x=0, y=-5),
           dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=2)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    assert SP.snap_to_doors(site, _merged(bldgs, ops)) == []
    p = site["paths"][0]
    assert p["from"] == "b0" and p["to"] == "b1"
    assert p["a"] == [5.0 + SP.DOOR_STANDOFF, -2.0]
    assert p["b"] == [25.0 - SP.DOOR_STANDOFF, 2.0]
    assert p["snapped"] == {"a": "ext_0_E", "b": "ext_0_W"}


def test_a_rotated_building_s_door_is_found_in_world_space():
    """b1 at (30, 0) rotated 90: its local south face (y = -5) turns to face
    world +x... rotating (0, -1) by +90 gives (1, 0), so the local SOUTH
    door faces EAST and the local EAST door faces NORTH. The path from the
    west must find the door whose world normal points west: local north
    (0, 1) -> (-1, 0)."""
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 90, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=0),
           dict(_DOOR, building="b1", wall="ext_0_N", story=0, x=1, y=5),
           dict(_DOOR, building="b1", wall="ext_0_S", story=0, x=0, y=-5)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    assert SP.snap_to_doors(site, _merged(bldgs, ops)) == []
    p = site["paths"][0]
    # local (1, 5) rotated 90 -> (-5, 1); world (25, 1); normal (-1, 0)
    assert [round(v, 6) for v in p["b"]] == [25.0 - SP.DOOR_STANDOFF, 1.0]
    assert p["snapped"]["b"] == "ext_0_N"


def test_a_blank_facade_is_said_and_the_end_stays():
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=0),
           dict(_DOOR, building="b1", wall="ext_0_S", story=0, x=0, y=-5)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    findings = SP.snap_to_doors(site, _merged(bldgs, ops))
    assert len(findings) == 1 and findings[0]["code"] == "LOT_PATH_END_OFF_DOOR"
    assert "'b1'" in findings[0]["message"] and "end 'b'" in findings[0]["message"]
    p = site["paths"][0]
    assert p["a"] == [6.0, 0.0] and p["b"] == [30.0, 0.0]


def test_endpoints_prefer_the_resolved_points_and_fall_back_to_centres():
    bld = {"b0": {"at": [0, 0]}, "b1": {"at": [30, 0]}}
    assert SP.endpoints({"from": "b0", "to": "b1"}, bld) == ((0.0, 0.0), (30.0, 0.0))
    assert SP.endpoints({"from": "b0", "to": "b1", "a": [6, 0], "b": [24, 0]}, bld) == ((6.0, 0.0), (24.0, 0.0))
    assert SP.endpoints_or_none({"from": "zz", "to": "b1"}, bld) == (None, None)


def test_the_slab_and_the_route_check_read_the_snapped_ends():
    """`path_slabs` draws the resolved span, and the enterability route check
    now finds the door's approach ON the path (0.83.0 wrote that whether a
    centre-to-centre route models 'a path leads to the door' was a separate
    question; this is the answer)."""
    import site_enterability as SE
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [40, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=-4),
           dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=4)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 3.0}])
    merged = _merged(bldgs, ops)
    SP.snap_to_doors(site, merged)
    (slab,) = lot.path_slabs(site)
    cx, _cy, cz = slab["centre"]
    assert abs(cx - 20.0) < 1e-9 and abs(cz - 0.0) < 1e-9   # midpoint of (6,-4)..(34,4)
    assert abs(slab["size"][0] - ((28.0 ** 2 + 8.0 ** 2) ** 0.5)) < 1e-9
    rep = SE.analyze(site, merged)
    assert all(b["routed_entries"] == 1 for b in rep["buildings"]), rep
