"""A heap of filled garbage bags beside each dumpster (Lot 0.104.0, roadmap 219 note 11)."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_dumpsters as SD  # noqa: E402
import site_streets  # noqa: E402
import site_yards  # noqa: E402

_DOOR = {"kind": "door", "width": 1.2, "height": 2.2, "sill": 0.0}
_WINDOW = {"kind": "window", "width": 1.6, "height": 1.2, "sill": 1.1}
W, D, H = SD.BAG_DIMS
CW, CD, CH = SD.DIMS
_B = {"id": "b0", "at": [0, 0], "rot": 0, "_footprint": [20, 10]}
_SOUTH_ROAD = {"a": [-40, -14], "b": [40, -14], "width": 10.0, "sidewalk": 3.0}
_FRONT = dict(_DOOR, building="b0", wall="ext_0_S", story=0, x=0, y=-5)


def _site(bldgs, roads=(), paths=()):
    return {"name": "t", "buildings": [dict(b) for b in bldgs], "roads": list(roads), "paths": list(paths)}


def _merged(bldgs, ops):
    return {"buildings": [dict(b) for b in bldgs], "openings": list(ops)}


def _dumpster(x):
    """A container against b0's back (y = 5) at x, as `plan_dumpsters` writes one."""
    return {"name": "Dumpster_b0", "species": "dumpster", "at": [x, 5.0 + 0.25 + CD / 2.0],
            "yaw": 180.0, "dims": [CW, CD, CH], "size": [CW, CH, CD], "base": "plate",
            "variant": 0, "building": "b0", "wall": "N", "source": "site_dumpsters"}


def _rect(p):
    sx, _h, sy = p["size"]
    return (p["at"][0] - sx / 2.0, p["at"][1] - sy / 2.0, p["at"][0] + sx / 2.0, p["at"][1] + sy / 2.0)


def _bags(site, ops, dumpsters, **kw):
    findings = []
    standing = kw.pop("standing", [_rect(p) for p in dumpsters])
    got = SD.plan_bags(site, _merged(site["buildings"], ops), site_streets.roads(site), dumpsters,
                       standing=standing, findings=findings, **kw)
    return got, findings


def test_a_heap_stands_beside_its_dumpster_turned_along_its_side_and_on_its_pad():
    """The whole road: the dumpster `plan_dumpsters` stands, the pad `plan_yards` lays under it,
    and the heap beside it. The literals are the rule; a constant read back from the module
    would pass whatever it said."""
    site = _site([_B], [_SOUTH_ROAD])
    merged = _merged(site["buildings"], [_FRONT])
    roads = site_streets.roads(site)
    (p,) = SD.plan_dumpsters(site, merged, roads)
    yards = site_yards.plan_yards(site, [p], [], standing=[_rect(p)])
    assert len(yards) == 1
    (b,), findings = _bags(site, [_FRONT], [p], yards=yards)
    assert findings == []
    assert b["species"] == "trash_bags" and b["building"] == "b0" and b["wall"] == "N"
    assert b["dumpster"] == p["name"] and b["on_pad"] is True
    # turned: its 0.8 m depth runs along the wall, its 1.4 m width out from it
    assert b["dims"] == [1.4, 0.8, 0.75] and b["size"] == [0.8, 0.75, 1.4] and b["base"] == "plate"
    assert b["yaw"] in (90.0, 270.0)
    # its back 0.15 m off the wall
    assert abs((b["at"][1] - 1.4 / 2) - (5.0 + 0.15)) < 1e-6
    # 0.1 m off the container's side, on the side away from the corner it stands toward
    gap = abs(b["at"][0] - p["at"][0]) - CW / 2 - 0.8 / 2
    assert abs(gap - 0.1) < 1e-6, gap
    assert abs(b["at"][0]) < abs(p["at"][0])
    # its front faces along the wall, away from the container
    away = 1.0 if b["at"][0] > p["at"][0] else -1.0
    assert b["yaw"] == (90.0 if away > 0 else 270.0)
    assert 0 <= b["variant"] < 4


def test_it_prefers_the_side_its_pad_covers():
    site = _site([_B], [_SOUTH_ROAD])
    p = _dumpster(0.0)
    y = p["at"][1]
    for x0, x1, want in ((-3.0, 1.5, -1.0), (-1.5, 3.0, 1.0)):
        pad = {"at": [(x0 + x1) / 2.0, 6.5], "size_x": x1 - x0, "size_y": 3.0, "dumpster": p["name"]}
        (b,), _f = _bags(site, [_FRONT], [p], yards=[pad])
        assert b["on_pad"] is True and (b["at"][0] - p["at"][0]) * want > 0, (want, b["at"], y)


def test_with_no_pad_it_still_stands_beside_and_says_so():
    site = _site([_B], [_SOUTH_ROAD])
    (b,), findings = _bags(site, [_FRONT], [_dumpster(0.0)])
    assert findings == [] and b["on_pad"] is False


