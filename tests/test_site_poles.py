"""The pole line (0.118.0, factory roadmap 240): one kerb of every street with a sidewalk carries
wooden utility poles, and the poles carry the street's lamps -- the walker's calls of 2026-10-12.
"""
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_furniture   # noqa: E402
import site_poles       # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")


def _probe():
    return json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))


def _plan(spec=None):
    spec = spec or _probe()
    roads = site_streets.roads(spec)
    return spec, roads, site_furniture.plan_furniture(roads, spec.get("buildings") or [])


def _poles(pieces):
    return [p for p in pieces if p["species"] == "utility_pole"]


def test_the_numbers_zoo_owns_are_these():
    """Zoo `core.utility_pole_forms` (1.104.0) owns them; its
    `test_the_numbers_lot_mirrors_are_these` pins the same literals."""
    assert site_poles.POLE_DIMS == {"auto": (0.3, 3.67, 10.4), "transformer": (0.46, 3.67, 10.4)}
    assert site_poles.POLE_AT == {"auto": (0.0, 0.615), "transformer": (0.0, 0.615)}
    assert site_poles.LENS_AT == (-2.171, 7.401)
    assert site_poles.WIRES == {"primary_0": (-1.07, 10.297), "primary_1": (-0.41, 10.297),
                                "primary_2": (1.07, 10.297), "neutral": (0.24, 9.3),
                                "secondary": (0.24, 7.95), "comm_0": (0.24, 6.4),
                                "comm_1": (0.24, 6.0)}


def test_one_kerb_carries_the_line_and_no_band_road_stands_a_steel_lamp():
    _spec, _roads, pieces = _plan()
    poles = _poles(pieces)
    assert poles
    assert len({p["kerb"] for p in poles}) == 1
    assert [p for p in pieces if p["species"] == "streetlight"] == []


def test_the_line_stands_its_inset_from_the_kerb_face_facing_the_road():
    """The probe road runs along x at y = 0, 10 m wide: the kerb faces are at
    y = +-5, so a pole stands at +-(5 + POLE_INSET), its cobra-head (module
    -Y) toward the road."""
    _spec, (road,), pieces = _plan()
    for p in _poles(pieces):
        assert abs(abs(p["at"][1]) - (5.0 + site_poles.POLE_INSET)) < 1e-3, p
        lx, ly, _lz = site_poles.lens_point(p, 0.0)
        assert abs(ly) < abs(p["at"][1]) - 2.0, (p, ly)


def test_every_station_stands_a_pole_so_no_two_spans_become_one():
    """A lost station doubles a span. The first draft stepped only
    `POLE_STEPS` and lost one inside the probe's 20 m footpath cut: a 75 m
    gap. A pole now steps to a cut's or a band's end too (`_steps`)."""
    _spec, (road,), pieces = _plan()
    poles = _poles(pieces)
    (side,) = {p["kerb"] for p in poles}
    assert len(poles) == len(site_poles.stations(road, road.kerb(side)))
    ts = sorted(p["t"] for p in poles)
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    assert gaps and max(gaps) < 2.0 * site_poles.POLE_SPAN, gaps


def test_poles_keep_clear_of_the_cuts_the_meters_and_each_other():
    _spec, (road,), pieces = _plan()
    meters = [p for p in pieces if p["species"] == "parking_meter"]
    half = site_poles.POLE_FOOTPRINT[0] / 2.0
    for p in _poles(pieces):
        kerb = road.kerb(p["kerb"])
        assert site_furniture._clear_of_cuts(p["t"], half, kerb), p
        for m in meters:
            if m["kerb"] == p["kerb"]:
                assert abs(m["t"] - p["t"]) >= half + m["along"] / 2.0, (p["name"], m["name"])


def test_every_pole_light_hangs_at_its_lens_as_the_scene_stands_the_module():
    """End to end, through the transform the scene writer emits: Zoo's lens
    point, in the module's own frame, carried by `lot._godot_transform` of
    the slot the module stands on, lands on the anchor Lux hangs its lamp at.
    A sign flipped anywhere -- the yaw, POLE_AT, LENS_AT, module_at -- puts
    the light metres off its lens."""
    spec, _roads, pieces = _plan()
    spec.setdefault("cover", []).extend(pieces)
    lights = {a["hardware"]: a for a in lot.merge_lights(spec, SPECS)["anchors"]
              if a["type"] == "streetlight"}
    checked = 0
    for i, cv in enumerate(spec["cover"]):
        if cv.get("species") != "utility_pole":
            continue
        a = lights["slot:cover_%d" % i]
        w, d, h = cv["dims"]
        base = lot.SIDEWALK_H
        nums = [float(v) for v in lot._godot_transform(
            tuple(cv["module_at"]), float(cv["yaw"]), z=base + h / 2.0).split(", ")]
        rows, origin = (nums[0:3], nums[3:6], nums[6:9]), nums[9:12]
        px, py = site_poles.POLE_AT[site_poles.form_of(cv)]
        ly, lz = site_poles.LENS_AT
        # the module is centre-pivot; Blender (x, y, z) is glTF (x, z, -y)
        local = (px, lz - h / 2.0, -(py + ly))
        world = [sum(r[k] * local[k] for k in range(3)) + o for r, o in zip(rows, origin)]
        plan = (world[0], -world[2], world[1])
        assert all(abs(plan[k] - a["pos"][k]) <= 0.002 for k in range(3)), (cv["name"], plan, a["pos"])
        assert a["rot_y"] == round(float(cv["yaw"]) % 360.0, 3)
        checked += 1
    assert checked == len(_poles(pieces)) > 0


