"""The walk test decides ladder or drop access from the anchor, not from where
Godot's path to an unreachable anchor happens to stop (Lot 0.97.2).

Cold run 9185 (roadmap 189 at the factory root): the same anchor in the same
navmesh -- deli_a03's objective, upstairs -- passed as "VERTICAL access" from
one start and failed as "disjoint islands" from another. The verdict read the
end of the path Godot returned for an unreachable target, and that fallback
failed inside the engine ("It's not expect to not find the most reachable
polygons") on exactly the failing calls, returning a path that stopped beside
the start.

The director is engine-bound GDScript with no test harness of its own, so it
is read as source, as Zoo's Blender-bound code is. The behaviour was proven by
running the walk test on cold run 9185's staged candidate (CHANGELOG 0.97.2).
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(os.path.dirname(HERE), "godot", "addons", "heist_nav_qa",
                  "nav_qa_director.gd")


def _src():
    with open(GD, encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def _func(src, name):
    start = src.index("\nfunc %s(" % name)
    end = src.find("\nfunc ", start + 1)
    return src[start:end if end > 0 else len(src)]


def test_vertical_access_is_its_own_question():
    body = _func(_src(), "_vertical_access")
    # asked of the anchor: its column, height by height, within the reach ...
    assert "map_get_closest_point(" in body
    assert "while dy <= VERTICAL_REACH_M" in body
    # ... inside the old concession's window, so a drop off a ledge beside the
    # anchor still counts (9185 seed_9003, proxy_2->proxy_3) ...
    assert "SNAP_MAX * 1.5" in body and "<= 1.0" in body
    # ... and reached by a STRICT route, which never takes the concession
    assert re.search(r"_reaches\(map, from_pt, c, true\)", body)


def test_neither_verdict_reads_the_end_of_a_failed_path():
    src = _src()
    for name in ("_prove_path", "_reaches"):
        body = _func(src, name)
        assert "_vertical_access(" in body, name
        # the old concession: a horizontal gap measured from the path's end
        assert "SNAP_MAX * 1.5" not in body, name


def test_the_reach_is_derived_and_says_from_what():
    src = _src()
    m = re.search(r"const VERTICAL_REACH_M := ([^\n]+)", src)
    assert m, "no VERTICAL_REACH_M"
    assert "STOREY_BAND" in m.group(1)
    head = src[:m.start()].rsplit("\n\n", 1)[-1]
    assert "longest ladder" in head and "8.0 m" in head
