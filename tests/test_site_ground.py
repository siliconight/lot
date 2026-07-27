"""A hole is cut in the site ground only where a building floors itself.

Guards the defect where Lot cut an inset hole under every building on the
premise that "the building's own slabs floor the interior". A baked shell.glb
imports as MeshInstance3D with no collision, so the premise was false and the
hole stayed a hole. Four adjacent footprints merged into one void carrying the
spawn, the objective, the extraction and every enemy; Laser Tag rayed down from
the spawn, hit nothing, refused the map with NO_WORLD_COLLISION and completed
zero runs -- four steps and fifteen minutes downstream of the cause.
"""
import json, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot
import site_ground


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _glb(node_names):
    """A minimal but real .glb: 12-byte header + a JSON chunk."""
    doc = json.dumps({"asset": {"version": "2.0"},
                      "nodes": [{"name": n} for n in node_names]}).encode()
    doc += b" " * (-len(doc) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    return struct.pack("<III", 0x46546C67, 2, 12 + len(chunk)) + chunk


def _write_glb(tmp_path, name, node_names):
    p = os.path.join(str(tmp_path), name)
    with open(p, "wb") as f:
        f.write(_glb(node_names))
    return p


def _site(building_ids, source_name, ground=(120, 80)):
    return {
        "name": "t", "ground": {"size_x": ground[0], "size_y": ground[1]},
        "buildings": [
            {"id": bid, "glb": source_name, "at": [i * 40 - 40, 0], "rot": 0,
             "_footprint": [24.0, 18.0]}
            for i, bid in enumerate(building_ids)
        ],
    }


def _ground_slabs(body):
    return [ln for ln in body if 'name="Ground' in ln]


# ---------------------------------------------------------------------------
# reading a source
# ---------------------------------------------------------------------------
def test_a_plain_shell_glb_brings_no_collision(tmp_path):
    p = _write_glb(tmp_path, "shell.glb", ["Shell", "Roof", "Wall_0"])
    rep = site_ground.inspect_source(p)
    assert rep.state == site_ground.ABSENT
    assert not rep.floors_itself
    print("  plain shell.glb: OK (no collision)")


def test_a_col_suffixed_node_brings_collision(tmp_path):
    p = _write_glb(tmp_path, "shell.glb", ["Shell", "floor-col"])
    assert site_ground.inspect_source(p).state == site_ground.PRESENT


def test_every_documented_collision_suffix_counts():
    for suffix in site_ground.COLLISION_SUFFIXES:
        assert site_ground.name_generates_collision("floor" + suffix), suffix


def test_blenders_duplicate_numbering_does_not_hide_the_suffix():
    # Blender appends `.001` to duplicate names; Godot still imports it.
    assert site_ground.name_generates_collision("floor-col.001")
    assert site_ground.name_generates_collision("Floor-ConvCol")


def test_a_name_that_merely_contains_col_is_not_a_collider():
    assert not site_ground.name_generates_collision("column_0")
    assert not site_ground.name_generates_collision("col-floor")


def test_import_settings_can_grant_collision_instead(tmp_path):
    p = _write_glb(tmp_path, "shell.glb", ["Shell"])
    with open(p + ".import", "w", encoding="utf-8") as f:
        f.write('[params]\n_subresources={"nodes": {"PATH:Shell": '
                '{"generate/physics": true}}}\n')
    assert site_ground.inspect_source(p).state == site_ground.PRESENT


def test_a_missing_file_is_unknown_not_absent(tmp_path):
    rep = site_ground.inspect_source(os.path.join(str(tmp_path), "nope.glb"))
    assert rep.state == site_ground.UNKNOWN
    assert "not found" in rep.detail


def test_a_truncated_glb_is_unknown_not_absent(tmp_path):
    p = os.path.join(str(tmp_path), "bad.glb")
    with open(p, "wb") as f:
        f.write(b"glTF" + b"\x00" * 8)
    assert site_ground.inspect_source(p).state == site_ground.UNKNOWN


def test_a_tscn_with_a_static_body_floors_itself(tmp_path):
    p = os.path.join(str(tmp_path), "b.tscn")
    with open(p, "w", encoding="utf-8") as f:
        f.write('[gd_scene format=3]\n[node name="B" type="Node3D"]\n'
                '[node name="slab" type="StaticBody3D" parent="."]\n')
    assert site_ground.inspect_source(p).state == site_ground.PRESENT


def test_a_tscn_inherits_collision_from_what_it_instances(tmp_path):
    mod = os.path.join(str(tmp_path), "mod.tscn")
    with open(mod, "w", encoding="utf-8") as f:
        f.write('[gd_scene format=3]\n'
                '[node name="slab" type="StaticBody3D"]\n')
    p = os.path.join(str(tmp_path), "b.tscn")
    with open(p, "w", encoding="utf-8") as f:
        f.write('[gd_scene format=3]\n'
                '[ext_resource type="PackedScene" path="res://mod.tscn" id="m"]\n'
                '[node name="B" type="Node3D"]\n'
                '[node name="m" parent="." instance=ExtResource("m")]\n')
    assert site_ground.inspect_source(p).state == site_ground.PRESENT


def test_an_unreadable_instance_makes_the_answer_unknown_not_absent(tmp_path):
    p = os.path.join(str(tmp_path), "b.tscn")
    with open(p, "w", encoding="utf-8") as f:
        f.write('[gd_scene format=3]\n'
                '[ext_resource type="PackedScene" path="res://gone.tscn" id="m"]\n'
                '[node name="B" type="Node3D"]\n')
    assert site_ground.inspect_source(p).state == site_ground.UNKNOWN


def test_a_scene_cycle_terminates(tmp_path):
    a = os.path.join(str(tmp_path), "a.tscn")
    b = os.path.join(str(tmp_path), "b.tscn")
    for src, other in ((a, "b.tscn"), (b, "a.tscn")):
        with open(src, "w", encoding="utf-8") as f:
            f.write('[gd_scene format=3]\n'
                    f'[ext_resource type="PackedScene" path="res://{other}" id="x"]\n'
                    '[node name="R" type="Node3D"]\n')
    assert site_ground.inspect_source(a).state == site_ground.UNKNOWN


# ---------------------------------------------------------------------------
# the ground policy
# ---------------------------------------------------------------------------
def test_a_shell_without_collision_keeps_its_ground(tmp_path):
    _write_glb(tmp_path, "shell.glb", ["Shell"])
    spec = _site(["b0", "b1", "b2", "b3"], "shell.glb")
    reports = site_ground.audit(spec, [str(tmp_path)])
    body, _ = lot._outdoor_nodes(
        spec, self_flooring=site_ground.self_flooring_ids(reports))
    assert len(_ground_slabs(body)) == 1, "the ground was cut up around a void"
    print("  unfloored shells: OK (ground kept solid)")


def test_a_shell_with_collision_still_gets_its_hole(tmp_path):
    _write_glb(tmp_path, "shell.glb", ["Shell", "floor-col"])
    spec = _site(["b0"], "shell.glb")
    reports = site_ground.audit(spec, [str(tmp_path)])
    body, _ = lot._outdoor_nodes(
        spec, self_flooring=site_ground.self_flooring_ids(reports))
    assert len(_ground_slabs(body)) > 1, "the basement stairwell got sealed"
    print("  floored shells: OK (hole still cut)")


def test_the_hole_is_cut_per_building_not_all_or_nothing(tmp_path):
    _write_glb(tmp_path, "solid.glb", ["Shell", "floor-col"])
    _write_glb(tmp_path, "hollow.glb", ["Shell"])
    spec = _site(["b0", "b1"], "solid.glb")
    spec["buildings"][1]["glb"] = "hollow.glb"
    reports = site_ground.audit(spec, [str(tmp_path)])
    assert site_ground.self_flooring_ids(reports) == {"b0"}


def test_an_unchecked_site_cuts_no_holes(tmp_path):
    # The default must never be the one that can open a void.
    spec = _site(["b0"], "shell.glb")
    body, _ = lot._outdoor_nodes(spec)
    assert len(_ground_slabs(body)) == 1


def test_ground_stays_deterministic(tmp_path):
    _write_glb(tmp_path, "shell.glb", ["Shell", "floor-col"])
    spec = _site(["b0", "b1"], "shell.glb")
    flooring = site_ground.self_flooring_ids(
        site_ground.audit(spec, [str(tmp_path)]))
    first = lot._outdoor_nodes(spec, self_flooring=flooring)
    second = lot._outdoor_nodes(spec, self_flooring=flooring)
    assert first == second


# ---------------------------------------------------------------------------
# and it says so out loud
# ---------------------------------------------------------------------------
def test_a_pass_through_shell_is_reported_even_though_the_ground_was_kept(tmp_path):
    _write_glb(tmp_path, "shell.glb", ["Shell"])
    spec = _site(["b0", "b1"], "shell.glb")
    found = site_ground.findings(site_ground.audit(spec, [str(tmp_path)]))
    assert [f["code"] for f in found] == ["LOT_SHELL_NO_COLLISION"]
    assert found[0]["severity"] == "major"
    assert "b0" in found[0]["message"] and "b1" in found[0]["message"]
    print("  reporting: OK (pass-through shells named)")


def test_a_resolved_path_beats_a_same_named_file_on_the_search_path(tmp_path):
    """The pack builder resolves its own assets; the audit must read those
    bytes, not a same-named decoy that happened to sit earlier on the path."""
    decoy = os.path.join(str(tmp_path), "decoy")
    real = os.path.join(str(tmp_path), "real")
    os.makedirs(decoy)
    os.makedirs(real)
    _write_glb(decoy, "shell.glb", ["Shell"])
    _write_glb(real, "shell.glb", ["Shell", "floor-col"])
    spec = _site(["b0"], "shell.glb")
    reports = site_ground.audit(
        spec, [decoy], resolved={"shell.glb": os.path.join(real, "shell.glb")})
    assert reports["b0"].state == site_ground.PRESENT


def test_a_missing_shell_reports_as_uncheckable_not_as_hollow(tmp_path):
    spec = _site(["b0"], "absent.glb")
    found = site_ground.findings(site_ground.audit(spec, [str(tmp_path)]))
    assert [f["code"] for f in found] == ["LOT_SHELL_COLLISION_UNKNOWN"]


def test_a_fully_floored_site_reports_nothing(tmp_path):
    _write_glb(tmp_path, "shell.glb", ["Shell", "floor-col"])
    spec = _site(["b0"], "shell.glb")
    assert site_ground.findings(site_ground.audit(spec, [str(tmp_path)])) == []


def _ground_rects(tscn_text):
    """(x0, x1, z0, z1) for every Ground slab, in scene-root space.

    A deliberately small reader of Lot's own output: the ground is written as
    StaticBody3D + BoxShape3D pairs, and whether a point stands on one is
    arithmetic, not opinion. Level Factory's pre-flight parses the same two
    facts out of the same text -- this keeps Lot honest without either repo
    importing the other.
    """
    sizes = {}
    for sid, sx, _sy, sz in re.findall(
            r'\[sub_resource type="BoxShape3D" id="([^"]+)"\]\s*\n'
            r'size = Vector3\(([-\d.e]+), ([-\d.e]+), ([-\d.e]+)\)', tscn_text):
        sizes[sid] = (float(sx), float(sz))
    rects = []
    for name, block in re.findall(
            r'\[node name="(Ground[^"]*)" type="StaticBody3D"[^\]]*\]\n'
            r'((?:(?!\[node name="[^"]*" type="StaticBody3D").)*)',
            tscn_text, re.S):
        tr = re.search(r"transform = Transform3D\(([^)]*)\)", block)
        shape = re.search(r'shape = SubResource\("([^"]+)"\)', block)
        if not tr or not shape or shape.group(1) not in sizes:
            continue
        nums = [float(v) for v in tr.group(1).split(",")]
        cx, cz = nums[9], nums[11]
        sx, sz = sizes[shape.group(1)]
        rects.append((cx - sx / 2, cx + sx / 2, cz - sz / 2, cz + sz / 2))
    return rects


def _lt_points(tscn_text):
    """LT_* hook positions (x, z) from a walk scene."""
    out = {}
    for name, parent, tr in re.findall(
            r'\[node name="([^"]+)" type="Node3D" parent="([^"]+)"\]\n'
            r'transform = Transform3D\(([^)]*)\)', tscn_text):
        if not (name.startswith("LT_") or "LT_" in parent):
            continue
        nums = [float(v) for v in tr.split(",")]
        out[f"{parent}/{name}"] = (nums[9], nums[11])
    return out


def test_no_mission_point_stands_over_a_hole(tmp_path):
    """The whole point, end to end: a block of collisionless shells must not
    put the spawn, the objective or an enemy over a void.

    This is the shape of the real failure -- four adjacent footprints whose
    inset holes merged into one contiguous void carrying 17 of 18 mission
    points, which Laser Tag met as NO_WORLD_COLLISION and zero evaluated runs.
    """
    ids = ["b0", "b1", "b2", "b3"]
    at = {"b0": [0, 0], "b1": [24, 0], "b2": [0, 24], "b3": [24, 24]}
    half = 11.0
    spec = {"name": "block", "ground": {"size_x": 120, "size_y": 80},
            "buildings": [{"id": b, "glb": f"{b}.glb",
                           "gameplay": f"{b}.gameplay.json",
                           "at": at[b], "rot": 0} for b in ids],
            "paths": [{"from": "b0", "to": "b3", "width": 4}],
            "perimeter": {"height": 3},
            "site_markers": [{"type": "extraction", "at": [12, 12]}],
            "mode": "heist", "spawn": "b0", "objective": "b3",
            "extraction": "b3"}
    for b in ids:
        _write_glb(tmp_path, f"{b}.glb", ["Shell", "Roof"])   # no collision
        with open(os.path.join(str(tmp_path), f"{b}.gameplay.json"), "w",
                  encoding="utf-8") as f:
            json.dump({
                "level": b, "mode": "assault", "footprint": [half * 2, half * 2],
                "markers": [{"name": "attacker_spawn", "type": "attacker_spawn",
                             "x": 0, "y": -half + 1, "z": 0},
                            {"name": "objective_0", "type": "objective",
                             "x": 0, "y": 0, "z": 0}],
                "rooms": [{"id": "main", "story": 0,
                           "bounds": [-half, -half, half, half], "role": "entry"}],
                "objectives": [{"id": "vault", "room": "main"}],
                "loot": [], "zones": [], "vertical_links": [], "openings": [],
                "surfaces": [{"node": "slab_0", "material": "Concrete"}],
                "surface_roles": {"slab_0": "floor"}}, f)
    spec_path = os.path.join(str(tmp_path), "block.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)

    out = os.path.join(str(tmp_path), "out")
    result = lot.assemble(spec_path, out)
    walk = os.path.join(out, "block_walk.tscn")
    lot.write_walk_scene(json.load(open(spec_path, encoding="utf-8")),
                         json.load(open(result["gameplay"], encoding="utf-8")),
                         walk, "block", portable=True)

    site_text = open(os.path.join(out, "block.tscn"), encoding="utf-8").read()
    rects = _ground_rects(site_text)
    points = _lt_points(open(walk, encoding="utf-8").read())
    assert points, "the walk scene carried no LaserTag hooks to check"

    floating = [n for n, (x, z) in points.items()
                if not any(x0 <= x <= x1 and z0 <= z <= z1
                           for x0, x1, z0, z1 in rects)]
    assert not floating, (
        f"{len(floating)} of {len(points)} mission point(s) stand over a hole: "
        f"{', '.join(sorted(floating)[:6])}")
    print(f"  end to end: OK ({len(points)} mission points, all on ground)")


def test_the_finding_reaches_the_gameplay_file(tmp_path):
    """End to end: assemble() folds the verdict into tactical.findings, which
    is the array Level Factory's Lot adapter normalizes into findings."""
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "specs")
    spec = json.load(open(os.path.join(src, "example_compound.json")))
    spec_dir = str(tmp_path)
    for f in os.listdir(src):
        if f.endswith(".json") and f != "example_compound.json":
            with open(os.path.join(src, f), encoding="utf-8") as rf:
                open(os.path.join(spec_dir, f), "w", encoding="utf-8").write(rf.read())
    _write_glb(tmp_path, "bank.glb", ["Shell"])
    _write_glb(tmp_path, "warehouse.glb", ["Shell", "floor-col"])
    spec_path = os.path.join(spec_dir, "example_compound.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)

    out = os.path.join(spec_dir, "out")
    result = lot.assemble(spec_path, out)
    data = json.load(open(result["gameplay"], encoding="utf-8"))
    codes = [f.get("code") for f in data["tactical"].get("findings", [])]
    assert "LOT_SHELL_NO_COLLISION" in codes, codes
    assert data["ground"]["bank"]["state"] == site_ground.ABSENT
    assert data["ground"]["warehouse"]["state"] == site_ground.PRESENT
    print("  gameplay file: OK (verdict travels with the site)")
