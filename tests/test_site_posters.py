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
    # spaced to stand alongside the 100 m road: past its end the nearest road
    # point is the end, and the facing is (correctly) diagonal
    step = 90.0 / max(1, n - 1)
    spec["cover"] = [{"name": f"lamp_{k}", "species": "streetlight", "at": [5.0 + step * k, y],
                      "base": "sidewalk"} for k in range(n)]
    return spec, roads


def _sleeve_checks(spec, sleeves, front):
    for r in sleeves:
        i = int(r["host"].split("_")[-1])
        cv = spec["cover"][i]
        # round the pole, centred on it (a record's position is to 0.1 mm)
        assert r["at"] == pytest.approx(cv["at"], abs=1e-4)
        assert r["species"] == "pole_flyers" and r["form"] in P.TIERS[1:]
        dia = 2 * (P.POLES[cv["species"]] + P.AIR + (P.FLYER_LAYERS - 1) * P.FLYER_LAYER)
        assert r["dims"][0] == r["dims"][1] == pytest.approx(dia, abs=1e-3)
        assert r["dims"][2] == P.TIER_BAND[r["form"]] and r["base"] == "sidewalk"
        assert site_furniture.plate_facing(r["yaw"]) == pytest.approx(front)


def test_a_sleeve_s_front_is_the_sidewalk_face_when_the_moon_lights_it():
    """Poles south of the road: the sidewalk face points south, which the
    night's key light reaches (0.50 in plan) -- the front stays on it."""
    spec, roads = _poles(-6.0, n=24)
    sleeves = P.plan_pole_bills(spec, roads)
    assert sleeves and all(r["face"] == "sidewalk" for r in sleeves)
    _sleeve_checks(spec, sleeves, (0.0, -1.0))


def test_a_sleeve_s_front_turns_to_a_lit_face_when_the_sidewalk_s_is_dark():
    """Poles north of the road: the sidewalk face points north, which 9117
    measured at 0.0 luma on 8 of 8 pieces; the front goes round the pole to
    the first lit face in preference order -- along the road, west."""
    spec, roads = _poles(6.0, n=24)
    sleeves = P.plan_pole_bills(spec, roads)
    assert sleeves and all(r["face"] == "along" and r["lit"] >= P.LIT_MIN for r in sleeves)
    _sleeve_checks(spec, sleeves, (-1.0, 0.0))


def test_every_sleeve_faces_the_key_light():
    for y in (-6.0, 6.0):
        spec, roads = _poles(y, n=24)
        for r in P.plan_pole_bills(spec, roads):
            n = site_furniture.plate_facing(r["yaw"])
            assert n[0] * P.LIGHT[0] + n[1] * P.LIGHT[1] >= P.LIT_MIN, r


def test_poles_are_papered_in_tiers_some_bare():
    """The photographs: bare poles, pairs, columns and wraps on one street,
    not one sheet on every other pole."""
    spec, roads = _poles(-6.0, n=40)
    sleeves = P.plan_pole_bills(spec, roads)
    forms = {r["form"] for r in sleeves}
    assert forms == {"pair", "stack", "wrap"}, forms
    assert 0 < len(sleeves) < 40                          # some poles bare


def test_a_junction_pole_is_papered_denser_but_a_bare_one_stays_bare():
    """A papered pole within `JUNCTION_M` of another road runs one tier
    denser: the corner is where a street's flyers go. A bare one stays bare
    (0.86.1): promoting it is how 0.86.0 papered 79 % of 9119's poles."""
    for k in range(80):
        name = f"lamp_{k}"
        plain, corner = P.tier_for(name, False), P.tier_for(name, True)
        if plain == "bare":
            assert corner == "bare", name
        else:
            assert P.TIERS.index(corner) == min(len(P.TIERS) - 1, P.TIERS.index(plain) + 1)


def test_about_a_third_of_poles_carry_paper():
    """The walker after 9119: "tune it down 50%...not every pole should have
    posters". Over many names, junction or not, about a third are papered."""
    import collections
    for junction in (False, True):
        c = collections.Counter(P.tier_for(f"pole_{k}", junction) for k in range(4000))
        papered = 1 - c["bare"] / 4000
        assert 0.30 <= papered <= 0.40, (junction, papered)


