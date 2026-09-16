"""The kerb line (roadmap 153): lamps at a spacing, a hydrant, a bin and a
sign at every crossing, on the sidewalk bands, as prop slots the site kit
builds. Every piece is taller than the step limit and carries collision,
so the honesty rule holds by species rather than by a check.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_furniture   # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "specs")


def _probe():
    return json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))


def test_every_piece_stands_on_a_band_clear_of_the_cuts():
    roads = site_streets.roads(_probe())
    pieces = site_furniture.plan_furniture(roads)
    assert pieces
    (road,) = roads
    for p in pieces:
        assert p["base"] == "sidewalk" and p["source"] == "site_furniture"
        x, y = p["at"]
        # the probe road runs along X at y = 0; bands are 5..8 and -8..-5
        assert 5.0 <= abs(y) <= 8.0, p
        assert -110.0 <= x <= 110.0
        t = x + 110.0
        kerb = road.kerb(p["kerb"])
        w, d, h = p["dims"]
        assert h > lot.STEP_MAX          # never a thing a body walks through
        # what must clear a dropped kerb is the piece's FOOTPRINT along the
        # road (a tree's grate), not its slot (the crown, 2.4 m up)
        half = p["along"] / 2
        for t0, t1, is_cut in kerb.spans:
            if is_cut:
                assert t + half <= t0 + 1e-6 or t - half >= t1 - 1e-6, (p, (t0, t1))


def test_lamps_at_the_spacing_and_the_corner_set_at_every_cut():
    roads = site_streets.roads(_probe())
    pieces = site_furniture.plan_furniture(roads)
    by = {}
    for p in pieces:
        by.setdefault(p["species"], []).append(p)
    lamps = sorted(p["at"][0] for p in by["streetlight"] if p["kerb"] == "L")
    gaps = [b - a for a, b in zip(lamps, lamps[1:])]
    assert gaps and all(abs(g - site_furniture.LAMP_SPACING) < 1e-6
                        or g > site_furniture.LAMP_SPACING for g in gaps)
    (road,) = roads
    cuts = sum(len(k.cuts) for k in road.kerbs)
    # the blade at a corner is a stop sign where the cut is a driveway and
    # the blank post where it is a footpath, so count the pair
    blades = by.get("sign_post", []) + [p for p in by.get("stop_sign", [])
                                        if p["breaks"].startswith("crossing@")]
    for species, got in (("fire_hydrant", by["fire_hydrant"]),
                         ("litter_bin", by["litter_bin"]),
                         ("blade", blades)):
        assert 1 <= len(got) <= cuts, species
    # THE BLADE FACES THE DRIVER IT IS FOR, not "the road". Until 0.73.0 every
    # corner blade was written at yaw_extra 90, which `plate_facing` turns into
    # +along: right for the L kerb, and edge-on-behind for the R kerb, whose
    # lane carries the +t driver. The post is a bare pole so nothing saw it;
    # the moment it carries a legend the facing is the legend.
    for p in [b for b in blades if b["breaks"].startswith("crossing@")]:
        travel = site_furniture._driver_on(road.kerb(p["kerb"]))
        fx, fy = site_furniture.plate_facing(p["yaw"])
        assert (fx * road.along[0] + fy * road.along[1]) * travel < -0.99, p


def test_assemble_writes_the_furniture_as_slots_standing_on_the_kerb(tmp_path):
    lot.assemble(os.path.join(SPECS, "coldrun_kerb_probe.json"), str(tmp_path))
    doc = json.loads((tmp_path / "coldrun_kerb_probe.slots.json").read_text(encoding="utf-8"))
    lamps = [s for s in doc["slots"] if s["species"] == "streetlight"]
    assert lamps
    for s in lamps:
        assert abs(s["transform"]["translation"][2] - (lot.SIDEWALK_H + 3.0)) < 1e-6
        assert s["fit"]["collision"] == "convex"
    g = json.loads((tmp_path / "coldrun_kerb_probe.site.gameplay.json").read_text(encoding="utf-8"))
    assert g["furniture_plan"]["placed"]
    # and the box the scene draws for a lamp stands on the band's top (the
    # kerb line is planned first, so the first lamp is the first slot)
    txt = (tmp_path / "coldrun_kerb_probe.tscn").read_text(encoding="utf-8")
    first_lamp = next(i for i, s in enumerate(doc["slots"]) if s["species"] == "streetlight")
    i = txt.index('name="cover_%d"' % first_lamp)
    assert f", {lot.SIDEWALK_H + 3.0:g}, " in txt[i:].split("\n")[1]


def test_a_tree_stands_between_every_two_lamps_on_the_grates_footprint():
    roads = site_streets.roads(_probe())
    (road,) = roads
    pieces = site_furniture.plan_furniture(roads)
    species = site_furniture.tree_for(road)
    trees = [p for p in pieces if p["species"] == species]
    lamps = [p for p in pieces if p["species"] == "streetlight"]
    assert trees and len(trees) <= len(lamps)
    w, _d, h = site_furniture.SPECIES[species]
    for p in trees:
        assert p["dims"] == list(site_furniture.SPECIES[species])   # the slot is the crown
        assert p["size"] == [1.2, h, 1.2]              # the box is the grate
        assert p["base"] == "sidewalk"
        # halfway between two lamp STATIONS (a lamp skipped for a cut still
        # leaves its station), on the outer half of the band
        phase = (p["t"] - site_furniture.LAMP_START - site_furniture.TREE_OFFSET)
        assert abs(phase % site_furniture.LAMP_SPACING) < 1e-6, p
        assert abs(abs(p["at"][1]) - (8.0 - site_furniture.TREE_INSET)) < 1e-6


def test_one_bus_stop_per_road_on_the_kerb_the_buildings_face():
    spec = _probe()
    roads = site_streets.roads(spec)
    pieces = site_furniture.plan_furniture(roads, spec["buildings"])
    shelters = [p for p in pieces if p["species"] == "bus_shelter"]
    benches = [p for p in pieces if p["species"] == "bench"]
    # the stop SET: a shelter, a bench inside it and a sign before it. The
    # mailbox, news racks and payphone carry the same `stop@` tag because
    # they stand at the same corner, so count the sign itself.
    signs = [p for p in pieces if p["species"] == "sign_post"
             and p["breaks"].startswith("stop@")]
    assert len(shelters) == 1 and len(benches) == 1 and len(signs) == 1
    (sh,), (bn,) = shelters, benches
    # the probe's buildings stand north of the road: the L kerb, back to +y
    assert sh["kerb"] == "L" and sh["yaw"] == 0.0 and bn["yaw"] == 0.0
    assert bn["t"] == sh["t"] and bn["at"][1] > sh["at"][1]      # inside, toward the back
    assert abs(sh["at"][1] - (8.0 - site_furniture.SHELTER_INSET)) < 1e-6
    # clear of every cut and of every other piece on that band
    kerb = roads[0].kerb("L")
    assert site_furniture._clear_of_cuts(sh["t"], 1.5, kerb)
    for p in pieces:
        if p["kerb"] == "L" and p["name"] not in (sh["name"], bn["name"]):
            assert abs(p["t"] - sh["t"]) >= 1.5 + p["along"] / 2, p
    # without buildings there is no facing kerb and no stop
    assert not [p for p in site_furniture.plan_furniture(roads) if p["species"] == "bus_shelter"]


def test_the_facing_kerb_is_read_from_the_buildings_side():
    (road,) = site_streets.roads(_probe())
    assert site_furniture._facing_kerb(road, [{"at": [0, 30]}]).side == "L"
    assert site_furniture._facing_kerb(road, [{"at": [0, -30]}]).side == "R"
    assert site_furniture._facing_kerb(road, []) is None


def test_a_piece_keeps_clear_of_the_mission_markers():
    """Cold run 9030, third seed: a lamp stood on Enemy_4 and the preflight
    refused the candidate. A lamp or a tree steps along its band; a corner
    piece or a bus stop is skipped."""
    roads = site_streets.roads(_probe())
    bare = site_furniture.plan_furniture(roads)
    lamp = next(p for p in bare if p["species"] == "streetlight")
    marker = tuple(lamp["at"])
    pieces = site_furniture.plan_furniture(roads, markers=[marker])
    for p in pieces:
        assert site_furniture._clear_of_markers(p, [marker]), p
    # the lamp stepped along its band rather than vanishing
    moved = [p for p in pieces if p["species"] == "streetlight" and p["kerb"] == lamp["kerb"]
             and abs(p["t"] - lamp["t"]) <= 4.0 + 1e-6]
    assert moved and moved[0]["t"] != lamp["t"]


def test_a_road_is_planted_with_one_species_and_the_species_is_the_roads():
    """A street plants one species per road (roadmap 153): five species
    scattered tree by tree reads as an arboretum."""
    spec = _probe()
    roads = site_streets.roads(spec)
    pieces = site_furniture.plan_furniture(roads, spec["buildings"])
    trees = [p for p in pieces if p["species"] in site_furniture.TREES]
    assert trees
    for road in roads:
        here = {p["species"] for p in trees if p["road"] == road.index}
        assert len(here) <= 1, here
        if here:
            assert here == {site_furniture.tree_for(road)}
    # stable: the same spec plants the same street twice
    again = site_furniture.plan_furniture(site_streets.roads(spec), spec["buildings"])
    assert [p["species"] for p in again if p["species"] in site_furniture.TREES] == \
        [p["species"] for p in trees]


def test_two_different_roads_can_carry_different_trees():
    """The hash is on the road's own endpoints, so a plate's avenue and its
    cross street are not the same tree by construction."""
    class _R:
        def __init__(self, a, b):
            self.a, self.b = a, b
    seen = {site_furniture.tree_for(_R((x, 0.0), (x + 100.0, 0.0)))
            for x in range(-40, 40, 3)}
    assert len(seen) >= 4, seen
    assert seen <= set(site_furniture.TREES)


def test_every_tree_lots_table_names_is_a_species_zoo_has_at_those_dims():
    """Lot's dims ARE the Zoo genomes' defaults; when the sibling repo is
    here, say so rather than trusting a comment. Measured 2026-09-13: a
    callery pear is 3.0 m across at planting and a London plane 5.0 m."""
    import json
    zoo = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "zoo",
        "zoo_keeper", "genome", "species")
    if not os.path.isdir(zoo):
        import pytest
        pytest.skip("no sibling zoo checkout")
    for sp in site_furniture.TREES:
        path = os.path.join(zoo, sp + ".json")
        assert os.path.isfile(path), sp
        g = json.load(open(path, encoding="utf-8"))
        dims = tuple(round(g["dimensions"][k]["default"], 3)
                     for k in ("width", "depth", "height"))
        assert dims == site_furniture.SPECIES[sp], (sp, dims, site_furniture.SPECIES[sp])


def test_the_junction_carries_a_signal_on_an_arterial_and_a_stop_sign_otherwise():
    """A Delco side street meeting a commercial strip has a signal; two
    side streets have a stop sign (roadmap 153, the 1990s street)."""
    tee = {"name": "tee", "ground": {"size_x": 140, "size_y": 120},
           "buildings": [],
           "roads": [{"a": [-60, 0], "b": [60, 0], "width": 10, "sidewalk": 3},
                     {"a": [0, 0], "b": [0, 50], "width": 10, "sidewalk": 3}]}
    through, side = site_streets.roads(tee)
    control = site_furniture.plan_traffic_control(side, [through, side])
    assert [p["species"] for p in control] == ["traffic_signal"]
    (sig,) = control
    # the pole stands back up the leg from its mouth, on the band
    assert sig["at"][0] != 0.0 or sig["at"][1] > 0
    assert abs(sig["at"][1] - (site_furniture.SIGNAL_SETBACK + 8.0)) < 1e-6
    assert sig["size"] == [0.7, 6.5, 0.7]          # the box is the pole
    assert sig["dims"] == [8.0, 0.62, 6.5]         # the slot is the reach
    # the through road ends on nothing, so it carries no control
    assert site_furniture.plan_traffic_control(through, [through, side]) == []
    # a narrow through road with no parking is not an arterial: a stop sign
    lane = {"name": "lane", "ground": {"size_x": 140, "size_y": 120},
            "buildings": [],
            "roads": [{"a": [-60, 0], "b": [60, 0], "width": 6, "sidewalk": 2},
                      {"a": [0, 0], "b": [0, 50], "width": 6, "sidewalk": 2}]}
    t2, s2 = site_streets.roads(lane)
    assert [p["species"] for p in site_furniture.plan_traffic_control(s2, [t2, s2])] \
        == ["stop_sign"]


def test_a_meter_stands_at_every_parking_bay_near_the_kerb():
    (road,) = site_streets.roads(_probe())
    meters = site_furniture.plan_meters(road)
    bays = site_streets.bays(road)
    assert len(meters) == len(bays)
    for m in meters:
        assert m["species"] == "parking_meter" and m["base"] == "sidewalk"
        # on the band, nearer the road than a lamp is
        assert 5.0 <= abs(m["at"][1]) <= 6.0, m


def test_the_stop_corner_stands_at_the_bus_stop():
    spec = _probe()
    roads = site_streets.roads(spec)
    pieces = site_furniture.plan_furniture(roads, spec["buildings"])
    by = {}
    for p in pieces:
        by.setdefault(p["species"], []).append(p)
    assert len(by.get("mailbox", [])) == 1
    assert len(by.get("newspaper_box", [])) == 2
    assert len(by.get("payphone", [])) == 1
    shelter = by["bus_shelter"][0]
    for sp in ("mailbox", "newspaper_box", "payphone"):
        for p in by[sp]:
            assert p["kerb"] == shelter["kerb"]
            assert abs(p["t"] - shelter["t"]) < 12.0, p
            assert p["breaks"].startswith("stop@")


def test_two_roads_that_meet_do_not_draw_the_same_tree():
    """Cold run 9035 planted red maples on both roads: one hash in five."""
    spec = {"name": "x", "ground": {"size_x": 200, "size_y": 200},
            "buildings": [{"id": "b0", "at": [0, 40]}],
            "roads": [{"a": [-88.5, -35.5], "b": [88.5, -35.5], "width": 10,
                       "sidewalk": 3},
                      {"a": [-29.35, -35.5], "b": [-29.35, 43.5], "width": 10,
                       "sidewalk": 3}]}
    roads = site_streets.roads(spec)
    assert site_furniture.tree_for(roads[0]) == site_furniture.tree_for(roads[1])
    pieces = site_furniture.plan_furniture(roads, spec["buildings"])
    per_road = {}
    for p in pieces:
        if p["species"] in site_furniture.TREES:
            per_road.setdefault(p["road"], set()).add(p["species"])
    assert len(per_road) == 2
    picked = [next(iter(v)) for v in per_road.values()]
    assert len(set(picked)) == 2, picked


def test_a_cut_of_any_width_keeps_the_blank_blade_and_never_a_stop_sign():
    """From 0.68.1 to 0.69.3 a cut 3.5 m or wider was read as a driveway and
    signed, so every 4 m door spur carried a stop sign and a path through
    both kerbs a pair (the walker, cold runs 9046 and 9048). A footpath is
    not an approach (docs/STREET_RULES.md)."""
    spec = _probe()
    roads = site_streets.roads(spec)
    (road,) = roads
    pieces = site_furniture.plan_furniture(roads, spec["buildings"])
    assert {c.width for k in road.kerbs for c in k.cuts} >= {4.0, 5.0}
    assert not [p for p in pieces if p["species"] == "stop_sign"]
    blanks = [p for p in pieces if p["species"] == "sign_post"
              and p["breaks"].startswith("crossing@")]
    assert blanks


#: Cold run 9060's `club_block_001` as `site_streets` reads it: a 173 m
#: arterial and a 72.65 m side street ending on it, both 10 m wide with 3 m
#: bands, and three buildings north of the arterial. The T's centre is plan
#: (-25.5, -32.15) and its north-east corner is where the walker's screenshot
#: was taken. The numbers are the spec's, not invented, so a change measured
#: against the shipped site is reproducible here.
CLUB_BLOCK = {
    "name": "club_block_t", "ground": {"size_x": 192, "size_y": 93},
    "buildings": [{"id": "b0", "at": [-59, -5]}, {"id": "b1", "at": [4, -5]},
                  {"id": "b2", "at": [53, 5]}],
    "roads": [{"a": [-86.5, -32.15], "b": [86.5, -32.15], "width": 10,
               "sidewalk": 3},
              {"a": [-25.5, -32.15], "b": [-25.5, 40.5], "width": 10,
               "sidewalk": 3}],
}


def _pairs(pieces):
    return [(a, b, math.hypot(a["at"][0] - b["at"][0], a["at"][1] - b["at"][1]))
            for i, a in enumerate(pieces) for b in pieces[i + 1:]]


def test_a_corner_where_two_kerb_lines_meet_stands_one_hydrant():
    """The walker, cold run 9060: "we wouldn't have fire hydrants that close
    to each other". Both roads of the T dropped their own kerb at the
    junction and each stood a hydrant past its own cut, so the north-east
    corner carried `cover_12` at Godot (-17.20, 24.60) and `cover_92` at
    (-17.95, 23.85) -- plan (-17.20, -24.60) and (-17.95, -23.85), 1.06 m
    apart. `plan_furniture` had no rule across roads: `_free` looked only at
    the band the piece stood on."""
    roads = site_streets.roads(CLUB_BLOCK)
    pieces = site_furniture.plan_furniture(roads, CLUB_BLOCK["buildings"])
    hydrants = [p for p in pieces if p["species"] == "fire_hydrant"]
    assert hydrants, "the spacing rule must not leave the site with none"
    # the corner the walker photographed: within a junction box of the T's
    # centre, on its north-east side. A DISTANCE, not `corner_key` -- the key
    # names a quadrant, so a hydrant 91 m down the same road is in the same
    # one, and it only identifies a corner among the pieces a given crossing
    # generated (which is all `plan_furniture` asks of it).
    jx, jy = roads[0].point(61.0, 0.0)
    corner = [p for p in hydrants
              if math.hypot(p["at"][0] - jx, p["at"][1] - jy) < 15.0
              and p["at"][0] >= jx and p["at"][1] >= jy]
    assert len(corner) == 1, [p["at"] for p in corner]
    # and nowhere on the site are two nearer than a spacing
    close = [(a["at"], b["at"], round(d, 2)) for a, b, d in _pairs(hydrants)
             if d < site_furniture.HYDRANT_MIN_SPACING]
    assert close == [], close
    # the rule is derived from the standard, not chosen
    assert site_furniture.HYDRANT_MIN_SPACING == \
        site_furniture.HYDRANT_SPACING_DESIGN / 2.0


def test_the_spacing_rule_does_not_delete_a_streets_only_hydrant():
    """A road whose every candidate is a corner's second hydrant would be
    left bare by a plain minimum-spacing filter. The piece is moved along
    the road's own kerb instead, and when no station on it is a spacing from
    the rest the road says so rather than going quiet."""
    roads = site_streets.roads(CLUB_BLOCK)
    findings = []
    pieces = site_furniture.plan_furniture(roads, CLUB_BLOCK["buildings"],
                                           findings=findings)
    hydrants = [p for p in pieces if p["species"] == "fire_hydrant"]
    # THE CONJUNCTION IS THE CLAIM. 0.72.2 gives every road a hydrant and
    # gives the corner two; a plain minimum-spacing filter would separate
    # them and leave the side street bare. Both halves, or the rule is a
    # trade rather than a fix.
    assert {p["road"] for p in hydrants} == {r.index for r in roads}
    assert [round(d, 2) for _a, _b, d in _pairs(hydrants)
            if d < site_furniture.HYDRANT_MIN_SPACING] == []
    moved = [p for p in hydrants if p["breaks"] == "spacing"]
    assert moved, "the side street's corner hydrant should have been re-homed"
    assert findings == [], findings        # a move is not a hole
    # AND THE HOLE IS SAID WHEN IT IS ONE. A stem too short to hold a
    # hydrant a spacing from the arterial's carries none, and says so rather
    # than going quiet: 20 m of road against a 45.7 m rule.
    stub = dict(CLUB_BLOCK, roads=[CLUB_BLOCK["roads"][0],
                                   {"a": [-25.5, -32.15], "b": [-25.5, -12.15],
                                    "width": 10, "sidewalk": 3}])
    said = []
    short = site_furniture.plan_furniture(site_streets.roads(stub),
                                          stub["buildings"], findings=said)
    assert [p for p in short if p["species"] == "fire_hydrant"]
    assert [f for f in said if f.startswith("LOT_HYDRANT_NONE_ON_ROAD")], said


def test_every_post_names_the_blade_it_carries_and_a_corner_holds_one_post():
    """The walker, cold run 9060: "no signs on the stop signs here anymore?"
    -- a screenshot of two bare poles. The site instanced five
    `prop_sign_post_delco_1997_01_w10_d10_h240`, a 0.10 x 0.10 x 2.40 m pole
    with no blade, and zero stop signs; two of the five stood 1.06 m apart at
    one corner of the T and a third stood 1.6 m from the signal mast on
    another. A post carries a legend or it is not there, and a corner carries
    one post."""
    roads = site_streets.roads(CLUB_BLOCK)
    pieces = site_furniture.plan_furniture(roads, CLUB_BLOCK["buildings"])
    posts = [p for p in pieces if p["species"] == "sign_post"]
    assert posts
    known = {site_furniture.BLADE_AT_JUNCTION, site_furniture.BLADE_AT_PATH,
             site_furniture.BLADE_AT_BUS_STOP}
    for p in posts:
        assert p.get("blade") in known, p
    # the blade a junction corner carries is the corner's, and a footpath
    # cut's is the warning for a marked uncontrolled crossing
    at_junction = [p for p in posts if p["breaks"].startswith("crossing@")
                   and p["blade"] == site_furniture.BLADE_AT_JUNCTION]
    assert at_junction
    # ONE POST PER CORNER, counting the signal masts and the stop signs. Only
    # the posts that stand AT a road-road crossing have a corner: a bus stop's
    # flag is a `sign_post` too and keying it to the nearest junction would
    # invent a corner it does not stand on.
    keys = []
    for p in pieces:
        if p["species"] not in site_furniture.CORNER_POSTS:
            continue
        road = roads[p["road"]]
        stations = [c.t for c in road.crossings if c.kind == "road"
                    and p["breaks"] in (f"junction@{c.t:.1f}",
                                        f"crossing@{c.t:.1f}")]
        if not stations:
            continue
        keys.append(site_furniture.corner_key(road, stations[0], p["at"]))
    assert keys and len(keys) == len(set(keys)), keys
    # and no two posts anywhere are inside a body's width of each other
    close = [(a["name"], b["name"], round(d, 2)) for a, b, d in _pairs(
        [p for p in pieces if p["species"] in site_furniture.CORNER_POSTS])
        if d < 2.0]
    assert close == [], close


def test_the_slot_carries_the_blade_as_zoos_dressing_form(tmp_path):
    """Lot's half of the ask: the slot says which legend the post wants, in
    the field Zoo's `honour_dressing` reads, and the slot Zoo builds to is
    the BLADE's box rather than the pole's.

    0.73.0 wrote the form and deliberately left `_f<form>` out of the stem,
    because against a genome listing no forms it would have resolved a name
    Zoo had not built. Zoo 0.96.0 lists them, so the stem spells it -- and
    `cover_module_refs` falls back to the undressed name, which is what
    makes either landing order survivable.
    """
    lot.assemble(os.path.join(SPECS, "coldrun_kerb_probe.json"), str(tmp_path))
    doc = json.loads((tmp_path / "coldrun_kerb_probe.slots.json").read_text(encoding="utf-8"))
    posts = [s for s in doc["slots"] if s["species"] == "sign_post"]
    assert posts
    for s in posts:
        blade = s.get("form")
        assert blade in site_furniture.BLADE_DIMS, s
        assert s["fit"]["dims"] == list(site_furniture.BLADE_DIMS[blade]), s
        # centre-pivot: the slot's z is half the module's own height, which
        # is now the sign's height and not the pole's
        assert abs(s["transform"]["translation"][2]
                   - (lot.SIDEWALK_H + s["fit"]["dims"][2] / 2.0)) < 1e-6
    assert lot.cover_module_stem("sign_post", "delco_1997", 1,
                                 (0.3048, 0.06, 2.4384), form="no_parking") \
        == "prop_sign_post_delco_1997_01_w30_d6_h244_fno_parking"
    # and a slot with no form is the name it always was
    assert "_f" not in lot.cover_module_stem("sign_post", "delco_1997", 1,
                                             (0.1, 0.1, 2.4))


def test_the_blade_slots_are_the_mutcd_arithmetic():
    """A sign's size and its mounting height are the standard; the slot is
    what they add up to. Zoo's `core.sign_blade_forms.MODULE_DIMS` is this
    table and cannot be imported from here, so both sides carry literals.

    The 30 in pedestrian diamond is the one worth reading twice: a diamond
    warning sign is a SQUARE on its point, so a 30 in sign needs 30*sqrt(2)
    = 42.43 in of box, and its top lands at 10.5 ft.
    """
    inch = 0.0254
    assert site_furniture.BLADE_DIMS == {
        "no_parking": (0.3048, 0.060, 2.4384),
        "ped_crossing": (1.0776, 0.060, 3.2112),
        "bus_stop": (0.3048, 0.060, 2.5908)}
    # TO A TENTH OF A MILLIMETRE, not exactly: this table is typed in metres
    # and Zoo's is `12 * 0.0254`, which is 0.30479999999999996. The two
    # spellings of one number meet at `int(round(w * 100))` in the stem, so
    # the centimetre is what has to agree and the float does not.
    for key, want in (("no_parking", (12 * inch, (84 + 12) * inch)),
                      ("ped_crossing", (30 * math.sqrt(2) * inch,
                                        (84 + 30 * math.sqrt(2)) * inch)),
                      ("bus_stop", (12 * inch, (84 + 18) * inch))):
        got = site_furniture.BLADE_DIMS[key]
        assert abs(got[0] - want[0]) < 1e-4 and abs(got[2] - want[1]) < 1e-4
        assert (int(round(got[0] * 100)), int(round(got[2] * 100)))             == (int(round(want[0] * 100)), int(round(want[1] * 100)))
    assert set(site_furniture.BLADE_DIMS) == {
        site_furniture.BLADE_AT_JUNCTION, site_furniture.BLADE_AT_PATH,
        site_furniture.BLADE_AT_BUS_STOP}


def test_a_wider_blade_does_not_move_a_single_post():
    """The blade grew the MODULE, not the plan footprint. `_free`,
    `_clear_of_cuts` and `along` all read the pole, the way
    `FOOTPRINT["traffic_signal"]` has kept an 8 m mast arm from clearing the
    sidewalk since 0.72.0 -- so a 1.08 m diamond changes no station and no
    census. Measured against the pole's own numbers rather than against a
    recorded baseline, because a baseline is a copy of the thing under test.
    """
    roads = site_streets.roads(_probe())
    pieces = site_furniture.plan_furniture(roads)
    posts = [p for p in pieces if p["species"] == "sign_post"]
    assert posts
    pole_w, pole_d, _pole_h = site_furniture.SPECIES["sign_post"]
    for p in posts:
        assert p["along"] in (pole_w, pole_d), p
        sx, h, sy = p["size"]
        assert (sx, sy) in ((pole_w, pole_d), (pole_d, pole_w)), p
        # the greybox box stands as tall as the module it stands in for
        assert h == p["dims"][2] == site_furniture.BLADE_DIMS[p["blade"]][2]
        assert p["dims"][:2] == list(site_furniture.BLADE_DIMS[p["blade"]][:2])


def test_the_resolver_falls_back_from_the_dressed_name_to_the_plain_one(tmp_path):
    """THE RUNG THAT MAKES THE ORDER SURVIVABLE. Against a Zoo that draws
    the blade, the dressed name is there and is used. Against one that does
    not -- an older checkout, or a blade nobody has drawn yet -- only the
    plain name is built, and the post keeps the bare pole instead of falling
    all the way to greybox. Both directions, because only having one of them
    is how a two-repo change goes wrong in exactly one order.
    """
    dims = list(site_furniture.BLADE_DIMS["no_parking"])
    spec = {"cover": [{"at": [10.0, -4.0], "size": [0.1, dims[2], 0.1],
                       "species": "sign_post", "yaw": 0.0, "dims": dims,
                       "blade": "no_parking"}],
            "cover_modules": {"dir": str(tmp_path), "theme": "delco_1997",
                              "style": 1},
            "buildings": []}
    plain = "prop_sign_post_delco_1997_01_w30_d6_h244"
    dressed = plain + "_fno_parking"

    # neither built: the box stays, and the finding names BOTH names tried
    refs, _ext, findings = lot.cover_module_refs(spec, "res://")
    assert refs == {} and findings[0][0] == lot.CODE_COVER_MODULE_MISSING
    assert dressed in findings[0][1] and plain in findings[0][1]

    # only the plain one: the bare pole stands rather than a greybox
    (tmp_path / (plain + ".glb")).write_bytes(b"glTF")
    refs, _ext, findings = lot.cover_module_refs(spec, "", str(tmp_path / "a"))
    assert findings == [] and refs == {0: "cover_" + plain}

    # both: the dressed one wins
    (tmp_path / (dressed + ".glb")).write_bytes(b"glTF")
    refs, _ext, findings = lot.cover_module_refs(spec, "", str(tmp_path / "b"))
    assert findings == [] and refs == {0: "cover_" + dressed}


def test_every_hydrant_turns_its_pumper_outlet_to_the_road():
    """Zoo 0.85.0's hydrant carries its pumper outlet on -Y, the face
    `plate_facing` reads. Until 0.72.2 both kerbs wrote the road's angle, so
    every R-kerb hydrant pointed its pumper at the buildings (cold run 9052's
    `fire_hydrant_37`)."""
    roads = site_streets.roads(_probe())
    (road,) = roads
    hydrants = [p for p in site_furniture.plan_furniture(roads)
                if p["species"] == "fire_hydrant"]
    assert {p["kerb"] for p in hydrants} == {"L", "R"}
    for p in hydrants:
        fx, fy = site_furniture.plate_facing(p["yaw"])
        cx, cy = road.point(p["t"], 0.0)
        toward = (cx - p["at"][0]) * fx + (cy - p["at"][1]) * fy
        assert toward > 0, p
    # and the one the spacing rule re-homes turns the same way: a second
    # writer of a hydrant's yaw is a second chance to get it wrong
    club = site_streets.roads(CLUB_BLOCK)
    for p in [q for q in site_furniture.plan_furniture(club, CLUB_BLOCK["buildings"])
              if q["species"] == "fire_hydrant"]:
        r = club[p["road"]]
        fx, fy = site_furniture.plate_facing(p["yaw"])
        cx, cy = r.point(p["t"], 0.0)
        assert (cx - p["at"][0]) * fx + (cy - p["at"][1]) * fy > 0, p
