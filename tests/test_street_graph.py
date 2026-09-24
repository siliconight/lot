"""The site graph includes the street, because the buildings do.

MEASURED BEFORE IT WAS WRITTEN, over every candidate site spec on disk
(`tools/level_recipe_census.py`):

    sites reporting an isolated building   65 of 79  ->  0 of 79
    objective_approaches 0                 38 specs  ->   2
    objective_approaches 2                  4 specs  ->  71

`build_graph` used building-to-building paths only and said so in its own
docstring. Level Factory emits a chain of those and deliberately DROPS any
segment crossing a road -- cold run 9049, where one cut across a cross street
and read as a fake crosswalk -- giving every building a door path to the
sidewalk instead. So the street carried the connection and the graph modelled
none of it: cold run 9077's shipped package, a run reported as a genuine zero,
had `{b0: [b1], b1: [b0], b2: []}` and printed "buildings with no declared
path-route from 'b0': b2".

WHAT THESE HOLD. That a door onto a road joins a building to the others on it;
that an unclear path end joins nothing; and that the change is only ever
PERMISSIVE, since `gate()` raises below two approaches and `isolated_buildings`
reports an absence.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import site_tactical as st


ROAD = {"a": [-80.0, -30.0], "b": [80.0, -30.0], "width": 10.0, "sidewalk": 3.0}
#: A door path ends ON the sidewalk, short of its centre line -- Level Factory
#: stops it there on purpose so Lot does not read it as a street crossing. The
#: band test has to reach it, which a centre-line test never would.
WALK_Y = -30.0 + 5.0 + 3.0 - 0.45


def _site(n=3, pitch=55.0, road=ROAD, spurs=True, paths=()):
    blds = [{"id": f"b{i}", "at": [(i - (n - 1) / 2.0) * pitch, 5.0], "rot": 0}
            for i in range(n)]
    p = [dict(x) for x in paths]
    if spurs:
        p += [{"a": [b["at"][0], -10.0], "b": [b["at"][0], WALK_Y],
               "width": 4.0} for b in blds]
    return {"buildings": blds, "roads": [road] if road else [], "paths": p,
            "spawn": "b0", "objective": "b1"}


def test_a_door_onto_a_road_joins_the_buildings_that_share_it():
    adj = st.build_graph(_site())
    assert adj["b0"] == {"b1", "b2"}
    assert adj["b2"] == {"b0", "b1"}, (
        "b2 has a door onto the same street as b0 and b1; before 0.77.0 it had "
        "no edges at all and Lot called it isolated")


def test_the_isolated_warning_stops_firing_on_a_site_that_is_not_isolated():
    rep = st.analyze(_site())
    assert rep["intel"]["isolated_buildings"] == []
    assert not [w for w in rep["warnings"] if "no declared path-route" in w]


def test_the_objective_gains_an_approach_from_each_direction():
    """Two, not three. Three buildings on one street afford two directions to
    come from, and the recipe's `min: 3` needs a fourth building or a second
    street the buildings front -- which is a Level Factory question, not this
    one."""
    rep = st.analyze(_site())
    assert rep["intel"]["objective_approaches"] == 2


def test_no_road_no_street_edges():
    """The old behaviour, still reachable. A spec with no roads gets exactly
    the graph it always got."""
    adj = st.build_graph(_site(road=None))
    assert all(v == set() for v in adj.values())


def test_a_path_that_reaches_no_road_joins_nothing():
    """A door path stopping short of the band is not a door onto that street.
    Without this the test above would pass for the wrong reason."""
    s = _site(spurs=False, paths=[{"a": [0.0, -10.0], "b": [0.0, -12.0],
                                   "width": 4.0}])
    assert all(v == set() for v in st.build_graph(s).values())


def test_declared_building_paths_still_join_buildings():
    """The original mechanism is untouched."""
    s = _site(road=None, spurs=False, paths=[{"from": "b0", "to": "b2",
                                              "width": 8.0}])
    adj = st.build_graph(s)
    assert adj["b0"] == {"b2"} and adj["b1"] == set()


def test_an_ambiguous_path_end_joins_nothing():
    """A path end equidistant between two buildings does not say which one's
    door it is. An edge nobody declared is worse than a missing one, so the
    match requires the nearest centre to be clearly nearest."""
    s = _site(n=2, pitch=40.0, spurs=False,
              paths=[{"a": [0.0, 5.0], "b": [0.0, WALK_Y], "width": 4.0}])
    assert st.street_members(s)[0] == set()


def test_street_members_names_the_road_each_building_fronts():
    s = _site()
    # a second road nothing has a door onto -- the cross street of a generated
    # site, which `_street_for` gives no addresses at all
    s["roads"].append({"a": [20.0, -30.0], "b": [20.0, 40.0],
                       "width": 10.0, "sidewalk": 3.0})
    members = st.street_members(s)
    assert members[0] == {"b0", "b1", "b2"}
    assert members[1] == set(), (
        "the cross street has no doors on it; if this ever fills, Level "
        "Factory has started addressing buildings to it")


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_the_change_is_only_ever_permissive(n):
    """`gate()` raises BELOW two approaches and `isolated_buildings` reports an
    absence, so adding edges can only move a site from failing to passing.
    Asserted rather than argued: the street graph is a superset of the path
    graph, edge for edge."""
    s = _site(n=n, paths=[{"from": "b0", "to": "b1", "width": 8.0}])
    without = {k: set(v) for k, v in st.build_graph(
        dict(s, roads=[])).items()}
    with_street = st.build_graph(s)
    for bid, nbrs in without.items():
        assert nbrs <= with_street[bid], (
            "%s lost edge(s) %s when the street was added"
            % (bid, nbrs - with_street[bid]))
