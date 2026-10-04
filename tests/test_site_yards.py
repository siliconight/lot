"""A concrete service pad under each dumpster (Lot 0.93.0)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lot  # noqa: E402
import site_dumpsters as SD  # noqa: E402
import site_landuse  # noqa: E402
import site_steps  # noqa: E402
import site_streets  # noqa: E402
import site_surfaces  # noqa: E402
import site_yards as SY  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}
W, D, H = SD.DIMS
_B = {"id": "b0", "at": [0, 0], "rot": 0, "_footprint": [20, 10]}
_SOUTH_ROAD = {"a": [-40, -14], "b": [40, -14], "width": 10.0, "sidewalk": 3.0}
_FRONT = dict(_DOOR, building="b0", wall="ext_0_S", story=0, x=0, y=-5)


def _site(bldgs, roads=(_SOUTH_ROAD,)):
    return {"name": "t", "buildings": [dict(b) for b in bldgs], "roads": list(roads), "paths": []}


def _dumpsters(site, ops):
    merged = {"buildings": [dict(b) for b in site["buildings"]], "openings": list(ops)}
    return SD.plan_dumpsters(site, merged, site_streets.roads(site))


def _rect(p):
    sx, _h, sy = p["size"]
    return (p["at"][0] - sx / 2, p["at"][1] - sy / 2, p["at"][0] + sx / 2, p["at"][1] + sy / 2)


def _yrect(y):
    return (y["at"][0] - y["size_x"] / 2, y["at"][1] - y["size_y"] / 2,
            y["at"][0] + y["size_x"] / 2, y["at"][1] + y["size_y"] / 2)


def _plan(site, dumpsters, slabs=(), **kw):
    findings = []
    standing = [_rect(p) for p in dumpsters] + list(kw.pop("standing", []))
    got = SY.plan_yards(site, dumpsters, list(slabs), standing=standing, findings=findings, **kw)
    return got, findings


def test_a_pad_runs_from_the_back_wall_under_the_dumpster_and_out_past_it():
    """The back of b0 is y = 5; the dumpster stands toward a corner, 1.515 m
    in from the wall's end, so its 3.7 m pad is clipped at that end: 10 -
    (8.485 - 1.85) = 3.365 m along, and 3 m of pad plus 3 m of apron out."""
    site = _site([_B])
    (p,) = _dumpsters(site, [_FRONT])
    (y,), findings = _plan(site, [p])
    assert findings == [] and y["building"] == "b0" and y["wall"] == "N"
    x0, y0, x1, y1 = _yrect(y)
    assert abs(y0 - 5.0) < 1e-3 and abs(y1 - 11.0) < 1e-3          # 3.0 pad + 3.0 apron
    assert abs((x1 - x0) - 3.365) < 1e-3 and -10.0 - 1e-3 <= x0 and x1 <= 10.0 + 1e-3
    assert y["apron"] == 3.0 and y["dumpster"] == p["name"]
    r = _rect(p)
    assert x0 <= r[0] and r[2] <= x1 and y0 <= r[1] and r[3] <= y1   # under the container


def test_the_apron_gives_way_to_a_walk_and_the_pad_keeps_the_container():
    site = _site([_B])
    (p,) = _dumpsters(site, [_FRONT])
    walk = {"name": "path_0", "family": "path", "centre": [0.0, 9.5], "size": [40.0, 2.0], "yaw_deg": 0.0}
    (y,), _f = _plan(site, [p], [walk])
    assert abs(_yrect(y)[3] - 8.5) < 1e-3                            # stops at the walk's edge
    assert y["apron"] == 0.5
    # a walk over the container's own front: even the least pad cannot clear it
    walk2 = dict(walk, centre=[0.0, 7.0])
    got, findings = _plan(site, [p], [walk2])
    assert got == [] and len(findings) == 1 and findings[0].startswith("LOT_YARD_NO_ROOM")


def test_a_diagonal_walk_is_cleared_by_its_shape_not_its_box():
    """A walk at 45 degrees across the pad's outer corner (10, 11), its centre
    line on x + y = 21.5 and 0.3 m half-wide, so its near edge is 0.354 -
    0.3 = 0.054 m off the corner: its bounding box covers the corner, the
    walk does not, and the pad keeps its full depth. Mirrored for a dumpster
    at the west end. The literals are the geometry."""
    site = _site([_B])
    (p,) = _dumpsters(site, [_FRONT])
    sx = 1.0 if p["at"][0] > 0 else -1.0
    walk = {"name": "path_0", "family": "path", "centre": [sx * 10.75, 10.75],
            "size": [8.0, 0.6], "yaw_deg": -45.0 if sx > 0 else 45.0}
    (y,), _f = _plan(site, [p], [walk])
    assert abs(_yrect(y)[3] - 11.0) < 1e-3
    # its centre line on x + y = 21.3: the near edge crosses the corner, and
    # the apron steps back
    walk2 = dict(walk, centre=[sx * 10.65, 10.65])
    (y2,), _f = _plan(site, [p], [walk2])
    assert _yrect(y2)[3] < 11.0 - 0.4


def test_the_plate_s_edge_and_a_neighbour_bound_it():
    site = _site([_B])
    (p,) = _dumpsters(site, [_FRONT])
    (y,), _f = _plan(site, [p], ground=(-40.0, -30.0, 40.0, 9.0))
    assert abs(_yrect(y)[3] - 8.5) < 1e-3                            # half a metre in from the edge
    got, findings = _plan(site, [p], ground=(-40.0, -30.0, 40.0, 6.9))
    assert got == [] and findings[0].startswith("LOT_YARD_NO_ROOM")
    # a neighbour 4 m behind: the pad stops GAP short of it
    nb = {"id": "b1", "at": [0, 19], "rot": 0, "_footprint": [40, 20]}   # its south face at y = 9
    site2 = _site([_B, nb])
    (y3,), _f = _plan(site2, [p])
    assert abs(_yrect(y3)[3] - 8.5) < 1e-3                           # 9 - 0.3, on a 0.5 m step


def test_a_row_of_buildings_gets_a_pad_each_and_no_two_overlap():
    bldgs = [dict(_B, id=f"b{i}", at=[i * 30, 0]) for i in range(4)]
    ops = [dict(_FRONT, building=b["id"]) for b in bldgs]
    site = _site(bldgs, [dict(_SOUTH_ROAD, a=[-40, -14], b=[130, -14])])
    ds = _dumpsters(site, ops)
    got, findings = _plan(site, ds)
    assert findings == [] and [y["building"] for y in got] == ["b0", "b1", "b2", "b3"]
    rs = [_yrect(y) for y in got]
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
    again, _f = _plan(site, ds)
    assert again == got


def _pawn_with_yard():
    spec = {
        "name": "fixture", "ground": {"size_x": 150, "size_y": 110},
        "buildings": [{"id": "garage", "at": [-48, -28], "rot": 0, "_footprint": [20.0, 14.0]}],
        "paths": [],
        "yards": [{"at": [-50.0, -18.0], "size_x": 3.5, "size_y": 6.0}],
    }
    return spec


def test_a_pad_is_drawn_declared_walked_on_and_counted():
    spec = _pawn_with_yard()
    body, sub = lot._outdoor_nodes(spec)
    assert any(line.startswith('[node name="yard_0"') for line in body)
    (slab,) = lot.yard_slabs(spec)
    assert slab["family"] == "yard" and abs(slab["top"] - lot.YARD_THICK) < 1e-9
    assert "yard_" in site_steps.WALKABLE_PREFIXES
    import test_site_surface_tops as T
    _drawn, declared = T._check_against_scene(spec)
    assert [s["name"] for s in declared if s["family"] == "yard"] == ["yard_0"]
    c = site_landuse.census(spec)
    assert abs(c["areas"]["yard"] - 21.0) <= 4.0                     # 3.5 x 6, a cell row of slack
    assert c["unknown_families"] == []


def test_the_pad_wears_its_own_skin_family():
    assert "yard" in lot.SKIN_FAMILIES
