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


def _merged_with(buildings, openings):
    """Minimal merged-site dict for site_enterability tests."""
    return {"buildings": buildings, "openings": openings}


def test_enterability_walled_in_gates():
    """A building whose only entry's approach sits inside a neighbour's
    footprint is walled in -> hard gate."""
    import site_enterability as SE
    # B at origin with a door on its S wall; A parked right below it.
    bldgs = [{"id": "B", "at": [0, 0], "rot": 0, "footprint": [10, 10]},
             {"id": "A", "at": [0, -10], "rot": 0, "footprint": [10, 10]}]
    ops = [{"building": "B", "wall": "S", "kind": "door",
            "width": 1.2, "height": 2.2, "sill": 0.0, "x": 0, "y": -5}]
    site = {"name": "t", "buildings": bldgs}
    merged = _merged_with(bldgs, ops)
    rep = SE.analyze(site, merged)
    assert any("walled in" in e for e in rep["errors"]), rep["errors"]
    try:
        SE.gate(site, merged)
        assert False, "gate should have raised"
    except SE.SiteEnterabilityError:
        pass
    # move the blocker away -> clear approach, gate passes
    bldgs[1]["at"] = [30, 0]
    merged2 = _merged_with(bldgs, ops)
    rep2 = SE.analyze(site, merged2)
    assert not rep2["errors"], rep2["errors"]
    assert rep2["buildings"][0]["clear_entries"] == 1
    print("  enterability walled-in gate + clear pass: OK")


def test_enterability_outside_perimeter_gates():
    """An entry whose approach falls outside the perimeter wall is blocked."""
    import site_enterability as SE
    # building at the south edge, door facing further south = outside perimeter
    bldgs = [{"id": "B", "at": [0, -9], "rot": 0, "footprint": [4, 4]}]
    ops = [{"building": "B", "wall": "S", "kind": "door",
            "width": 1.2, "height": 2.2, "sill": 0.0, "x": 0, "y": -2}]
    site = {"name": "t", "buildings": bldgs,
            "ground": {"size_x": 20, "size_y": 20}, "perimeter": {"height": 3}}
    rep = SE.analyze(site, _merged_with(bldgs, ops))
    assert any("walled in" in e for e in rep["errors"]), rep["errors"]
    print("  enterability outside-perimeter gate: OK")


def test_enterability_no_route_warns_not_gates():
    """Reachable but no authored path to the entry -> warning, never a gate."""
    import site_enterability as SE
    bldgs = [{"id": "B", "at": [0, 0], "rot": 0, "footprint": [6, 6]}]
    ops = [{"building": "B", "wall": "N", "kind": "door",
            "width": 1.2, "height": 2.2, "sill": 0.0, "x": 0, "y": 3}]
    # paths declared, but none near building B's north entry (approach ~ (0,4.5))
    site = {"name": "t", "buildings": bldgs,
            "paths": [{"a": [40, 40], "b": [60, 40], "width": 3}]}
    rep = SE.analyze(site, _merged_with(bldgs, ops))
    assert not rep["errors"], rep["errors"]
    assert any("no authored path" in w for w in rep["warnings"]), rep["warnings"]
    print("  enterability no-route warning (not a gate): OK")


def test_scene_building_instances_tscn():
    """A building referenced by `scene` (a .tscn) is instanced in the site
    .tscn exactly like a `glb` building, and shared scenes dedup to one
    ExtResource. Backward compat: `glb`-only buildings still work."""
    site = {
        "name": "scene_site",
        "ground": {"size_x": 60, "size_y": 60},
        "buildings": [
            {"id": "a", "scene": "bank.tscn", "gameplay": "missing.json",
             "at": [0, 0], "rot": 0},
            {"id": "b", "scene": "bank.tscn", "gameplay": "missing.json",
             "at": [20, 0], "rot": 90},
            {"id": "c", "glb": "warehouse.glb", "gameplay": "missing.json",
             "at": [0, 20], "rot": 0},
        ],
    }
    merged = lot.merge_gameplay(site, "/tmp")
    out = "/tmp/lot_scene/scene_site.tscn"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    lot.write_godot_scene(site, merged, out)
    txt = open(out).read()
    assert 'path="res://bank.tscn"' in txt, "scene .tscn not referenced"
    assert 'path="res://warehouse.glb"' in txt, "glb building broke"
    assert txt.count("[ext_resource") == 2, "shared .tscn should dedup to one"
    assert txt.count("instance=ExtResource") == 3, "three building instances"
    # source resolved into the merged record; glb/scene preserved
    recs = {r["id"]: r for r in merged["buildings"]}
    assert recs["a"]["source"] == "bank.tscn" and recs["a"]["scene"] == "bank.tscn"
    assert recs["c"]["source"] == "warehouse.glb" and recs["c"]["glb"] == "warehouse.glb"
    print("  scene (.tscn) building instances + dedup + glb back-compat: OK")


