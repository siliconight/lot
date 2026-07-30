"""Every place the site asks a body to step up.

The number under test is one nobody had written down. A capsule meets a low step
on its bottom hemisphere, so the contact normal is sloped rather than
horizontal, and the engine calls the contact a floor only while that angle stays
inside floor_max_angle. `max_step_up_m: 0.5` in the agent contract is what a
controller can LIFT itself over; what a body WALKS over is
R * (1 - cos(floor_max_angle)), which is 0.117 m for the 0.4 m player capsule.

Lot's kerb is 0.16.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import site_steps as S


def _scene(tmp_path, boxes):
    """A minimal .tscn holding axis-aligned StaticBody3D boxes."""
    sub, body = [], []
    for i, (name, cx, cy, cz, sx, sy, sz) in enumerate(boxes):
        sid = f"S{i}"
        sub.append(f'[sub_resource type="BoxShape3D" id="{sid}"]\n'
                   f'size = Vector3({sx}, {sy}, {sz})\n')
        body.append(
            f'[node name="{name}" type="StaticBody3D" parent="."]\n'
            f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {cx}, {cy}, {cz})\n\n'
            f'[node name="col" type="CollisionShape3D" parent="./{name}"]\n'
            f'shape = SubResource("{sid}")\n')
    p = tmp_path / "site.tscn"
    p.write_text("[gd_scene format=3]\n\n" + "\n".join(sub) + "\n"
                 + "\n".join(body), encoding="utf-8")
    return str(p)


#: Lot's own outdoor surface heights, from lot.py's module constants.
GROUND = ("Ground", 0.0, -0.25, 0.0, 40.0, 0.5, 40.0)          # top 0.00
ROAD = ("road_0", 0.0, 0.04, 10.0, 40.0, 0.08, 9.0)            # top 0.08
PATH = ("path_0", 0.0, 0.05, -10.0, 40.0, 0.10, 6.0)           # top 0.10
COURT = ("courtyard_0", 15.0, 0.06, 0.0, 8.0, 0.12, 8.0)       # top 0.12
KERB = ("sidewalk_0L", 0.0, 0.08, 16.0, 40.0, 0.16, 2.0)       # top 0.16

R = 0.4
ANGLE = 45.0
ASSIST = 0.5


# --- the derivation itself ---------------------------------------------------

def test_the_unassisted_limit_is_the_capsule_geometry():
    """Not a tuned constant: it falls out of where a hemisphere touches a step."""
    assert abs(S.unassisted_step_max_m(0.4, 45.0) - 0.1172) < 0.001
    assert abs(S.unassisted_step_max_m(0.35, 45.0) - 0.1025) < 0.001


def test_a_bigger_body_walks_up_more_not_less():
    assert S.unassisted_step_max_m(0.6, 45.0) > S.unassisted_step_max_m(0.4, 45.0)


def test_a_more_forgiving_floor_angle_raises_it():
    assert S.unassisted_step_max_m(0.4, 55.0) > S.unassisted_step_max_m(0.4, 45.0)


# --- the kerb ----------------------------------------------------------------

def test_the_kerb_is_a_wall(tmp_path):
    """The defect this module exists for, reported from play: walking from the
    spawn toward the street stops at the kerb and needs a jump."""
    rows = S.steps(_scene(tmp_path, [GROUND, KERB]), radius_m=R,
                   floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    step = next(s for s in rows if s["to"] == "sidewalk_0L")
    assert step["rise_m"] == 0.16
    assert step["walkable_unassisted"] is False
    assert step["climbable_with_assist"] is True


def test_the_kerb_is_reported_and_says_what_a_stock_body_does(tmp_path):
    issues = S.findings(_scene(tmp_path, [GROUND, KERB]), radius_m=R,
                        floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    f = next(i for i in issues if i["code"] == S.CODE_NEEDS_ASSIST)
    assert "WALL" in f["message"]
    assert "0.16" in f["message"]
    # It has to say why this matters for the DELIVERABLE, not just for our own
    # preview player: the shell ships into projects with none of these tools.
    assert "none of these tools" in f["suggested_fix"]


def test_a_road_and_a_path_are_fine(tmp_path):
    """0.08 and 0.10 are under the limit and must not be reported. A check that
    fires on every transition is one nobody reads."""
    issues = S.findings(_scene(tmp_path, [GROUND, ROAD, PATH]), radius_m=R,
                        floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    assert issues == []


def test_the_courtyard_edge_clears_the_limit_by_three_millimetres(tmp_path):
    """0.12 against 0.1172. It is over, and calling that a margin would be
    generous -- a capsule radius of 0.41 would make it legal again."""
    issues = S.findings(_scene(tmp_path, [GROUND, COURT]), radius_m=R,
                        floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    assert [i["code"] for i in issues] == [S.CODE_NEEDS_ASSIST]
    assert S.unassisted_step_max_m(0.41, ANGLE) > 0.12


def test_something_nothing_can_climb_is_its_own_code(tmp_path):
    tall = ("courtyard_9", 15.0, 0.3, 0.0, 8.0, 0.6, 8.0)       # top 0.60
    issues = S.findings(_scene(tmp_path, [GROUND, tall]), radius_m=R,
                        floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    assert [i["code"] for i in issues] == [S.CODE_TOO_TALL]
    assert "without a jump" in issues[0]["message"]


# --- what it must NOT report -------------------------------------------------

def test_cover_and_walls_are_obstacles_not_steps(tmp_path):
    """A 1.1 m cover block is not a step someone forgot to ramp. Reporting the
    height of an obstacle is how a check earns its way into being ignored."""
    cover = ("cover_0", 5.0, 0.55, 5.0, 2.5, 1.1, 1.2)
    issues = S.findings(_scene(tmp_path, [GROUND, cover]), radius_m=R,
                        floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    assert issues == []


def test_surfaces_that_do_not_touch_are_not_a_transition(tmp_path):
    """A kerb on the far side of the site is not a step off this ground tile."""
    far = ("sidewalk_9R", 500.0, 0.08, 500.0, 40.0, 0.16, 2.0)
    rows = S.steps(_scene(tmp_path, [GROUND, far]), radius_m=R,
                   floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    assert rows == []


def test_flush_surfaces_are_silent(tmp_path):
    flush = ("courtyard_1", 12.0, -0.25, 0.0, 6.0, 0.5, 6.0)    # top 0.00
    rows = S.steps(_scene(tmp_path, [GROUND, flush]), radius_m=R,
                   floor_max_angle_deg=ANGLE, assist_m=ASSIST)
    assert rows == []


def test_a_rotated_road_does_not_touch_the_whole_site(tmp_path):
    """Roads and sidewalks are yaw'd boxes. Their axis-aligned bounds cover half
    the map, so adjacency has to be a separating-axis test on the real
    rectangle or every ground tile reads as adjacent to every road.

    The first version of this test put the ground tile at (-60, -60), which is
    exactly ON the diagonal road's centreline -- the test was wrong and the code
    was right. The tile sits at (-60, +60) now, 85 m off the line."""
    import math as _m
    c, s = _m.cos(_m.radians(45)), _m.sin(_m.radians(45))
    p = tmp_path / "rot.tscn"
    p.write_text(
        "[gd_scene format=3]\n\n"
        '[sub_resource type="BoxShape3D" id="S0"]\nsize = Vector3(40, 0.5, 4)\n\n'
        '[sub_resource type="BoxShape3D" id="S1"]\nsize = Vector3(200, 0.16, 3)\n\n'
        '[node name="Ground_0" type="StaticBody3D" parent="."]\n'
        'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -60, -0.25, 60)\n\n'
        '[node name="col" type="CollisionShape3D" parent="./Ground_0"]\n'
        'shape = SubResource("S0")\n\n'
        f'[node name="sidewalk_0L" type="StaticBody3D" parent="."]\n'
        f'transform = Transform3D({c}, 0, {s}, 0, 1, 0, {-s}, 0, {c}, 0, 0.08, 0)\n\n'
        '[node name="col" type="CollisionShape3D" parent="./sidewalk_0L"]\n'
        'shape = SubResource("S1")\n', encoding="utf-8")
    assert S.steps(str(p), radius_m=R, floor_max_angle_deg=ANGLE,
                   assist_m=ASSIST) == []


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    for fn in ALL:
        with tempfile.TemporaryDirectory() as d:
            if fn.__code__.co_argcount:
                fn(Path(d))
            else:
                fn()
        print(f"[ok] {fn.__name__}")
    print(f"\n{len(ALL)} step tests passed.")