def test_no_shared_centreline_and_within_reach():
    """The placement guide's "repeated perfect centerline" tell, and its
    reach rule: tiers start at different heights; paper stops at `REACH`,
    and under a sign post's blade."""
    import site_streets
    spec, roads = _poles(-6.0, n=40)
    spec["cover"] += [{"name": f"post_{k}", "species": "sign_post", "at": [4.0 + 7.5 * k, -6.2],
                       "base": "sidewalk"} for k in range(12)]
    centres = {}
    for r in P.plan_pole_bills(spec, roads):
        top = r["z"] + r["dims"][2] / 2
        limit = P.BLADE_CLEAR if "post" in spec["cover"][int(r["host"].split("_")[-1])]["name"] else P.REACH
        assert top <= limit + 1e-6, (r["name"], top, limit)
        centres.setdefault(r["form"], []).append(r["z"])
    mids = {f: sum(v) / len(v) for f, v in centres.items()}
    assert len({round(m, 1) for m in mids.values()}) == len(mids), mids
    assert site_streets  # the road model the planner reads


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


def test_the_band_and_the_sleeve_are_zoo_s():
    _zoo()
    from zoo_keeper.core import pole_flyers_forms as PFF
    from zoo_keeper.core import poster_wall_forms as F
    assert F.band_height("alley", 2) == P.BAND_WALL
    assert (PFF.LAYERS, PFF.LAYER) == (P.FLYER_LAYERS, P.FLYER_LAYER)
    assert set(P.TIERS[1:]) == set(PFF.FORMS)


def test_zoo_fills_every_slot_lot_asks_for():
    """Zoo builds to exact fit and refuses a module that does not fill its
    slot (cold run 9116: all four pole modules, a band no single sheet
    fills). This asks Zoo's planners the same question for every slot shape
    Lot writes -- every wall run 0.9-3.0 m, and every pole species x tier --
    in every variant, before a run does."""
    _zoo()
    from zoo_keeper.core import pole_flyers_forms as PFF
    from zoo_keeper.core import poster_wall_forms as F
    from zoo_keeper.core import prims as PR
    for w in range(int(P.RUN_MIN * 10), int(P.RUN_MAX * 10) + 1):
        for v in range(P.VARIANTS):
            g = F.plan(w / 10.0, P.DEPTH, P.BAND_WALL, "alley", v, f"t{v}")
            lo, hi = PR.bounds(g["prims"])
            assert abs((hi[0] - lo[0]) - w / 10.0) <= F.FIT_TOL
            assert abs((hi[2] - lo[2]) - P.BAND_WALL) <= F.FIT_TOL
    for sp, r in P.POLES.items():
        dia = round(2.0 * (r + P.AIR + (P.FLYER_LAYERS - 1) * P.FLYER_LAYER), 3)
        for form in P.TIERS[1:]:
            h = P.TIER_BAND[form]
            for v in range(P.VARIANTS):
                g = PFF.plan(dia, dia, h, form, v, f"t{v}")
                lo, hi = PR.bounds(g["prims"])
                for got, want in ((hi[0] - lo[0], dia), (hi[1] - lo[1], dia), (hi[2] - lo[2], h)):
                    assert abs(got - want) <= PFF.FIT_TOL, (sp, form, v, got, want)
                # and the innermost paper clears the pole
                inner = min(((x * x + y * y) ** 0.5 for pr in g["prims"] for x, y, _z in pr["verts"]))
                assert inner >= r - 1e-6, (sp, form, inner, r)


def test_the_stem_is_the_one_zoo_builds():
    _zoo()
    from zoo_keeper.core import kit
    shapes = [("poster_wall", "alley", (2.4, P.DEPTH, P.BAND_WALL), 2),
              ("poster_wall", "alley", (3.0, P.DEPTH, P.BAND_WALL), 3)]
    for sp, r in P.POLES.items():
        dia = round(2.0 * (r + P.AIR + (P.FLYER_LAYERS - 1) * P.FLYER_LAYER), 3)
        shapes += [("pole_flyers", form, (dia, dia, P.TIER_BAND[form]), n)
                   for n, form in enumerate(P.TIERS[1:])]
    for species, form, dims, n in shapes:
        slot = {"slot_id": "h", "role": "prop", "size_mod": "full", "style": 1,
                "species": species, "form": form, "material": "paper",
                "fit": {"dims": list(dims), "pivot": "center"}}
        if n:
            slot["variant"] = n
        plan = kit.plan_kit({"building_id": "site", "slots": [slot]}, theme="delco_1997", style=1)
        assert plan["dressing_fallbacks"] == []
        assert plan["modules"][0]["stem"] == lot.cover_module_stem(
            species, "delco_1997", 1, dims, form=form, variant=n)
