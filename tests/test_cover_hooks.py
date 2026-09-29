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


def _point(height):
    """Where a cover of this height puts its point (0.82.0): half of what
    shelters a body."""
    return min(height, lot._player_metric("height_m", 1.8)) / 2.0


PIECES = [{"at": [18.079, -4.55], "size": [2.0, 2.0, 2.0], "source": "site_cover"},
          {"at": [-34.78, 1.43], "size": [2.0, 2.0, 2.0], "source": "site_cover"}]


def test_a_basement_objective_does_not_drag_the_cover_underground():
    """THE DEFECT. Same cover, an objective 3.1 m down, and the points used to
    follow it there."""
    ys = _cover_ys(_hooks(-3.10, PIECES))
    # a 2 m cube: half of min(2.0, a body's height) -- 0.9 since 0.82.0
    assert ys == [_point(2.0)] * 2, ys


def test_the_points_do_not_move_when_the_objective_does():
    """The cover has not moved, so neither should its description of itself."""
    at_grade = _cover_ys(_hooks(0.0, PIECES))
    in_a_basement = _cover_ys(_hooks(-3.10, PIECES))
    on_a_roof = _cover_ys(_hooks(7.4, PIECES))
    assert at_grade == in_a_basement == on_a_roof


def test_the_point_agrees_with_the_body_lot_writes():
    """`_box_node` puts the body at `sy / 2` -- half its own height -- and a
    cover no taller than a player's body puts its point there too."""
    low = [{"at": [0.0, 0.0], "size": [2.0, 1.2, 2.0]}]
    assert _cover_ys(_hooks(-3.10, low)) == [0.6]


def test_a_cover_taller_than_a_body_puts_its_point_at_a_bodys_centre():
    """0.82.0, SUPERSEDING "the point is always half the cover's height"
    (this test pinned 1.5 for a 3 m cover). Laser Tag's bot walks to these
    under fire, so the point is where a BODY takes cover: half the height of
    what shelters one. Cold run 9109: the 9 m price pylon's point stood 4.5 m
    up, over Level Factory's MAX_DROP of 4.0, and the pre-flight refused the
    map."""
    body = lot._player_metric("height_m", 1.8)
    for h in (3.0, 9.0):
        tall = [{"at": [0.0, 0.0], "size": [3.4, h, 0.7]}]
        assert _cover_ys(_hooks(0.0, tall)) == [body / 2.0], h


def test_the_height_is_the_second_component():
    """`size` is written in the GODOT frame -- (x, height, y) -- which
    `site_cover.Cover.as_spec` states outright. Reading the third would be
    right only while cover is a cube, which it is today and need not be."""
    oblong = [{"at": [0.0, 0.0], "size": [4.0, 1.5, 1.0]}]
    assert _cover_ys(_hooks(0.0, oblong)) == [0.75]


def test_a_piece_with_no_size_falls_back_to_the_planner_default():
    """An older spec, or one hand-written. It must not crash and must not
    silently land at zero."""
    import site_cover
    ys = _cover_ys(_hooks(-3.10, [{"at": [4.0, 4.0]}]))
    assert ys == [_point(site_cover.COVER_HEIGHT)]


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
