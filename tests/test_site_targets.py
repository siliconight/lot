"""The guide's gameplay targets as audit findings (Lot 0.112.0, roadmap 230): the measures from
the drawn spec, the road graph's approaches and loops, the focal points along the critical
route, and the `S_TARGETS` lines, every one INFO."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_targets as ST  # noqa: E402
import site_audit  # noqa: E402

GROUND = {"size_x": 180.0, "size_y": 100.0}
MAIN = {"a": [-90.0, -23.0], "b": [90.0, -23.0], "width": 10.0}      # reaches both edges
SIDE = {"a": [30.0, -23.0], "b": [30.0, 50.0], "width": 8.0}          # a T off it, to the north edge


def _b(bid, archetype, x, y):
    return {"id": bid, "archetype": archetype, "at": [x, y], "_footprint": [30.0, 24.0], "rot": 0}


def _site(**kw):
    s = {"name": "t", "mode": "heist",
         "buildings": [_b("b0", "deli", -58.0, 1.0), _b("b1", "office", -10.0, 1.0),
                       _b("b2", "rail_station", 40.0, 1.0)],
         "blockers": [{"id": "e%d" % i, "archetype": "gs_empty_rowhome_a", "at": [-80.0 + 7.0 * i, -40.0],
                       "empty": True} for i in range(6)],
         "roads": [MAIN, SIDE], "ground": GROUND, "objective": "b0", "spawn": "b2", "extraction": "b2",
         "fields": [{"name": "field_0", "bays": 3}], "driveways": [{}], "yards": [{}, {}, {}],
         "paths": [], "site_markers": [], "cover": []}
    s.update(kw)
    return s


def test_the_measures_read_the_spec():
    m = ST.measures(_site())
    assert m["enterable"] == 3 and m["empties"] == 6 and m["total"] == 9
    assert abs(m["ordinary_share"] - 8.0 / 9.0) < 1e-9        # six Empties and two supporting buildings of nine
    assert m["plate_approaches"] == 3                          # the main road's two ends and the side road's north end
    assert m["junctions"] == 1 and m["loops"] == 0
    assert m["fields"] == 1 and m["bays"] == 3 and m["driveways"] == 1 and m["yards"] == 3


def test_a_loop_in_the_road_graph_is_counted():
    ring = [{"a": [-50.0, -20.0], "b": [50.0, -20.0], "width": 10.0},
            {"a": [-50.0, 20.0], "b": [50.0, 20.0], "width": 10.0},
            {"a": [-50.0, -20.0], "b": [-50.0, 20.0], "width": 10.0},
            {"a": [50.0, -20.0], "b": [50.0, 20.0], "width": 10.0}]
    m = ST.measures(_site(roads=ring))
    assert m["junctions"] == 4 and m["loops"] == 1


def test_focal_points_along_the_critical_route():
    # b2 (40, 1) -> b0 (-58, 1) is 98 m with b1 (-10, 1) on the line; the junction at (30, -23)
    # is 24 m off it, out of reach; the way back is the same leg the other way
    legs = {name: (length, gap) for name, length, gap in ST.measures(_site())["focal"]}
    assert set(legs) == {"spawn->objective", "objective->extraction"}
    for length, gap in legs.values():
        assert abs(length - 98.0) < 1e-6 and abs(gap - 50.0) < 1e-6   # 40 -> -10 is 50, -10 -> -58 is 48


def test_the_findings_say_the_measure_and_the_range():
    found = ST.findings(_site())
    assert found and all(f[0] == "INFO" and f[1] == "S_TARGETS" for f in found)
    text = " | ".join(f[2] for f in found)
    assert "3 enterable building(s), inside the guide's starting 3 to 8" in text
    assert "ordinary fabric 89% of 9 building instances" in text and "above the guide's 50% to 75%" in text
    assert "3 road end(s) reach the plate's edge" in text
    assert "0 loop(s) in the road graph over 1 junction(s): the way back is the way in" in text
    assert "1 parking field(s) with 3 bay(s), 1 driveway(s) and 3 yard(s) with a dumpster for 3 building(s)" in text


def test_a_long_empty_leg_asks_for_a_focal_point():
    s = _site(buildings=[_b("b0", "deli", -80.0, 1.0), _b("b2", "rail_station", 80.0, 1.0)], roads=[MAIN])
    leg = [f[2] for f in ST.findings(s) if f[2].startswith("spawn->objective")][0]
    assert "160 m as the crow flies" in leg and "longest stretch between focal points 160 m" in leg
    assert "wants a corner, a threshold or a landmark view" in leg


def test_the_site_audit_carries_the_targets():
    res = site_audit.audit(_site())
    assert [f[1] for f in res["findings"]].count("S_TARGETS") >= 5
