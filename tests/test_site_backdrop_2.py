"""The other backdrop recipes (Lot 0.109.0, roadmap 228): yards, parkland and roadside, laid from
Zoo 1.96.0's tree and warehouse and the cargo container, each piece beyond the plate."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot                # noqa: E402
import site_backdrop as SB  # noqa: E402

GROUND = (-98.0, -50.0, 98.0, 50.0)


def _plan(recipe, seed=9104):
    findings = []
    got = SB.plan({"name": "site", "surroundings": recipe}, GROUND, seed=seed, findings=findings)
    return got, findings


def _outside(p):
    x0, y0, x1, y1 = GROUND
    x, y = p["at"]
    w, d, h = p["dims"]
    r = max(w, d) / 2.0
    return (y - r >= y1 - 1e-9 or y + r <= y0 + 1e-9 or x - r >= x1 - 1e-9 or x + r <= x0 + 1e-9)


def test_every_recipe_has_a_kit_now_and_lays_without_a_finding():
    assert set(SB.BUILT) == set(SB.RECIPES)
    for recipe in ("yards", "parkland", "roadside"):
        got, findings = _plan(recipe)
        assert findings == [] and got, recipe


def test_the_yards_stack_containers_along_the_near_band_and_warehouses_behind():
    got, _ = _plan("yards")
    s = SB.summary(got)
    assert s["towers"] == 1
    assert s["by_species"][SB.CONTAINER_SPECIES] > 40 and s["by_species"][SB.WAREHOUSE_SPECIES] > 8
    stacked = [p for p in got if p.get("z")]
    assert stacked and all(p["species"] == SB.CONTAINER_SPECIES and p["z"] == SB.CONTAINER[2] for p in stacked)
    for p in got:
        assert _outside(p), p
        if p["species"] == SB.CONTAINER_SPECIES:
            assert p["dims"] == list(SB.CONTAINER) and p["yaw"] == (SB.FACING[p["side"]] + 90.0) % 360.0
        if p["species"] == SB.WAREHOUSE_SPECIES:
            assert tuple(p["dims"]) in SB.WAREHOUSES and p["yaw"] == SB.FACING[p["side"]]
    # a stacked container stands exactly where the one under it stands
    for top in stacked:
        under = [p for p in got if p["at"] == top["at"] and not p.get("z")]
        assert len(under) == 1


def test_the_parkland_is_a_belt_of_trees_and_no_tower():
    got, _ = _plan("parkland")
    s = SB.summary(got)
    assert s["towers"] == 0 and set(s["by_species"]) == {SB.TREE_SPECIES}
    assert 300 <= s["by_species"][SB.TREE_SPECIES] <= 1200
    assert all(s["by_side"][k] > 20 for k in "NSEW")
    assert s["modules"] <= len(SB.TREES)
    for p in got:
        assert _outside(p) and tuple(p["dims"]) in SB.TREES and p["yaw"] in (0.0, 90.0, 180.0, 270.0)
    bands = {p["band"] for p in got}
    assert bands == {0, 1}


def test_the_roadside_is_a_thin_belt_and_a_few_far_warehouses():
    got, _ = _plan("roadside")
    s = SB.summary(got)
    assert s["towers"] == 0
    assert set(s["by_species"]) == {SB.TREE_SPECIES, SB.WAREHOUSE_SPECIES}
    park = SB.summary(_plan("parkland")[0])
    assert s["by_species"][SB.TREE_SPECIES] < park["by_species"][SB.TREE_SPECIES]
    assert 2 <= s["by_species"][SB.WAREHOUSE_SPECIES] <= 40
    for p in got:
        assert _outside(p)


def test_a_recipe_is_deterministic_for_a_seed_and_moves_with_it():
    for recipe in ("yards", "parkland", "roadside"):
        a, _ = _plan(recipe, 1)
        b, _ = _plan(recipe, 1)
        c, _ = _plan(recipe, 2)
        assert json.dumps(a) == json.dumps(b) and json.dumps(a) != json.dumps(c)


def test_the_borough_lays_as_0_108_0_did():
    got, findings = _plan("borough")
    s = SB.summary(got)
    assert findings == [] and s["towers"] == 1 and set(s["by_species"]) == {SB.SPECIES, SB.TOWER_SPECIES}
    assert 150 <= s["houses"] <= 450 and s["modules"] <= SB.MODULES_PER_LEVEL + 1


def test_the_slots_manifest_lifts_a_stacked_piece_by_its_z(tmp_path):
    spec = {"name": "site", "cover": [], "backdrop": _plan("yards")[0]}
    out = tmp_path / "site.slots.json"
    lot.write_site_slots(spec, str(out))
    doc = json.loads(out.read_text(encoding="utf-8"))
    by_id = {s["slot_id"]: s for s in doc["slots"]}
    for i, p in enumerate(spec["backdrop"]):
        s = by_id[f"backdrop_{i}"]
        assert abs(s["transform"]["translation"][2] - (p.get("z", 0.0) + p["dims"][2] / 2.0)) < 1e-9
        assert s["fit"]["collision"] == "none"
    tree = next(s for s in doc["slots"] if s["species"] == SB.WAREHOUSE_SPECIES)
    assert tree["material"] == "concrete"