def test_site_crew_spawn_marker():
    """A site-level crew_spawn marker overrides building spawn markers (the
    crew stages where the SITE says — across the street — not where a
    building's own spec happens to put an attacker_spawn). Symmetric with the
    site-level extraction marker."""
    site = {"name": "t", "spawn": "b",
            "buildings": [{"id": "b", "at": [10, 20]}],
            "site_markers": [{"type": "crew_spawn", "at": [-5, -30]},
                             {"type": "extraction", "at": [40, 0]}]}
    merged = {"markers": [{"type": "attacker_spawn", "building": "b",
                           "x": 10.0, "y": 20.0, "z": 0.0}],
              "site_markers": site["site_markers"], "objectives": []}
    pos = lot._walk_positions(site, merged)
    assert pos["spawn"] == (-5, -30, 0.0), f"site crew_spawn ignored: {pos['spawn']}"
    assert pos["extraction"] == (40, 0, 0.0)
    # without the site marker, the building marker still wins (back-compat)
    merged2 = dict(merged, site_markers=[{"type": "extraction", "at": [40, 0]}])
    pos2 = lot._walk_positions(dict(site, site_markers=merged2["site_markers"]), merged2)
    assert pos2["spawn"] == (10.0, 20.0, 0.0)
    # nav-QA proxies include the site crew_spawn
    anc = lot._navqa_anchors(site, merged)
    assert (-5, -30, 0.0) in anc["player_proxies"]
    print("  site-level crew_spawn marker (walk + nav-QA): OK")


def test_preview_rarity_contract():
    """Preview-synthesized gameplay carries the building's rarity + the
    published contract colour, so the site rarity index works pre-Blender."""
    import preview
    gp = preview.gameplay_from_spec({"name": "p", "rarity": "very_rare"})
    assert gp["rarity"] == "very_rare"
    rc = gp["rarity_color"]
    assert rc["hex"] == "#A335EE" and rc["color_name"] == "purple" and rc["rank"] == 3
    assert "rarity" not in preview.gameplay_from_spec({"name": "p"})
    print("  preview rarity contract stamped: OK")


def test_cater_needs_build():
    """Incremental decision: build if forced, missing, or spec newer than glb."""
    import tempfile, time, cater
    d = tempfile.mkdtemp()
    spec = os.path.join(d, "b.json")
    glb = os.path.join(d, "b.glb")
    open(spec, "w").write("{}")
    assert cater.needs_build(spec, glb) is True            # glb missing
    open(glb, "wb").write(b"x")
    os.utime(spec, (time.time() - 100, time.time() - 100))  # spec older
    assert cater.needs_build(spec, glb) is False            # fresh
    assert cater.needs_build(spec, glb, force=True) is True
    os.utime(spec, None)                                    # spec newer
    assert cater.needs_build(spec, glb) is True
    print("  cater incremental build decision: OK")


def test_cater_facade_jobs():
    """Blocker glb refs map to same-stem DC specs; unknowns reported not fatal;
    reused shells dedupe."""
    import tempfile, cater
    dc = tempfile.mkdtemp()
    os.makedirs(os.path.join(dc, "specs"))
    open(os.path.join(dc, "specs", "shell_a.json"), "w").write("{}")
    site = {"blockers": [
        {"at": [0, 0], "glb": "shell_a.glb"},
        {"at": [9, 0], "glb": "shell_a.glb"},        # same shell reused
        {"at": [5, 0], "glb": "hand_made.glb"},      # no DC spec
        {"at": [7, 0]},                              # plain box
    ]}
    jobs, unknown = cater.facade_jobs(site, dc)
    assert [s for _, s in jobs] == ["shell_a"], jobs
    assert unknown == ["hand_made.glb"], unknown
    print("  cater facade shell job mapping: OK")


def test_walk_and_navqa_scenes_are_lit():
    """The generated walk + nav-QA scenes must carry a sun + sky/ambient rig
    (mirroring DC's walk harness) — without it the runtime renders unlit and
    the editor's preview sun hides the bug. Also: load_steps must stay in sync
    with the resource count, and the walk HUD gets the site's own name."""
    import re, tempfile
    d = tempfile.mkdtemp()
    site = {"name": "littest", "buildings": [
        {"id": "a", "glb": "a.glb", "gameplay": "missing.json", "at": [0, 0]}]}
    merged = {"markers": [], "site_markers": [], "objectives": [],
              "buildings": [{"id": "a", "at": [0, 0], "rot": 0,
                             "source": "a.glb", "glb": "a.glb"}]}
    wp = os.path.join(d, "w.tscn")
    lot.write_walk_scene(site, merged, wp, "littest")
    nq = os.path.join(d, "n.tscn")
    lot.write_navqa_scene(site, merged, nq, "littest")
    for f in (wp, nq):
        t = open(f).read()
        for s in ("DirectionalLight3D", "WorldEnvironment",
                  "ProceduralSkyMaterial", "shadow_enabled = true"):
            assert s in t, f"{f} missing {s}"
        steps = int(re.search(r"load_steps=(\d+)", t).group(1))
        assert steps == t.count("[ext_resource") + t.count("[sub_resource") + 1, \
            f"{f} load_steps out of sync"
    assert 'site_title = "LITTEST"' in open(wp).read()
    print("  walk + nav-QA scenes carry the lighting rig: OK")


