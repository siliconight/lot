"""Offline tests for the Lot site assembler (Phase 1)."""
import json, os, re, sys, hashlib
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


def test_a_door_off_the_declared_rim_is_not_walled_in_because_the_plate_grew():
    """A building hanging off the declared plate used to have its door read as
    'outside the perimeter'. The plate is now sized from the buildings on it, so
    the door faces ground and the wall stands further out -- the site is honest
    rather than gated, and the growth is reported instead of assumed.
    """
    import site_enterability as SE
    import site_extent as SX
    # B's footprint reaches y = -11 on a plate declared only to y = -10.
    bldgs = [{"id": "B", "at": [0, -9], "rot": 0, "footprint": [4, 4]}]
    ops = [{"building": "B", "wall": "S", "kind": "door",
            "width": 1.2, "height": 2.2, "sill": 0.0, "x": 0, "y": -2}]
    site = {"name": "t", "buildings": bldgs,
            "ground": {"size_x": 20, "size_y": 20}, "perimeter": {"height": 3}}
    ground = SX.resolve(site)
    assert ground.extended and ground.rect[1] <= -11.0 - SX.CLEARANCE
    assert any(f["code"] == SX.CODE_EXTENDED for f in ground.findings), \
        "the plate grew without saying so"
    rep = SE.analyze(site, _merged_with(bldgs, ops))
    assert not rep["errors"], rep["errors"]
    print("  enterability on an extended plate (not a gate): OK")


def test_enterability_outside_perimeter_gates():
    """An entry whose approach falls outside the perimeter wall is still blocked.

    The premise has to be a plate that genuinely cannot be grown to reach the
    door: with no footprint to read, Lot sizes the ground from B's origin alone,
    so a door standing 6 m out from that origin faces past the rim and is walled
    in. That the shell and the footprint disagree is itself worth saying, so the
    unknown extent is reported alongside.
    """
    import site_enterability as SE
    import site_extent as SX
    # same placement as the extended case, minus the footprint Lot would size from
    bldgs = [{"id": "B", "at": [0, -9], "rot": 0}]
    ops = [{"building": "B", "wall": "S", "kind": "door",
            "width": 1.2, "height": 2.2, "sill": 0.0, "x": 0, "y": -6}]
    site = {"name": "t", "buildings": bldgs,
            "ground": {"size_x": 20, "size_y": 20}, "perimeter": {"height": 3}}
    ground = SX.resolve(site)
    # the plate reaches clearance past B's origin and no further -- there is no
    # footprint telling it the building (or its door) needs more
    assert ground.rect[1] == -9.0 - SX.CLEARANCE
    assert any(f["code"] == SX.CODE_UNKNOWN_EXTENT for f in ground.findings), \
        "an unmeasurable building was passed over in silence"
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
    """Incremental decision: build if forced, missing, or built from a
    different spec than the one on disk now.

    The decision is about CONTENT, not clocks. It used to compare mtimes, and
    a filesystem timestamp comes from a coarse clock one timer tick wide --
    ~1-4 ms on Linux, ~15.6 ms on Windows -- so a spec edited in the same tick
    the build finished compared EQUAL, the strict `>` answered False, and the
    glb was declared current permanently. A digest cannot tie."""
    import tempfile, cater
    d = tempfile.mkdtemp()
    spec = os.path.join(d, "b.json")
    glb = os.path.join(d, "b.glb")
    open(spec, "w").write("{}")
    assert cater.needs_build(spec, glb) is True            # glb missing
    open(glb, "wb").write(b"x")
    assert cater.needs_build(spec, glb) is True            # built, but unstamped
    cater.record_build(spec, glb)
    assert cater.needs_build(spec, glb) is False           # stamped and current
    assert cater.needs_build(spec, glb, force=True) is True
    open(spec, "w").write('{"doors": 2}')                  # spec edited
    assert cater.needs_build(spec, glb) is True
    cater.record_build(spec, glb)
    assert cater.needs_build(spec, glb) is False
    print("  cater incremental build decision: OK")


