"""A lane stops at a street (Lot 0.113.0): a road without a sidewalk is a service lane or an
alley, its junction with a street is stop-controlled and never signalised; a side street ending
on an arterial still gets its signal."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_streets  # noqa: E402

STREET = {"a": [-90.0, -23.0], "b": [90.0, -23.0], "width": 10.0, "sidewalk": 3.0}


def _legs(roads):
    spec = {"buildings": [], "roads": roads, "ground": {"size_x": 200.0, "size_y": 120.0}}
    return site_streets.approaches(site_streets.roads(spec))


def test_a_lane_ending_on_an_arterial_stops_and_the_street_runs_through():
    lane = {"a": [0.0, -23.0], "b": [0.0, 30.0], "width": 5.0, "sidewalk": 0.0, "kind": "service_lane"}
    legs = _legs([STREET, lane])
    mine = [a for a in legs if a.road == 1]
    theirs = [a for a in legs if a.road == 0]
    assert mine and all(a.control == "stop" and a.minor for a in mine), mine
    assert theirs and all(a.control == "through" and not a.minor for a in theirs), theirs


def test_a_side_street_ending_on_an_arterial_still_gets_its_signal():
    side = {"a": [0.0, -23.0], "b": [0.0, 30.0], "width": 10.0, "sidewalk": 3.0}
    legs = _legs([STREET, side])
    assert legs and all(a.control == "signal" for a in legs), legs
