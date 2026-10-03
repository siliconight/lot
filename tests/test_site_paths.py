"""Where a walk goes (Lot 0.91.0): a walk leads to a door; a spur with no
door to meet is not drawn; two neighbours' side doors get a landing each,
not a walk; every door no walk reaches gets a landing."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_paths as SP  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}
_BREACH = {"kind": "breach", "width": 1.4, "height": 2.2, "sill": 0.0}
_GARAGE = {"kind": "garage", "width": 4.5, "height": 3.0, "sill": 0.0}
_LOW_WINDOW = {"kind": "window", "width": 2.0, "height": 1.4, "sill": 0.9, "vaultable": True}


def _merged(bldgs, ops):
    return {"buildings": [dict(b) for b in bldgs], "openings": list(ops)}


def _site(bldgs, paths):
    return {"name": "t", "buildings": [dict(b) for b in bldgs], "paths": paths}


def _landings(site):
    return [p for p in site["paths"] if p.get("landing_of")]


def test_a_spur_slides_to_its_door_and_runs_up_to_the_wall():
    """The spur ran at the building's centre x, a metre off the face; the
    south door is 3 m east. It slides 3 m east and its near end meets the
    wall, 5 cm into it; the far end only slides."""
    bldgs = [{"id": "B", "at": [10, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="B", wall="ext_0_S", story=0, x=3, y=-5)]
    site = _site(bldgs, [{"a": [10.0, -6.0], "b": [10.0, -12.0], "width": 4.0, "building": "B"}])
    assert SP.snap_to_doors(site, _merged(bldgs, ops)) == []
    p = site["paths"][0]
    assert p.get("drawn", True) is True
    assert [round(v, 9) for v in p["a"]] == [13.0, -5.0 + 0.05] and p["b"] == [13.0, -12.0]
    assert p["width"] == 4.0 and p["snapped"] == {"a": "ext_0_S"}
    assert _landings(site) == []                      # the door the spur meets needs none


def test_a_breach_a_window_or_a_garage_is_not_a_door_to_walk_to():
    """The walker's frame of the bank's west wall: a walk to a breach. A
    spur facing only a breach, a vaultable window and a garage is not drawn,
    it is said, and none of the three gets a landing."""
    bldgs = [{"id": "B", "at": [0, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_BREACH, building="B", wall="ext_0_S", story=0, x=0, y=-5),
           dict(_LOW_WINDOW, building="B", wall="ext_0_S", story=0, x=3, y=-5),
           dict(_GARAGE, building="B", wall="ext_0_S", story=0, x=-3, y=-5)]
    site = _site(bldgs, [{"a": [0.0, -6.0], "b": [0.0, -12.0], "width": 4.0, "building": "B"}])
    findings = SP.snap_to_doors(site, _merged(bldgs, ops))
    p = site["paths"][0]
    assert p["drawn"] is False and p["a"] == [0.0, -6.0]
    assert len(findings) == 1 and findings[0]["code"] == "LOT_PATH_END_OFF_DOOR"
    assert "not drawn" in findings[0]["message"]
    assert _landings(site) == []
    assert lot.path_slabs(site) == []


def test_two_neighbours_side_doors_get_a_landing_each_and_no_walk():
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=-2),
           dict(_DOOR, building="b1", wall="ext_0_W", story=0, x=-5, y=2)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    assert SP.snap_to_doors(site, _merged(bldgs, ops)) == []
    route = site["paths"][0]
    assert route["drawn"] is False and route["from"] == "b0" and "a" not in route
    (l0, l1) = sorted(_landings(site), key=lambda p: p["landing_of"])
    # 60 in deep from the wall, the door's width plus a foot each side but
    # never under 60 in, 5 cm into the wall
    assert l0["landing_of"] == "b0" and l0["wall"] == "ext_0_E"
    assert [round(v, 9) for v in l0["a"]] == [5.0 - 0.05, -2.0]
    assert [round(v, 9) for v in l0["b"]] == [5.0 + 1.525, -2.0]
    assert abs(l0["width"] - 1.8) < 1e-9
    assert [round(v, 9) for v in l1["b"]] == [25.0 - 1.525, 2.0]
    slabs = lot.path_slabs(site)
    assert len(slabs) == 2 and all(abs(s["size"][0] - 1.575) < 1e-9 for s in slabs)


def test_a_narrow_door_s_landing_is_still_sixty_inches_wide():
    bldgs = [{"id": "B", "at": [0, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="B", wall="ext_0_N", story=0, x=0, y=5, width=0.8)]
    site = _site(bldgs, [])
    SP.snap_to_doors(site, _merged(bldgs, ops))
    (l,) = _landings(site)
    assert l["width"] == 1.525


def test_a_rotated_building_s_landing_points_out_of_its_own_wall():
    """b0 rotated 90: its local south door (0, -5) is at world (5, 0) facing
    +x, so its landing runs east from x 5."""
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 90, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_S", story=0, x=0, y=-5)]
    site = _site(bldgs, [])
    SP.snap_to_doors(site, _merged(bldgs, ops))
    (l,) = _landings(site)
    assert [round(v, 9) for v in l["a"]] == [4.95, 0.0]
    assert [round(v, 9) for v in l["b"]] == [5.0 + 1.525, 0.0]


def test_the_street_graph_still_joins_buildings_whose_walk_is_not_drawn():
    import site_tactical
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0}])
    SP.snap_to_doors(site, _merged(bldgs, []))
    assert "b1" in site_tactical.build_graph(site)["b0"]


def test_endpoints_prefer_the_resolved_points_and_fall_back_to_centres():
    bld = {"b0": {"at": [0, 0]}, "b1": {"at": [30, 0]}}
    assert SP.endpoints({"from": "b0", "to": "b1"}, bld) == ((0.0, 0.0), (30.0, 0.0))
    assert SP.endpoints({"from": "b0", "to": "b1", "a": [6, 0], "b": [24, 0]}, bld) == ((6.0, 0.0), (24.0, 0.0))
    assert SP.endpoints_or_none({"from": "zz", "to": "b1"}, bld) == (None, None)


def test_the_route_check_counts_a_walk_and_not_a_landing():
    """A door a spur reaches is routed; a door with only its landing is not
    -- a landing is where a door meets the lot, not a way to it, and the
    enterability warning has to keep meaning that."""
    import site_enterability as SE
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_S", story=0, x=0, y=-5),
           dict(_DOOR, building="b1", wall="ext_0_N", story=0, x=0, y=5)]
    site = _site(bldgs, [{"a": [0.0, -6.0], "b": [0.0, -12.0], "width": 4.0, "building": "b0"}])
    merged = _merged(bldgs, ops)
    SP.snap_to_doors(site, merged)
    rep = {b["id"]: b for b in SE.analyze(site, merged)["buildings"]}
    assert rep["b0"]["routed_entries"] == 1 and rep["b1"]["routed_entries"] == 0


def test_the_drawn_list_is_what_every_drawing_reader_reads():
    import site_furniture
    import site_steps
    import site_surfaces
    bldgs = [{"id": "b0", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "b1", "at": [30, 0], "rot": 0, "footprint": [10, 10]}]
    ops = [dict(_DOOR, building="b0", wall="ext_0_E", story=0, x=5, y=0)]
    site = _site(bldgs, [{"from": "b0", "to": "b1", "width": 8.0},
                         {"a": [30.0, -6.0], "b": [30.0, -12.0], "width": 4.0, "building": "b1"}])
    SP.snap_to_doors(site, _merged(bldgs, ops))
    assert len(SP.drawn(site)) == 1                          # b0's landing only
    assert len(lot.path_slabs(site)) == 1
    assert len(site_surfaces._path_segments(site)) == 1
    assert len(site_steps.routes(site)) == 1
    # the corridors are the landing's: nothing between the two buildings
    rects = site_furniture.path_corridors(site)
    assert rects and all(r[2] <= 5.0 + 1.525 + 1.0 for r in rects), rects
