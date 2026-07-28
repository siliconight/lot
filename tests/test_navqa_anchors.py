"""Where the nav-QA anchors are emitted, in Godot space.

Offline and self-asserting, same style as test_lot.py. No Godot: the things
under test are a coordinate conversion and a height.

The height has now been wrong twice, in opposite directions, so both mistakes
have a test here. A marker is where a thing IS; an anchor is where a body has
to stand to use it. Deli Counter puts OBJECTIVE_CAGE on the cashier counter and
LOOT_VAULT_CASH inside the vault block -- neither is a standing position, and
neither is the marker height plus a metre.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot as L


def _room(rid, story, floor_z):
    return {"id": rid, "story": story, "center": [0.0, 0.0, floor_z],
            "bounds": [-100.0, -100.0, 100.0, 100.0]}


def _merged(markers=None, site_markers=None, rooms=None):
    return {"markers": list(markers or []),
            "site_markers": list(site_markers or []),
            "rooms": list(rooms or [])}


# --- the conversion ----------------------------------------------------------

def test_site_space_becomes_godot_space():
    """Site space is (x, y_plan, z_up); Godot is (x, y_up, -z_plan)."""
    assert L._pv3_array([(1.0, 2.0, 0.9)]) == "PackedVector3Array(1, 0.9, -2)"


def test_a_lift_raises_the_godot_y_and_nothing_else():
    assert L._pv3_array([(1.0, 2.0, 0.9)], 1.0) == "PackedVector3Array(1, 1.9, -2)"


# --- the height, which is the regression -------------------------------------

def test_an_anchor_is_emitted_on_its_rooms_floor_not_at_the_marker():
    """Defect 2 of 2: the marker height was trusted. OBJECTIVE_CAGE carries
    z 0.9 because it is ON the cashier counter, and the floor directly beneath
    it is inside a solid box -- so the nearest navmesh in any direction is the
    counter top, an island no body can climb to. Sixteen of twenty-one anchors
    in the first honest walktest were standing on furniture."""
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "objective", "x": 1.0, "y": 2.0, "z": 0.9,
                  "building": "b0", "room": "cashier_cage"}],
        rooms=[_room("b0/cashier_cage", 0, 0.0)]))
    assert anc["player_proxies"] == [(1.0, 2.0, 0.0)]
    assert L._pv3_array(anc["player_proxies"]) == "PackedVector3Array(1, 0, -2)"


def test_no_lift_is_added_on_top_of_the_floor():
    """Defect 1 of 2: a +1.0 m lift on markers that already carried body height
    put every building anchor ~1.9 m over its own floor."""
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "objective", "x": 1.0, "y": 2.0, "z": 0.9,
                  "building": "b0", "room": "cashier_cage"}],
        rooms=[_room("b0/cashier_cage", 0, 0.0)]))
    emitted = L._pv3_array(anc["player_proxies"])
    assert "1.9" not in emitted, emitted
    assert "0.9" not in emitted, emitted


def test_an_upper_storey_anchor_lands_on_the_upper_storey():
    """The floor comes from the room, so a storey height is never assumed."""
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "objective", "x": 0.0, "y": 0.0, "z": 4.9,
                  "building": "b0", "room": "upper_lounge"},
                 {"type": "loot", "x": 0.0, "y": 8.0, "z": -2.8,
                  "building": "b0", "room": "vault"}],
        rooms=[_room("b0/upper_lounge", 1, 4.0), _room("b0/vault", -1, -4.0)]))
    assert anc["player_proxies"] == [(0.0, 0.0, 4.0), (0.0, 8.0, -4.0)]


def test_a_marker_with_no_room_falls_back_to_the_storey_below_it():
    """An unroomed marker still belongs to a storey: the highest floor in its
    building at or below it. Guessing upward would put a basement anchor on the
    ground floor's slab, which is a ceiling from where it stands."""
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "objective", "x": 0.0, "y": 0.0, "z": -2.8,
                  "building": "b0"}],
        rooms=[_room("b0/vault", -1, -4.0), _room("b0/hall", 0, 0.0)]))
    assert anc["player_proxies"] == [(0.0, 0.0, -4.0)]
    assert anc["unresolved"] == []


def test_a_marker_with_no_rooms_at_all_is_reported_not_guessed():
    anc = L._navqa_anchors({}, _merged(
        markers=[{"name": "b0/OBJ", "type": "objective",
                  "x": 0.0, "y": 0.0, "z": 0.9, "building": "b0"}]))
    assert anc["player_proxies"] == [(0.0, 0.0, 0.9)]
    assert anc["unresolved"] == ["b0/OBJ"]


def test_stacked_markers_collapse_to_one_anchor():
    """Deli Counter puts the vault objective and the vault loot at one XY, 0.2 m
    apart in Z. Dropped to their shared floor they become the same point, and
    two anchors on one point are not two tests -- a stranded anchor once passed
    the reachability census by reaching its own twin."""
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "objective", "x": 4.0, "y": 5.0, "z": -3.0,
                  "building": "b0", "room": "vault"},
                 {"type": "loot", "x": 4.0, "y": 5.0, "z": -2.8,
                  "building": "b0", "room": "vault"}],
        rooms=[_room("b0/vault", -1, -4.0)]))
    assert anc["player_proxies"] == [(4.0, 5.0, -4.0)]
    assert anc["merged_pairs"] == 1


def test_distinct_anchors_are_not_merged():
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "objective", "x": 4.0, "y": 5.0, "z": -3.0,
                  "building": "b0", "room": "vault"},
                 {"type": "loot", "x": 9.0, "y": 5.0, "z": -2.8,
                  "building": "b0", "room": "vault"}],
        rooms=[_room("b0/vault", -1, -4.0)]))
    assert len(anc["player_proxies"]) == 2
    assert anc["merged_pairs"] == 0


def test_site_markers_join_the_proxies_at_ground_level():
    """Extraction and crew spawn come from site geography, not a building, and
    carry no elevation -- they are already at the floor."""
    anc = L._navqa_anchors({}, _merged(
        site_markers=[{"type": "extraction", "at": [5.0, 6.0]}]))
    assert anc["player_proxies"] == [(5.0, 6.0, 0.0)]
    assert L._pv3_array(anc["player_proxies"]) == "PackedVector3Array(5, 0, -6)"


def test_bot_spawns_are_separated_from_proxies():
    anc = L._navqa_anchors({}, _merged(
        markers=[{"type": "loot", "x": 0.0, "y": 0.0, "z": 0.9,
                  "building": "b0", "room": "hall"},
                 {"type": "responder_spawn", "x": 3.0, "y": 0.0, "z": 0.0,
                  "building": "b0", "room": "hall"}],
        rooms=[_room("b0/hall", 0, 0.0)]))
    assert len(anc["player_proxies"]) == 1
    assert anc["bot_spawns"] == [(3.0, 0.0, 0.0)]


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    for fn in ALL:
        fn()
        print(f"[ok] {fn.__name__}")
    print(f"\n{len(ALL)} navqa anchor tests passed.")
