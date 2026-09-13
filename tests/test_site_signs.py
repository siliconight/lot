"""The shop signs (roadmap 153, the 1990s street): a lit cabinet over the
door, on the facade that faces the street.
"""
import json
import os
import sys

import pytest

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


def _numbers(line):
    return [float(v) for v in line.split("(", 1)[1].rstrip(")").split(",")]


def _z_axis(line):
    """Where the cabinet's local +Z lands in the world, read the way Godot
    reads the text: the first nine numbers of `Transform3D(...)` are the
    basis ROWS, so the image of local +Z is the third COLUMN, numbers 2, 5
    and 8. Measured in Godot 4.7 with `str_to_var` on this writer's own
    text (2026-09-13). 0.69.2 read numbers 6, 7 and 8 -- the third row --
    which agrees with the column for a north or south facade and is its
    mirror for an east or west one, so the test passed while every east
    and west sign faced its wall."""
    n = _numbers(line)
    return (round(n[2], 6), round(n[5], 6), round(n[8], 6))


#: facade -> (a road on that side of b0, the Godot direction the lit face
#: must point). Plan (x, y) is Godot (x, -z), so north is -z.
_FACADES = {
    "N": ({"a": [-55, 40], "b": [55, 40]}, (0.0, 0.0, -1.0)),
    "S": ({"a": [-55, -20], "b": [55, -20]}, (0.0, 0.0, 1.0)),
    "E": ({"a": [60, -40], "b": [60, 40]}, (1.0, 0.0, 0.0)),
    "W": ({"a": [-60, -40], "b": [-60, 40]}, (-1.0, 0.0, 0.0)),
}


@pytest.mark.parametrize("side", sorted(_FACADES))
def test_the_sign_faces_the_road_it_was_hung_for(tmp_path, side):
    """Cold run 9041 was a zero and shipped all three signs edge-on: the
    plan-space facade angle was handed to the scene writer as a Godot yaw.
    Assert the emitted basis, not the intermediate number -- the
    intermediate number was already correct and already tested.

    On every facade the lit face (a QuadMesh, whose own normal is local +Z,
    measured in Godot 4.7) must point away from the building, and the face
    child stands on that same side of the cabinet, so the dark body is
    between the face and the wall."""
    spec = _spec(tmp_path)
    (b0, _b1) = spec["buildings"]
    road, want = _FACADES[side]
    spec["roads"] = [dict(road, width=10, sidewalk=3)]
    _x, _y, yaw, _f = lot.sign_placement(b0, site_streets.roads(spec))
    assert yaw == {"E": 0.0, "N": 90.0, "W": 180.0, "S": 270.0}[side]
    body, _sub = lot._sign_node("sign_b0", (0.0, lot.SIGN_Z, 0.0),
                                lot.sign_facing(yaw), {"id": "s"}, (6.0, 1.0))
    tf = [l for l in body if l.startswith("transform =")]
    cabinet, face = tf[0], tf[1]
    assert _z_axis(cabinet) == want, (side, yaw, cabinet)
    # the face child is offset along the cabinet's local +Z only, and
    # forward of the can's front
    fx = _numbers(face)
    assert fx[:9] == [1, 0, 0, 0, 1, 0, 0, 0, 1] and fx[9] == 0 and fx[10] == 0
    assert fx[11] > lot.SIGN_D / 2.0
    # so in the world it sits toward the street from the cabinet's centre
    zx, zy, zz = _z_axis(cabinet)
    offset = (zx * fx[11], zy * fx[11], zz * fx[11])
    assert sum(o * w for o, w in zip(offset, want)) > lot.SIGN_D / 2.0


def test_the_lit_face_is_a_quad_and_the_box_is_only_the_can():
    """A BoxMesh shows a SUB-RECTANGLE of its texture on any side -- its
    unwrap's extents are proportional to the box's dimensions -- so cold run
    9042's 9 x 1.5 x 0.22 cabinet cut "KEYSTONE SAVINGS" off below the letter
    tops. The face is a QuadMesh, which spans the full 0..1 by construction.
    """
    body, sub = lot._sign_node("sign_b0", (0.0, lot.SIGN_Z, 0.0), 0.0,
                               {"id": "s", "emissive": True, "nearest": True},
                               (9.0, 1.5))
    text = "\n".join(sub)
    assert 'size = Vector2(9, 1.5)' in text          # the face, exactly
    assert 'size = Vector3(9, 1.5, 0.22)' in text    # the can, with depth
    # the pack is on the face's material and the box wears a plain colour
    assert 'albedo_texture = ExtResource("s_albedo")' in text
    assert 'albedo_color = Color(' in text
    face = [i for i, l in enumerate(body) if l.startswith('[node name="face"')]
    assert face, body
    assert 'material_override = SubResource("Mat_sign_b0")' in body[face[0] + 3]
    # and it stands proud of the can rather than inside it
    assert float(body[face[0] + 1].rstrip(")").rsplit(",", 1)[1]) > lot.SIGN_D / 2.0
