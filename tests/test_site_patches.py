"""The utility cuts (0.138.0, the factory's roadmap 324): a patch of newer asphalt where each building's
services were trenched in from the main under the centre line to the kerb on its side -- two for a wide
frontage -- clear of the paint it does not cut and of the drains, on the road's own slab, its joints
sealed; drawn as the paint is, and with the art only.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_drains      # noqa: E402
import site_furniture   # noqa: E402
import site_patches     # noqa: E402
import site_streets     # noqa: E402

#: one street along x, and a T off it
STREET = [{"a": [-80.0, 0.0], "b": [80.0, 0.0], "width": 10.0, "sidewalk": 3.0}]
T_ROADS = STREET + [{"a": [0.0, 0.0], "b": [0.0, 60.0], "width": 10.0, "sidewalk": 3.0}]


def _bld(bid, x, y, w, d):
    return {"id": bid, "archetype": "card_shop_a01", "at": [x, y], "rot": 0, "_footprint": [w, d]}


def _plan(roads_spec, buildings):
    spec = {"name": "t", "roads": roads_spec, "buildings": buildings}
    roads = site_streets.roads(spec)
    marks = site_streets.markings(roads)
    drains = site_drains.plan(roads, site_furniture.plan_furniture(roads, []), marks)
    return roads, marks, drains, site_patches.plan(spec, roads, marks, drains)


def test_the_numbers_are_the_sources():
    assert abs(site_patches.TRENCH_W - 36 * 0.0254) < 1e-9       # a 24 in trench, 6 in T-cut each side
    assert site_patches.PROUD == site_drains.PROUD == 0.003


def test_one_trench_a_building_from_past_the_main_to_its_own_kerb():
    roads, _m, _d, patches = _plan(STREET, [_bld("b0", -30.0, 14.0, 8.0, 10.0),
                                            _bld("b1", 30.0, -14.0, 8.0, 10.0)])
    assert sorted(p["building"] for p in patches) == ["b0", "b1"]
    road = roads[0]
    for p in patches:
        across = [(c[0] - road.a[0]) * road.perp[0] + (c[1] - road.a[1]) * road.perp[1]
                  for c in p["corners"]]
        side = 1 if p["building"] == "b0" else -1     # b0 north of the road: its left
        # runs to the kerb face on the building's side, and PAST_MAIN over the centre line
        assert abs(max(a * side for a in across) - road.width / 2.0) < 1e-3
        assert abs(min(a * side for a in across) + site_patches.PAST_MAIN) < 1e-3
        assert abs(p["size"][0] - site_patches.TRENCH_W) < 1e-3


def test_a_wide_frontage_takes_two_laterals_side_by_side():
    _r, _m, _d, patches = _plan(STREET, [_bld("b0", -20.0, 16.0, 20.0, 12.0)])
    assert [p["lateral"] for p in patches] == [0, 1]
    a, b = patches
    assert abs(abs(a["t"] - b["t"]) - site_patches.LATERAL_GAP) < 1.0
    assert abs(a["t"] - b["t"]) >= site_patches.TRENCH_W + site_patches.PATCH_CLEAR - 1e-6


def test_a_building_set_back_is_still_served_and_a_site_with_no_street_takes_none():
    # a gas station across its forecourt (the slice's: 26 m back from the kerb face)
    _r, _m, _d, patches = _plan(STREET, [_bld("b0", 0.0, 42.0, 32.0, 22.0)])
    assert [p["building"] for p in patches] == ["b0", "b0"]
    lane = [{"a": [-80.0, 0.0], "b": [80.0, 0.0], "width": 5.0, "sidewalk": 0.0}]
    _r, _m, _d, patches = _plan(lane, [_bld("b0", 0.0, 14.0, 8.0, 10.0)])
    assert patches == []


def test_a_patch_keeps_clear_of_the_paint_it_does_not_cut_of_drains_and_of_junctions():
    buildings = [_bld(f"b{i}", x, 14.0, 9.0, 10.0) for i, x in enumerate((-12.0, 12.0, -40.0, 40.0))]
    roads, marks, drains, patches = _plan(T_ROADS, buildings)
    assert patches
    obstacles = [site_drains._paint(m)[0] for m in marks if m["kind"] not in site_patches.LINES_ALONG]
    obstacles += [site_patches._drain_poly(d)[0] for d in drains]
    for p in patches:
        poly = [tuple(c) for c in p["corners"]]
        for q in obstacles:
            assert site_drains._gap(poly, q) >= site_patches.PATCH_CLEAR - 1e-6
        road = roads[p["road"]]
        h = site_patches.TRENCH_W / 2.0
        for b0, b1 in site_patches._blocked_spans(road):
            assert p["t"] + h <= b0 + 1e-9 or p["t"] - h >= b1 - 1e-9
    # a patch beside the T was stepped off the junction box, not dropped
    assert {"b0", "b1"} <= {p["building"] for p in patches}


def test_two_buildings_the_same_width_are_not_cut_at_the_same_place_in_their_frontage():
    _r, _m, _d, patches = _plan(STREET, [_bld("b0", -40.0, 14.0, 8.0, 10.0),
                                         _bld("b1", 40.0, 14.0, 8.0, 10.0)])
    a, b = sorted(patches, key=lambda p: p["building"])
    assert abs((a["t"] - 40.0) - (b["t"] - 120.0)) > 0.05     # each from its own frontage centre


def test_the_meshes_are_the_road_pack_retinted_proud_of_the_paint_and_no_sealant_line():
    """The first build's 4 in sealant band broke into dashes at the street's distances (the module's
    retraction): a patch is its body only."""
    _r, _m, _d, patches = _plan(STREET, [_bld("b0", -30.0, 14.0, 8.0, 10.0)])
    skin = {"id": "road_pack", "albedo": "a.png", "meters_per_tile": 4.0}
    body, sub, files = site_patches.meshes(patches, 0.1, skin, lot.paint_offset, lot._mat_sub)
    names = sorted(files)
    assert names and all(n.startswith("site_patches_") and n.endswith(".obj") for n in names)
    assert names and all("_asphalt_" in n for n in names)
    text = "\n".join(sub)
    assert 'albedo_texture = ExtResource("road_pack_albedo")' in text
    # the material wears the oldest tint; each patch's age darkens it in its vertex colour (0.140.0)
    assert "albedo_color = Color(0.84, 0.84, 0.85, 1)" in text
    assert "vertex_color_use_as_albedo = true" in text and "vertex_color_is_srgb = true" in text
    assert "cast_shadow = 0" in "\n".join(body)
    ys = {n: {float(ln.split()[2]) for ln in files[n].splitlines() if ln.startswith("v ")} for n in names}
    for n, y in ys.items():
        want = 0.1 + site_patches.PROUD
        assert y == {round(want, 6)} or all(abs(v - want) < 1e-6 for v in y)


def test_no_road_pack_no_patches():
    _r, _m, _d, patches = _plan(STREET, [_bld("b0", -30.0, 14.0, 8.0, 10.0)])
    assert site_patches.meshes(patches, 0.1, None, lot.paint_offset, lot._mat_sub) == ([], [], {})


def test_a_greybox_lot_draws_no_patches_and_a_themed_one_does():
    """The graders' lots stay as they were (roadmap 242): a patch comes with the art, as a drain does --
    and with the road's pack, which it is."""
    import json
    spec = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "specs", "coldrun_kerb_probe.json")))
    # the footprints `annotate_footprints` reads off each building's export, standing in
    for b in spec["buildings"]:
        b["_footprint"] = [12.0, 60.0]
    roads = site_streets.roads(spec)
    spec["cover"] = site_furniture.plan_furniture(roads, spec.get("buildings") or [])
    skins = {"road": {"id": "road_pack", "albedo": "a.png", "meters_per_tile": 4.0}}
    grey, bare, themed = {}, {}, {}
    lot._outdoor_nodes(dict(spec), skins=skins, files=grey)
    lot._outdoor_nodes(dict(spec), cover_refs={0: "cover_0_module"}, files=bare)
    lot._outdoor_nodes(dict(spec), skins=skins, cover_refs={0: "cover_0_module"}, files=themed)
    assert not [n for n in grey if n.startswith("site_patches_")]
    assert not [n for n in bare if n.startswith("site_patches_")]
    assert [n for n in themed if n.startswith("site_patches_asphalt_")]
