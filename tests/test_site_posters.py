"""Handbills on the alley walls and the poles (Lot 0.84.0, `site_posters`).

What is held: where a run goes (a true alley first, then the rear, then a
side; never the street facade, never over an opening, never where nobody can
stand to read it), which way it faces (the measured `plate_facing`
convention), that it is HUNG and not cover, how the slot and the module name
are written, and that the numbers Lot mirrors from Zoo are Zoo's.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_furniture  # noqa: E402
import site_posters as P  # noqa: E402

ZOO = os.environ.get("LOT_ZOO_ROOT") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "zoo")


def _bld(bid, at, fp, rot=0):
    return {"id": bid, "at": list(at), "rot": rot, "_footprint": list(fp)}


def _door(bid, wall, x, y, width=1.2):
    return {"building": bid, "wall": wall, "story": 0, "kind": "door", "x": x, "y": y,
            "width": width, "height": 2.2, "sill": 0.0}


def _site(blds, openings=(), ground=None):
    spec = {"name": "t", "buildings": blds}
    if ground:
        spec["ground"] = ground
    return spec, {"buildings": blds, "openings": list(openings)}


# --- facing -------------------------------------------------------------------------------


@pytest.mark.parametrize("n", [(0, -1), (1, 0), (0, 1), (-1, 0), (0.6, 0.8)])
def test_a_run_faces_where_it_is_asked_to(n):
    """`facing_yaw` is the inverse of the measured `plate_facing`."""
    got = site_furniture.plate_facing(P.facing_yaw(*n))
    assert math.hypot(got[0] - n[0], got[1] - n[1]) < 1e-6


# --- the walls ------------------------------------------------------------------------------


def test_a_true_alley_is_papered_on_the_stretch_the_neighbour_faces_clear_of_its_door():
    """A and B stand 2 m apart, A's north face to B's south; A's door is in
    the middle of that face. Worked by hand: the facing stretch 15..25 less a
    metre each corner is 16..24, less the door's 19.0..21.0 -- two 3 m runs,
    centred at 17.5 and 22.5, 0.159 m off the footprint edge, facing north."""
    a = _bld("A", (20, 0), (10, 10))
    b = _bld("B", (20, 12), (10, 10))
    spec, merged = _site([a, b], [_door("A", "ext_0_N", 0.0, 5.0)])
    runs = [r for r in P.plan_alley_walls(spec, merged, []) if r["host"] == "wall:A:N"]
    assert sorted(r["at"][0] for r in runs) == [17.5, 22.5], runs
    for r in runs:
        assert r["dims"] == [3.0, P.DEPTH, P.BAND_WALL] and r["wall"] == "alley"
        assert r["faces"] == "B" and abs(r["gap"] - 2.0) < 1e-9
        assert abs(r["at"][1] - (5.0 + P.WALL_THICK / 2 + P.AIR + P.DEPTH / 2)) < 1e-9
        assert site_furniture.plate_facing(r["yaw"]) == pytest.approx((0.0, 1.0))
        assert r["z"] == P.EYE and r["form"] == "alley" and r["species"] == "poster_wall"


def test_the_door_is_what_splits_the_run():
    """A control: without the door the same wall takes one run over the middle."""
    a = _bld("A", (20, 0), (10, 10))
    b = _bld("B", (20, 12), (10, 10))
    spec, merged = _site([a, b])
    runs = [r for r in P.plan_alley_walls(spec, merged, []) if r["host"] == "wall:A:N"]
    assert [r["at"][0] for r in runs] == [20.0] and runs[0]["dims"][0] == P.RUN_MAX


def test_the_street_facade_is_never_papered():
    """With no road, the street is the side facing the plate's centre
    (`lot.sign_placement`): west, for a building at x = 20."""
    a = _bld("A", (20, 0), (10, 10))
    spec, merged = _site([a])
    assert P._street_side(a, []) == "W"
    runs = P.plan_alley_walls(spec, merged, [])
    assert runs and all(not r["host"].endswith(":W") for r in runs)
    # the rear first
    assert runs[0]["host"] == "wall:A:E" and runs[0]["wall"] == "rear"
    assert len(runs) <= P.RUNS_PER_BUILDING


def test_a_wall_nobody_can_stand_in_front_of_is_left_bare():
    """A neighbour 0.5 m off the north face: that stretch is a party wall."""
    a = _bld("A", (20, 0), (10, 10))
    b = _bld("B", (20, 10.5), (10, 10))
    spec, merged = _site([a, b])
    assert not [r for r in P.plan_alley_walls(spec, merged, []) if r["host"] == "wall:A:N"]


def test_a_road_between_two_buildings_makes_it_a_street():
    import site_streets
    a = _bld("A", (20, 0), (10, 10))
    b = _bld("B", (20, 16), (10, 10))
    spec, merged = _site([a, b])
    spec["roads"] = [{"a": [-40, 8], "b": [80, 8], "width": 3.0}]
    roads = site_streets.roads(spec, [])
    runs = P.plan_alley_walls(spec, merged, roads)
    assert not [r for r in runs if r.get("wall") == "alley"], runs


# --- the poles ------------------------------------------------------------------------------


def _poles(y, n=12):
    import site_streets
    spec = {"name": "t", "buildings": [], "roads": [{"a": [0, 0], "b": [100, 0], "width": 8.0,
                                                    "sidewalk": True}]}
    roads = site_streets.roads(spec, [])
    spec["cover"] = [{"name": f"lamp_{k}", "species": "streetlight", "at": [5.0 + 8 * k, y],
                      "base": "sidewalk"} for k in range(n)]
    return spec, roads


def _check_on_face(spec, bills, normal):
    for r in bills:
        i = int(r["host"].split("_")[-1])
        px, py = spec["cover"][i]["at"]
        off = P.POLES["streetlight"] + P.AIR + P.DEPTH / 2
        assert r["at"] == pytest.approx([px + normal[0] * off, py + normal[1] * off])
        assert site_furniture.plate_facing(r["yaw"]) == pytest.approx(normal)
        assert r["dims"] == [P.SHEET_W, P.DEPTH, P.BAND_POLE] and r["base"] == "sidewalk"


def test_a_pole_bill_takes_the_sidewalk_face_when_the_moon_lights_it():
    """Poles south of the road: the sidewalk face points south, which the
    night's key light reaches (0.50 in plan) -- the bill stays on it."""
    spec, roads = _poles(-6.0)
    bills = P.plan_pole_bills(spec, roads)
    assert 0 < len(bills) < 12            # every other pole, by its name's hash
    assert all(r["face"] == "sidewalk" for r in bills)
    _check_on_face(spec, bills, (0.0, -1.0))


