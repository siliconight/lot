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
    # the material holds a wire to a pixel (0.119.1): a shader, unshaded
    assert sub[0] == '[sub_resource type="Shader" id="Shader_site_wires"]'
    assert '[sub_resource type="ShaderMaterial" id="Mat_site_wires"]' in sub
    assert "render_mode unshaded, cull_back;" in site_poles.WIRE_SHADER
    ring = site_poles.WIRE_SIDES * (site_poles.WIRE_SEGMENTS + 1)
    verts = sum(t.count("\nv ") for t in files.values())
    uvs = sum(t.count("\nvt ") for t in files.values())
    norms = sum(t.count("\nvn ") for t in files.values())
    faces = sum(t.count("\nf ") for t in files.values())
    assert verts == uvs == norms == ring * len(site_poles.WIRES) * len(spans)
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


def _obj(text):
    """``(v, vt, vn, f)`` of one wire OBJ: positions, each vertex's u, normals,
    and faces as ``[(v, vt, vn), ...]`` with OBJ's one-based indices (None
    where a face leaves one out, as 0.119.0's ``a//a`` did)."""
    v, vt, vn, f = [], [], [], []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append(tuple(float(x) for x in p[1:4]))
        elif p[0] == "vt":
            vt.append(float(p[1]))
        elif p[0] == "vn":
            vn.append(tuple(float(x) for x in p[1:4]))
        elif p[0] == "f":
            f.append([tuple(int(i) if i else None for i in c.split("/")) for c in p[1:]])
    return v, vt, vn, f


def test_every_vertex_carries_its_wires_drawn_radius():
    """0.119.1: the shader finds a wire's centre as VERTEX - NORMAL * UV.x, so
    each vertex's u is the drawn radius of the wire it belongs to, and the four
    vertices of a ring give the shader one centre."""
    _roads, cover = _cover()
    spans = site_poles.spans(cover)
    _body, _sub, files = site_poles.wire_meshes(cover, lot.SIDEWALK_H)
    ring = site_poles.WIRE_SIDES * (site_poles.WIRE_SEGMENTS + 1)
    want = {}
    for name in site_poles.WIRES:
        r = round(site_poles.WIRE_R[site_poles._kind(name)], 4)
        want[r] = want.get(r, 0) + ring * len(spans)
    got = {}
    sides = site_poles.WIRE_SIDES
    for text in files.values():
        v, vt, vn, _f = _obj(text)
        assert len(vt) == len(v) == len(vn)
        for r in vt:
            got[round(r, 4)] = got.get(round(r, 4), 0) + 1
        for i in range(0, len(v), sides):
            centres = [tuple(v[j][k] - vn[j][k] * vt[j] for k in range(3)) for j in range(i, i + sides)]
            for c in centres[1:]:
                assert max(abs(c[k] - centres[0][k]) for k in range(3)) < 2e-3, (i, centres)
    assert got == want


def test_every_face_is_wound_outward_so_one_layer_draws():
    """0.119.1: the material culls back faces, so a wire draws one layer and
    the coverage fade is the coverage; a face is wound counter-clockwise about
    its outward normal, OBJ's front. 0.119.0 wound every face inward and drew
    both sides (`cull_mode = 2`)."""
    _roads, cover = _cover()
    _body, _sub, files = site_poles.wire_meshes(cover, lot.SIDEWALK_H)
    n = 0
    for text in files.values():
        v, _vt, vn, f = _obj(text)
        for face in f:
            (a, _ta, _na), (b, _tb, _nb), (c, _tc, _nc) = face
            p0, p1, p2 = v[a - 1], v[b - 1], v[c - 1]
            e1 = [p1[k] - p0[k] for k in range(3)]
            e2 = [p2[k] - p0[k] for k in range(3)]
            g = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
            out = [vn[a - 1][k] + vn[b - 1][k] + vn[c - 1][k] for k in range(3)]
            assert sum(g[k] * out[k] for k in range(3)) > 0, face
            n += 1
    assert n == 2 * site_poles.WIRE_SIDES * site_poles.WIRE_SEGMENTS * len(site_poles.WIRES) * len(
        site_poles.spans(cover))


def test_the_shader_holds_a_wire_to_a_pixel_and_fades_it_by_coverage():
    """The contract the vertex shader keeps; whether it draws what it says is
    a question for frames, not for this file. The drawn radius from UV.x, half
    a pixel from the clip's w -- the depth in a perspective view, 1 in an
    orthographic one -- the clamp sqrt(2) wider for a four-sided tube, the fade
    the ratio of the two. Written into the scene as a string, it can carry no
    double quote and no backslash."""
    s = site_poles.WIRE_SHADER
    for want in ("shader_type spatial;", "render_mode unshaded, cull_back;", "float r = UV.x;",
                 "VIEWPORT_SIZE.y", "abs(clip.w)", "1.41421356", "coverage = r / drawn;",
                 "VERTEX = centre + NORMAL * drawn;", "ALPHA = colour.a * coverage;"):
        assert want in s, want
    assert '"' not in s and "\\" not in s
    assert not [line for line in s.splitlines() if line.startswith("[")]
    _roads, cover = _cover()
    _body, sub, _files = site_poles.wire_meshes(cover, lot.SIDEWALK_H)
    assert 'shader = SubResource("Shader_site_wires")' in sub
    assert "shader_parameter/min_px = %r" % float(site_poles.WIRE_MIN_PX) in sub
    assert sub.index('[sub_resource type="Shader" id="Shader_site_wires"]') < sub.index(
        '[sub_resource type="ShaderMaterial" id="Mat_site_wires"]')


def test_a_float_uniform_is_written_as_a_float():
    """0.119.2: Godot 4.7 reads an integer literal given to a float uniform as no value -- a scene
    written `shader_parameter/min_px = 1` loads it null, and a re-save writes `null` (cold run 9264's
    package; the factory's docs/findings/pole_line/min_px_resave.gd). Every shader parameter Lot
    writes for a float uniform carries a decimal point, whatever WIRE_MIN_PX is."""
    _roads, cover = _cover()
    keep = site_poles.WIRE_MIN_PX
    try:
        for value in (1, 2, 1.5):
            site_poles.WIRE_MIN_PX = value
            _body, sub, _files = site_poles.wire_meshes(cover, lot.SIDEWALK_H)
            line = [l for l in sub if l.startswith("shader_parameter/min_px = ")]
            assert len(line) == 1, sub
            literal = line[0].split(" = ", 1)[1]
            assert "." in literal and float(literal) == float(value), line[0]
    finally:
        site_poles.WIRE_MIN_PX = keep
