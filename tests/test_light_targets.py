"""0.99.1 -- a stage light's aim moves with its club (roadmap 207).

`merge_lights` carried each light anchor's `pos` into site space and copied
the rest of the record verbatim -- `target`, the stage light's aim, among it.
So a strip club standing off the site's origin aimed both stages at points in
its own frame. Cold run 9197 placed strip_club_a01 as b2 at (69, -1.5),
unturned, and shipped:
- `b2/main_floor_stage`, pos (73.0, -6.5, 3.2), aimed at (0.0, -5.0, 1.68):
  a 73.03 m throw;
- `b2/vip_wing_stage`, pos (69.0, 5.5, 3.2), aimed at (-5.0, 7.0, 1.68):
  74.03 m.
Lux clamps a stage light's range to 12 m and refused both
(`LUX_CLUB_REFUSED`; cold runs 9060, 9167 and 9197 carried it).

The fixture is Deli Counter's build of strip_club_a01's light manifest
(`deli_counter/build/strip_club_a01.lights.json`, manifest 1.3.0), verbatim.
The instrument is the property Lux reads: a placement is a rotation and a
translation, so it preserves distance, and a placed stage throws exactly as
far as it does in its own building, at any turn and any offset.
"""
import json
import math
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lot  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "strip_club_a01.lights.json")
#: The range `lux_light_loader.gd` clamps a stage light to.
LUX_STAGE_RANGE = 12.0


def _spec():
    return {"name": "t", "buildings": [{"id": "b2", "at": [0.0, 0.0], "rot": 0,
                                        "lights": "club.lights.json"}]}


def _merged(tmp_path, at, rot, manifest=None):
    if manifest is None:
        shutil.copy(FIXTURE, tmp_path / "club.lights.json")
    else:
        (tmp_path / "club.lights.json").write_text(json.dumps(manifest), encoding="utf-8")
    spec = _spec()
    spec["buildings"][0].update(at=at, rot=rot)
    return {a["id"]: a for a in lot.merge_lights(spec, str(tmp_path))["anchors"]}


def _stages():
    with open(FIXTURE, encoding="utf-8") as f:
        return {a["id"]: a for a in json.load(f)["anchors"] if a.get("type") == "stage_light"}


def test_the_fixture_has_both_stages():
    assert sorted(_stages()) == ["main_floor_stage", "vip_wing_stage"]


@pytest.mark.parametrize("at,rot", [([69.0, -1.5], 0), ([-30.0, 40.0], 90), ([12.0, -8.0], 270)])
def test_each_stage_throws_as_far_as_it_does_in_its_building(tmp_path, at, rot):
    merged = _merged(tmp_path, at, rot)
    for sid, local in _stages().items():
        placed = merged[f"b2/{sid}"]
        throw = math.dist(placed["pos"], placed["target"])
        assert math.isclose(throw, math.dist(local["pos"], local["target"]), abs_tol=1e-3), (sid, throw)
        assert throw < LUX_STAGE_RANGE, (sid, throw)


def test_cold_run_9197s_club(tmp_path):
    """b2 at (69, -1.5), unturned: each stage aims where its building says,
    offset with the building."""
    merged = _merged(tmp_path, [69.0, -1.5], 0)
    assert merged["b2/main_floor_stage"]["target"] == [69.0, -6.5, 1.68]
    assert merged["b2/vip_wing_stage"]["target"] == [64.0, 5.5, 1.68]


def test_a_numeric_triple_nobody_classed_is_refused(tmp_path):
    """A field added upstream must not ride into site space in the building's
    frame unnoticed -- the rule `_ladder_to_site` keeps."""
    with open(FIXTURE, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["anchors"][0]["aim_at"] = [1.0, 2.0, 3.0]
    with pytest.raises(ValueError, match="aim_at"):
        _merged(tmp_path, [69.0, -1.5], 0, manifest)
