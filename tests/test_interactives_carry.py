"""Interactives reach the site: roadmap item 46, step 1.

Deli Counter emits one replicable state machine per interactive fixture
(docs/INTERACTIVES.md); until now `merge_gameplay` carried markers, rooms,
objectives, loot, zones, vertical_links, openings and surfaces -- and dropped
`interactives`, so the shipped site never contained the netcode's input.

The carry follows the marker precedent: transforms offset to world space
(Z-up yaw, then translate), the building tag added -- but ids stay VERBATIM.
They are the network handle every client, snapshot and saved game
references, already globally unique ("<building>:if:<hash>"); namespacing
them would break the correlation with slots.json and the composed scene's
metadata/interactive_id. Concatenation, not a merge.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot


def _site(d):
    # building a at origin, unrotated; building w at (45, 10) rotated 90.
    json.dump({"building_id": "a", "interactives": [
        {"id": "a:if:11111111", "kind": "door", "slot_ref": "ext_0_S_open0",
         "transform": {"translation": [6.0, -4.0, 1.1], "rot_y": 180},
         "states": ["closed", "open"], "default": "closed",
         "transitions": [{"event": "toggle", "from": "closed", "to": "open"},
                         {"event": "toggle", "from": "open", "to": "closed"}]},
        {"id": "a:if:22222222", "kind": "breach_wall", "slot_ref": "ext_0_N_open1",
         "states": ["intact", "breached"], "default": "intact",
         "transitions": [
             {"event": "breach", "from": "intact", "to": "breached"}]},
    ]}, open(os.path.join(d, "a.gameplay.json"), "w"))
    json.dump({"building_id": "w", "interactives": [
        {"id": "w:if:33333333", "kind": "window", "slot_ref": "ext_0_S_open1",
         "transform": {"translation": [6.0, -4.0, 1.1], "rot_y": 180},
         "states": ["intact", "broken"], "default": "intact",
         "transitions": [{"event": "break", "from": "intact", "to": "broken"}]},
    ]}, open(os.path.join(d, "w.gameplay.json"), "w"))
    json.dump({"building_id": "n"},  # no interactives key at all
              open(os.path.join(d, "n.gameplay.json"), "w"))
    return {"name": "t", "buildings": [
        {"id": "a", "glb": "a.glb", "gameplay": "a.gameplay.json", "at": [0, 0]},
        {"id": "w", "glb": "w.glb", "gameplay": "w.gameplay.json",
         "at": [45, 10], "rot": 90},
        {"id": "n", "glb": "n.glb", "gameplay": "n.gameplay.json", "at": [90, 0]},
    ]}


def test_interactives_carried_ids_verbatim():
    d = tempfile.mkdtemp()
    merged = lot.merge_gameplay(_site(d), d)
    ids = [i["id"] for i in merged["interactives"]]
    # verbatim -- the network handle is never rewritten
    assert ids == ["a:if:11111111", "a:if:22222222", "w:if:33333333"], ids
    assert all("/" not in i for i in ids), "ids must not be namespaced"
    by_id = {i["id"]: i for i in merged["interactives"]}
    assert by_id["a:if:11111111"]["building"] == "a"
    assert by_id["w:if:33333333"]["building"] == "w"
    # slot_ref stays building-local; the building tag says whose slots.json
    assert by_id["w:if:33333333"]["slot_ref"] == "ext_0_S_open1"
    print("  interactives: ids verbatim, building-tagged: OK")


def test_interactive_transform_offsets_like_a_marker():
    d = tempfile.mkdtemp()
    merged = lot.merge_gameplay(_site(d), d)
    by_id = {i["id"]: i for i in merged["interactives"]}
    # unrotated building at origin: transform unchanged
    a_tf = by_id["a:if:11111111"]["transform"]
    assert a_tf["translation"] == [6.0, -4.0, 1.1], a_tf
    assert a_tf["rot_y"] == 180
    # w at (45,10) rot 90: local (6,-4) -> rotate90 -> (4,6) -> world (49,16);
    # height untouched; rot_y accumulates the placement yaw
    w_tf = by_id["w:if:33333333"]["transform"]
    wx, wy, wz = w_tf["translation"]
    assert abs(wx - 49.0) < 1e-6 and abs(wy - 16.0) < 1e-6, w_tf
    assert abs(wz - 1.1) < 1e-6
    assert w_tf["rot_y"] == 270, w_tf
    print("  interactive transforms: world-offset like markers: OK")


def test_no_transform_and_no_key_both_stay_clean():
    d = tempfile.mkdtemp()
    merged = lot.merge_gameplay(_site(d), d)
    by_id = {i["id"]: i for i in merged["interactives"]}
    # an entry without a transform carries through untouched
    assert "transform" not in by_id["a:if:22222222"]
    # the state machine itself is untouched -- states, default, transitions
    br = by_id["a:if:22222222"]
    assert br["states"] == ["intact", "breached"] and br["default"] == "intact"
    assert br["transitions"][0]["event"] == "breach"
    # and the key exists site-level even when every building lacked it
    d2 = tempfile.mkdtemp()
    json.dump({"building_id": "n"}, open(os.path.join(d2, "n.gameplay.json"), "w"))
    merged2 = lot.merge_gameplay(
        {"name": "t2", "buildings": [
            {"id": "n", "glb": "n.glb", "gameplay": "n.gameplay.json",
             "at": [0, 0]}]}, d2)
    assert merged2["interactives"] == []
    print("  interactives: absent key -> empty list, entries untouched: OK")


if __name__ == "__main__":
    test_interactives_carried_ids_verbatim()
    test_interactive_transform_offsets_like_a_marker()
    test_no_transform_and_no_key_both_stay_clean()
    print("ALL OK")
