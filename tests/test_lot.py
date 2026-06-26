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


def test_tactical_intel_isolated():
    """Connectivity graph flags a building with no declared path-route."""
    import site_tactical as st
    spec = {"name": "t",
            "buildings": [{"id": "a", "at": [0, 0]}, {"id": "b", "at": [40, 0]},
                          {"id": "c", "at": [80, 0]}],
            "paths": [{"from": "a", "to": "b"}]}
    r = st.analyze(spec)
    assert r["intel"]["isolated_buildings"] == ["c"], r["intel"]
    print("  tactical intel (isolated buildings): OK")


def test_tactical_assault_gate():
    """Assault objective needs >=2 distinct approaches."""
    import site_tactical as st
    ok = {"name": "t", "mode": "assault", "objective": "obj", "spawn": "s",
          "buildings": [{"id": "s", "at": [0, 0]}, {"id": "m", "at": [20, 20]},
                        {"id": "obj", "at": [40, 0]}],
          "paths": [{"from": "s", "to": "obj"}, {"from": "s", "to": "m"},
                    {"from": "m", "to": "obj"}]}
    st.gate(ok)  # should not raise
    bad = {"name": "t", "mode": "assault", "objective": "obj", "spawn": "s",
           "buildings": [{"id": "s", "at": [0, 0]}, {"id": "obj", "at": [40, 0]}],
           "paths": [{"from": "s", "to": "obj"}]}
    try:
        st.gate(bad)
        assert False, "1-approach assault should fail"
    except st.SiteTacticalError:
        pass
    print("  tactical assault gate (>=2 approaches): OK")


def test_tactical_heist_gate():
    """Heist needs spawn -> objective -> extraction path-connected."""
    import site_tactical as st
    bad = {"name": "t", "mode": "heist", "spawn": "s", "objective": "o",
           "extraction": "e",
           "buildings": [{"id": "s", "at": [0, 0]}, {"id": "o", "at": [30, 0]},
                         {"id": "e", "at": [60, 0]}],
           "paths": [{"from": "s", "to": "o"}]}  # missing o->e
    try:
        st.gate(bad)
        assert False, "disconnected extraction should fail"
    except st.SiteTacticalError:
        pass
    print("  tactical heist gate (spawn->obj->extraction): OK")


def test_tactical_no_mode_no_gate():
    """No declared mode => pure intel, no gates raised."""
    import site_tactical as st
    spec = {"name": "t", "buildings": [{"id": "a", "at": [0, 0]}], "paths": []}
    st.gate(spec)  # must not raise
    print("  tactical no-mode (intel only): OK")


def test_pacing_too_short():
    """A tiny tight compound is flagged as too short vs the 7-15 min target."""
    import site_pacing as sp
    spec={"name":"t","mode":"heist","spawn":"a","objective":"b","extraction":"b",
          "buildings":[{"id":"a","at":[0,0]},{"id":"b","at":[10,0]}],
          "paths":[{"from":"a","to":"b"}]}
    merged={"markers":[{"building":"b","type":"objective"}]}
    p=sp.estimate_pacing(spec,merged)
    assert "TOO SHORT" in p["status"], p["status"]
    assert p["estimate_expected_s"] > 0
    print("  pacing too-short detection: OK")


def test_pacing_breakdown_sums():
    """Breakdown phases sum to the expected estimate (arithmetic is transparent)."""
    import site_pacing as sp
    spec={"name":"t","mode":"heist","spawn":"a","objective":"b","extraction":"c",
          "buildings":[{"id":"a","at":[0,0]},{"id":"b","at":[80,0]},{"id":"c","at":[160,0]}],
          "paths":[{"from":"a","to":"b"},{"from":"b","to":"c"}]}
    merged={"markers":[{"building":"b","type":"objective"}]}
    p=sp.estimate_pacing(spec,merged)
    s=sum(b["secs"] for b in p["breakdown"])
    assert abs(s - p["estimate_expected_s"]) < 1.0, (s, p["estimate_expected_s"])
    print("  pacing breakdown sums to estimate: OK")


