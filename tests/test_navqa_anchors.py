"""Where the nav-QA anchors are emitted, in Godot space.

Offline and self-asserting, same style as test_lot.py. No Godot: the two things
under test are a coordinate conversion and a height.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot as L


def _merged(markers=None, site_markers=None):
    return {"markers": list(markers or []),
            "site_markers": list(site_markers or [])}


# --- the conversion ----------------------------------------------------------

def test_site_space_becomes_godot_space():
    """Site space is (x, y_plan, z_up); Godot is (x, y_up, -z_plan)."""
    assert L._pv3_array([(1.0, 2.0, 0.9)]) == "PackedVector3Array(1, 0.9, -2)"


def test_a_lift_raises_the_godot_y_and_nothing_else():
    assert L._pv3_array([(1.0, 2.0, 0.9)], 1.0) == "PackedVector3Array(1, 1.9, -2)"


# --- the height, which is the regression -------------------------------------

def test_proxies_are_emitted_at_the_height_the_marker_carries():
    """The defect: proxies were emitted with a +1.0 m lift on top of a marker
    that ALREADY sits at body height. A ground-floor marker carries z 0.9 over
    a floor at 0.0, so the anchor floated 1.9 m up, and the QA snapped it to
    the nearest navmesh in ANY direction -- a counter top at 1.4 m, not the
    floor at 0.2. Every route query started on a scrap of furniture.
    """
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "objective", "x": 1.0, "y": 2.0, "z": 0.9}]))
    assert anc["player_proxies"] == [(1.0, 2.0, 0.9)]
    emitted = L._pv3_array(anc["player_proxies"])
    assert emitted == "PackedVector3Array(1, 0.9, -2)", emitted
    # and explicitly NOT the old 1.9
    assert "1.9" not in emitted


def test_site_markers_join_the_proxies_at_ground_level():
    """Extraction and crew spawn come from site geography, not a building, and
    carry no elevation -- they are already at the floor."""
    anc = L._navqa_anchors({}, _merged(
        site_markers=[{"type": "extraction", "at": [5.0, 6.0]}]))
    assert anc["player_proxies"] == [(5.0, 6.0, 0.0)]
    assert L._pv3_array(anc["player_proxies"]) == "PackedVector3Array(5, 0, -6)"


def test_bot_spawns_are_separated_from_proxies():
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "loot", "x": 0.0, "y": 0.0, "z": 0.9},
                 {"type": "responder_spawn", "x": 3.0, "y": 0.0, "z": 0.0}]))
    assert len(anc["player_proxies"]) == 1
    assert anc["bot_spawns"] == [(3.0, 0.0, 0.0)]


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    for fn in ALL:
        fn()
        print(f"[ok] {fn.__name__}")
    print(f"\n{len(ALL)} navqa anchor tests passed.")