def test_cater_same_tick_edit_is_not_missed():
    """The defect the digest closes, forced rather than waited for.

    Write the spec and the glb, stamp it, then edit the spec and pin BOTH
    mtimes to one identical value -- exactly what a coarse clock produces when
    two operations land in the same tick. Every mtime comparison says "current";
    the content says otherwise, and the content is right."""
    import tempfile, cater
    d = tempfile.mkdtemp()
    spec = os.path.join(d, "b.json")
    glb = os.path.join(d, "b.glb")
    open(spec, "w").write("{}")
    open(glb, "wb").write(b"x")
    cater.record_build(spec, glb)
    open(spec, "w").write('{"doors": 2}')
    same = 1_700_000_000
    for p in (spec, glb, cater.spec_stamp_path(glb)):
        os.utime(p, (same, same))
    assert os.path.getmtime(spec) == os.path.getmtime(glb)   # the tie, forced
    assert cater.needs_build(spec, glb) is True
    print("  cater same-tick spec edit caught: OK")


def test_cater_unstamped_glb_rebuilds():
    """A glb from before stamps existed cannot say what it came from. Rebuild:
    the cost is Blender time, the alternative is shipping stale geometry."""
    import tempfile, cater
    d = tempfile.mkdtemp()
    spec = os.path.join(d, "b.json")
    glb = os.path.join(d, "b.glb")
    open(spec, "w").write("{}")
    open(glb, "wb").write(b"x")
    os.utime(spec, (1_600_000_000, 1_600_000_000))   # spec far older than glb
    assert cater.needs_build(spec, glb) is True
    print("  cater unstamped glb rebuilds: OK")


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


def test_site_audit_grammar():
    """Site-level grammar: a rewound exfil flags, a responder on the exfil
    flags, a naked anchor flags -- and a backstopped anchor does not."""
    import site_audit
    base = {"name": "t", "mode": "heist",
            "buildings": [{"id": "b", "at": [0, 30]}],
            "spawn": "b", "objective": "b", "extraction": "b",
            "site_markers": [
                {"type": "crew_spawn", "at": [0, -30]},
                {"type": "extraction", "at": [4, -32]},      # 4.5 m away
                {"type": "responder_spawn", "at": [2, -30]},  # on the spawn
            ],
            "cover": [], "roads": [], "blockers": []}
    res = site_audit.audit(base)
    codes = {c for _, c, _ in res["findings"]}
    assert "S_BACKTRACK" in codes          # extraction rewinds the entry
    assert "S_RESPONDER_CAMP" in codes     # wave spawns on the anchor
    assert "S_NAKED_ANCHOR" in codes       # nothing to fight from
    # backstop the spawn, move the exfil + responder: all three clear
    good = dict(base)
    good["site_markers"] = [
        {"type": "crew_spawn", "at": [0, -30]},
        {"type": "extraction", "at": [-45, 0]},
        {"type": "responder_spawn", "at": [45, 0]},
    ]
    good["cover"] = [{"at": [0, -26], "size": [4, 1.5, 1.8]},
                     {"at": [-40, -2], "size": [4, 1.5, 1.8]},
                     {"at": [0, 0], "size": [3, 1.5, 1.8]},
                     {"at": [-22, -12], "size": [3, 1.5, 1.8]}]
    res2 = site_audit.audit(good)
    codes2 = {c for _, c, _ in res2["findings"]}
    for c in ("S_BACKTRACK", "S_RESPONDER_CAMP", "S_NAKED_ANCHOR",
              "S_BARE_LEG"):
        assert c not in codes2, (c, res2["findings"])
    print("  site_audit grammar (backtrack/camp/anchor + clean pass): OK")


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


def test_lights_merge_offset_namespace():
    """Building light anchors are offset to world space and namespaced,
    mirroring the gameplay merge."""
    spec = json.load(open(os.path.join(SPECS, "example_compound.json")))
    m = lot.merge_lights(spec, SPECS)
    by_id = {a["id"]: a for a in m["anchors"]}
    # bank at origin, rot 0 -> unchanged + namespaced
    assert "bank/lobby_ceiling" in by_id
    assert by_id["bank/lobby_ceiling"]["room"] == "bank/lobby"
    # warehouse at (45,10) rot 90 -> anchor offset + rot_y composed
    wh = by_id["warehouse/main_floor_ceiling"]
    assert abs(wh["pos"][0] - 45.0) < 1e-3 and abs(wh["pos"][1] - 10.0) < 1e-3
    assert wh["rot_y"] == 90
    assert wh["building"] == "warehouse"


