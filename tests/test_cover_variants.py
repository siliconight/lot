"""A parked box truck wears one of Zoo's four fleets (0.103.0, roadmap 219 note 5).

Zoo 1.92.0 draws `box_truck` in four invented Delco fleets, chosen by a slot's `variant`
(`module_variants: 4`). Lot carried a cover record's variant into the slot since 0.90.0 (the
dumpster's hauler) and never gave a cover piece one, so every truck on a lot would have been the
first fleet. Fails on 0.102.2: `site_cover` has no `COVER_VARIANTS` and no `cover_variant`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_cover     # noqa: E402

GROUND = (-150.0, -100.0, 150.0, 100.0)


def _truck(spawn, enemy):
    plan = site_cover.plan_cover({"LT_PlayerSpawn": spawn, "Enemy_0": enemy}, [], GROUND,
                                 opening_range=45.0, species=site_cover.COVER_SPECIES)
    (p,) = [c for c in plan.cover if c.species == "box_truck"][:1]
    return p


def test_a_truck_has_four_looks_and_nothing_else_has_one():
    assert site_cover.COVER_VARIANTS == {"box_truck": 4}
    for spot in ((0.0, 0.0), (12.5, -3.25), (-80.0, 40.0)):
        assert 0 <= site_cover.cover_variant("box_truck", spot) < 4
        assert site_cover.cover_variant("cargo_container", spot) == 0
        assert site_cover.cover_variant("simple_car", spot) == 0


def test_a_truck_keeps_its_look_where_it_stands_and_trucks_differ():
    a = site_cover.cover_variant("box_truck", (10.0, 4.0))
    assert site_cover.cover_variant("box_truck", (10.0, 4.0)) == a
    looks = {site_cover.cover_variant("box_truck", (x * 7.3, y * 5.1))
             for x in range(-6, 7) for y in range(-4, 5)}
    assert looks == {0, 1, 2, 3}


def test_the_plan_gives_its_truck_the_look_its_spot_picks():
    p = _truck((-60.0, 0.0), (60.0, 0.0))
    assert p.variant == site_cover.cover_variant("box_truck", (p.x, p.y))


def test_the_record_carries_a_look_only_when_it_is_not_the_plain_one():
    base = dict(name="c", x=0.0, y=0.0, size=6.0, height=2.8, species="box_truck",
                size_x=2.4, size_y=6.0, width=2.4, depth=6.0)
    plain = site_cover.Cover(**base)
    assert "variant" not in plain.as_site_cover() and "variant" not in plain.as_dict()
    third = site_cover.Cover(variant=3, **base)
    assert third.as_site_cover()["variant"] == 3 and third.as_dict()["variant"] == 3


def test_the_slot_and_the_module_ask_for_the_look(tmp_path):
    """0.90.0's road, now walked by a truck: the site's slot carries the variant, and the module
    asked for first is the variant's, `_n<v>`, before the plain one."""
    spec = {"cover": [{"at": [10.0, -4.0], "size": [6.0, 2.8, 2.4], "species": "box_truck",
                       "yaw": 90.0, "dims": [2.4, 6.0, 2.8], "variant": 2, "breaks": "a -> b"}]}
    out = tmp_path / "site.slots.json"
    assert lot.write_site_slots(spec, str(out)) == 1
    import json
    slots = json.load(open(out, encoding="utf-8"))["slots"]
    assert slots[0]["variant"] == 2
    assert lot.cover_module_stem("box_truck", "delco_1997", 1, [2.4, 6.0, 2.8], variant=2) \
        == "prop_box_truck_delco_1997_01_w240_d600_h280_n2"
