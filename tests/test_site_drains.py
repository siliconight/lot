"""The drains (0.120.0, factory roadmap 179): manhole covers and storm inlets by the rules the factory's
docs/reference/STREET_DRAINS.md read at source -- a cover at every junction and no two farther apart
than 400 ft along a street, an inlet a corner in the gutter on the block side of the cut, a lid in the
sidewalk a step behind an inlet and only so many -- flush, without collision, and with the art only.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_drains      # noqa: E402
import site_furniture   # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")

#: Cold run 9262's lot (seed_9104): a main road, two side streets off it at a T each, and a lane
#: between them.
T_ROADS = [{"a": [-85.5, -21.665], "b": [85.5, -21.665], "width": 10.0, "sidewalk": 3.0},
           {"a": [-19.9875, -21.665], "b": [-19.9875, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [75.15, -21.665], "b": [75.15, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [-19.9875, 27.185], "b": [75.15, 27.185], "width": 5.0, "sidewalk": 0.0}]
#: two streets crossing (an X)
X_ROADS = [{"a": [-60.0, 0.0], "b": [60.0, 0.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [0.0, -60.0], "b": [0.0, 60.0], "width": 10.0, "sidewalk": 3.0}]
#: one long street and nothing crossing it
LONG_ROAD = [{"a": [-250.0, 0.0], "b": [250.0, 0.0], "width": 10.0, "sidewalk": 3.0}]


def _roads(rr):
    return site_streets.roads({"name": "t", "roads": rr, "buildings": []})


def _plan(rr):
    roads = _roads(rr)
    cover = site_furniture.plan_furniture(roads, [])
    return roads, cover, site_drains.plan(roads, cover)


def _of(pieces, kind):
    return [p for p in pieces if p["kind"] == kind]


def test_the_numbers_are_the_sources():
    assert abs(site_drains.MANHOLE_SPACING_MAX - 121.92) < 1e-6          # 400 ft
    assert abs(2 * site_drains.COVER_R - 25.3125 * 0.0254) < 1e-9          # the lid, 25 5/16 in
    assert abs(2 * site_drains.FRAME_R - 32.1875 * 0.0254) < 1e-9          # the frame, 32 3/16 in
    assert abs(site_drains.INLET_L - 0.9144) < 1e-9 and abs(site_drains.INLET_D - 0.6096) < 1e-9
    assert site_drains.WALK_COVER_MIN_SPACING == site_furniture.HYDRANT_MIN_SPACING
    # a floater stands proud by 3 mm and rests on a 4 mm skirt (Zoo's README)
    assert site_drains.PROUD == 0.003 and site_drains.SKIRT == 0.004


def test_a_cover_at_every_junction_once_at_its_centre():
    roads, _cover, pieces = _plan(X_ROADS)
    junction = [p for p in _of(pieces, "manhole") if p["why"] == "junction"]
    assert len(junction) == 1
    assert math.hypot(*junction[0]["at"]) < 0.01
    roads, _cover, pieces = _plan(T_ROADS)
    junction = [p for p in _of(pieces, "manhole") if p["why"] == "junction"]
    # the main road's two T's and the lane's two
    assert len(junction) == 4
    for i, a in enumerate(junction):
        for b in junction[i + 1:]:
            assert math.hypot(a["at"][0] - b["at"][0], a["at"][1] - b["at"][1]) > 1.0


def test_no_two_covers_along_a_street_farther_apart_than_the_standard():
    roads, _cover, pieces = _plan(LONG_ROAD)
    (road,) = roads
    ts = sorted(p["t"] for p in _of(pieces, "manhole"))
    assert len(ts) >= 4
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    assert max(gaps) <= site_drains.MANHOLE_SPACING_MAX + 1e-6, gaps
    lo, hi = road.slab
    assert all(lo + site_drains.END_MARGIN - 1e-6 <= t <= hi - site_drains.END_MARGIN + 1e-6 for t in ts)
    # and a run shorter than the standard between two junctions takes none between them
    roads, _cover, pieces = _plan(T_ROADS)
    assert not [p for p in _of(pieces, "manhole") if p["why"] == "run" and p["road"] == 0]


def test_one_inlet_a_corner_in_the_gutter_on_the_block_side_of_the_cut():
    for rr, corners in ((X_ROADS, 4), (T_ROADS, None)):
        roads, _cover, pieces = _plan(rr)
        inlets = _of(pieces, "inlet")
        assert inlets
        if corners is not None:
            assert len(inlets) == corners
        by = {r.index: r for r in roads}
        keys = set()
        for p in inlets:
            road = by[p["road"]]
            kerb = road.kerb(p["kerb"])
            face = site_drains._face_offset(road, kerb)
            # the kerb face is the carriageway's edge
            assert abs(abs(face) - road.width / 2.0) < 1e-6
            # tight against the kerb, on the road's side of it
            fx, fy = road.point(p["t"], face)
            assert abs(math.hypot(p["at"][0] - fx, p["at"][1] - fy) - site_drains.INLET_D / 2.0) < 1e-3
            cx, cy = road.point(p["t"], 0.0)
            assert math.hypot(p["at"][0] - cx, p["at"][1] - cy) < abs(face)
            # clear of every cut along the kerb
            assert site_furniture._clear_of_cuts(p["t"], site_drains.INLET_L / 2.0, kerb, 0.0)
            # next to a junction's cut: its near end a hand from the dropped stretch's edge
            near = min(min(abs(p["t"] - lo), abs(p["t"] - hi))
                       for lo, hi in (site_drains._cut_span(kerb, c) for c in kerb.cuts if c.kind == "road"))
            # (a piece's station is kept to the millimetre)
            assert abs(near - site_drains.INLET_L / 2.0 - site_drains.INLET_CLEAR) < 6e-4, near
            junction = min((c for c in kerb.cuts if c.kind == "road"), key=lambda c: abs(p["t"] - c.t))
            key = site_furniture.corner_key(road, junction.t, p["at"])
            assert key not in keys
            keys.add(key)


def test_a_sidewalk_lid_a_step_behind_an_inlet_and_only_so_many():
    roads, cover, pieces = _plan(T_ROADS)
    walks, inlets = _of(pieces, "walk_cover"), _of(pieces, "inlet")
    assert walks
    by = {r.index: r for r in roads}
    for w in walks:
        road = by[w["road"]]
        kerb = road.kerb(w["kerb"])
        assert any(i["road"] == w["road"] and i["kerb"] == w["kerb"] and abs(i["t"] - w["t"]) < 1e-6
                   for i in inlets)
        x, y = road.point(w["t"], site_drains._face_offset(road, kerb) + kerb.sign * site_drains.STEP_BEHIND)
        assert math.hypot(w["at"][0] - x, w["at"][1] - y) < 1e-3
        assert not site_drains._rect_hits(w["at"], site_drains.WALK_COVER / 2.0, cover, 0.0)
    for i, a in enumerate(walks):
        for b in walks[i + 1:]:
            assert math.hypot(a["at"][0] - b["at"][0], a["at"][1] - b["at"][1]) >= site_drains.WALK_COVER_MIN_SPACING


def _obj(text):
    v, vn, f = [], [], []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append(tuple(float(x) for x in p[1:4]))
        elif p[0] == "vn":
            vn.append(tuple(float(x) for x in p[1:4]))
        elif p[0] == "f":
            f.append([tuple(int(i) for i in c.split("/")) for c in p[1:]])
    return v, vn, f


def test_every_face_winds_about_its_normal_and_stands_proud_of_the_paint():
    roads, cover, pieces = _plan(T_ROADS)
    road_top, paint_top, band_top = 0.010, 0.013, 0.1026
    body, sub, files = site_drains.meshes(pieces, road_top, paint_top, band_top)
    assert files and any(n.startswith("site_drains_iron_") for n in files)
    assert any(n.startswith("site_drains_void_") for n in files)
    for name, text in files.items():
        v, vn, faces = _obj(text)
        for face in faces:
            (a, _, n), (b, _, _), (c, _, _) = face
            pa, pb, pc = v[a - 1], v[b - 1], v[c - 1]
            u = [pb[k] - pa[k] for k in range(3)]
            w = [pc[k] - pa[k] for k in range(3)]
            cross = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
            assert sum(cross[k] * vn[n - 1][k] for k in range(3)) > 0.0, (name, face)
        ys = [p[1] for p in v]
        # nothing sinks past its skirt, and every face of a piece in the road that faces up stands
        # PROUD of the paint
        assert min(ys) >= road_top - site_drains.SKIRT - 1e-6, name
        for face in faces:
            (a, _, n), (b, _, _), (c, _, _) = face
            if vn[n - 1][1] > 0.99 and max(v[a - 1][1], v[b - 1][1], v[c - 1][1]) < band_top - 0.01:
                assert v[a - 1][1] >= paint_top + site_drains.PROUD - 1e-6, (name, v[a - 1])
    assert "cast_shadow = 0" in body
    assert any(ln.startswith('[sub_resource type="StandardMaterial3D" id="Mat_site_drains_iron"]') for ln in sub)


def test_a_greybox_lot_draws_no_drains_and_a_themed_one_does():
    """The graders' lots stay as they were (roadmap 242): a drain comes with the art, as a wire does."""
    spec = json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))
    roads = site_streets.roads(spec)
    spec["cover"] = site_furniture.plan_furniture(roads, spec.get("buildings") or [])
    grey, themed = {}, {}
    lot._outdoor_nodes(dict(spec), files=grey)
    lot._outdoor_nodes(dict(spec), cover_refs={0: "cover_0_module"}, files=themed)
    assert not [n for n in grey if n.startswith("site_drains_")]
    assert [n for n in themed if n.startswith("site_drains_")]
