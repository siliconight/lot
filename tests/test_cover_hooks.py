"""The cover test points Lot hands Laser Tag stand where the cover stands.

`LT_CoverTestPoints/Cover_N` describes a piece of cover to Laser Tag's bot, so
its position has to be the cover's. `at` is a ground-plan XY and carries no
height, and the emitter used to fill the third component with the OBJECTIVE's
elevation -- which is invisible while the objective is at grade and wrong the
moment it is not.

Measured on a five-building street whose objective sits in a basement at
-3.10: the eight cover BODIES were written at y 1.00, standing on the street,
and their eight test points at y -3.10, three metres under it. Level Factory's
ground-contact preflight refused the map with "8 of 19 mission point(s) have no
ground beneath them" and no firefight was ever evaluated. Re-running that
checker with the points corrected takes the count from 10 to 2, and the two
survivors are the objective itself, which really is below grade.
"""

import re

import lot


def _hooks(objective_z, cover):
    pos = {"spawn": (60.0, 0.0, 0.0),
           "objective": (0.0, 0.0, objective_z),
           "extraction": (-60.0, 0.0, 0.0)}
    return "\n".join(lot._lasertag_hook_nodes(
        pos, site_spec={"cover": cover, "buildings": []}))


def _cover_ys(text):
    return [float(m.group(1).split(",")[10])
            for m in re.finditer(
                r'\[node name="Cover_\d+" type="Node3D" '
                r'parent="LT_CoverTestPoints"\]\s*\n'
                r'transform = Transform3D\(([^)]*)\)', text)]


PIECES = [{"at": [18.079, -4.55], "size": [2.0, 2.0, 2.0], "source": "site_cover"},
          {"at": [-34.78, 1.43], "size": [2.0, 2.0, 2.0], "source": "site_cover"}]


def test_a_basement_objective_does_not_drag_the_cover_underground():
    """THE DEFECT. Same cover, an objective 3.1 m down, and the points used to
    follow it there."""
    ys = _cover_ys(_hooks(-3.10, PIECES))
    assert ys == [1.0, 1.0], ys


def test_the_points_do_not_move_when_the_objective_does():
    """The cover has not moved, so neither should its description of itself."""
    at_grade = _cover_ys(_hooks(0.0, PIECES))
    in_a_basement = _cover_ys(_hooks(-3.10, PIECES))
    on_a_roof = _cover_ys(_hooks(7.4, PIECES))
    assert at_grade == in_a_basement == on_a_roof


def test_the_point_agrees_with_the_body_lot_writes():
    """`_box_node` puts the body at `sy / 2` -- half its own height. The point
    reads the same size, because two writers of one thing disagreeing is what
    produced this."""
    tall = [{"at": [0.0, 0.0], "size": [2.0, 3.0, 2.0]}]
    assert _cover_ys(_hooks(-3.10, tall)) == [1.5]


def test_the_height_is_the_second_component():
    """`size` is written in the GODOT frame -- (x, height, y) -- which
    `site_cover.Cover.as_spec` states outright. Reading the third would be
    right only while cover is a cube, which it is today and need not be."""
    oblong = [{"at": [0.0, 0.0], "size": [1.0, 2.5, 4.0]}]
    assert _cover_ys(_hooks(0.0, oblong)) == [1.25]


def test_a_piece_with_no_size_falls_back_to_the_planner_default():
    """An older spec, or one hand-written. It must not crash and must not
    silently land at zero."""
    import site_cover
    ys = _cover_ys(_hooks(-3.10, [{"at": [4.0, 4.0]}]))
    assert ys == [site_cover.COVER_HEIGHT / 2.0]


def test_no_planned_cover_still_emits_the_rosette_around_the_objective():
    """The fallback is unchanged and SHOULD track the objective -- those four
    points are a rosette about it, not real cover. An empty node would read as
    'this map has no cover' when the truth is 'none was planned'."""
    text = _hooks(-3.10, [])
    ys = _cover_ys(text)
    assert len(ys) == 4
    assert set(ys) == {-3.10}


def test_deterministic():
    assert _hooks(-3.10, PIECES) == _hooks(-3.10, PIECES)
