"""The shop signs (roadmap 153, the 1990s street): a lit cabinet over the
door, on the facade that faces the street.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_streets   # noqa: E402


def _pack(tmp_path, slug="goose_mart"):
    d = tmp_path / f"sign_{slug}"
    d.mkdir()
    (d / f"sign_{slug}_albedo.png").write_bytes(b"PNG")
    (d / f"sign_{slug}_emissive.png").write_bytes(b"PNG")
    (d / f"sign_{slug}.pack.json").write_text(json.dumps({
        "maps": {"albedo": f"sign_{slug}_albedo.png",
                 "emissive": f"sign_{slug}_emissive.png"},
        "material_profile": f"sign_{slug}",
        "import_hints": {"interpolation": "nearest", "emissive": True}}),
        encoding="utf-8")
    return d


def _spec(tmp_path):
    return {"name": "shops", "ground": {"size_x": 120, "size_y": 90},
            "buildings": [{"id": "b0", "at": [-20, 6], "rot": 0,
                           "footprint": [24, 16], "glb": "shop_a.glb"},
                          {"id": "b1", "at": [22, 8], "rot": 0,
                           "footprint": [20, 14], "glb": "shop_b.glb"}],
            "roads": [{"a": [-55, -20], "b": [55, -20], "width": 10,
                       "sidewalk": 3}],
            "signs": {"b0": str(_pack(tmp_path))}}


def test_the_sign_hangs_on_the_facade_that_faces_the_street(tmp_path):
    spec = _spec(tmp_path)
    (b0, _b1) = spec["buildings"]
    roads = site_streets.roads(spec)
    x, y, yaw, facade = lot.sign_placement(b0, roads)
    # the road is south of the row, so the sign is on the south face
    assert abs(x - b0["at"][0]) < 1e-6
    assert y < b0["at"][1] and abs(y - (6 - 8 - lot.SIGN_D / 2 - lot.SIGN_PROUD)) < 1e-6
    assert yaw == 270.0
    # move the road north and the sign moves with it
    spec["roads"] = [{"a": [-55, 40], "b": [55, 40], "width": 10, "sidewalk": 3}]
    _x, y2, yaw2, facade2 = lot.sign_placement(b0, site_streets.roads(spec))
    assert y2 > b0["at"][1] and yaw2 == 90.0
    # the band is sized from the facade it hangs on, not pinned
    assert facade == facade2 == 24.0
    # 24 m of frontage wants 17.3 m of sign and is capped: a band the width
    # of a supermarket reads as a billboard, not a shop sign
    w, h = lot.sign_size(facade)
    assert w == lot.SIGN_MAX_W and abs(w / h - lot.SIGN_ASPECT) < 1e-9
    assert abs(lot.sign_size(8.0)[0] - 8.0 * lot.SIGN_SPAN) < 1e-9
    assert lot.sign_size(2.0)[0] == lot.SIGN_MIN_W        # a kiosk still reads


def test_a_pack_that_cannot_be_read_is_said_out_loud(tmp_path):
    spec = _spec(tmp_path)
    spec["signs"] = {"b0": str(tmp_path / "nothing_here"), "b9": "x"}
    signs, findings = lot.building_signs(spec)
    assert signs == {}
    codes = [c for c, _m in findings]
    assert codes == [lot.CODE_SIGN_PACK_MISSING, lot.CODE_SIGN_PACK_MISSING]
    assert "no *.pack.json" in findings[0][1]
    assert "not a building" in findings[1][1]


def test_the_scene_wears_the_sign_and_lights_it(tmp_path):
    spec = _spec(tmp_path)
    p = tmp_path / "shops.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    lot.assemble(str(p), str(tmp_path))
    txt = (tmp_path / "shops.tscn").read_text(encoding="utf-8")
    assert 'id="sign_b0_albedo"' in txt and 'id="sign_b0_emissive"' in txt
    assert 'name="sign_b0"' in txt
    assert "emission_enabled = true" in txt
    assert "cull_mode = 2" in txt                 # both sides
    # the maps travel beside the scene, like a ground skin's
    assert (tmp_path / "signs" / "sign_goose_mart_albedo.png").exists()
    # b1 named no sign and has none
    assert 'name="sign_b1"' not in txt