def test_a_walk_or_what_stands_keeps_it_off_a_side():
    site = _site([_B], [_SOUTH_ROAD])
    p = _dumpster(0.0)
    east = (CW / 2.0 + 0.05, 5.0, CW / 2.0 + 1.5, 8.0)
    (b,), _f = _bags(site, [_FRONT], [p], keep_out=[east])
    assert b["at"][0] < 0.0
    (c,), _f = _bags(site, [_FRONT], [p], standing=[_rect(p), east])
    assert c["at"][0] < 0.0


def test_a_door_or_a_window_keeps_it_off_a_side_and_none_is_said():
    """A back door 1.5 m past where the east heap would stand, and a window just past the west
    one: neither side clears, so no bags, and it says so."""
    site = _site([_B], [_SOUTH_ROAD])
    p = _dumpster(0.0)
    far = CW / 2.0 + 0.1 + 0.8                          # the heap's far side, from the centre
    ops = [_FRONT,
           dict(_DOOR, building="b0", wall="ext_0_N", story=0, x=far + 1.5 + 0.6, y=5),
           dict(_WINDOW, building="b0", wall="ext_0_N", story=0, x=-(far + 0.3 + 0.8), y=5)]
    got, findings = _bags(site, ops, [p])
    assert got == []
    assert len(findings) == 1 and findings[0].startswith("LOT_BAGS_NO_ROOM") and p["name"] in findings[0]
    # the window alone: the east side is clear again
    (b,), _f = _bags(site, ops[:1] + ops[2:], [p])
    assert b["at"][0] > 0.0


def test_it_never_passes_the_wall_s_end():
    """A container 0.6 m in from the west corner: the west heap would stand past it."""
    site = _site([_B], [_SOUTH_ROAD])
    p = _dumpster(-10.0 + 0.6 + CW / 2.0)
    (b,), _f = _bags(site, [_FRONT], [p])
    assert b["at"][0] > p["at"][0]
    east_walk = (p["at"][0] + CW / 2.0, 5.0, p["at"][0] + CW / 2.0 + 1.0, 8.0)
    got, findings = _bags(site, [_FRONT], [p], keep_out=[east_walk])
    assert got == [] and findings[0].startswith("LOT_BAGS_NO_ROOM")


def test_the_same_site_stands_the_same_bags():
    site = _site([_B], [_SOUTH_ROAD])
    a, _f = _bags(site, [_FRONT], [_dumpster(0.0)])
    b, _f = _bags(site, [_FRONT], [_dumpster(0.0)])
    assert a == b and len(a) == 1


def test_the_slot_asks_for_the_plastic_heap(tmp_path):
    site = _site([_B], [_SOUTH_ROAD])
    (b,), _f = _bags(site, [_FRONT], [_dumpster(0.0)])
    b["variant"] = 3
    site["cover"] = [b]
    out = tmp_path / "t.slots.json"
    assert lot.write_site_slots(site, str(out)) == 1
    (slot,) = json.loads(out.read_text(encoding="utf-8"))["slots"]
    assert slot["species"] == "trash_bags" and slot["variant"] == 3
    assert slot["material"] == "plastic" and slot["fit"]["dims"] == [1.4, 0.8, 0.75]
    assert slot["transform"]["rot_y"] == b["yaw"]
    assert slot["transform"]["translation"][2] == round(0.75 / 2, 4)          # on the plate
    assert lot.cover_module_stem("trash_bags", "delco_1997", 1, [1.4, 0.8, 0.75], variant=3) \
        == "prop_trash_bags_delco_1997_01_w140_d80_h75_n3"


def test_lot_knows_the_species_and_zoo_draws_it():
    """Lot's dims ARE the genome's defaults; when the sibling repo is here, say so rather than
    trusting a comment. A Zoo without the genome is a landing out of order: Zoo 1.93.0 first."""
    import site_furniture
    assert site_furniture.SPECIES["trash_bags"] == SD.BAG_DIMS == (1.4, 0.8, 0.75)
    assert lot.COVER_MATERIALS["trash_bags"] == "plastic"
    zoo = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "zoo", "zoo_keeper", "genome", "species")
    if not os.path.isdir(zoo):
        import pytest
        pytest.skip("no sibling zoo checkout")
    path = os.path.join(zoo, "trash_bags.json")
    assert os.path.isfile(path), "Zoo has no trash_bags genome: land Zoo 1.93.0 first"
    g = json.load(open(path, encoding="utf-8"))
    dims = tuple(round(g["dimensions"][k]["default"], 3) for k in ("width", "depth", "height"))
    assert dims == SD.BAG_DIMS, dims
    assert g["materials"]["default"] == lot.COVER_MATERIALS["trash_bags"]
    assert g["module_variants"] == SD.BAG_VARIANTS