def test_portable_scene_refs():
    """portable=True emits RELATIVE ext_resource paths (drop-anywhere pack);
    default stays res:// (project-root assemble). Both walk-scene variants."""
    import tempfile
    d = tempfile.mkdtemp()
    site = {"name": "port", "buildings": [
        {"id": "a", "glb": "a.glb", "gameplay": "missing.json", "at": [0, 0]}]}
    merged = lot.merge_gameplay(site, d)
    p1 = os.path.join(d, "abs.tscn")
    lot.write_godot_scene(site, merged, p1)
    assert 'path="res://a.glb"' in open(p1).read()
    p2 = os.path.join(d, "rel.tscn")
    lot.write_godot_scene(site, merged, p2, portable=True)
    t2 = open(p2).read()
    assert 'path="a.glb"' in t2 and "res://" not in t2
    p3 = os.path.join(d, "w.tscn")
    lot.write_walk_scene(site, merged, p3, "port", portable=True)
    t3 = open(p3).read()
    assert 'path="port.tscn"' in t3 and 'path="lot_site_walk.gd"' in t3 \
        and "res://" not in t3
    print("  portable (relative-ref) scene emission: OK")


def test_package_site_pack():
    """package.py: builds a zip with scenes + assets + contract + README + QA
    scripts, all refs relative; fails loudly when an asset is missing."""
    import tempfile, zipfile, package
    d = tempfile.mkdtemp()
    spec = {"name": "packtest",
            "buildings": [{"id": "a", "glb": "a.glb", "gameplay": "a.gameplay.json",
                           "at": [0, 0]}],
            "blockers": [{"at": [9, 9], "size_x": 4, "size_y": 4, "glb": "shell.glb"}]}
    sp = os.path.join(d, "site.json")
    json.dump(spec, open(sp, "w"))
    # missing assets -> loud SystemExit naming them
    try:
        package.build_pack(sp, out_dir=os.path.join(d, "dist"))
        assert False, "expected SystemExit for missing assets"
    except SystemExit as e:
        assert "a.glb" in str(e) and "shell.glb" in str(e)
    # stage assets next to the spec and build for real
    open(os.path.join(d, "a.glb"), "wb").write(b"G")
    open(os.path.join(d, "shell.glb"), "wb").write(b"G")
    json.dump({"markers": [], "rooms": [], "objectives": [], "loot": [],
               "zones": [], "vertical_links": [], "openings": [],
               "surfaces": [], "surface_roles": {}},
              open(os.path.join(d, "a.gameplay.json"), "w"))
    zp = package.build_pack(sp, out_dir=os.path.join(d, "dist"))
    assert os.path.basename(zp) == "packtest_pack_v0.0.0.zip", zp
    names = set(zipfile.ZipFile(zp).namelist())
    need = {"packtest_pack/packtest.tscn", "packtest_pack/packtest_walk.tscn",
            "packtest_pack/pack.manifest.json",
            "packtest_pack/packtest.site.gameplay.json",
            "packtest_pack/PACK_README.md", "packtest_pack/a.glb",
            "packtest_pack/shell.glb", "packtest_pack/lot_site_walk.gd",
            "packtest_pack/lot_player.gd"}
    assert need <= names, need - names
    tscn = zipfile.ZipFile(zp).read("packtest_pack/packtest.tscn").decode()
    assert "res://" not in tscn
    print("  package.py site pack (contents + relative refs + gate): OK")


