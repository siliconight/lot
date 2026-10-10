"""A shop sign's pack manifest travels beside its maps (Lot 0.105.0, roadmap 223).

Pixelcoat 0.62.0 letters a business's band smooth and asks for `linear` sampling and a mip chain;
a pixel pack asks for `nearest`. The maps alone cannot say which, so Level Factory's export reads
the manifest beside them in `signs/` and pins each map's import to match.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot  # noqa: E402


def _pack(tmp_path, slug="flappahs"):
    d = tmp_path / f"sign_{slug}"
    d.mkdir()
    (d / f"sign_{slug}_albedo.png").write_bytes(b"PNG")
    (d / f"sign_{slug}_emissive.png").write_bytes(b"PNG")
    (d / f"sign_{slug}.pack.json").write_text(json.dumps({
        "maps": {"albedo": f"sign_{slug}_albedo.png", "emissive": f"sign_{slug}_emissive.png"},
        "material_profile": f"sign_{slug}",
        "import_hints": {"interpolation": "linear", "generate_mipmaps": True,
                         "emissive": True}}), encoding="utf-8")
    return d


def _assemble(tmp_path, pack):
    spec = {"name": "shops", "ground": {"size_x": 120, "size_y": 90},
            "buildings": [{"id": "b0", "at": [-20, 6], "rot": 0, "footprint": [24, 16],
                           "glb": "shop_a.glb"}],
            "roads": [{"a": [-55, -20], "b": [55, -20], "width": 10, "sidewalk": 3}],
            "signs": {"b0": str(pack)}}
    p = tmp_path / "shops.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    lot.assemble(str(p), str(tmp_path / "out"))
    return tmp_path / "out"


def test_the_manifest_is_copied_beside_the_maps(tmp_path):
    """FAILS on 0.104.0: only the albedo and the emissive were copied."""
    pack = _pack(tmp_path)
    out = _assemble(tmp_path, pack)
    copied = out / "signs" / "sign_flappahs.pack.json"
    assert copied.read_bytes() == (pack / "sign_flappahs.pack.json").read_bytes()
    assert (out / "signs" / "sign_flappahs_albedo.png").exists()


def test_no_scene_names_the_manifest(tmp_path):
    """It is a sibling for the export to read, not a resource a scene loads."""
    out = _assemble(tmp_path, _pack(tmp_path))
    txt = (out / "shops.tscn").read_text(encoding="utf-8")
    assert "pack.json" not in txt


def test_a_smooth_pack_is_not_forced_nearest(tmp_path):
    """The band's material leaves a `linear` pack at Godot's filtered default."""
    out = _assemble(tmp_path, _pack(tmp_path))
    txt = (out / "shops.tscn").read_text(encoding="utf-8")
    start = txt.index('[sub_resource type="StandardMaterial3D" id="Mat_sign_b0"]')
    block = txt[start:txt.index("\n\n", start)]
    assert "texture_filter" not in block
