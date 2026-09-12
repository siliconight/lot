"""Cover is a species-shaped slot, not a cube (roadmap 22).

The walker, 2026-09-12: "the green boxes should be larger props with collision
to offer cover between buildings to force creative traversal." Until 0.59.0
every piece was a 3 m cube and nothing downstream could replace it, because
the site had no slot manifest. Now the planner places the largest species
that fits -- a box truck, a container, a car -- turned ACROSS the sightline it
breaks, writes each as a prop slot in `<site>.slots.json` in Deli Counter's
manifest shape, and the themed scene stands Zoo's module where the box stood.
The box stays, and says so, whenever the module is not there.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_cover     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "specs")
GROUND = (-150.0, -100.0, 150.0, 100.0)
CREW = (-60.0, 0.0)
ENEMY = (60.0, 0.0)


def _plan(**kw):
    return site_cover.plan_cover({"LT_PlayerSpawn": CREW, "Enemy_0": ENEMY}, [],
                                 GROUND, opening_range=45.0,
                                 species=site_cover.COVER_SPECIES, **kw)


def test_a_species_piece_lies_across_the_line_it_breaks():
    """The line runs along X, so the piece's LENGTH lies along Y."""
    plan = _plan()
    assert plan.cover, "nothing placed on a bare 120 m lane"
    p = plan.cover[0]
    assert p.species == "box_truck"           # the largest fits on open ground
    assert p.yaw == 0.0                        # as Zoo builds it: length along Y
    assert (p.size_x, p.size_y) == (2.4, 6.0)  # width across X, length along Y
    assert p.height == 2.8
    # and the line is closed
    assert site_cover.open_span(CREW, ENEMY, [p.rect]) < math.dist(CREW, ENEMY) - 1e-6


def test_the_yaw_follows_the_line():
    assert site_cover.across_yaw((0, 0), (10, 1)) == 0.0
    assert site_cover.across_yaw((0, 0), (1, 10)) == 90.0
    assert site_cover.footprint(2.4, 6.0, 0.0) == (2.4, 6.0)
    assert site_cover.footprint(2.4, 6.0, 90.0) == (6.0, 2.4)
    plan = site_cover.plan_cover({"LT_PlayerSpawn": (0.0, -60.0), "Enemy_0": (0.0, 60.0)},
                                 [], GROUND, opening_range=45.0,
                                 species=site_cover.COVER_SPECIES)
    assert plan.cover[0].yaw == 90.0 and (plan.cover[0].size_x, plan.cover[0].size_y) == (6.0, 2.4)


def test_a_lane_too_tight_for_a_truck_gets_a_car():
    """Two building footprints leave a 9 m lane across the line: a 6 m truck
    turned across it needs its footprint plus clearance either side and is
    refused; the 4.3 m car fits."""
    clear = site_cover.building_clearance(3.0)
    lane = 11.0        # 4.3 + 2 x 2.7 fits; 6.0 + 2 x 2.7 does not
    # the walls run the WHOLE length of the line, so there is no open ground
    # beside them for the search to slide the piece out to
    rects = [(-70.0, lane / 2, 70.0, 40.0), (-70.0, -40.0, 70.0, -lane / 2)]
    plan = _plan()  # sanity: open ground takes the truck
    assert plan.cover[0].species == "box_truck"
    plan = site_cover.plan_cover({"LT_PlayerSpawn": CREW, "Enemy_0": ENEMY}, rects,
                                 GROUND, opening_range=45.0,
                                 species=site_cover.COVER_SPECIES)
    kinds = {p.species for p in plan.cover}
    assert kinds and "box_truck" not in kinds, (kinds, clear)


def test_the_square_form_is_untouched_when_no_species_is_given():
    plan = site_cover.plan_cover({"LT_PlayerSpawn": CREW, "Enemy_0": ENEMY}, [],
                                 GROUND, opening_range=45.0)
    p = plan.cover[0]
    assert p.species == "" and (p.size_x, p.size_y) == (3.0, 3.0)
    assert p.as_site_cover()["size"] == [3.0, 2.0, 3.0]
    assert "species" not in p.as_site_cover()


def test_the_site_cover_record_carries_the_slot():
    p = _plan().cover[0]
    rec = p.as_site_cover()
    assert rec["species"] == "box_truck" and rec["yaw"] == 0.0
    assert rec["dims"] == [2.4, 6.0, 2.8]              # width, depth, height
    assert rec["size"] == [2.4, 2.8, 6.0]              # plan x, height, plan y


def test_the_stem_mirrors_deli_counter_and_zoo_by_literal():
    """`themed_tscn.module_stem` / `kit.module_stem`: change one, change all."""
    assert lot.cover_module_stem("simple_car", "delco_1997", 1, [1.75, 4.3, 1.45]) \
        == "prop_simple_car_delco_1997_01_w175_d430_h145"
    assert lot.cover_module_stem("box_truck", "delco", 3, [2.4, 6.0, 2.8]) \
        == "prop_box_truck_delco_03_w240_d600_h280"