def test_lights_streetlights_paths_and_perimeter():
    """Lot derives exterior streetlights along paths and the ground perimeter."""
    spec = json.load(open(os.path.join(SPECS, "example_compound.json")))
    m = lot.merge_lights(spec, SPECS)
    ids = [a["id"] for a in m["anchors"] if a["type"] == "streetlight"]
    assert "site/path_0_lights" in ids                 # a row down the road
    assert {"site/perimeter_s_lights", "site/perimeter_n_lights",
            "site/perimeter_w_lights", "site/perimeter_e_lights"} <= set(ids)
    # streetlights are exterior: not alarm-reactive, mounted high
    sl = next(a for a in m["anchors"] if a["id"] == "site/path_0_lights")
    assert sl["reacts_to_alarm"] is False and sl["pos"][2] == lot.STREETLIGHT_H


def test_lights_manifest_shape():
    spec = json.load(open(os.path.join(SPECS, "example_compound.json")))
    m = lot.merge_lights(spec, SPECS)
    assert m["light_manifest_version"] == "1.0.0"
    assert m["rig_library"] == "lux" and m["site"] == "example_compound"


def test_lights_deterministic():
    spec = json.load(open(os.path.join(SPECS, "example_compound.json")))
    a = json.dumps(lot.merge_lights(spec, SPECS), sort_keys=True)
    b = json.dumps(lot.merge_lights(spec, SPECS), sort_keys=True)
    assert a == b


# ---------------------------------------------------------------------------
# The walk scene has to survive contact with Godot and with LaserTag.
# ---------------------------------------------------------------------------
def _walk_scene(tmp_name="ltw", ladder_name="b0/LADDER_0"):
    import tempfile
    merged = {"markers": [{"name": ladder_name, "type": "ladder",
                           "x": 10.0, "y": 4.0, "z": 3.0, "climb_height": 3.6,
                           "width": 0.5, "depth": 0.15, "building": "b0"}],
              "site_markers": [], "objectives": [],
              "buildings": [{"id": "b0", "at": [0, 0], "rot": 0,
                             "source": "b0.glb", "glb": "b0.glb"}]}
    site = {"name": tmp_name, "spawn": "b0", "objective": "b1",
            "extraction": "b2", "buildings": [
                {"id": "b0", "glb": "b0.glb", "gameplay": "x.json", "at": [0, 0]},
                {"id": "b1", "glb": "b1.glb", "gameplay": "x.json", "at": [45, 0]},
                {"id": "b2", "glb": "b2.glb", "gameplay": "x.json", "at": [90, 10]}]}
    p = os.path.join(tempfile.mkdtemp(), "w.tscn")
    lot.write_walk_scene(site, merged, p, tmp_name)
    return open(p).read()


def test_node_names_are_legal_in_godot():
    """A '/' in a node name is not a name -- it is a path, and Godot drops the
    children that reference it.

    Ladder markers are building-namespaced ("b0/LADDER_0"), and Lot wrote that
    straight into `[node name=...]` and into the CollisionShape3D's `parent=`.
    Godot's set_name() rewrites the '/' to '_' on load, the parent string is
    then resolved as the path b0 -> LADDER_0_climb, no such node exists, and
    the shape is dropped: every ladder volume arrived with no collision and
    nothing could climb it. Invisible in Lot's own output, which looked fine.
    """
    t = _walk_scene(ladder_name="b0/LADDER_0")
    assert 'name="b0_LADDER_0_climb"' in t
    assert 'parent="b0_LADDER_0_climb"' in t
    assert "b0/LADDER_0" not in t, "an illegal name survived into the scene"
    # And the volume still carries its shape, which is the whole point.
    assert t.index('name="b0_LADDER_0_climb"') < t.index('parent="b0_LADDER_0_climb"')
    for name in re.findall(r'\[node name="([^"]*)"', t):
        assert not (set(name) & set(lot._GODOT_BAD_NAME_CHARS)), name
    print("  walk scene node names are Godot-legal: OK")