def test_package_reproducible_release():
    """A pack is a traceable RELEASE: versioned by the site's own version,
    byte-identical for identical inputs (deterministic zip, no timestamps),
    every file hash recorded in pack.manifest.json, DC build provenance
    chained per asset, sidecar .sha256 matching the zip."""
    import tempfile, time, zipfile, hashlib, package
    d = tempfile.mkdtemp()
    spec = {"name": "repro", "version": "1.2.3",
            "buildings": [{"id": "a", "glb": "a.glb",
                           "gameplay": "a.gameplay.json", "at": [0, 0]}]}
    sp = os.path.join(d, "site.json")
    json.dump(spec, open(sp, "w"))
    open(os.path.join(d, "a.glb"), "wb").write(b"GLBBYTES")
    json.dump({"kit_name": "Deli Counter", "kit_version": "0.54.0",
               "spec": "a.json", "spec_sha256_16": "abcd1234abcd1234",
               "built_utc": "x"}, open(os.path.join(d, "a.manifest.json"), "w"))
    json.dump({"markers": [], "rooms": [], "objectives": [], "loot": [],
               "zones": [], "vertical_links": [], "openings": [],
               "surfaces": [], "surface_roles": {}},
              open(os.path.join(d, "a.gameplay.json"), "w"))
    z1 = package.build_pack(sp, out_dir=os.path.join(d, "d1"), note="walked")
    time.sleep(1.1)
    z2 = package.build_pack(sp, out_dir=os.path.join(d, "d2"), note="walked")
    b1 = open(z1, "rb").read()
    assert b1 == open(z2, "rb").read(), "pack not byte-identical across runs"
    assert os.path.basename(z1) == "repro_pack_v1.2.3.zip"
    zf = zipfile.ZipFile(z1)
    man = json.loads(zf.read("repro_pack/pack.manifest.json"))
    assert man["assets"]["a.glb"]["deli_counter"]["kit_version"] == "0.54.0"
    assert man["note"] == "walked"
    for fn, rec in man["files"].items():
        if fn == "pack.manifest.json":
            continue
        h = hashlib.sha256(zf.read(f"repro_pack/{fn}")).hexdigest()
        assert h == rec["sha256"], f"hash mismatch: {fn}"
    assert open(z1 + ".sha256").read().split()[0] \
        == hashlib.sha256(b1).hexdigest()
    print("  package reproducible release (deterministic + provenance): OK")


def test_ladder_climb_volumes():
    """Lot's half of the DC ladder contract: preview synthesizes ladder
    markers from the spec's ladders array (parity with the Blender build),
    and the walk scene emits an Area3D climb volume (group "ladder") per
    marker, placed through the building transform, sized like DC's
    post-import (+1 m dismount lip, base-anchored)."""
    import tempfile, preview
    gp = preview.gameplay_from_spec({
        "name": "lad", "story_height": 3.0,
        "ladders": [{"x": 2.0, "y": -3.0, "from_story": 0, "to_story": 2,
                     "width": 0.5, "depth": 0.15, "facing": "N"}]})
    lm = [m for m in gp["markers"] if m["type"] == "ladder"]
    assert len(lm) == 1 and lm[0]["climb_height"] == 6.0 and lm[0]["z"] == 0.0
    merged = {"markers": [{"name": "b/LADDER_0", "type": "ladder",
                           "x": 10.0, "y": 4.0, "z": 3.0,
                           "climb_height": 3.6, "width": 0.5, "depth": 0.15,
                           "building": "b"}],
              "site_markers": [], "objectives": [],
              "buildings": [{"id": "b", "at": [0, 0], "rot": 0,
                             "source": "b.glb", "glb": "b.glb"}]}
    site = {"name": "lad", "buildings": [
        {"id": "b", "glb": "b.glb", "gameplay": "x.json", "at": [0, 0]}]}
    d = tempfile.mkdtemp()
    wp = os.path.join(d, "w.tscn")
    lot.write_walk_scene(site, merged, wp, "lad")
    t = open(wp).read()
    assert 'type="Area3D" parent="." groups=["ladder"]' in t
    assert "0, 0, 1, 10.0, 3.0, -4.0)" in t     # site (x,y,z) -> Godot (x,z,-y)
    assert "size = Vector3(1.3, 4.6, 1.3)" in t  # w=max(.5+.8,1), h=3.6+1 lip
    import re
    steps = int(re.search(r"load_steps=(\d+)", t).group(1))
    assert steps == t.count("[ext_resource") + t.count("[sub_resource") + 1
    gd = open(os.path.join(os.path.dirname(__file__), "..", "godot",
                           "addons", "lot", "lot_player.gd")).read()
    assert "_current_ladder" in gd and "func _climb" in gd
    print("  ladder climb volumes (preview parity + walk scene + player): OK")


def test_building_needs_geometry():
    """A building with neither scene nor glb is a spec error."""
    site = {"name": "bad", "buildings": [
        {"id": "x", "gameplay": "missing.json", "at": [0, 0]}]}
    try:
        lot.merge_gameplay(site, "/tmp")
        assert False, "expected ValueError for missing geometry"
    except ValueError as e:
        assert "no geometry" in str(e)
    print("  building with no geometry rejected: OK")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); n += 1
    print(f"\nAll {n} Lot tests passed.")
