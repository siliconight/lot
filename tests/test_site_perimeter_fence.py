"""The fence at the plate's edge (Lot 0.107.0, roadmap 228 step B).

The walker picked E from the edge menu: a chain-link fence at the plate's edge with the backdrop
behind it. `site_fences.plan_perimeter` lays one run a side, `PERIM_INSET` inside the wall, split
where a side is longer than Zoo's widest module, and never on a mission marker; the wall behind it
keeps its collision and shows nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_fences as SF  # noqa: E402


def _runs(ground, **kw):
    findings = []
    got = SF.plan_perimeter(ground, findings=findings, **kw)
    return got, findings


def test_a_small_plate_gets_one_run_a_side_inside_the_wall():
    got, findings = _runs((-30.0, -20.0, 30.0, 20.0))
    assert findings == []
    assert [p["name"] for p in got] == ["Perim_S_0", "Perim_N_0", "Perim_W_0", "Perim_E_0"]
    assert {p["species"] for p in got} == {"chain_link_fence"}
    s, n, w, e = got
    # the long sides run the plate's length less the inset at each end, centred
    assert s["dims"] == [60.0 - 2 * SF.PERIM_INSET, SF.DEPTH, SF.HEIGHT] and s["yaw"] == 0.0
    assert s["at"] == [0.0, -20.0 + SF.PERIM_INSET] and n["at"] == [0.0, 20.0 - SF.PERIM_INSET]
    # the short sides butt the long runs without overlapping them
    assert w["yaw"] == 90.0 and e["yaw"] == 90.0
    assert abs(w["dims"][0] - (40.0 - 2 * SF.PERIM_INSET - 2 * SF.DEPTH)) < SF.QUANTUM + 1e-9
    assert w["at"] == [-30.0 + SF.PERIM_INSET, 0.0] and e["at"] == [30.0 - SF.PERIM_INSET, 0.0]
    for p in got:
        assert p["base"] == "plate" and p["source"] == "site_fences.perimeter"
        assert p["size"][1] == SF.HEIGHT


def test_a_side_longer_than_zoos_widest_module_is_split_into_equal_runs():
    # cold run 9223's plate, 196 x 100 m
    got, findings = _runs((-98.0, -50.0, 98.0, 50.0))
    assert findings == []
    by_side = {}
    for p in got:
        by_side.setdefault(p["name"].split("_")[1], []).append(p)
    assert len(by_side["N"]) == 2 and len(by_side["S"]) == 2
    assert len(by_side["E"]) == 1 and len(by_side["W"]) == 1
    for p in got:
        assert p["dims"][0] <= SF.MAX_RUN
    n0, n1 = sorted(by_side["N"], key=lambda p: p["at"][0])
    assert abs(n0["dims"][0] - n1["dims"][0]) < SF.QUANTUM + 1e-9
    # the two halves meet: the first ends where the second begins
    assert abs((n0["at"][0] + n0["dims"][0] / 2) - (n1["at"][0] - n1["dims"][0] / 2)) < SF.QUANTUM + 1e-9
    assert abs(sum(p["dims"][0] for p in by_side["N"]) - (196.0 - 2 * SF.PERIM_INSET)) < 2 * SF.QUANTUM + 1e-9


def test_a_marker_at_the_edge_leaves_that_run_out_and_says_so():
    got, findings = _runs((-30.0, -20.0, 30.0, 20.0), markers=[(10.0, -19.8)])
    assert [p["name"] for p in got] == ["Perim_N_0", "Perim_W_0", "Perim_E_0"]
    assert len(findings) == 1 and findings[0].startswith("LOT_FENCE_SKIPPED: Perim_S_0")


def test_no_ground_is_no_fence():
    assert SF.plan_perimeter(None) == []


def test_a_box_node_without_its_visual_keeps_the_shape_and_draws_nothing():
    body, sub = lot._box_node("perim_N", (60.0, 3.0, 0.3), (0.0, 1.5, -20.0), lot.PERIM_COLOR,
                              visual=False)
    text = "\n".join(body + sub)
    assert "MeshInstance3D" not in text and "BoxMesh" not in text and "StandardMaterial3D" not in text
    assert 'type="StaticBody3D"' in text and 'type="CollisionShape3D"' in text
    assert "size = Vector3(60, 3, 0.3)" in text
    seen, _ = lot._box_node("perim_N", (60.0, 3.0, 0.3), (0.0, 1.5, -20.0), lot.PERIM_COLOR)
    assert "MeshInstance3D" in "\n".join(seen)


def test_the_wall_shows_nothing_only_when_runs_stand():
    spec = {"name": "t", "perimeter": {"height": 3}}
    assert lot._wall_seen(spec) is True
    spec["perimeter"]["fenced_runs"] = 4
    assert lot._wall_seen(spec) is False
    spec["perimeter"]["fenced_runs"] = 0
    assert lot._wall_seen(spec) is True
