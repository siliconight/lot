"""The road paint as one mesh per colour (Lot 0.114.0, roadmap 231): an OBJ beside the scene, a
quad a marking at the paint's top face, one MeshInstance3D and one material a colour, the wear
offset in the UVs; a spec without roads paints nothing."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_streets  # noqa: E402


def _spec():
    return {"name": "probe", "ground": {"size_x": 140.0, "size_y": 100.0}, "buildings": [],
            "roads": [{"a": [-60.0, 0.0], "b": [60.0, 0.0], "width": 10.0, "sidewalk": 3.0},
                      {"a": [0.0, 0.0], "b": [0.0, 45.0], "width": 10.0, "sidewalk": 3.0}]}


def _quads(text):
    v = [tuple(float(x) for x in l.split()[1:]) for l in text.splitlines() if l.startswith("v ")]
    vt = [tuple(float(x) for x in l.split()[1:]) for l in text.splitlines() if l.startswith("vt ")]
    f = [l for l in text.splitlines() if l.startswith("f ")]
    assert len(v) == len(vt) and len(f) == len(v) // 2 and len(v) % 4 == 0
    return [(v[i:i + 4], vt[i:i + 4]) for i in range(0, len(v), 4)]


def test_one_mesh_a_colour_a_quad_a_marking_and_the_nodes():
    spec = _spec()
    files = {}
    body, sub = lot._outdoor_nodes(spec, files=files)
    marks = site_streets.markings(site_streets.roads(spec))
    colours = {tuple(float(v) for v in m["color"]) for m in marks}
    assert len(files) == len(colours) >= 2
    assert sum(len(_quads(t)) for t in files.values()) == len(marks)
    nodes = [l for l in body if l.startswith('[node name="site_marks_')]
    assert len(nodes) == len(files) and all('type="MeshInstance3D"' in l for l in nodes)
    txt = "\n".join(body)
    for fname in files:
        n = fname[:-4]
        assert f'mesh = ExtResource("{n}")' in txt and f'material_override = SubResource("Mat_{n}")' in txt
    assert not any(l.startswith('[node name="mark_') or l.startswith('[node name="fmark_') for l in body)
    mats = [l for l in sub if l.startswith('[sub_resource type="StandardMaterial3D" id="Mat_site_marks_')]
    assert len(mats) == len(files)
    assert "cull_mode = 2" in "\n".join(sub) and "uv1_triplanar" not in "\n".join(sub).split("Mat_site_marks_")[1]


def test_the_quads_lie_where_the_markings_are_at_the_paint_height():
    spec = _spec()
    files = {}
    lot._outdoor_nodes(spec, files=files)
    marks = site_streets.markings(site_streets.roads(spec))
    want = {(round(m["at"][0], 3), round(-m["at"][1], 3)) for m in marks}
    got = set()
    top = lot.MARKING_Y + lot.SURFACE_TIER / 2.0
    for text in files.values():
        for verts, _uv in _quads(text):
            assert all(abs(y - top) < 1e-6 for _x, y, _z in verts)
            got.add((round(sum(x for x, _y, _z in verts) / 4.0, 3), round(sum(z for _x, _y, z in verts) / 4.0, 3)))
    assert got == want


def test_each_marking_keeps_its_wear_offset_in_its_uvs_under_a_paint_pack(tmp_path):
    pack = tmp_path / "road_paint_probe"
    pack.mkdir()
    (pack / "road_paint_probe_albedo.png").write_bytes(b"PNG")
    (pack / "road_paint_probe.pack.json").write_text(json.dumps({
        "maps": {"albedo": "road_paint_probe_albedo.png"}, "meters_per_tile": 8.0,
        "material_profile": "road_paint_probe"}), encoding="utf-8")
    spec = _spec()
    spec["ground_skins"] = {"paint": str(pack)}
    skins, _f = lot.ground_skins(spec)
    assert skins.get("paint")
    files, body, sub = {}, None, None
    body, sub = lot._outdoor_nodes(spec, skins=skins, files=files)
    marks = site_streets.markings(site_streets.roads(spec))
    s = 1.0 / 8.0
    offsets = []
    for text in files.values():
        for verts, uvs in _quads(text):
            offsets.append((round(uvs[0][0] - verts[0][0] * s, 4), round(uvs[0][1] - verts[0][2] * s, 4)))
    assert len(offsets) == len(marks) and len(set(offsets)) == len(marks)   # each its own scuffs
    txt = "\n".join(sub)
    m = txt[txt.index('id="Mat_site_marks_'):]
    assert 'albedo_texture = ExtResource(' in m and "uv1_triplanar" not in m and "uv1_scale = Vector3(1, 1, 1)" in m


def test_a_spec_without_roads_paints_nothing():
    spec = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs", "example_compound.json")))
    files = {}
    body, _sub = lot._outdoor_nodes(spec, files=files)
    assert files == {} and not any(l.startswith('[node name="site_marks_') for l in body)