def test_walk_scene_meets_the_lasertag_map_contract():
    """LaserTag finds spawns by node name; without them it never runs.

    The harness walks the tree for LT_PlayerSpawn / LT_EnemySpawnPoints /
    LT_ObjectivePoint. Lot emitted none of them, so validate_map() failed and
    run_evaluation returned before a single firefight -- and the report came
    back grade "BROKEN", runs 0, which every downstream reader treated as a
    verdict on the level instead of on the handoff.
    """
    t = _walk_scene()
    for hook in ("LT_PlayerSpawn", "LT_EnemySpawnPoints", "LT_ObjectivePoint",
                 "LT_PlayerRoutePoints", "LT_CoverTestPoints"):
        assert f'name="{hook}"' in t, f"missing {hook}"
    # LT_EnemySpawnPoints contributes its CHILDREN, so the container alone is
    # still "no enemy spawns found".
    assert t.count('parent="LT_EnemySpawnPoints"') >= 2
    assert t.count('parent="LT_PlayerRoutePoints"') >= 2
    print("  walk scene meets the LaserTag map contract: OK")


def test_enemy_spawns_spread_along_the_route():
    """Enemy spawns stacked on one point are one encounter, not an evaluation."""
    t = _walk_scene()
    block = t[t.index('name="LT_EnemySpawnPoints"'):t.index('name="LT_ObjectivePoint"')]
    xs = re.findall(r"Transform3D\(1, 0, 0, 0, 1, 0, 0, 0, 1, ([-\d.]+),", block)
    assert len(set(xs)) > 1, "every enemy spawned in the same place"


def test_walk_scene_load_steps_still_match():
    """load_steps counts resources, and the hook nodes add none of them."""
    t = _walk_scene()
    steps = int(re.search(r"load_steps=(\d+)", t).group(1))
    assert steps == t.count("[ext_resource") + t.count("[sub_resource") + 1


def test_walk_scene_does_not_race_an_external_navmesh_bake():
    """The walk scene bakes its own navmesh for the human walkthrough. That bake
    is threaded and unawaited, so when an evaluation runner loads the same scene
    headless and bakes it too, Godot refuses the second bake ("NavigationMesh is
    already baking") and leaves a 0-polygon mesh -- which reads identically to a
    map with no collision at all. Laser Tag then reported NAVIGATION_MISSING on
    a fully walkable site and spent 900 seconds watching bots walk into walls.

    Headless means nobody is walking. The bake has to be guarded by that."""
    import os
    gd = open(os.path.join(os.path.dirname(__file__), "..", "godot",
                           "addons", "lot", "lot_site_walk.gd")).read()
    body = gd[gd.index("func _bake_nav"):]
    body = body[:body.index("\nfunc ", 1)]
    # the call, not the several mentions of it in the comment above it
    call = body.index("\tnav.bake_navigation_mesh()")
    guard = body.index('DisplayServer.get_name() == "headless"')
    assert guard < call, (
        "the headless guard must come before the bake, or the runner still races it")
    assert "return" in body[guard:call], (
        "the headless branch has to leave without baking")
    print("  walk scene leaves the headless navmesh bake to the runner: OK")


def test_route_samples_are_interior_and_evenly_spaced():
    """Endpoints are already markers and the marker pass has asked about them.
    What sampling adds is the ground BETWEEN them, which nothing asked about."""
    import site_cover as sc
    route = [(0.0, 0.0), (60.0, 0.0)]
    s = sc.route_samples(route, spacing=15.0)
    assert s == [(15.0, 0.0), (30.0, 0.0), (45.0, 0.0)], s
    # A leg shorter than the spacing has no interior worth sampling.
    assert sc.route_samples([(0.0, 0.0), (10.0, 0.0)], spacing=15.0) == []
    assert sc.route_samples([], spacing=15.0) == []
    print("  route sampling: OK")


