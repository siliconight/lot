"""The outdoor ground wears a Pixelcoat skin when the spec names one.

Cold run 9014 (roadmap 152): the exterior plate was one untextured 0.52
grey with no image, so the only detail outdoors was the clutter scattered
on it, and 2,708 pieces of clutter read as defects in a texture that was not
there. The spec now names a pack directory per outdoor family; Lot reads the
pack, writes the maps as world-projected textures with the pack's own tile
period, and says out loud when a pack cannot be read rather than shipping a
grey plate that looks exactly like one nobody asked to skin.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot  # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "specs")


def _pack(tmp_path, name, kind, *, meters=3.0, roughness=True, nearest=True):
    d = tmp_path / f"{kind}_delco_1997"
    d.mkdir()
    (d / f"{name}_albedo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    maps = {"albedo": f"{name}_albedo.png"}
    if roughness:
        (d / f"{name}_roughness.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        maps["roughness"] = f"{name}_roughness.png"
    (d / f"{name}.pack.json").write_text(json.dumps({
        "asset_id": name, "material_kind": kind, "material_profile": name,
        "maps": maps, "meters_per_tile": meters,
        "import_hints": {"interpolation": "nearest" if nearest else "linear"},
    }), encoding="utf-8")
    return str(d)


def _spec():
    return json.load(open(os.path.join(SPECS, "example_compound.json")))


def test_a_named_pack_becomes_a_world_projected_material(tmp_path):
    spec = _spec()
    spec["ground_skins"] = {"ground": _pack(tmp_path, "asphalt_street", "asphalt"),
                            "path": _pack(tmp_path, "concrete_sidewalk_street",
                                          "sidewalk", meters=2.0, roughness=False)}
    skins, findings = lot.ground_skins(spec)
    assert findings == []
    assert set(skins) == {"ground", "path"}
    assert skins["ground"]["meters_per_tile"] == 3.0
    assert skins["ground"]["albedo"].endswith("asphalt_delco_1997/asphalt_street_albedo.png")
    assert "\\" not in skins["ground"]["albedo"]
    assert skins["path"]["roughness"] is None

    body, sub = lot._outdoor_nodes(spec, skins=skins)
    txt = "\n".join(sub)
    g = txt[txt.index('id="Mat_Ground"'):]
    g = g[:g.index("\n\n")]
    assert 'albedo_texture = ExtResource("skin_ground_albedo")' in g
    assert 'roughness_texture = ExtResource("skin_ground_roughness")' in g
    assert "uv1_world_triplanar = true" in g and "uv1_triplanar = true" in g
    assert "uv1_scale = Vector3(0.333333, 0.333333, 0.333333)" in g
    assert "texture_filter = 2" in g
    assert "albedo_color" not in g          # the texture is the colour
    p = txt[txt.index('id="Mat_path_0"'):]
    p = p[:p.index("\n\n")]
    assert "uv1_scale = Vector3(0.5, 0.5, 0.5)" in p
    assert "roughness_texture" not in p
    # the courtyard was not named, so it keeps its flat greybox colour
    c = txt[txt.index('id="Mat_courtyard_0"'):]
    c = c[:c.index("\n\n")]
    assert "albedo_color = Color(0.48, 0.52, 0.55, 1)" in c
    assert "albedo_texture" not in c
    # every tile of the plate still shares the ONE material
    assert "\n".join(body).count('material_override = SubResource("Mat_Ground")') >= 1
    assert sum(1 for ln in sub if 'id="Mat_Ground"' in ln) == 1


def test_the_scene_declares_each_map_once_and_counts_it_in_load_steps(tmp_path):
    spec = _spec()
    spec.pop("courtyards", None)
    spec["ground_skins"] = {"ground": _pack(tmp_path, "asphalt_street", "asphalt"),
                            "courtyard": _pack(tmp_path, "concrete_delco", "concrete")}
    path = os.path.join(SPECS, "_skin_probe.json")
    json.dump(spec, open(path, "w", encoding="utf-8"))
    try:
        r = lot.assemble(path, str(tmp_path / "out"))
    finally:
        os.remove(path)
    txt = open(r["scene"], encoding="utf-8").read()
    ext = [ln for ln in txt.splitlines() if ln.startswith("[ext_resource")]
    tex = [ln for ln in ext if 'type="Texture2D"' in ln]
    assert len(tex) == 2                 # albedo + roughness; no courtyard, no courtyard maps
    assert any('id="skin_ground_albedo"' in ln for ln in tex)
    assert not any("courtyard" in ln for ln in tex)
    # the maps are COPIED beside the scene and referenced as siblings, the
    # way a staged building is -- Godot has no importer for a png outside
    # the project, and the Lux stage loads this scene in one
    assert all('path="res://skins/' in ln for ln in tex)
    out_dir = os.path.dirname(r["scene"])
    assert os.path.isfile(os.path.join(out_dir, "skins", "asphalt_street_albedo.png"))
    assert os.path.isfile(os.path.join(out_dir, "skins", "asphalt_street_roughness.png"))
    assert not os.path.exists(os.path.join(out_dir, "skins", "concrete_delco_albedo.png"))
    import re
    n = int(re.search(r"load_steps=(\d+)", txt).group(1))
    assert n == len(ext) + txt.count("[sub_resource") + 1


def test_an_unreadable_pack_is_reported_and_the_plate_stays_flat(tmp_path):
    spec = _spec()
    spec["ground_skins"] = {"ground": str(tmp_path / "nowhere"),
                            "roof": str(tmp_path)}
    skins, findings = lot.ground_skins(spec)
    assert skins == {}
    codes = [c for c, _ in findings]
    assert codes == [lot.CODE_GROUND_SKIN_MISSING] * 2
    assert "ground stays flat" in findings[0][1]
    assert "not an outdoor family" in findings[1][1]
    body, sub = lot._outdoor_nodes(spec, skins=skins)
    assert "albedo_color = Color(0.3, 0.32, 0.34, 1)" in "\n".join(sub)


def test_portable_mode_references_the_copied_maps_relative_to_the_scene(tmp_path):
    spec = _spec()
    spec["ground_skins"] = {"ground": _pack(tmp_path, "asphalt_street", "asphalt")}
    path = os.path.join(SPECS, "_skin_probe2.json")
    json.dump(spec, open(path, "w", encoding="utf-8"))
    try:
        r = lot.assemble(path, str(tmp_path / "out"), portable=True)
    finally:
        os.remove(path)
    txt = open(r["scene"], encoding="utf-8").read()
    tex = [ln for ln in txt.splitlines() if 'type="Texture2D"' in ln]
    assert tex and all('path="skins/' in ln for ln in tex)


def test_a_pack_without_a_period_is_refused_not_guessed(tmp_path):
    d = tmp_path / "asphalt_delco_1997"
    d.mkdir()
    (d / "x_albedo.png").write_bytes(b"")
    (d / "x.pack.json").write_text(json.dumps({"maps": {"albedo": "x_albedo.png"}}),
                                   encoding="utf-8")
    skins, findings = lot.ground_skins({"buildings": [], "ground_skins": {"ground": str(d)}})
    assert skins == {} and "meters_per_tile" in findings[0][1]


def test_no_key_means_the_scene_it_always_was():
    spec = _spec()
    before = lot._outdoor_nodes(spec)
    assert lot.ground_skins(spec) == ({}, [])
    assert lot._outdoor_nodes(spec, skins={}) == before
