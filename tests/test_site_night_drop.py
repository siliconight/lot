"""A bank's night depository beside its door (`site_night_drop`, Zoo 1.138.0's `night_drop`): on the facade its sign is
over, clear of the openings, facing out, hung. FAILS ON 0.131.0, which hangs none.
"""
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import site_night_drop as N   # noqa: E402
import site_posters as SP     # noqa: E402

RECT = (60.0, 12.0, 80.0, 30.0)       # a bank 20 x 18, its south face on y 12
BDEF = {"id": "bank", "at": [70.0, 21.0], "rot": 0}


def _merged(openings):
    # storey-0 exterior openings on the south wall, in the building's frame (its centre at (70, 21))
    return {"openings": [{"building": "bank", "wall": "ext_0_S", "story": 0, "x": x - 70.0, "y": -9.0, "width": w,
                          "kind": k} for x, w, k in openings]}


def _plan(openings, rect=RECT):
    findings = []
    got = N.plan({"buildings": [BDEF]}, _merged(openings), [("bank", (70.0, 11.6), "bank_branch_a02")],
                 {"bank": rect}, findings)
    return got, findings


def test_it_hangs_beside_the_door_clear_of_it_facing_the_street():
    (r,), _f = _plan([(70.0, 1.8, "door")])
    assert r["species"] == "night_drop" and r["z"] == N.CENTRE_Z and tuple(r["dims"]) == N.DIMS
    # beside the door, OPENING_KEEP clear of it
    u = r["at"][0]
    assert abs(u - 70.0) == pytest.approx(0.9 + SP.OPENING_KEEP + N.DIMS[0] / 2.0)
    # off the south face by half its depth and the air, facing south (-y)
    assert r["at"][1] == pytest.approx(12.0 - N.DIMS[1] / 2.0 - SP.AIR)
    y = math.radians(r["yaw"])
    assert (math.sin(y), -math.cos(y)) == pytest.approx((0.0, -1.0), abs=1e-9)


def test_a_window_beside_the_door_moves_it_to_the_other_side_or_the_nearest_span():
    # windows tight on the door's +x side: it goes to the -x side
    (r,), _f = _plan([(70.0, 1.8, "door"), (72.4, 2.0, "window")])
    assert r["at"][0] < 70.0
    # windows tight on both: the nearest free span, its end nearest the door
    (r,), _f = _plan([(70.0, 1.8, "door"), (72.4, 2.0, "window"), (67.6, 2.0, "window")])
    lo_hole = 67.6 - 1.0 - SP.OPENING_KEEP
    hi_hole = 72.4 + 1.0 + SP.OPENING_KEEP
    u = r["at"][0]
    assert u - N.DIMS[0] / 2.0 >= hi_hole - 1e-9 or u + N.DIMS[0] / 2.0 <= lo_hole + 1e-9
    assert min(abs(u - N.DIMS[0] / 2.0 - hi_hole), abs(u + N.DIMS[0] / 2.0 - lo_hole)) < 1e-6


def test_a_facade_with_no_room_or_no_door_hangs_none_and_says_so():
    # a 4 m facade, a 2.6 m door: no 0.6 m clear of it and the corners
    got, findings = _plan([(70.0, 2.6, "door")], rect=(68.0, 12.0, 72.0, 30.0))
    assert got == [] and any("LOT_NIGHT_DROP_NO_ROOM" in f for f in findings), findings
    got, findings = _plan([])
    assert got == [] and any("LOT_NIGHT_DROP_NO_DOOR" in f for f in findings), findings