def test_the_slots_manifest_is_deli_counters_shape(tmp_path):
    spec = {"cover": [
        {"at": [10.0, -4.0], "size": [6.0, 2.8, 2.4], "species": "box_truck",
         "yaw": 90.0, "dims": [2.4, 6.0, 2.8], "breaks": "a -> b"},
        {"at": [0.0, 0.0], "size": [3.0, 2.0, 3.0]},           # a square piece
    ]}
    out = tmp_path / "site.slots.json"
    assert lot.write_site_slots(spec, str(out)) == 1
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["slot_manifest_version"] == "1.2.0" and doc["building_id"] == "site"
    (s,) = doc["slots"]
    assert s["slot_id"] == "cover_0" and s["role"] == "prop" and s["species"] == "box_truck"
    assert s["fit"]["dims"] == [2.4, 6.0, 2.8] and s["fit"]["collision"] == "convex"
    assert s["transform"]["translation"] == [10.0, -4.0, 1.4]
    assert s["transform"]["rot_y"] == 90.0
    assert s["material"] == "metal_painted"


def test_a_missing_module_keeps_the_box_and_says_so(tmp_path):
    spec = {"cover": [{"at": [10.0, -4.0], "size": [6.0, 2.8, 2.4],
                       "species": "box_truck", "yaw": 90.0, "dims": [2.4, 6.0, 2.8]}],
            "cover_modules": {"dir": str(tmp_path), "theme": "delco_1997", "style": 1},
            "buildings": []}
    refs, ext, findings = lot.cover_module_refs(spec, "res://")
    assert refs == {} and ext == []
    assert findings[0][0] == lot.CODE_COVER_MODULE_MISSING
    assert "prop_box_truck_delco_1997_01_w240_d600_h280.glb" in findings[0][1]
    body, sub = lot._outdoor_nodes(spec, cover_refs=refs)
    assert 'name="cover_0" type="StaticBody3D"' in "\n".join(body)


def test_a_built_module_stands_where_the_box_stood(tmp_path):
    glb = tmp_path / "prop_box_truck_delco_1997_01_w240_d600_h280.glb"
    glb.write_bytes(b"glTF")
    spec = {"cover": [{"at": [10.0, -4.0], "size": [6.0, 2.8, 2.4],
                       "species": "box_truck", "yaw": 90.0, "dims": [2.4, 6.0, 2.8]},
                      {"at": [30.0, 5.0], "size": [6.0, 2.8, 2.4],
                       "species": "box_truck", "yaw": 90.0, "dims": [2.4, 6.0, 2.8]}],
            "cover_modules": {"dir": str(tmp_path), "theme": "delco_1997", "style": 1},
            "buildings": []}
    out = tmp_path / "out"
    out.mkdir()
    refs, ext, findings = lot.cover_module_refs(spec, "", str(out))
    assert findings == [] and refs == {0: "cover_prop_box_truck_delco_1997_01_w240_d600_h280",
                                       1: "cover_prop_box_truck_delco_1997_01_w240_d600_h280"}
    # copied beside the scene and referenced as a sibling -- Godot has no
    # loader for a glb outside the project, and the Lux stage loads this
    # scene in one (cold run 9019: three modules built, none in the level)
    assert len(ext) == 1 and 'type="PackedScene"' in ext[0]
    assert 'path="cover/prop_box_truck_delco_1997_01_w240_d600_h280.glb"' in ext[0]
    assert (out / "cover" / "prop_box_truck_delco_1997_01_w240_d600_h280.glb").read_bytes() == b"glTF"
    assert lot.cover_module_refs(spec, "res://", str(out))[1][0].count('path="res://cover/') == 1
    body, sub = lot._outdoor_nodes(spec, cover_refs=refs)
    txt = "\n".join(body)
    assert txt.count('instance=ExtResource("cover_prop_box_truck_delco_1997_01_w240_d600_h280")') == 2
    assert 'name="cover_0" type="StaticBody3D"' not in txt
    # centre-pivot module at the box's centre: origin (x, h/2, -y)
    i = txt.index('name="cover_0"')
    line = txt[i:].split("\n")[1]
    assert line.endswith("10, 1.4, 4)")
    assert not any('id="Mat_cover_0"' in ln for ln in sub)


def test_assemble_writes_the_manifest_beside_the_scene(tmp_path):
    r = lot.assemble(os.path.join(SPECS, "example_compound.json"), str(tmp_path))
    slots = tmp_path / "site.slots.json"
    if not slots.exists():                      # the example spec's stem
        slots = next(tmp_path.glob("*.slots.json"))
    doc = json.loads(slots.read_text(encoding="utf-8"))
    assert doc["building_id"] == "site"
    for s in doc["slots"]:
        assert s["species"] in {n for n, *_ in site_cover.COVER_SPECIES}
        assert s["fit"]["dims"][2] > site_cover.MIN_COVER_HEIGHT


def test_marker_clearance_is_measured_from_the_pieces_edge():
    """Cold run 9018: a 6 m truck's END lay on an enemy spawn under the
    centre rule, Laser Tag's preflight refused the candidate ("Enemy_2 is
    sealed off from the crew spawn"), and the export gate held. A marker must
    be MARKER_CLEARANCE clear of the piece's edge, whatever its length."""
    # a marker 2.5 m past where a truck's end would land, on the line
    plan = site_cover.plan_cover(
        {"LT_PlayerSpawn": CREW, "Enemy_0": ENEMY, "Enemy_1": (0.0, 5.5)},
        [], GROUND, opening_range=45.0, species=site_cover.COVER_SPECIES)
    for p in plan.cover:
        for m in (CREW, ENEMY, (0.0, 5.5)):
            r = p.rect
            dx = max(r[0] - m[0], 0.0, m[0] - r[2])
            dy = max(r[1] - m[1], 0.0, m[1] - r[3])
            assert max(dx, dy) >= site_cover.MARKER_CLEARANCE - 1e-9, (p.name, p.species, m, r)
