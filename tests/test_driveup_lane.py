"""The drive-up lane as the research drew it (0.135.0): a clearance bar at the served lane's entry, bollards guarding
the station, the island painted, an arrow on each lane the way it runs. FAILS ON 0.134.0, which has none of them.
"""
import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import site_driveup as D  # noqa: E402
import site_parking       # noqa: E402
import site_streets       # noqa: E402

SPECS = os.path.join(HERE, "specs")
BANK = (60.0, 12.0, 80.0, 30.0)


def _roads():
    return site_streets.roads(json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json"))))


def _plan():
    roads = _roads()
    (r,), _p = D.plan_driveups([("bank", (70.0, 12.0), "bank_branch_a02")], roads, [], {"bank": BANK},
                               ground=(0.0, -20.0, 160.0, 80.0), variants={"bank": 11})
    return r, roads[r["road"]]


def test_the_clearance_bar_spans_the_served_lane_at_its_entry_facing_the_car():
    r, road = _plan()
    bar, *bollards = D.lane_pieces(r, road)
    assert bar["species"] == "clearance_bar" and bar["dims"] == [D.CLEARANCE_W, D.CLEARANCE_D, D.CLEARANCE_H]
    assert D.CLEARANCE_W >= 3.91          # Zoo's least width
    # its module across the served lane's centre, CLEARANCE_IN into the block from the entry end
    mx, my = bar["module_at"]
    assert mx == pytest.approx(_lane_x(r, road, "served"), abs=1e-3)
    entry_y = 8.0 if r["served_travel"] == "away" else 30.0
    assert my == pytest.approx(entry_y + (1 if r["served_travel"] == "away" else -1) * D.CLEARANCE_IN)
    # its plate (local -Y) faces the car coming in: back toward the entry
    face = site_parking.nose(bar["yaw"])
    assert face[1] == pytest.approx(-1.0 if r["served_travel"] == "away" else 1.0, abs=1e-9)
    # its record is a post, not a box across the lane
    assert bar["size"] == [D.CLEARANCE_POST, D.CLEARANCE_H, D.CLEARANCE_D]


def test_two_bollards_guard_the_station_on_the_island_line():
    r, road = _plan()
    _bar, *bollards = D.lane_pieces(r, road)
    assert [b["species"] for b in bollards] == ["bollard", "bollard"]
    _r2, pieces = D.plan_driveups([("bank", (70.0, 12.0), "bank_branch_a02")], _roads(), [], {"bank": BANK},
                                  ground=(0.0, -20.0, 160.0, 80.0), variants={"bank": 11})
    station = pieces[1]
    for b in bollards:
        assert b["at"][0] == pytest.approx(station["at"][0])
        assert abs(b["at"][1] - station["at"][1]) == pytest.approx(D.BOLLARD_OFF)


def test_the_paint_is_a_yellow_island_and_an_arrow_each_lane_the_way_it_runs():
    r, road = _plan()
    marks = D.markings([r], [road])
    island = [m for m in marks if m["kind"] == "driveup_island"]
    arrows = [m for m in marks if m["kind"] == "driveup_arrow"]
    assert len(island) == 1 and island[0]["color"] == list(D.YELLOW)
    assert len(arrows) == 6                    # two arrows, three strokes each
    served_dir = 1 if r["served_travel"] == "away" else -1   # +y is away from the probe's road
    # each lane's shaft points its way: its tip beyond its centre in that direction
    for lane, direction in (("served", served_dir), ("passing", -served_dir)):
        shafts = [m for m in arrows if m["size"][0] == D.ARROW_SHAFT]
        shaft = min(shafts, key=lambda m: abs(m["at"][0] - _lane_x(r, road, lane)))
        assert math.sin(math.radians(shaft["yaw"])) == pytest.approx(direction, abs=1e-9)


def _lane_x(r, road, lane):
    return road.point(r["lanes"][lane], 0.0)[0]


def test_the_manifest_carries_the_lanes_paint():
    r, road = _plan()
    spec = json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))
    spec["driveups"] = [r]
    kinds = {m["kind"] for m in site_streets.manifest(spec)["markings"]}
    assert {"driveup_island", "driveup_arrow"} <= kinds