def test_pacing_overrides():
    """Spec pacing overrides take effect (more waves -> longer survival)."""
    import site_pacing as sp
    base={"name":"t","mode":"survival","safe":"a","objective":"b",
          "buildings":[{"id":"a","at":[0,0]},{"id":"b","at":[40,0]}],
          "paths":[{"from":"a","to":"b"}]}
    m={"markers":[{"building":"b","type":"objective"}]}
    few=dict(base,pacing={"waves":3}); many=dict(base,pacing={"waves":12})
    assert sp.estimate_pacing(many,m)["estimate_expected_s"] > sp.estimate_pacing(few,m)["estimate_expected_s"]
    print("  pacing overrides: OK")


def test_encounter_intel_facts():
    """Encounter intel returns per-leg geometric facts, not a score."""
    import site_pacing as sp, site_tactical as st
    spec={"name":"t","mode":"heist","spawn":"a","objective":"b","extraction":"b",
          "buildings":[{"id":"a","at":[0,0]},{"id":"b","at":[50,0]}],
          "paths":[{"from":"a","to":"b"}],"cover":[{"at":[25,2]}]}
    adj=st.build_graph(spec)
    e=sp.encounter_intel(spec,adj)
    leg=e["legs"][0]
    assert leg["length_m"]==50.0 and leg["cover_near"]>=1, leg
    assert "score" not in e and "quality" not in e  # never a verdict
    print("  encounter intel (facts not score): OK")


def test_rarity_carries_through():
    """A building's rarity lands on its site record, and stamped door openings
    pass through the merge untouched."""
    import tempfile
    d = tempfile.mkdtemp()
    # building a: very_rare, with all openings stamped (DC now stamps every
    # opening kind, since door/window/breach are all valid entry attempts)
    legendary = {"tier": "legendary", "rank": 4, "color_name": "gold",
                 "hex": "#FFD700", "rgb": [1.0, 0.8431, 0.0]}
    json.dump({"level": "a", "mode": "assault", "building_id": "a",
               "rarity": "legendary", "rarity_color": legendary,
               "openings": [
                   {"kind": "door", "x": 0, "y": -6, "z": 1.1, "building": "a",
                    "rarity": "legendary", "rarity_color": legendary},
                   {"kind": "window", "x": 6, "y": 0, "z": 1.5, "building": "a",
                    "rarity": "legendary", "rarity_color": legendary}]},
              open(os.path.join(d, "a.gameplay.json"), "w"))
    # building b: no rarity declared
    json.dump({"level": "b", "mode": "assault", "rarity": None,
               "openings": [{"kind": "door", "x": 0, "y": 0, "z": 1.1}]},
              open(os.path.join(d, "b.gameplay.json"), "w"))
    # minimal glbs needn't exist for merge_gameplay; it reads gameplay only
    spec = {"name": "t", "buildings": [
        {"id": "a", "glb": "a.glb", "gameplay": "a.gameplay.json", "at": [0, 0]},
        {"id": "b", "glb": "b.glb", "gameplay": "b.gameplay.json", "at": [40, 0]}]}
    merged = lot.merge_gameplay(spec, d)
    by_id = {b["id"]: b for b in merged["buildings"]}
    assert by_id["a"].get("rarity") == "legendary", by_id["a"]
    assert by_id["a"]["rarity_color"]["hex"] == "#FFD700"
    assert "rarity" not in by_id["b"], "no-rarity building must stay clean"
    # the stamped door opening survives the merge; the window now ALSO carries
    # the rarity (a window breach is a valid entry attempt -> must resolve to the
    # building's rarity). Both keep their building tag for is_revealed grouping.
    a_door = [o for o in merged["openings"]
              if o["building"] == "a" and o["kind"] == "door"][0]
    a_win = [o for o in merged["openings"]
             if o["building"] == "a" and o["kind"] == "window"][0]
    assert a_door["rarity_color"]["hex"] == "#FFD700", a_door
    assert a_win["rarity_color"]["hex"] == "#FFD700", a_win
    assert a_win["building"] == "a"
    print("  rarity carry-through (record + all entries incl window): OK")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); n += 1
    print(f"\nAll {n} Lot tests passed.")
