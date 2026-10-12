"""A pole or a tree keeps out of a shop band's span (0.106.0; the pole since 0.118.0).

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
import site_poles       # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")


def _roads(extra=()):
    spec = json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))
    spec["roads"] = list(spec["roads"]) + list(extra)
    return site_streets.roads(spec)


def _band(x, y, half=4.5, axis="x"):
    return {"building": "b0", "at": (x, y), "half": half, "axis": axis}


def _poles(pieces, kerb=None):
    return sorted(p["t"] for p in pieces if p["species"] == "utility_pole"
                  and (kerb is None or p["kerb"] == kerb))


def _line_kerb(pieces):
    (side,) = {p["kerb"] for p in pieces if p["species"] == "utility_pole"}
    return side


def _a_band_on_a_pole(roads):
    """A pole of the bare plan standing at its own station -- stepped off
    nothing, so the station a finding names is the pole's -- and a 9 m band
    centred on it behind its kerb (the probe road runs along x from -110, so
    station t is x = t - 110)."""
    bare = site_furniture.plan_furniture(roads)
    side = _line_kerb(bare)
    sign = 1.0 if side == "L" else -1.0
    (road,) = [r for r in roads if r.a[1] == 0.0]
    nominal = [round(t, 3) for t, _r0, _r1 in site_poles.stations(road, road.kerb(side))]
    for t in _poles(bare, side):
        if 20.0 < t < 200.0 and t in nominal:
            # and the same band behind the other kerb: a band on one kerb
            # alone would move the whole line across the road (`pole_kerb`
            # takes the kerb with less to dodge), which is not what is tried
            return bare, side, t, [_band(t - 110.0, 12.0 * sign),
                                   _band(t - 110.0, -12.0 * sign)]
    raise AssertionError("no pole of the probe stands at its own station")


def test_a_pole_in_front_of_a_band_steps_out_of_it():
    roads = _roads()
    bare, side, t, bands = _a_band_on_a_pole(roads)
    pieces = site_furniture.plan_furniture(roads, sign_bands=bands)
    got = _poles(pieces, side)
    assert t not in got
    # the band is t-4.5..t+4.5, widened by SIGN_CLEAR; no pole's column inside it
    half = site_poles.POLE_FOOTPRINT[0] / 2.0
    lo, hi = t - 4.5 - site_furniture.SIGN_CLEAR, t + 4.5 + site_furniture.SIGN_CLEAR
    assert not [s for s in got if lo - half < s < hi + half]
    # and it stepped out rather than vanishing: a pole's own steps come first
    # (6 m clears a 9 m band from its middle), the band's ends after them
    assert len(got) == len(_poles(bare, side))
    end = 4.5 + site_furniture.SIGN_CLEAR + half + site_furniture.PIECE_GAP
    assert min(abs(s - t) for s in got) <= max(max(site_poles.POLE_STEPS), end) + 1e-6


def test_a_band_across_the_road_moves_no_pole():
    roads = _roads()
    bare, side, t, bands = _a_band_on_a_pole(roads)
    pieces = site_furniture.plan_furniture(roads, sign_bands=bands[1:])
    assert _poles(pieces) == _poles(bare)


def test_a_band_facing_another_road_moves_nothing_here():
    far = {"a": [-110, 200.0], "b": [110, 200.0], "width": 10, "sidewalk": 3}
    roads = _roads([far])
    bare = site_furniture.plan_furniture(roads)
    pieces = site_furniture.plan_furniture(roads, sign_bands=[_band(-54.0, 190.0)])
    near = [r for r in roads if r.a[1] == 0.0][0]
    ours = lambda ps: sorted(p["t"] for p in ps if p["species"] == "utility_pole"
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


def test_the_finding_names_the_pole_and_both_stations():
    roads = _roads()
    bare, side, t, bands = _a_band_on_a_pole(roads)
    findings = []
    pieces = site_furniture.plan_furniture(roads, findings=findings, sign_bands=bands)
    said = [f for f in findings if f.startswith("LOT_BAND_KEPT_CLEAR: Pole_")]
    assert len(said) == 1, said
    moved = min(_poles(pieces, side), key=lambda s: abs(s - t))
    assert f"would have stood at station {t:.2f}" in said[0], said[0]
    assert f"it stands at {moved:.2f}" in said[0], said[0]


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
