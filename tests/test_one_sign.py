"""One sign a building (0.129.0). The walker, walking cold run 9386, of a pharmacy with its band along the parapet
and a lit box over its door: "in real life this would be 1 sign". A building the spec deals a band loses its door
box's lamp (a `sign` anchor) from the site's lights; a building with no band keeps its box. FAILS ON 0.128.0."""
import json

import lot


def _site(tmp_path, signs):
    lights = {"light_manifest_version": "1.1.0", "anchors": [
        {"id": "ext_0_S_sign", "type": "sign", "pos": [-3.5, -9.35, 2.55], "rot_y": 270.0},
        {"id": "ceiling_0", "type": "fluorescent", "pos": [0.0, 0.0, 3.0]}]}
    for name in ("shop", "office"):
        (tmp_path / (name + ".lights.json")).write_text(json.dumps(lights), encoding="utf-8")
    return {"name": "t", "buildings": [
        {"id": "b0", "at": [0.0, 0.0], "rot": 0, "lights": "shop.lights.json"},
        {"id": "b1", "at": [40.0, 0.0], "rot": 0, "lights": "office.lights.json"}],
        "roads": [], "signs": signs}


def test_a_banded_building_loses_its_door_box_lamp_and_an_unbanded_one_keeps_it(tmp_path):
    site = lot.merge_lights(_site(tmp_path, {"b0": "packs/sign_x"}), str(tmp_path))
    ids = {a["id"] for a in site["anchors"]}
    assert "b0/ext_0_S_sign" not in ids and "b0/ceiling_0" in ids
    assert "b1/ext_0_S_sign" in ids and "b1/ceiling_0" in ids
    assert site["door_signs_dropped"] == ["b0/ext_0_S_sign"]


def test_no_bands_drops_nothing(tmp_path):
    site = lot.merge_lights(_site(tmp_path, {}), str(tmp_path))
    assert {"b0/ext_0_S_sign", "b1/ext_0_S_sign"} <= {a["id"] for a in site["anchors"]}
    assert site["door_signs_dropped"] == []