def test_route_sightlines_ask_the_opposite_question_to_marker_pairs():
    """`open_sightlines` asks about the OPENING: marker pairs further apart than
    the range at which the fight starts. `route_sightlines` asks about TRANSIT:
    stretches of the walk that lie WITHIN an enemy's reach across open ground.
    A crew walking 20 m from an enemy is not a standoff problem and no marker
    pair describes it, which is how a 74 m approach stayed bare while every
    marker pair on the site was answered."""
    import site_cover as sc
    points = {"LT_PlayerSpawn": (0.0, 0.0), "LT_ObjectivePoint": (80.0, 0.0),
              "Enemy_0": (40.0, 12.0)}
    route = [points["LT_PlayerSpawn"], points["LT_ObjectivePoint"]]
    samples = sc.route_samples(route, spacing=15.0)
    lines = sc.route_sightlines(samples, points, [], envelope=45.0)
    assert lines, "an enemy 12 m off the middle of the walk must be seen"
    assert all(d <= 45.0 for _a, _b, _pa, _pb, d in lines)
    assert all(a.startswith("route@") and b == "Enemy_0"
               for a, b, _pa, _pb, _d in lines)
    # And the enemy is close enough to BOTH endpoints that the opening pass has
    # nothing to say about it at all.
    assert sc.open_sightlines(
        {k: v for k, v in points.items() if k != "LT_ObjectivePoint"},
        [], limit=45.0) == []
    print("  route sightlines (transit, not opening): OK")


def _approach_case():
    points = {"LT_PlayerSpawn": (0.0, 0.0), "LT_ObjectivePoint": (120.0, 0.0),
              "LT_ExtractionPoint": (120.0, 60.0),
              "Enemy_0": (55.0, 14.0), "Enemy_1": (95.0, -16.0)}
    route = [points["LT_PlayerSpawn"], points["LT_ObjectivePoint"],
             points["LT_ExtractionPoint"]]
    return points, route, (-40.0, -60.0, 180.0, 100.0)


def test_cover_lands_on_the_approach_not_only_at_the_markers():
    """The defect, in miniature. Budgeting cover against marker pairs alone put
    all four of seed 5017's pieces at the objective, 69 m from the crew spawn
    and 10.8-19.3 m from an enemy — cover for the enemies, bought with the
    crew's budget. The route pass puts pieces on the ground the crew crosses."""
    import site_cover as sc
    points, route, ground = _approach_case()
    without = sc.plan_cover(points, [], ground, opening_range=45.0)
    with_route = sc.plan_cover(points, [], ground, opening_range=45.0, route=route)

    assert len(with_route.cover) > len(without.cover)
    named = [c for c in with_route.cover if c.breaks.startswith("route@")]
    assert named, "the route pass placed nothing"

    def nearest_to_route(plan):
        best = float("inf")
        for c in plan.cover:
            for a, b in zip(route, route[1:]):
                best = min(best, _point_segment_distance((c.x, c.y), a, b))
        return best

    assert nearest_to_route(with_route) <= nearest_to_route(without) + 1e-6
    print("  route cover placement: OK")


def _point_segment_distance(p, a, b):
    import math
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def test_route_budget_scales_with_the_route_and_is_reported_when_short():
    """A flat twelve is generous on a 40 m approach and nothing on a 250 m one.
    When the budget runs out the remaining exposure is reported rather than
    silently dropped — a bare stretch nobody mentions is the same defect as an
    unbroken sightline nobody mentions."""
    import site_cover as sc
    points, route, ground = _approach_case()
    plan = sc.plan_cover(points, [], ground, opening_range=45.0, route=route,
                         route_metres_per_piece=1000.0)   # budget of 1
    assert len([c for c in plan.cover if c.breaks.startswith("route@")]) == 1
    assert plan.route_open, "unspent exposure must be reported"
    codes = {f["code"] for f in sc.findings(plan, opening_range=45.0)}
    assert "LOT_ROUTE_EXPOSED" in codes
    assert "LOT_ROUTE_COVER_PLACED" in codes
    print("  route budget + exposure reporting: OK")


def test_route_exposure_is_not_folded_into_the_open_sightline_finding():
    """`open_lines` means "too far apart and open"; `route_open` means "close
    and open". One finding cannot say both without lying about one of them."""
    import site_cover as sc
    points, route, ground = _approach_case()
    plan = sc.plan_cover(points, [], ground, opening_range=45.0, route=route,
                         route_metres_per_piece=1000.0)
    assert all(d <= 45.0 for _a, _b, _pa, _pb, d in plan.route_open)
    assert all(d > 45.0 for _a, _b, _pa, _pb, d in plan.open_lines)
    print("  route exposure kept distinct from open sightlines: OK")