def test_a_pole_bill_turns_to_a_lit_face_when_the_sidewalk_s_is_dark():
    """Poles north of the road: the sidewalk face points north, which 9117
    measured at 0.0 luma on 8 of 8 pieces. The bill goes round the pole to
    the first lit face in preference order -- along the road, west."""
    spec, roads = _poles(6.0)
    bills = P.plan_pole_bills(spec, roads)
    assert bills and all(r["face"] == "along" and r["lit"] >= P.LIT_MIN for r in bills)
    _check_on_face(spec, bills, (-1.0, 0.0))


def test_every_pole_bill_faces_the_key_light():
    for y in (-6.0, 6.0):
        spec, roads = _poles(y)
        for r in P.plan_pole_bills(spec, roads):
            n = site_furniture.plate_facing(r["yaw"])
            assert n[0] * P.LIGHT[0] + n[1] * P.LIGHT[1] >= P.LIT_MIN, r


def test_the_key_light_lights_what_9117_measured_lit():
    """Of 21 hung posters in cold run 9117, south- and west-facing read 43-101
    luma at centre, north-facing 0.0. The derived direction must agree."""
    lx, ly = P.light_from()
    dot = lambda n: n[0] * lx + n[1] * ly
    assert dot((0, -1)) >= P.LIT_MIN and dot((-1, 0)) >= P.LIT_MIN
    assert dot((0, 1)) < 0 and dot((1, 0)) < 0


def test_the_key_light_is_lux_s_night():
    lux = os.environ.get("LOT_LUX_ROOT") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lux")
    path = os.path.join(lux, "addons", "lux", "presets", "delco_night.tres")
    if not os.path.isfile(path):
        pytest.skip("lux repo not found (set LOT_LUX_ROOT)")
    got = {}
    for line in open(path, encoding="utf-8"):
        k, _, v = line.partition(" = ")
        if k in ("sun_elevation_deg", "sun_azimuth_deg"):
            got[k] = float(v)
    assert got == {"sun_elevation_deg": P.NIGHT_ELEVATION_DEG,
                   "sun_azimuth_deg": P.NIGHT_AZIMUTH_DEG}, got


# --- hung, not cover --------------------------------------------------------------------------


def test_a_hung_piece_is_a_slot_with_no_collision_at_its_own_height(tmp_path):
    import json
    rec = P._record("x", (1.0, 2.0), 90.0, (2.4, P.DEPTH, P.BAND_WALL), P.EYE, host="wall:A:E")
    spec = {"name": "t", "cover": [{"species": "streetlight", "at": [0, 0], "dims": [0.7, 0.3, 6.0],
                                    "base": "sidewalk"}],
            "hung": [rec, dict(rec, base="sidewalk")]}
    out = tmp_path / "t.slots.json"
    assert lot.write_site_slots(spec, str(out)) == 3
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["coverage"] == {"prop/site_cover": 1, "prop/site_hung": 2}
    h0, h1 = [s for s in doc["slots"] if s["slot_id"].startswith("hung_")]
    assert h0["fit"]["collision"] == "none" and h0["material"] == "paper"
    assert h0["transform"]["translation"][2] == P.EYE
    assert h1["transform"]["translation"][2] == round(lot.SIDEWALK_H + P.EYE, 4)
    assert h0["form"] == "alley" and h0.get("variant", 0) == rec["variant"]


