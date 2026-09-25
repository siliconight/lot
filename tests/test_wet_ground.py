"""Lot chooses the wet variant of a ground pack.

WHY THIS IS IN LOT AND NOT IN ZOO, established by cold run 9079 rather than by
reasoning. The chooser was wired into Zoo first, on the assumption that wetting
Zoo's packs wets the road. The shipped package refuted it: 170 distinct
`M_Skin` materials across 247 GLBs and ZERO ending `_wet`, because Zoo skinned
24 kinds -- canvas, carpet, ceiling tile, concrete, drywall, glass, leather,
metal, plaster, plastic, rubber, tile, vegetation, velvet, wallpaper, wood and
the rest -- and not one is a ground kind. `--wet` was passed, was honoured, and
had nothing to choose.

`site.tscn` carries the road: `StandardMaterial3D` nodes whose `albedo_texture`
is an `ExtResource` pointing at `skins/asphalt_delco_albedo.png` and
`skins/sidewalk_delco_albedo.png`, written from records `ground_skins` builds
by reading the pack manifest directly. So the substitution lives here too. Lot
imports nothing of Zoo's and vice versa; what must not drift between them is
the map NAMES Pixelcoat writes, and those are the pack contract.

    python -m pytest tests/test_wet_ground.py -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import lot as lotmod


def _pack(root, dirname, asset_id, maps, missing=()):
    d = os.path.join(root, dirname)
    os.makedirs(d, exist_ok=True)
    files = {k: f"{asset_id}_{k}.png" for k in maps}
    for k, fname in files.items():
        if k not in missing:
            with open(os.path.join(d, fname), "wb") as f:
                f.write(f"pixels:{k}".encode())
    with open(os.path.join(d, f"{asset_id}.pack.json"), "w",
              encoding="utf-8") as f:
        json.dump({"schema": "pixelcoat-pack/2", "asset_id": asset_id,
                   "maps": files, "meters_per_tile": 3.0,
                   "material_profile": asset_id}, f)
    return d


GROUND = ["albedo", "roughness", "wetness", "wet_albedo", "wet_roughness"]
WALL = ["albedo", "roughness", "normal"]


def _spec(tmp_path, wet=None, **fams):
    root = str(tmp_path)
    gs = {}
    for fam, (dirname, asset, maps) in fams.items():
        gs[fam] = _pack(root, dirname, asset, maps)
    spec = {"ground_skins": gs}
    if wet is not None:
        spec["wet_ground"] = wet
    return spec


def _base(tmp_path, **kw):
    return _spec(tmp_path,
                 ground=("asphalt_x", "asphalt_delco", GROUND),
                 path=("sidewalk_x", "sidewalk_delco", GROUND),
                 courtyard=("brick_x", "brick_delco", WALL), **kw)


def _names(skins):
    return {fam: os.path.basename(s["albedo"]) for fam, s in skins.items()}


# --------------------------------------------------------------------------- #
# Choosing
# --------------------------------------------------------------------------- #

def test_wet_ground_points_the_road_at_its_wet_maps(tmp_path):
    skins, _ = lotmod.ground_skins(_base(tmp_path, wet=True))
    assert _names(skins)["ground"] == "asphalt_delco_wet_albedo.png"
    assert os.path.basename(skins["ground"]["roughness"]) == \
        "asphalt_delco_wet_roughness.png"
    assert _names(skins)["path"] == "sidewalk_delco_wet_albedo.png"


def test_without_the_flag_nothing_moves(tmp_path):
    """The regression guard. Every site that is not raining must resolve what
    it always did."""
    skins, findings = lotmod.ground_skins(_base(tmp_path))
    assert _names(skins)["ground"] == "asphalt_delco_albedo.png"
    assert _names(skins)["path"] == "sidewalk_delco_albedo.png"
    assert not [f for f in findings if f[0] == lotmod.CODE_GROUND_SKIN_WET]


def test_a_family_whose_pack_has_no_wet_maps_is_untouched(tmp_path):
    """THE PROPERTY THAT MAKES A WHOLE-SITE FLAG SAFE. Which families are wet
    is Pixelcoat's decision, carried in the grammar; restating it here would
    be a second place to get it wrong."""
    skins, _ = lotmod.ground_skins(_base(tmp_path, wet=True))
    assert _names(skins)["courtyard"] == "brick_delco_albedo.png"


def test_only_a_wet_map_that_exists_is_substituted(tmp_path):
    """A pack naming a wet map it did not write falls back to the dry one --
    the same rule the dry maps already follow, and for the same reason: a
    resolved path that is not on disk is worse than the surface it replaced."""
    spec = _spec(tmp_path, wet=True,
                 ground=("asphalt_x", "asphalt_delco", GROUND))
    os.remove(os.path.join(tmp_path, "asphalt_x",
                           "asphalt_delco_wet_roughness.png"))
    skins, _ = lotmod.ground_skins(spec)
    assert os.path.basename(skins["ground"]["albedo"]) == \
        "asphalt_delco_wet_albedo.png"
    assert os.path.basename(skins["ground"]["roughness"]) == \
        "asphalt_delco_roughness.png"


# --------------------------------------------------------------------------- #
# Said out loud
# --------------------------------------------------------------------------- #

def test_what_was_substituted_is_reported(tmp_path):
    _, findings = lotmod.ground_skins(_base(tmp_path, wet=True))
    wet = [m for c, m in findings if c == lotmod.CODE_GROUND_SKIN_WET]
    assert len(wet) == 1
    for expect in ("ground.albedo", "ground.roughness",
                   "path.albedo", "path.roughness"):
        assert expect in wet[0]
    assert "courtyard" not in wet[0]


def test_asking_for_wet_and_getting_none_is_a_finding(tmp_path):
    """A site that asked for wet ground and got none is a level that rains on
    a dry road. That shipped once, from cold run 9079, without a word."""
    spec = _spec(tmp_path, wet=True,
                 ground=("brick_x", "brick_delco", WALL))
    _, findings = lotmod.ground_skins(spec)
    wet = [m for c, m in findings if c == lotmod.CODE_GROUND_SKIN_WET]
    assert len(wet) == 1 and "NO pack carried a wet map" in wet[0]


# --------------------------------------------------------------------------- #
# What must not change, because the point is that it costs nothing
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("key", ["meters_per_tile", "nearest", "alpha_mode",
                                 "id", "profile"])
def test_the_skin_record_is_otherwise_identical(tmp_path, key):
    """Only which image the material samples changes. No extra texture, no
    extra material, no extra draw call -- the same property Zoo 1.3.0
    asserts for the packs it resolves."""
    dry, _ = lotmod.ground_skins(_base(tmp_path))
    wet, _ = lotmod.ground_skins(_base(tmp_path, wet=True))
    assert dry["ground"][key] == wet["ground"][key]


def test_the_map_slots_are_the_same_slots(tmp_path):
    dry, _ = lotmod.ground_skins(_base(tmp_path))
    wet, _ = lotmod.ground_skins(_base(tmp_path, wet=True))
    assert set(dry["ground"]) == set(wet["ground"])


def test_the_wet_names_match_what_pixelcoat_writes():
    """The one thing that must not drift between Lot and Zoo, neither of which
    imports the other: the map names are the pack contract."""
    assert lotmod.WET_SUBSTITUTIONS == {"albedo": "wet_albedo",
                                        "roughness": "wet_roughness"}