def _cover_hook_origins(body):
    """(x, y, z) of every LT_CoverTestPoints hook in an emitted node body."""
    import re
    text = "\n".join(body)
    out = []
    for m in re.finditer(
            r'\[node name="Cover_\d+" type="Node3D" parent="LT_CoverTestPoints"\]\n'
            r'transform = Transform3D\(([^)]*)\)', text):
        nums = [float(v) for v in m.group(1).split(",")]
        out.append(tuple(nums[-3:]))
    return out


def test_cover_hooks_name_the_cover_that_exists():
    """`LT_CoverTestPoints` is the list the crew bot's cover-seek reads. It was
    a hardcoded rosette 5 m around the objective, unrelated to any cover the
    site had — so `_on_damaged` seeking "nearest cover" always sought the
    objective, wherever `site_cover` had actually put anything. On seed 5017
    that sent a crew taking fire 69 m out walking toward four imaginary points
    10.8–19.4 m from an enemy spawn."""
    spec = {"cover": [{"at": [10.0, 20.0], "size": [3.0, 2.0, 3.0]},
                      {"at": [-30.0, 5.0], "size": [3.0, 2.0, 3.0]},
                      {"at": [55.0, -12.0], "size": [3.0, 2.0, 3.0]}]}
    pos = {"spawn": (0.0, 0.0, 0.0), "objective": (100.0, 0.0, 0.0),
           "extraction": (100.0, 60.0, 0.0)}
    body = lot._lasertag_hook_nodes(pos, spec)
    got = _cover_hook_origins(body)
    assert len(got) == 3, f"one hook per placed piece, got {got}"
    # Godot frame: site (x, y) -> (x, _, -y). Compare what the bot will read.
    assert [(round(gx, 3), round(-gz, 3)) for gx, _gy, gz in got] == [
        (10.0, 20.0), (-30.0, 5.0), (55.0, -12.0)], got
    # The rosette is gone: nothing sits at objective +/- 5 m any more.
    assert all(abs(gx - 100.0) > 1e-6 for gx, _gy, _gz in got), got
    print("  LT cover hooks follow the placed cover: OK")


def test_a_site_with_no_planned_cover_keeps_the_fallback():
    """The hook is optional to Laser Tag, but an EMPTY node reads as "this map
    has no cover" when what is true is "nothing was planned". Those want
    different answers, so a site with no cover keeps the old rosette rather
    than emitting nothing."""
    pos = {"spawn": (0.0, 0.0, 0.0), "objective": (100.0, 0.0, 0.0),
           "extraction": (100.0, 60.0, 0.0)}
    body = "\n".join(lot._lasertag_hook_nodes(pos, {"cover": []}))
    assert body.count('name="Cover_') == 4
    body_none = "\n".join(lot._lasertag_hook_nodes(pos, None))
    assert body_none.count('name="Cover_') == 4
    print("  cover hook fallback when nothing was planned: OK")


def test_malformed_cover_records_do_not_reach_the_hook():
    """A record without a usable `at` is not a position. Emitting a hook from
    one would put a cover marker wherever the parse happened to land, and a bot
    seeking it would walk to where nothing is.

    Scoped to malformed *records*: a non-dict entry in `cover` breaks
    `site_spawns` well before the hooks are written, so guarding against one
    here would only be theatre."""
    spec = {"cover": [{"size": [3.0, 2.0, 3.0]}, {"at": [1.0]},
                      {"at": [7.0, 8.0], "size": [3.0, 2.0, 3.0]}]}
    pos = {"spawn": (0.0, 0.0, 0.0), "objective": (100.0, 0.0, 0.0),
           "extraction": (100.0, 60.0, 0.0)}
    body = "\n".join(lot._lasertag_hook_nodes(pos, spec))
    assert body.count('name="Cover_') == 1
    print("  malformed cover records skipped: OK")


