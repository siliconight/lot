"""Offline tests for the Lot site assembler (Phase 1)."""
import json, os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot

HERE = os.path.dirname(os.path.abspath(__file__))
SPECS = os.path.join(os.path.dirname(HERE), "specs")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_determinism():
    """Same site spec -> byte-identical outputs across runs."""
    r1 = lot.assemble(os.path.join(SPECS, "example_compound.json"), "/tmp/lot_a")
    r2 = lot.assemble(os.path.join(SPECS, "example_compound.json"), "/tmp/lot_b")
    assert _sha(r1["gameplay"]) == _sha(r2["gameplay"]), "gameplay not deterministic"
    assert _sha(r1["scene"]) == _sha(r2["scene"]), "scene not deterministic"
    print("  determinism: OK (byte-identical across runs)")


def test_world_offset_and_rotation():
    """A 90-deg-rotated building's markers land at correct world positions."""
    merged = lot.merge_gameplay(
        json.load(open(os.path.join(SPECS, "example_compound.json"))), SPECS)
    by_name = {m["name"]: m for m in merged["markers"]}
    # warehouse at (45,10) rot90: local spawn (0,-12) -> rotate90 (12,0) -> (57,10)
    ws = by_name["warehouse/attacker_spawn"]
    assert abs(ws["x"] - 57.0) < 1e-6 and abs(ws["y"] - 10.0) < 1e-6, ws
    # warehouse cover local (4,0) -> rotate90 (0,4) -> (45,14)
    wc = by_name["warehouse/cover_0"]
    assert abs(wc["x"] - 45.0) < 1e-6 and abs(wc["y"] - 14.0) < 1e-6, wc
    # bank rot0: unchanged
    bs = by_name["bank/attacker_spawn"]
    assert abs(bs["x"] - 0.0) < 1e-6 and abs(bs["y"] - -10.0) < 1e-6, bs
    print("  world offset + rotation: OK")


def test_namespacing():
    """Same marker/room name in two buildings doesn't collide."""
    merged = lot.merge_gameplay(
        json.load(open(os.path.join(SPECS, "example_compound.json"))), SPECS)
    names = [m["name"] for m in merged["markers"]]
    assert names.count("bank/attacker_spawn") == 1
    assert names.count("warehouse/attacker_spawn") == 1
    assert len(names) == len(set(names)), "marker name collision"
    roles = merged["surface_roles"]
    assert "bank/slab_0" in roles and "warehouse/slab_0" in roles, roles
    print("  namespacing: OK (no collisions across buildings)")


def test_scene_valid():
    """Generated .tscn has the expected structure."""
    r = lot.assemble(os.path.join(SPECS, "example_compound.json"), "/tmp/lot_c")
    txt = open(r["scene"]).read()
    assert txt.startswith("[gd_scene"), "missing scene header"
    assert txt.count("[ext_resource") == 2, "expected 2 building resources"
    assert "res://./" not in txt, "redundant ./ in resource path"
    assert 'instance=ExtResource' in txt
    print("  scene generation: OK")


def test_outdoor_nodes():
    """Phase 2: outdoor geometry generates the expected node set."""
    spec = json.load(open(os.path.join(SPECS, "example_compound.json")))
    body, sub = lot._outdoor_nodes(spec)
    txt = "\n".join(body)
    assert 'name="Ground"' in txt, "missing ground slab"
    assert 'name="path_0"' in txt, "missing path"
    assert 'name="courtyard_0"' in txt, "missing courtyard"
    assert txt.count('name="perim_') == 4, "expected 4 perimeter walls"
    assert txt.count('type="StaticBody3D"') >= 8, "missing outdoor bodies"
    # each box has a BoxMesh + BoxShape3D sub_resource
    n_mesh = sum(1 for ln in sub if ln.startswith('[sub_resource type="BoxMesh"'))
    n_shape = sum(1 for ln in sub if ln.startswith('[sub_resource type="BoxShape3D"'))
    assert n_mesh == n_shape and n_mesh >= 8, (n_mesh, n_shape)
    print("  outdoor nodes: OK (ground/path/courtyard/perimeter/cover)")


def test_path_geometry():
    """A path between two buildings has the right length."""
    spec = json.load(open(os.path.join(SPECS, "example_compound.json")))
    body, sub = lot._outdoor_nodes(spec)
    # bank(0,0)->warehouse(45,10): length = sqrt(45^2+10^2) = 46.0977
    txt = "\n".join(sub)
    assert "46.0977" in txt or "46.097" in txt, "path length wrong"
    print("  path geometry: OK (length matches building separation)")


def test_load_steps():
    """load_steps header matches actual resource count (Godot sanity)."""
    r = lot.assemble(os.path.join(SPECS, "example_compound.json"), "/tmp/lot_ls")
    txt = open(r["scene"]).read()
    import re
    declared = int(re.search(r"load_steps=(\d+)", txt).group(1))
    actual = txt.count("[sub_resource") + txt.count("[ext_resource") + 1
    assert declared == actual, f"load_steps {declared} != {actual}"
    print("  load_steps: OK")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); n += 1
    print(f"\nAll {n} Lot tests passed.")
