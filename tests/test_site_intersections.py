"""Intersections in the street model (roadmap 153): a road that ends on
another begins its slab at that road's band edge; a road crossing is a
box with crosswalks at its ends; the leg that ends is the one that stops;
the edge lines break over a mouth; parking keeps clear of the box.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_streets   # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "specs")


def _tee():
    """A 120 m through road along X and a 50 m side street north from its
    centre line at x = 0: a T junction, both roads 10 m with 3 m bands."""
    return {"name": "tee", "ground": {"size_x": 140, "size_y": 120},
            "buildings": [],
            "roads": [{"a": [-60, 0], "b": [60, 0], "width": 10, "sidewalk": 3},
                      {"a": [0, 0], "b": [0, 50], "width": 10, "sidewalk": 3}]}


def test_the_side_street_begins_at_the_through_roads_band_edge():
    through, side = site_streets.roads(_tee())
    assert through.slab == (0.0, 120.0)
    assert side.slab == (8.0, 50.0)                # 5 m half road + 3 m band
    assert side.slab_centre == (0.0, 29.0) and side.slab_length == 42.0
    # the through road's L kerb is cut for the mouth; the side street's
    # kerbs are cut where the through road crosses them, at t = 0
    (cut,) = through.kerb("L").cuts
    assert cut.kind == "road" and cut.width == 10 and cut.sidewalk == 3 and cut.terminal
    assert abs(cut.t - 60.0) < 1e-9 and abs(cut.span - 10.0) < 1e-9
    assert through.kerb("R").cuts == []
    for k in side.kerbs:
        (c,) = k.cuts
        assert c.kind == "road" and not c.terminal and abs(c.t) < 1e-9


def test_a_crossing_is_a_box_with_crosswalks_at_its_ends():
    through, side = site_streets.roads(_tee())
    marks = site_streets.markings([through, side])
    walks = [m for m in marks if m["kind"] == "crosswalk_bar"]
    # through road: a crosswalk each side of the mouth, in line with the
    # side street's sidewalks, 3 m wide (six 0.5 m bars in 3 m: three)
    through_walks = [m for m in walks if m["yaw"] == 0.0]
    xs = sorted({round(m["at"][0], 2) for m in through_walks})
    assert min(xs) >= -8.0 and max(xs) <= 8.0
    assert all(x <= -5.0 or x >= 5.0 for x in xs), xs        # none in the box
    # side street: ONE crosswalk, across its mouth at t = 5..8 (y = 5..8)
    side_walks = [m for m in walks if m["yaw"] == 90.0]
    ys = sorted({round(m["at"][1], 2) for m in side_walks})
    assert ys and 5.0 <= min(ys) and max(ys) <= 8.0, ys
    # the leg that ends is the one that stops: no stop bar on the through
    # road, one on the side street on the lane travelling toward the T
    stops = [m for m in marks if m["kind"] == "stop_bar"]
    assert not [m for m in stops if m["yaw"] == 0.0]
    (stop,) = [m for m in stops if m["yaw"] == 90.0]
    assert abs(stop["at"][1] - (8.0 + site_streets.STOP_BAR_SETBACK
                                + site_streets.STOP_BAR_DEPTH / 2)) < 1e-9
    assert stop["at"][0] > 0                                  # the -t lane (R side)
    # the centre lines keep out of the boxes and the side street's stays
    # within its slab
    for m in marks:
        if m["kind"] != "centre_line":
            continue
        half = m["size"][0] / 2
        if m["yaw"] == 0.0:
            assert m["at"][0] + half <= -8.0 - 1.4 + 1e-9 or m["at"][0] - half >= 8.0 + 1.4 - 1e-9, m
        else:
            assert m["at"][1] - half >= 8.0 - 1e-9, m


def test_the_edge_line_breaks_over_the_mouth_and_not_over_a_path():
    through, side = site_streets.roads(_tee())
    marks = site_streets.markings([through, side])
    edges = [m for m in marks if m["kind"] == "edge_line" and m["yaw"] == 0.0]
    left = sorted((m for m in edges if m["side"] == "L"), key=lambda m: m["at"][0])
    right = [m for m in edges if m["side"] == "R"]
    assert len(right) == 1 and abs(right[0]["size"][0] - 120.0) < 1e-9
    assert len(left) == 2
    ends = sorted((m["at"][0] - m["size"][0] / 2, m["at"][0] + m["size"][0] / 2) for m in left)
    assert abs(ends[0][1] - (-5.0)) < 1e-9 and abs(ends[1][0] - 5.0) < 1e-9
    # a path crossing (the kerb probe) keeps its edge lines whole
    (road,) = site_streets.roads(json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json"))))
    probe_edges = [m for m in site_streets.markings([road]) if m["kind"] == "edge_line"]
    assert len(probe_edges) == 2


def test_parking_keeps_clear_of_the_junction_box():
    through, side = site_streets.roads(_tee())
    for b in site_streets.bays(through):
        x0, x1 = b["t0"] - 60.0, b["t1"] - 60.0
        assert x1 <= -8.0 - site_streets.CROSSING_SETBACK + 1e-9 or \
            x0 >= 8.0 + site_streets.CROSSING_SETBACK - 1e-9, b


def test_the_scene_draws_the_side_streets_slab_and_bands_from_the_band_edge():
    import re
    body, sub = lot._outdoor_nodes(_tee())
    txt = "\n".join(body)
    subs = "\n".join(sub)
    # the side street's slab: centred at plan (0, 29) -> Godot z = -29,
    # 42 m long
    i = txt.index('name="road_1"')
    nums = [float(v) for v in re.search(r"Transform3D\(([^)]*)\)", txt[i:]).group(1).split(",")]
    assert abs(nums[9]) < 1e-6 and abs(nums[11] + 29.0) < 1e-6, nums
    j = subs.index('id="BoxShape_road_1"')
    assert "size = Vector3(42, " in subs[j:].split("\n")[1]
    # every band piece of the side street lies north of the through road's
    # band edge (plan y >= 8, Godot z <= -8), and there is no kerbcut of
    # its own left over the mouth
    assert 'name="sidewalk_1L_' in txt
    for m in re.finditer(r'name="(sidewalk|kerbcut)_1[LR]_\d+" type="StaticBody3D" parent="\."\]\ntransform = Transform3D\(([^)]*)\)', txt):
        vals = [float(v) for v in m.group(2).split(",")]
        assert -vals[11] >= 8.0 - 1e-6, (m.group(1), vals[11])


def test_the_manifest_carries_the_slab_and_the_cuts_terminal_flag(tmp_path):
    spec = _tee()
    p = tmp_path / "tee.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    lot.assemble(str(p), str(tmp_path))
    doc = json.loads((tmp_path / "tee.markings.json").read_text(encoding="utf-8"))
    assert doc["roads"][1]["slab"] == [8.0, 50.0]
    (cut,) = doc["roads"][0]["kerbs"][0]["cuts"]
    assert cut["terminal"] is True and cut["sidewalk"] == 3


def test_the_written_scene_wears_the_paint_pack_as_a_scissor_decal(tmp_path):
    """Cold run 9028: the spec named the road-paint pack, `ground_skins`
    resolved it, and the scene shipped flat markings -- the writer's
    'present' table did not know the family."""
    pack = tmp_path / "road_paint_delco_1997"
    pack.mkdir()
    (pack / "road_paint_delco_albedo.png").write_bytes(b"PNG")
    (pack / "road_paint_delco.pack.json").write_text(json.dumps({
        "maps": {"albedo": "road_paint_delco_albedo.png"}, "meters_per_tile": 0.5,
        "material_profile": "road_paint_delco",
        "import_hints": {"interpolation": "nearest",
                         "transparency": {"opacity": 1.0, "alpha_mode": "scissor"}}}),
        encoding="utf-8")
    spec = _tee()
    spec["ground_skins"] = {"paint": str(pack)}
    p = tmp_path / "tee.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    lot.assemble(str(p), str(tmp_path))
    txt = (tmp_path / "tee.tscn").read_text(encoding="utf-8")
    assert 'id="skin_paint_albedo"' in txt
    assert txt.count("transparency = 2") >= 1
    assert "albedo_color = Color(0.9, 0.9, 0.88, 1)" in txt        # the white tint
    assert (tmp_path / "skins" / "road_paint_delco_albedo.png").exists()


def _cross():
    """Two 10 m roads with 3 m bands crossing at the origin: an X."""
    return {"name": "cross", "ground": {"size_x": 140, "size_y": 140},
            "buildings": [],
            "roads": [{"a": [-60, 0], "b": [60, 0], "width": 10, "sidewalk": 3},
                      {"a": [0, -60], "b": [0, 60], "width": 10, "sidewalk": 3}]}


def test_an_x_crossing_gaps_the_higher_road_over_the_lowers_box():
    ew, ns = site_streets.roads(_cross())
    assert ew.gaps == [] and ew.slab == (0.0, 120.0)
    assert ns.slab == (0.0, 120.0) and ns.gaps == [(52.0, 68.0)]     # 60 +- (5 + 3)
    assert site_streets.drawn_spans(ns) == [(0.0, 52.0), (68.0, 120.0)]
    assert site_streets.drawn_spans(ew) == [(0.0, 120.0)]
    for c in ns.crossings + ew.crossings:
        assert c.kind == "road" and not c.terminal
    assert ns.crossings[0].crosser == 0 and ew.crossings[0].crosser == 1


def test_the_scene_draws_the_x_without_a_coplanar_slab():
    import re
    body, sub = lot._outdoor_nodes(_cross())
    txt = "\n".join(body)
    assert 'name="road_0"' in txt and 'name="road_1_0"' in txt and 'name="road_1_1"' in txt
    assert 'name="road_1"' not in txt
    # no piece of road 1 -- slab, sidewalk or dropped kerb -- has its centre
    # inside the box the through road owns (plan |y| < 8)
    for m in re.finditer(r'name="(road_1_\d|sidewalk_1[LR]_[\d_]+|kerbcut_1[LR]_[\d_]+)" type="StaticBody3D" parent="\."\]\ntransform = Transform3D\(([^)]*)\)', txt):
        vals = [float(v) for v in m.group(2).split(",")]
        assert abs(vals[11]) >= 8.0 - 1e-6, (m.group(1), vals[11])
    # the through road's own dropped kerbs carry the crossing
    assert 'name="kerbcut_0L_' in txt and 'name="kerbcut_0R_' in txt
    # and the manifest says so
    doc = site_streets.manifest(_cross())
    assert doc["roads"][1]["gaps"] == [[52.0, 68.0]] and doc["roads"][0]["gaps"] == []
