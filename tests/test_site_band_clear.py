"""A lamp or a tree keeps out of a shop band's span (0.106.0).

Cold run 9222's frame of deli_a01 showed Lamp_2 standing 2.46 m in front of the SCRAPPLE & SONS
DELI band and hiding its E: the band spans stations 26 to 35 of road 0's left kerb and the lamp
spacing put it at 30. The furniture planner never knew the band was there. These hold it to the
band on the probe spec's one road (along x, its left kerb at y = 6.5, the band behind it).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_furniture   # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")


def _roads(extra=()):
    spec = json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))
    spec["roads"] = list(spec["roads"]) + list(extra)
    return site_streets.roads(spec)


def _band(x, y, half=4.5, axis="x"):
    return {"building": "b0", "at": (x, y), "half": half, "axis": axis}


def _lamps(pieces, kerb):
    return sorted(p["t"] for p in pieces if p["species"] == "streetlight" and p["kerb"] == kerb)


def test_a_lamp_in_front_of_a_band_steps_to_its_nearer_end():
    roads = _roads()
    assert 55.0 in _lamps(site_furniture.plan_furniture(roads), "L")
    # the band behind the left kerb, centred at station 56: 51.5 to 60.5, widened to 51 to 61
    pieces = site_furniture.plan_furniture(roads, sign_bands=[_band(-54.0, 12.0)])
    left = _lamps(pieces, "L")
    assert 55.0 not in left
    half = site_furniture.SPECIES["streetlight"][1] / 2.0
    assert abs(min(left, key=lambda t: abs(t - 51.0)) - (51.0 - half - site_furniture.PIECE_GAP)) < 1e-9
    assert not [t for t in left if 51.0 - half < t < 61.0 + half]


def test_a_band_across_the_road_moves_nothing_on_this_kerb():
    roads = _roads()
    bare = site_furniture.plan_furniture(roads)
    pieces = site_furniture.plan_furniture(roads, sign_bands=[_band(-54.0, -12.0)])
    assert _lamps(pieces, "L") == _lamps(bare, "L")
    assert 55.0 in _lamps(bare, "R") and 55.0 not in _lamps(pieces, "R")


def test_a_band_facing_another_road_moves_nothing_here():
    far = {"a": [-110, 200.0], "b": [110, 200.0], "width": 10, "sidewalk": 3}
    roads = _roads([far])
    bare = site_furniture.plan_furniture(roads)
    pieces = site_furniture.plan_furniture(roads, sign_bands=[_band(-54.0, 190.0)])
    near = [r for r in roads if r.a[1] == 0.0][0]
    ours = lambda ps: sorted(p["t"] for p in ps if p["species"] == "streetlight"
                             and p["road"] == near.index)
    assert ours(pieces) == ours(bare)


def test_without_a_band_in_the_way_nothing_changes():
    roads = _roads()
    bare = site_furniture.plan_furniture(roads)
    assert site_furniture.plan_furniture(roads, sign_bands=()) == bare
    # a 2.4 m band where no lamp or tree stands
    assert site_furniture.plan_furniture(roads, sign_bands=[_band(-80.0, 12.0, 1.2)]) == bare


def test_a_tree_keeps_out_too():
    roads = _roads()
    trees = lambda ps: sorted(p["t"] for p in ps if p["kerb"] == "L"
                              and p["species"] in site_furniture.TREES)
    bare = trees(site_furniture.plan_furniture(roads))
    assert 42.5 in bare
    pieces = site_furniture.plan_furniture(roads, sign_bands=[_band(-67.5, 12.0, 2.0)])
    assert 42.5 not in trees(pieces)


def test_the_finding_names_the_piece_and_both_stations():
    findings = []
    site_furniture.plan_furniture(_roads(), findings=findings, sign_bands=[_band(-54.0, 12.0)])
    said = [f for f in findings if f.startswith("LOT_BAND_KEPT_CLEAR:")]
    assert len(said) == 1
    assert "would have stood at station 55.00" in said[0] and "it stands at 50.55" in said[0]


def test_sign_bands_is_the_band_the_scene_draws():
    spec = {"buildings": [{"id": "b0", "at": [-54.0, 20.0], "rot": 0,
                           "footprint": [12.5, 16.0]}],
            "roads": [{"a": [-110, 0.0], "b": [110, 0.0], "width": 10, "sidewalk": 3}]}
    roads = site_streets.roads(spec)
    (band,) = lot.sign_bands(spec, roads, signs={"b0": {"id": "sign_b0"}})
    x, y, yaw, facade = lot.sign_placement(spec["buildings"][0], roads)
    assert band["at"] == (x, y) and band["half"] == lot.sign_size(facade)[0] / 2.0
    assert yaw in (90.0, 270.0) and band["axis"] == "x"     # a facade facing the road runs along x
    assert lot.sign_bands(spec, roads, signs={}) == []
