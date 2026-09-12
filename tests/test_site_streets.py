"""The street is a model (roadmap 153): roads, kerbs, cuts and paint.

`site_streets` answers the street's geometry once; `lot._outdoor_nodes` draws
what it says and adds the paint as collision-free quads. The kerb-probe spec
is the fixture: one 220 m road with 3 m sidewalks and six paths crossing it.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_streets   # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "specs")


def _probe():
    return json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))


def test_the_model_resolves_the_road_and_its_kerbs():
    (road,) = site_streets.roads(_probe())
    assert road.width == 10 and road.sidewalk == 3 and abs(road.length - 220) < 1e-9
    assert road.along == (1.0, 0.0) and road.perp == (0.0, 1.0)
    assert [k.side for k in road.kerbs] == ["L", "R"]
    assert road.kerb("L").offset == 6.5 and road.kerb("R").offset == -6.5
    assert road.point(0.0, 6.5) == (-110.0, 6.5)


def test_the_cuts_are_the_crossings_and_nothing_else():
    findings = []
    (road,) = site_streets.roads(_probe(), findings)
    # eight paths cross the road: six authored a->b and the two door-to-door
    # chains that happen to cross it
    assert len(road.crossings) == 8
    for k in road.kerbs:
        assert len(k.cuts) == 8, (k.side, len(k.cuts))
        assert all(c.kind == "path" for c in k.cuts)
        cut_spans = [s for s in k.spans if s[2]]
        assert 1 <= len(cut_spans) <= 8            # merged when they overlap
        assert sum(1 for s in k.spans if not s[2]) >= 1
    # the two shallow crossings are said, into findings, not printed
    assert sum("LOT_KERB_CROSSED_SHALLOW" in f for f in findings) == 4


def test_the_scene_draws_what_the_model_says():
    body, sub = lot._outdoor_nodes(_probe())
    txt = "\n".join(body)
    (road,) = site_streets.roads(_probe())
    n_cut_nodes = txt.count('name="kerbcut_0')
    n_walk_nodes = txt.count('name="sidewalk_0')
    assert n_cut_nodes == sum(1 for k in road.kerbs for s in k.spans if s[2] and s[1] - s[0] > 0.05)
    assert n_walk_nodes == sum(1 for k in road.kerbs for s in k.spans if not s[2] and s[1] - s[0] > 0.05)


def test_the_paint_is_where_the_model_puts_it():
    (road,) = site_streets.roads(_probe())
    marks = site_streets.markings([road])
    kinds = {}
    for m in marks:
        kinds.setdefault(m["kind"], []).append(m)
    assert len(kinds["edge_line"]) == 2
    assert {m["side"] for m in kinds["edge_line"]} == {"L", "R"}
    for m in kinds["edge_line"]:
        assert m["size"] == [220.0, site_streets.LINE_WIDTH]
        assert abs(abs(m["at"][1]) - (5.0 - site_streets.EDGE_INSET)) < 1e-6
    stations = sorted({m["station"] for m in kinds["crosswalk_bar"]})
    # eight crossings, one station each, at the CENTRE line -- not two per
    # diagonal path (one per kerb), which is what stationing at the kerb gave
    assert len(stations) == 8
    for s in stations:
        bars = [m for m in kinds["crosswalk_bar"] if m["station"] == s]
        assert len(bars) in (4, 5)                        # a 4 m or 5 m crossing
        assert all(m["size"][1] == 10 - 2 * site_streets.EDGE_INSET for m in bars)
    # the centre line is dashed and stays out of the crosswalks
    dashes = kinds["centre_line"]
    assert all(m["at"][1] == 0.0 and m["size"][1] == site_streets.LINE_WIDTH for m in dashes)
    widths = {round(c.t, 3): c.width for c in road.crossings}
    clear = site_streets.STOP_BAR_SETBACK + site_streets.STOP_BAR_DEPTH
    for d in dashes:
        t0, t1 = d["at"][0] + 110 - d["size"][0] / 2, d["at"][0] + 110 + d["size"][0] / 2
        for s in stations:
            b0, b1 = s - widths[s] / 2 - clear, s + widths[s] / 2 + clear
            assert t1 <= b0 + 1e-6 or t0 >= b1 - 1e-6, (d, s)
    # a stop bar per lane per station, one each side of the crossing
    bars = kinds["stop_bar"]
    assert len(bars) == 2 * len(stations)
    assert {round(m["at"][1], 2) for m in bars} == {2.35, -2.35}


def test_paint_has_no_collision_and_sits_on_the_road():
    body, sub = lot._outdoor_nodes(_probe())
    marks = [l for l in body if l.startswith('[node name="mark_')]
    assert marks and all('type="Node3D"' in l for l in marks)
    txt = "\n".join(body)
    assert 'parent="./mark_0_edge_line"]' in txt
    i = txt.index('name="mark_0_edge_line"')
    tf = txt[i:].split("\n")[1]
    assert f", {lot.MARKING_Y:g}, " in tf
    assert lot.MARKING_Y > lot.ROAD_THICK
    # no collision shape under any marking
    for l in body:
        if 'type="CollisionShape3D"' in l:
            assert "/mark_" not in l


def test_assemble_writes_the_markings_manifest(tmp_path):
    r = lot.assemble(os.path.join(SPECS, "coldrun_kerb_probe.json"), str(tmp_path))
    doc = json.loads((tmp_path / "coldrun_kerb_probe.markings.json").read_text(encoding="utf-8"))
    assert doc["schema"] == "site-markings/1"
    assert len(doc["roads"]) == 1 and doc["roads"][0]["kerbs"][0]["cuts"]
    assert {m["kind"] for m in doc["markings"]} == {"edge_line", "centre_line", "crosswalk_bar", "stop_bar"}


def test_a_spec_without_roads_paints_nothing():
    spec = json.load(open(os.path.join(SPECS, "example_compound.json")))
    assert site_streets.roads(spec) == []
    assert site_streets.markings([]) == []
    body, _ = lot._outdoor_nodes(spec)
    assert not any(l.startswith('[node name="mark_') for l in body)