def test_passable_gap_is_the_agent_contracts_own_derivation():
    """Not a chosen number. `AGENT_CONTRACT.md` derives min door width as
    `2*ceil(agent_radius/cell_size)*cell_size + 2*cell_size` because navmesh
    erosion removes whole voxels per side — at the ratified 0.4 m radius and
    0.15 m cells that is 1.2 m, which is why the ratified door is 1.25. A cover
    piece beside a wall is a doorway made of street furniture and nothing was
    applying the rule to it."""
    import site_cover as sc
    assert abs(sc.min_passable_gap() - 1.2) < 1e-9
    # A coarser bake erodes more, so the gap a lane needs grows with it.
    assert abs(sc.min_passable_gap(
        {"agent_radius_m": 0.4, "cell_size_m": 0.25}) - 1.5) < 1e-9
    # A missing or junk contract degrades to the ratified values, never crashes.
    assert sc.min_passable_gap({}) == sc.min_passable_gap()
    assert sc.min_passable_gap({"agent_radius_m": "wide"}) == sc.min_passable_gap()
    print("  passable gap from the agent contract: OK")


class _Piece:
    def __init__(self, name, x, y, size=3.0):
        self.name, self.x, self.y, self.size = name, x, y, size

    @property
    def rect(self):
        h = self.size / 2.0
        return (self.x - h, self.y - h, self.x + h, self.y + h)


def test_the_old_flat_clearance_left_an_unwalkable_lane():
    """The regression this closes, measured. `BUILDING_CLEARANCE` was a flat
    2.0 enforced against the piece's CENTRE while a piece is 3 m wide, so an
    edge could sit 0.5 m off a wall against a bake that needs 1.2 m. Seed 5118
    went from zero stuck events to one player and one enemy stuck in all 25
    runs the moment cover density rose enough to hit the case."""
    import site_cover as sc
    wall = (10.0, -20.0, 40.0, 20.0)
    old = _Piece("Cover_old", 10.0 - 2.0, 0.0)            # the flat constant
    new = _Piece("Cover_new", 10.0 - sc.building_clearance(), 0.0)
    assert abs(sc._lane_gap(old.rect, wall) - 0.5) < 1e-9
    assert sc.pinches([old], [wall]), "0.5 m is not a lane"
    assert abs(sc._lane_gap(new.rect, wall) - sc.min_passable_gap()) < 1e-6
    assert not sc.pinches([new], [wall]), "the derived clearance must be passable"
    print("  derived clearance leaves a walkable lane: OK")


def test_a_lane_at_exactly_the_minimum_is_the_contract_met():
    """`building_clearance` is derived to produce exactly the minimum, so an
    exclusive comparison reports every piece it places as a defect. Same rule
    as the door it is derived from: meeting the width is passing."""
    import site_cover as sc
    wall = (10.0, -20.0, 40.0, 20.0)
    exact = _Piece("Cover_exact", 10.0 - sc.building_clearance(), 0.0)
    assert not sc.pinches([exact], [wall])
    hair_under = _Piece("Cover_under", exact.x + 0.05, 0.0)
    assert sc.pinches([hair_under], [wall])
    print("  exact-minimum lane passes: OK")


def test_a_piece_flush_against_a_wall_is_a_wall_not_a_pinch():
    """Solid, visible, and nothing tries to walk it. What strands a bot is the
    lane that survives in the scene and not in the bake."""
    import site_cover as sc
    wall = (10.0, -20.0, 40.0, 20.0)
    flush = _Piece("Cover_flush", 8.5, 0.0)      # edge exactly on the wall face
    assert not sc.pinches([flush], [wall])
    print("  flush cover is not reported as a pinch: OK")


def test_pieces_can_pinch_each_other_not_just_walls():
    """Two crates 3.6 m apart leave 0.6 m between them. `COVER_SEPARATION`
    keeps them from touching; it does not keep the lane between them
    walkable."""
    import site_cover as sc
    a, b = _Piece("Cover_a", 0.0, 0.0), _Piece("Cover_b", 0.0, 3.6)
    found = sc.pinches([a, b], [])
    assert found and all(abs(g - 0.6) < 1e-9 for _n, _w, g in found)
    print("  piece-to-piece pinch caught: OK")


