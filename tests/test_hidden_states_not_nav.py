"""A hidden interactive state is not navigation (0.142.0).

Godot's navmesh parse takes every MeshInstance3D under the region, visible or not --
`MeshInstance3D::navmesh_parse_source_geometry` checks no visibility, read off godotengine/godot master on
2026-10-31 -- and a composed building parks each interactive's other states hidden at the same transform. The walker
asked for the slice's vault door open, "open enough to get inside (human/enemies colision)": shown open, the hidden
shut door still baked a disc across the vault's mouth, so the crew (physics) could walk in and the enemies (the
navmesh) could not.

THE INSTRUMENT IS A REAL BAKE, AND IT IS SHOWN IT CAN SEE THE DIFFERENCE. A headless Godot builds a 10 m floor under a
NavigationRegion3D (parsed geometry BOTH, as Lot's walk bake) with a door across it -- a 10 x 2.5 x 0.3 m slab
standing on the floor's centre line, hidden and carrying `metadata/interactive_state` -- and bakes twice: as Godot
does (the control -- the floor must stop at the slab, or the slab was never in the bake and the test proves nothing),
then through `lot_navqa_setup.gd`'s `_park_hidden_states`. Python reads both meshes and decides.

REFUTED, kept: the first fixture was a hidden 2 m CUBE and the question "is its centre a hole". The cube was in the
bake (its lid came back as walkable ground 2.2 m up), but Recast fills nothing in: the floor inside it survived as a
walled-off island, so the centre was "covered" in the control and the test could not tell the two bakes apart. A door
is a slab across a passage, and the question is whether the floor runs through it.

FAILS ON 0.141.0: there is no `_park_hidden_states`, and the parked bake is cut by the door as the control is.
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
ADDON = os.path.join(HERE, "godot", "addons", "lot")

PROBE = r'''extends SceneTree

func _bake(park: bool, setup: Script) -> Dictionary:
	var region := NavigationRegion3D.new()
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_BOTH
	nm.cell_size = 0.1
	nm.cell_height = 0.1
	nm.agent_radius = 0.4
	region.navigation_mesh = nm
	root.add_child(region)
	var floor := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(10, 10)
	floor.mesh = pm
	region.add_child(floor)
	var shut := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(10, 2.5, 0.3)
	shut.mesh = bm
	shut.position = Vector3(0, 1.25, 0)
	shut.visible = false
	shut.set_meta("interactive_state", "locked")
	region.add_child(shut)
	var parked: Array = []
	if park:
		parked = setup._park_hidden_states(region)
	region.bake_navigation_mesh(false)
	if park:
		setup._unpark_states(parked)
	var polys: Array = []
	for i in nm.get_polygon_count():
		polys.append(Array(nm.get_polygon(i)))
	var verts: Array = []
	for v in nm.get_vertices():
		verts.append([v.x, v.y, v.z])
	var back := shut.get_parent() == region and shut.get_index() == 1
	region.queue_free()
	return {"verts": verts, "polys": polys, "parked": parked.size(), "restored": back}


func _initialize() -> void:
	# the root enters the tree after this returns, and a bake parses only what is in it
	_run.call_deferred()


func _run() -> void:
	var setup: Script = load("res://lot_navqa_setup.gd")
	var out := {"control": _bake(false, setup), "parked": {}}
	if setup.has_method("_park_hidden_states"):
		out["parked"] = _bake(true, setup)
	print("PROBE_JSON " + JSON.stringify(out))
	quit()
'''


def _covers(mesh, x, z, floor_y=0.0):
    """True when (x, z) lies inside a baked polygon ON THE FLOOR (every vertex within 0.3 m of ``floor_y``; metres,
    Godot's frame, Y up). REFUTED, kept: the first cut tested XZ alone, and the control "covered" its centre --
    Godot bakes the hidden 2 m box's lid as walkable ground 2 m up, a polygon over the very point asked about."""
    vs = mesh["verts"]
    for poly in mesh["polys"]:
        if any(abs(vs[i][1] - floor_y) > 0.3 for i in poly):
            continue
        pts = [(vs[i][0], vs[i][2]) for i in poly]
        inside = False
        for k in range(len(pts)):
            (x0, z0), (x1, z1) = pts[k], pts[(k + 1) % len(pts)]
            if (z0 > z) != (z1 > z) and x < x0 + (z - z0) * (x1 - x0) / (z1 - z0):
                inside = not inside
        if inside:
            return True
    return False


def test_a_hidden_state_is_kept_out_of_the_bake_and_put_back(tmp_path):
    import walktest
    godot = walktest.find_godot()
    godot = godot[0] if isinstance(godot, tuple) else godot
    if not godot:
        pytest.skip("no Godot 4 (LOT_GODOT / DC_GODOT / PATH)")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "project.godot").write_text('config_version=5\n\n[application]\nconfig/name="probe"\n', encoding="utf-8")
    for name in ("lot_navqa_setup.gd",):
        (proj / name).write_bytes(open(os.path.join(ADDON, name), "rb").read())
    (proj / "probe.gd").write_text(PROBE, encoding="utf-8")
    r = subprocess.run([godot, "--headless", "--path", str(proj), "--script", "res://probe.gd"],
                       capture_output=True, text=True, timeout=180)
    line = next((l for l in (r.stdout or "").splitlines() if l.startswith("PROBE_JSON ")), None)
    assert line, (r.returncode, (r.stdout or "")[-1500:], (r.stderr or "")[-1500:])
    got = json.loads(line[len("PROBE_JSON "):])
    control = got["control"]
    # the control: the floor baked, and the hidden door cuts it (Godot's own behaviour) -- else nothing is measured
    assert control["polys"] and _covers(control, 4.0, 4.0)
    assert not _covers(control, 0.0, 0.0)
    parked = got["parked"]
    assert parked, "lot_navqa_setup.gd has no _park_hidden_states"
    assert parked["parked"] == 1 and parked["restored"]
    assert _covers(parked, 0.0, 0.0) and _covers(parked, 4.0, 4.0)
