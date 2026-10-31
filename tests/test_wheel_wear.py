"""Tyres wear the paint where they cross it (Lot 0.139.0).

A crosswalk's bars and a stop bar go in two bands a lane, where the wheels run; the vertical slice's were whole.
`site_streets.wheel_offsets` puts two wheel paths in each driving lane, `wheel_gaps` wears a seeded share of the
bars through where they cross, and Lot's mesh writer lays a quad a painted piece. FAILS ON 0.138.0: no wheel paths.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_streets as ss  # noqa: E402


def _spec():
    return {"name": "probe", "ground": {"size_x": 140.0, "size_y": 100.0}, "buildings": [],
            "roads": [{"a": [-60.0, 0.0], "b": [60.0, 0.0], "width": 10.0, "sidewalk": 3.0},
                      {"a": [0.0, 0.0], "b": [0.0, 45.0], "width": 10.0, "sidewalk": 3.0}]}


def test_two_wheel_paths_a_driving_lane():
    road = ss.roads(_spec())[0]
    # a 10 m road with parking: 2.8 m of driving lane each side, one lane, its centre 1.4 m out
    assert ss.has_parking(road) and ss.approach_lanes(road) == 1
    want = sorted(c + d for c in (1.4, -1.4) for d in (-ss.TRACK_M / 2.0, ss.TRACK_M / 2.0))
    assert [round(w, 4) for w in ss.wheel_offsets(road)] == [round(w, 4) for w in want]


def test_bars_worn_through_on_the_wheel_paths_and_lines_never():
    road_list = ss.roads(_spec())
    marks = ss.markings(road_list)
    worn = [m for m in marks if m.get("gaps")]
    assert worn and {m["kind"] for m in worn} <= {"crosswalk_bar", "stop_bar"}
    assert {m["kind"] for m in worn} == {"crosswalk_bar", "stop_bar"}
    by_road = {r.index: r for r in road_list}
    # some crossings stay painted: a bar carries fewer gaps than the wheel paths that cross it (four on a bar across
    # the road, at WHEEL_WORN 0.7 a bar keeps all four painted 0.3^4 of the time, so a bar is seldom whole)
    crossable = sum(len(ss.wheel_offsets(by_road[m["road"]])) for m in worn if m["kind"] == "crosswalk_bar")
    assert sum(len(m["gaps"]) for m in worn if m["kind"] == "crosswalk_bar") < crossable
    for m in worn:
        road = by_road[m["road"]]
        across = m["size"][1]
        # the bar's centre across its road, from its plan point (left +)
        dx, dy = m["at"][0] - road.a[0], m["at"][1] - road.a[1]
        centre = dx * road.perp[0] + dy * road.perp[1]
        for a0, a1 in m["gaps"]:
            assert -across / 2.0 < a0 < a1 < across / 2.0
            assert ss.WHEEL_PATH_M[0] - 1e-3 <= a1 - a0 <= ss.WHEEL_PATH_M[1] + 1e-3
            mid = centre + (a0 + a1) / 2.0
            assert min(abs(mid - w) for w in ss.wheel_offsets(road)) < 1e-3
    assert ss.markings(ss.roads(_spec())) == marks      # seeded: a rebuild wears the same street


def test_a_worn_bar_is_painted_as_its_pieces():
    marks = ss.markings(ss.roads(_spec()))
    m = next(m for m in marks if m["kind"] == "crosswalk_bar" and m.get("gaps"))
    quads = lot._marking_quads(m)
    assert len(quads) == len(m["gaps"]) + 1
    along, across = m["size"]

    def area(q):
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
        return abs((x0 * y1 - x1 * y0) + (x1 * y2 - x2 * y1) + (x2 * y3 - x3 * y2) + (x3 * y0 - x0 * y3)) / 2.0

    worn = sum(a1 - a0 for a0, a1 in m["gaps"])
    assert abs(sum(area(q) for q in quads) - along * (across - worn)) < 1e-6
    whole = next(m for m in marks if not m.get("gaps"))
    assert lot._marking_quads(whole) == [lot._marking_quad(whole)]
