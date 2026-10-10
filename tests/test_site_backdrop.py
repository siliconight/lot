"""The backdrop beyond the plate's edge (Lot 0.108.0, roadmap 228 step D): rows of rowhomes
and a water tower by recipe, in their own list, never cover."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot                # noqa: E402
import site_backdrop as SB  # noqa: E402

GROUND = (-98.0, -50.0, 98.0, 50.0)       # cold run 9223's plate


def _plan(spec=None, ground=GROUND, seed=9104):
    findings = []
    got = SB.plan(dict(spec or {"name": "site"}), ground, seed=seed, findings=findings)
    return got, findings


def test_the_borough_is_the_recipe_a_spec_does_not_name():
    assert SB.surroundings({}) == "borough"
    assert SB.surroundings({"surroundings": " Parkland "}) == "parkland"


def test_the_borough_lays_three_bands_a_side_and_one_tower():
    got, findings = _plan()
    assert findings == []
    s = SB.summary(got)
    assert s["towers"] == 1 and 150 <= s["houses"] <= 450
    assert all(s["by_side"][k] > 10 for k in "NSEW")
    assert s["modules"] <= SB.MODULES_PER_LEVEL
    bands = {(p["side"], p["band"]) for p in got if p["species"] == SB.SPECIES}
    assert bands == {(sd, b) for sd in "NSEW" for b in range(len(SB.BANDS))}
    for p in got:
        assert p["source"] == "site_backdrop" and "size" not in p


def test_every_piece_stands_outside_the_plate_facing_it():
    got, _ = _plan()
    x0, y0, x1, y1 = GROUND
    for p in got:
        x, y = p["at"]
        w, d, h = p["dims"]
        outside = (y - d / 2 >= y1 + SB.BANDS[0][0] - 1e-9 or y + d / 2 <= y0 - SB.BANDS[0][0] + 1e-9
                   or x - w / 2 >= x1 + SB.BANDS[0][0] - 1e-9 or x + w / 2 <= x0 - SB.BANDS[0][0] + 1e-9)
        assert outside, p
        assert p["yaw"] == (SB.FACING[p["side"]] if p["species"] == SB.SPECIES else 0.0)
    tower = next(p for p in got if p["species"] == SB.TOWER_SPECIES)
    assert tower["at"][1] == y1 + SB.TOWER_OUT and tower["dims"] == list(SB.TOWER)


def test_a_house_takes_its_band_as_its_depth_and_one_of_the_levels_modules():
    got, _ = _plan()
    rng_kinds = set()
    for p in got:
        if p["species"] != SB.SPECIES:
            continue
        near, far = SB.BANDS[p["band"]]
        assert abs(p["dims"][1] - (far - near)) < 1e-9
        assert p["dims"][0] in SB.WIDTHS and p["dims"][2] in SB.HEIGHTS
        rng_kinds.add((p["dims"][0], p["dims"][2]))
    assert 1 < len(rng_kinds) <= SB.MODULES_PER_LEVEL


def test_the_plan_is_deterministic_for_a_seed_and_moves_with_it():
    a, _ = _plan(seed=9104)
    b, _ = _plan(seed=9104)
    c, _ = _plan(seed=9205)
    assert json.dumps(a) == json.dumps(b)
    assert json.dumps(a) != json.dumps(c)


def test_none_lays_nothing_and_no_ground_lays_nothing():
    assert _plan({"name": "site", "surroundings": "none"})[0] == []
    assert _plan(ground=None)[0] == []


def test_a_recipe_without_a_kit_and_an_unknown_one_lay_the_borough_and_say_so():
    got, findings = _plan({"name": "site", "surroundings": "parkland"})
    assert SB.summary(got)["towers"] == 1
    assert len(findings) == 1 and findings[0].startswith("LOT_BACKDROP_RECIPE_PENDING")
    got, findings = _plan({"name": "site", "surroundings": "moon"})
    assert SB.summary(got)["towers"] == 1
    assert len(findings) == 1 and findings[0].startswith("LOT_BACKDROP_RECIPE_UNKNOWN")


def test_the_slots_manifest_carries_the_backdrop_without_collision(tmp_path):
    spec = {"name": "site", "cover": [], "backdrop": _plan()[0]}
    out = tmp_path / "site.slots.json"
    n = lot.write_site_slots(spec, str(out))
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert n == len(spec["backdrop"]) == doc["coverage"]["prop/site_backdrop"]
    assert doc["coverage"].get("prop/site_cover", 0) == 0
    for s in doc["slots"]:
        assert s["slot_id"].startswith("backdrop_") and s["role"] == "prop"
        assert s["fit"]["collision"] == "none" and s["source"] == "site_backdrop"
        assert s["species"] in (SB.SPECIES, SB.TOWER_SPECIES)
    house = next(s for s in doc["slots"] if s["species"] == SB.SPECIES)
    assert house["material"] == "brick"
    assert abs(house["transform"]["translation"][2] - house["fit"]["dims"][2] / 2.0) < 1e-9