def test_plan_cover_reads_back_its_own_geometry_and_reports_pinches():
    """The read-back, in the shape `_opening_findings` established: the search
    deciding a piece MAY stand somewhere and the navmesh actually baking a lane
    past it are two different claims, and a report derived from the search
    cannot disagree with the search."""
    import site_cover as sc
    points = {"LT_PlayerSpawn": (0.0, 0.0), "LT_ObjectivePoint": (120.0, 0.0),
              "LT_ExtractionPoint": (120.0, 60.0),
              "Enemy_0": (55.0, 14.0), "Enemy_1": (95.0, -16.0)}
    ground = (-40.0, -60.0, 180.0, 100.0)
    route = [points["LT_PlayerSpawn"], points["LT_ObjectivePoint"],
             points["LT_ExtractionPoint"]]
    plan = sc.plan_cover(points, [], ground, opening_range=45.0, route=route)
    assert plan.pinches == [], f"open ground should pinch nothing: {plan.pinches}"

    # Force one: a clearance too small for the footprint, which is exactly what
    # the flat 2.0 was.
    tight = sc.plan_cover(points, [(60.0, -5.0, 70.0, 5.0)], ground,
                          opening_range=45.0, route=route, clearance=2.0)
    codes = {f["code"] for f in sc.findings(tight, opening_range=45.0)}
    if tight.pinches:
        assert "LOT_COVER_PINCH" in codes
    print("  cover pinch read-back: OK")


def test_the_pinch_check_sees_the_site_boundary_not_just_buildings():
    """The gap seed 5320 exposed. `pinches()` measured placed cover against
    `rects` — `site_spawns.footprints()`, buildings only — and reported ZERO
    while Laser Tag counted 835 player-stuck events across 25 runs. Cover is
    placed on open ground, and the edge of open ground is a wall: a piece parked
    near the boundary closes the lane along it and nothing upstream noticed."""
    import site_cover as sc
    ground = (-100.0, -50.0, 100.0, 50.0)
    walls = sc.perimeter_rects(ground)
    assert len(walls) == 4
    # 0.8 m of lane to the east wall — under the 1.2 m the bake can carry.
    tight = _Piece("Cover_edge", 100.0 - 1.5 - 0.8, 0.0)
    assert sc.pinches([tight], walls), "the boundary must be an obstacle"
    assert not sc.pinches([tight], []), "and buildings-only is exactly what missed it"
    clear = _Piece("Cover_clear", 100.0 - 1.5 - sc.min_passable_gap() - 0.15, 0.0)
    assert not sc.pinches([clear], walls)
    print("  perimeter walls counted as obstacles: OK")


def test_plan_cover_measures_pinches_against_the_perimeter_itself():
    """Computed inside `plan_cover` rather than asked of the caller, the same
    way the building rects are grown here: a caller passes what it has and
    cannot get this wrong on Lot's behalf."""
    import site_cover as sc
    # A narrow site, so the placer has to work close to the boundary.
    points = {"LT_PlayerSpawn": (-55.0, 0.0), "LT_ObjectivePoint": (55.0, 0.0),
              "LT_ExtractionPoint": (55.0, 8.0),
              "Enemy_0": (0.0, 6.0), "Enemy_1": (25.0, -6.0)}
    ground = (-60.0, -10.0, 60.0, 10.0)
    route = [points["LT_PlayerSpawn"], points["LT_ObjectivePoint"],
             points["LT_ExtractionPoint"]]
    plan = sc.plan_cover(points, [], ground, opening_range=45.0, route=route)
    # Whatever it placed, every reported pinch must name a real lane under the
    # bake minimum — the check is allowed to find nothing, never to lie.
    for _name, _what, gap in plan.pinches:
        assert 0.0 < gap < sc.min_passable_gap()
    # And the perimeter is in scope: nothing placed may sit in a lane the
    # boundary closes without being reported.
    walls = sc.perimeter_rects(ground)
    for piece in plan.cover:
        for wall in walls:
            g = sc._lane_gap(piece.rect, wall)
            if g is not None and 1e-9 < g < sc.min_passable_gap() - sc.GAP_TOLERANCE:
                assert any(n == piece.name for n, _w, _g in plan.pinches), (
                    f"{piece.name} pinches the perimeter and was not reported")
    print("  plan_cover pinches include the perimeter: OK")
