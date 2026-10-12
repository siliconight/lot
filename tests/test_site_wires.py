"""The wires (0.119.0, factory roadmap 240): the full set the walker asked for, without house drops,
along every pole line and across each junction -- drawn with the art only, unshaded, casting no
shadow and out of the lightmap.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_furniture   # noqa: E402
import site_poles       # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")

#: Cold run 9262's lot (seed_9104): a main road, two side streets off it at a
#: signalised T each, and a lane between them.
T_ROADS = [{"a": [-85.5, -21.665], "b": [85.5, -21.665], "width": 10.0, "sidewalk": 3.0},
           {"a": [-19.9875, -21.665], "b": [-19.9875, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [75.15, -21.665], "b": [75.15, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [-19.9875, 27.185], "b": [75.15, 27.185], "width": 5.0, "sidewalk": 0.0}]


def _cover():
    roads = site_streets.roads({"name": "t", "roads": T_ROADS, "buildings": []})
    return roads, site_furniture.plan_furniture(roads, [])


def _poles(cover):
    return [p for p in cover if p.get("species") == "utility_pole"]


def test_the_spans_are_each_lines_and_a_tie_across_each_junction():
    _roads, cover = _cover()
    spans = site_poles.spans(cover)
    lines = {}
    for p in _poles(cover):
        lines.setdefault(p["line"], []).append(p)
    along = sum(len(v) - 1 for v in lines.values())
    ties = [(a, b) for a, b in spans if a["road"] != b["road"]]
    assert len(spans) == along + len(ties)
    # both side streets tie to the main road's line, which runs along the far kerb
    assert {frozenset((a["road"], b["road"])) for a, b in ties} == {frozenset((0, 1)), frozenset((0, 2))}
    for a, b in ties:
        assert math.hypot(a["at"][0] - b["at"][0], a["at"][1] - b["at"][1]) <= site_poles.LINK_MAX
    assert len({frozenset((a["name"], b["name"])) for a, b in spans}) == len(spans)


def test_a_wire_hangs_from_its_poles_attachments_and_sags_its_share():
    _roads, cover = _cover()
    a, b = site_poles.spans(cover)[0]
    base = lot.SIDEWALK_H
    for name in site_poles.WIRES:
        pts = site_poles.wire_path(a, b, name, base)
        for got, want in ((pts[0], site_poles.wire_point(a, name, base)),
                          (pts[-1], site_poles.wire_point(b, name, base))):
            assert all(abs(g - w) < 1e-9 for g, w in zip(got, want)), name
        span = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
        mid = pts[len(pts) // 2]
        chord = (pts[0][2] + pts[-1][2]) / 2.0
        assert abs((chord - mid[2]) - site_poles.SAG[site_poles._kind(name)] * span) < 1e-9, name


def test_the_lowest_cable_clears_a_road_on_every_span():
    """NESC: about 4.7 m for a communication cable over a road. The heights
    are above the road's surface: a pole stands on the sidewalk band's top."""
    _roads, cover = _cover()
    low = min(z for a, b in site_poles.spans(cover)
              for name in site_poles.WIRES
              for _x, _y, z in site_poles.wire_path(a, b, name, lot.SIDEWALK_H))
    assert low >= 4.7, low


def test_one_unshaded_shadowless_mesh_a_cell():
    _roads, cover = _cover()
    spans = site_poles.spans(cover)
    body, sub, files = site_poles.wire_meshes(cover, lot.SIDEWALK_H)
    assert files and all(n.startswith("site_wires_c") and n.endswith(".obj") for n in files)
    nodes = [l for l in body if l.startswith("[node ")]
    assert len(nodes) == len(files)
    assert body.count("cast_shadow = 0") == len(files) and body.count("gi_mode = 0") == len(files)
    assert sub[0] == '[sub_resource type="StandardMaterial3D" id="Mat_site_wires"]'
    assert "shading_mode = 0" in sub
    ring = site_poles.WIRE_SIDES * (site_poles.WIRE_SEGMENTS + 1)
    verts = sum(t.count("\nv ") for t in files.values())
    norms = sum(t.count("\nvn ") for t in files.values())
    faces = sum(t.count("\nf ") for t in files.values())
    assert verts == norms == ring * len(site_poles.WIRES) * len(spans)
    assert faces == 2 * site_poles.WIRE_SIDES * site_poles.WIRE_SEGMENTS * len(site_poles.WIRES) * len(spans)


def test_a_line_of_one_pole_and_no_neighbour_strings_nothing():
    _roads, cover = _cover()
    one = [dict(p) for p in _poles(cover)[:1]]
    assert site_poles.spans(one) == []
    assert site_poles.wire_meshes(one, lot.SIDEWALK_H) == ([], [], {})


def test_a_greybox_lot_draws_no_wires_and_a_themed_one_does():
    """The graders' lots stay as they were: Laser Tag and the walk test grade a
    candidate's greybox lot, Lot's walk navmeshes parse visual meshes, and a
    grade on these lots moves with any change to what stands on them (roadmap
    242) -- so a wire, which is visual, comes with the art."""
    spec = json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))
    roads = site_streets.roads(spec)
    spec["cover"] = site_furniture.plan_furniture(roads, spec.get("buildings") or [])
    grey, themed = {}, {}
    lot._outdoor_nodes(dict(spec), files=grey)
    lot._outdoor_nodes(dict(spec), cover_refs={0: "cover_0_module"}, files=themed)
    assert not [n for n in grey if n.startswith("site_wires_")]
    assert [n for n in themed if n.startswith("site_wires_")]