def test_the_slot_stands_the_module_where_the_pole_stands_in_it():
    spec, _roads, pieces = _plan()
    spec.setdefault("cover", []).extend(pieces)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "s.slots.json")
        lot.write_site_slots(spec, out)
        slots = {s["slot_id"]: s for s in json.load(open(out))["slots"]}
    for i, cv in enumerate(spec["cover"]):
        if cv.get("species") != "utility_pole":
            continue
        s = slots["cover_%d" % i]
        tx, ty, tz = s["transform"]["translation"]
        assert [round(tx, 3), round(ty, 3)] == cv["module_at"]
        assert abs(tz - (lot.SIDEWALK_H + cv["dims"][2] / 2.0)) < 1e-6
        assert s["material"] == "wood"
        assert s.get("form") == (cv.get("form") or None)
        assert s["fit"]["dims"] == list(site_poles.POLE_DIMS[site_poles.form_of(cv)])


def test_the_stems_are_the_ones_zoo_builds():
    """Zoo 1.104.0 built these two names from slots shaped as Lot writes them."""
    assert lot.cover_module_stem("utility_pole", "delco", 1, (0.3, 3.67, 10.4)) == \
        "prop_utility_pole_delco_01_w30_d367_h1040"
    assert lot.cover_module_stem("utility_pole", "delco", 1, (0.46, 3.67, 10.4),
                                 form="transformer") == \
        "prop_utility_pole_delco_01_w46_d367_h1040_ftransformer"


def _long_street(buildings):
    return {"name": "poles", "roads": [{"a": [0.0, 0.0], "b": [400.0, 0.0], "width": 10,
                                        "sidewalk": 3}],
            "buildings": buildings}


def test_a_can_every_third_or_fourth_pole_on_the_pole_the_buildings_front():
    rows = [{"id": "b%d" % i, "at": [12.0 + 16.0 * i, 20.0]} for i in range(24)]
    spec, _roads, pieces = _plan(_long_street(rows))
    poles = sorted(_poles(pieces), key=lambda p: p["t"])
    cans = [i for i, p in enumerate(poles) if p.get("form") == "transformer"]
    assert len(poles) >= 8 and cans
    assert all(b - a in site_poles.CAN_EVERY for a, b in zip(cans, cans[1:])), cans
    assert cans[0] < site_poles.CAN_EVERY[1]
    for i in cans:
        assert poles[i]["dims"] == list(site_poles.POLE_DIMS["transformer"])


def test_a_line_that_serves_nothing_carries_no_can():
    _spec, _roads, pieces = _plan(_long_street([]))
    assert _poles(pieces)
    assert not [p for p in _poles(pieces) if p.get("form")]


def test_the_line_takes_the_kerb_with_less_to_dodge():
    """Three driveways across the left band (a parking field's, which runs
    from the carriageway's edge to the back of walk and drops that kerb only),
    none across the right: the line stands on the right."""
    spec = _long_street([])
    spec["driveways"] = [{"a": [x, 5.2], "b": [x, 8.5], "width": 4.0} for x in (60.0, 140.0, 220.0)]
    roads = site_streets.roads(spec)
    (road,) = roads
    left, right = road.kerb("L"), road.kerb("R")
    assert len(left.cuts) > len(right.cuts), (len(left.cuts), len(right.cuts))
    assert site_poles.pole_kerb(road) is right


#: Cold run 9262's lot (seed_9104): a main road, two side streets off it at a
#: signalised T each, and a lane between them.
T_ROADS = [{"a": [-85.5, -21.665], "b": [85.5, -21.665], "width": 10.0, "sidewalk": 3.0},
           {"a": [-19.9875, -21.665], "b": [-19.9875, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [75.15, -21.665], "b": [75.15, 32.0], "width": 10.0, "sidewalk": 3.0},
           {"a": [-19.9875, 27.185], "b": [75.15, 27.185], "width": 5.0, "sidewalk": 0.0}]


def test_every_line_stands_its_corner_poles_beside_a_signal():
    """Cold run 9262's west side street lost the pole at its junction (0.118.1):
    its runs began a cut's width from the crossing where the kerb's span
    reaches `CUT_MARGIN` further, so the first station sat in the cut's
    clearance, and the 5 m circle a signal kept refused every step off it."""
    roads = site_streets.roads({"name": "t", "roads": T_ROADS, "buildings": []})
    pieces = site_furniture.plan_furniture(roads, [])
    signals = [p for p in pieces if p["species"] == "traffic_signal"]
    assert signals, "the T stands no signal, so this proves nothing"
    half = site_poles.POLE_FOOTPRINT[0] / 2.0
    lines = 0
    for road in roads:
        poles = sorted((p for p in _poles(pieces) if p["road"] == road.index), key=lambda p: p["t"])
        if not poles:
            continue
        lines += 1
        kerb = road.kerb(poles[0]["kerb"])
        assert len(poles) == len(site_poles.stations(road, kerb)), (road.index, [p["t"] for p in poles])
        for t0, _t1 in site_poles._runs(road, kerb):
            assert site_furniture._clear_of_cuts(t0, half, kerb), (road.index, t0)
    assert lines == 3
    for p in _poles(pieces):
        assert site_poles._room(p, signals), p["name"]
    # and a corner pole has room among EVERY road's pieces, not its own kerb's
    # alone: at a corner two roads' furniture meet
    others = [q for q in pieces if q["species"] != "utility_pole"]
    for p in _poles(pieces):
        assert site_poles._room(p, others), p["name"]
