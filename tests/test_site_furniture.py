"""The kerb line (roadmap 153): lamps at a spacing, a hydrant, a bin and a
sign at every crossing, on the sidewalk bands, as prop slots the site kit
builds. Every piece is taller than the step limit and carries collision,
so the honesty rule holds by species rather than by a check.
"""
import json
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
    for species in ("fire_hydrant", "litter_bin", "sign_post"):
        assert 1 <= len(by[species]) <= cuts, species
    assert all(p["yaw"] == 90.0 for p in by["sign_post"])     # faces the road


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
    assert abs(sig["at"][1] - (site_furniture.JUNCTION_SETBACK + 8.0)) < 3.0
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