def test_a_site_with_no_hung_pieces_writes_the_manifest_it_always_did(tmp_path):
    import json
    spec = {"name": "t", "cover": [{"species": "streetlight", "at": [0, 0],
                                    "dims": [0.7, 0.3, 6.0], "base": "sidewalk"}]}
    out = tmp_path / "t.slots.json"
    lot.write_site_slots(spec, str(out))
    assert json.loads(out.read_text(encoding="utf-8"))["coverage"] == {"prop/site_cover": 1}


def test_the_stem_spells_zoo_s_variant_and_nothing_moves_without_one():
    assert (lot.cover_module_stem("poster_wall", "delco_1997", 1, (2.4, 0.01, 0.814),
                                  form="alley", variant=2)
            == "prop_poster_wall_delco_1997_01_w240_d1_h81_falley_n2")
    assert (lot.cover_module_stem("sign_post", "delco_1997", 1, (0.3048, 0.06, 2.4384),
                                  form="no_parking")
            == "prop_sign_post_delco_1997_01_w30_d6_h244_fno_parking")
    assert lot.cover_module_stem("poster_wall", "delco_1997", 1, (2.4, 0.01, 0.814),
                                 form="alley", variant=0).endswith("_falley")


def test_a_hung_piece_with_no_module_is_not_given_another_family_s(tmp_path):
    """A plain `poster_wall` module is the club's art; an alley slot must not
    fall back to it."""
    stem_plain = lot.cover_module_stem("poster_wall", "delco_1997", 1, (2.4, 0.01, 0.814))
    (tmp_path / (stem_plain + ".glb")).write_bytes(b"")
    rec = P._record("x", (0, 0), 0.0, (2.4, 0.01, 0.814), P.EYE, host="wall:A:E")
    spec = {"hung": [rec], "cover_modules": {"dir": str(tmp_path), "theme": "delco_1997", "style": 1}}
    refs, _ext, findings = lot.cover_module_refs(spec, "", key="hung")
    assert refs == {} and findings and "hung_0" in findings[0][1]


# --- the numbers Lot mirrors from Zoo --------------------------------------------------------


def _zoo():
    if not os.path.isdir(os.path.join(ZOO, "zoo_keeper")):
        pytest.skip("zoo repo not found at %s (set LOT_ZOO_ROOT)" % ZOO)
    if ZOO not in sys.path:
        sys.path.insert(0, ZOO)


def test_the_bands_and_the_sheet_are_zoo_s():
    _zoo()
    from zoo_keeper.core import poster_art as PA
    from zoo_keeper.core import poster_wall_forms as F
    assert F.band_height("alley", 2) == P.BAND_WALL
    assert PA.SIZES_M["alley"][1] == P.BAND_POLE        # one sheet, no wander
    assert PA.SIZES_M["alley"][0] == P.SHEET_W


def test_zoo_fills_every_slot_lot_asks_for():
    """Zoo builds to exact fit and refuses a module that does not fill its
    slot. Cold run 9116 found the pole slot's band (0.52) was one no single
    sheet fills, and all four pole modules failed; this asks Zoo's planner
    the same question, for both slot shapes, every variant, before a run."""
    _zoo()
    from zoo_keeper.core import poster_wall_forms as F
    from zoo_keeper.core import prims as PR
    shapes = [(P.SHEET_W, P.BAND_POLE)] + [(w / 10.0, P.BAND_WALL)
                                           for w in range(int(P.RUN_MIN * 10), int(P.RUN_MAX * 10) + 1)]
    for w, h in shapes:
        for v in range(P.VARIANTS):
            g = F.plan(w, P.DEPTH, h, "alley", v, f"t{v}")
            lo, hi = PR.bounds(g["prims"])
            assert abs((hi[0] - lo[0]) - w) <= F.FIT_TOL and abs((hi[2] - lo[2]) - h) <= F.FIT_TOL,                 (w, h, v, hi[0] - lo[0], hi[2] - lo[2])


def test_the_stem_is_the_one_zoo_builds():
    _zoo()
    from zoo_keeper.core import kit
    for w, h, n in ((2.4, P.BAND_WALL, 2), (P.SHEET_W, P.BAND_POLE, 0), (3.0, P.BAND_WALL, 3)):
        slot = {"slot_id": "h", "role": "prop", "size_mod": "full", "style": 1,
                "species": "poster_wall", "form": "alley", "material": "paper",
                "fit": {"dims": [w, P.DEPTH, h], "pivot": "center"}}
        if n:
            slot["variant"] = n
        plan = kit.plan_kit({"building_id": "site", "slots": [slot]}, theme="delco_1997", style=1)
        assert plan["dressing_fallbacks"] == []
        assert plan["modules"][0]["stem"] == lot.cover_module_stem(
            "poster_wall", "delco_1997", 1, (w, P.DEPTH, h), form="alley", variant=n)
