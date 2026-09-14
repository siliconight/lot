"""A diagonal slab is drawn where the spec puts it, and read where it is drawn.

Cold run 9052 (`bank_block_001`, seed 9052): `path_0` is Level Factory's
chain path from `b1` at plan (4, -10) to `b2` at (45, 10), 8 m wide. Its
written literal was `Transform3D(0.898768, 0, -0.438424, 0, 1, 0, 0.438424,
0, 0.898768, 24.5, 0.005, -0)`. Godot 4.7, headless, on a scratch copy of the
walk package `_runs/walk_9052_rain`: `str_to_var` on that text and the
instantiated node's `global_transform` both give `basis.x = (0.898768, 0,
0.438424)`, and the collision box's plan corners are (5.754, 13.595), (2.246,
6.405), (46.754, -6.405), (43.246, -13.595). The path ran from (4, 10) to
(45, -10): the spec's path mirrored across its own centre line, its far end
20 m from the building it was drawn to reach.

Two errors, one class. The writers passed `-angle` as the yaw, which under
Godot's ROW-major reading of the literal is the mirror of `angle`; and
`site_steps.surfaces` read the literal COLUMN-major, the transpose, which
mirrors it back -- so the step gate agreed with the spec and not with the
scene. Axis-aligned slabs are symmetric under both, which is why no street
caught either.

The scene reader here is written out, row-major, as the engine reads it, and
does not share code with `site_steps`: a test that reads the scene with the
checker's own parser cannot catch the checker.
"""
import math
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot             # noqa: E402
import site_collision  # noqa: E402
import site_steps      # noqa: E402
import site_streets    # noqa: E402
import site_surfaces   # noqa: E402

#: `%g` writes six significant figures; a 60 m coordinate keeps 1 mm.
SCENE_DIGITS_M = 2e-3

#: Four quadrants, two yaws each, none within 26 degrees of a plan axis --
#: a yaw near an axis is nearly its own mirror and would prove little.
ANGLES = (26.0, 63.0, 117.0, 153.0, 207.0, 243.0, 297.0, 333.0)

_NODE = re.compile(
    r'\[node name="([\w\-]+)" type="(StaticBody3D|Node3D)" parent="\."\]\s*\n'
    r'transform = Transform3D\(([^)]*)\)')
_SHAPE = re.compile(
    r'\[sub_resource type="BoxShape3D" id="BoxShape_([\w\-]+)"\]\s*\n'
    r'size = Vector3\(([^)]*)\)')


def _scene(spec):
    body, sub = lot._outdoor_nodes(spec)
    return ('[gd_scene format=3]\n\n' + "\n".join(sub) + "\n"
            + '[node name="Site" type="Node3D"]\n\n' + "\n".join(body))


def _engine_axes(numbers):
    """Images of local +X and +Z in Godot, reading the nine numbers as basis
    ROWS -- measured, see the module docstring."""
    n = [float(v) for v in numbers]
    rows = (n[0:3], n[3:6], n[6:9])
    x = tuple(rows[k][0] for k in range(3))
    z = tuple(rows[k][2] for k in range(3))
    return x, z, tuple(n[9:12])


def _drawn(src):
    """{name: (plan corners, plan axis of local x)} for every top-level
    yawed/boxed node, plan = Godot (x, -z)."""
    sizes = {m.group(1): [float(v) for v in m.group(2).split(",")]
             for m in _SHAPE.finditer(src)}
    out = {}
    for m in _NODE.finditer(src):
        name = m.group(1)
        x, z, o = _engine_axes(m.group(3).split(","))
        axis = (x[0], -x[2])
        size = sizes.get(name)
        corners = None
        if size is not None:
            hx, hz = size[0] / 2, size[2] / 2
            corners = [(o[0] + a * hx * x[0] + b * hz * z[0],
                        -(o[2] + a * hx * x[2] + b * hz * z[2]))
                       for a in (-1, 1) for b in (-1, 1)]
        out[name] = (corners, axis)
    return out


def _rect(a, b, width):
    """Plan corners of the width-wide rectangle whose centre line is a -> b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    px, py = -dy / ln * width / 2, dx / ln * width / 2
    return [(a[0] + px, a[1] + py), (a[0] - px, a[1] - py),
            (b[0] + px, b[1] + py), (b[0] - px, b[1] - py)]


def _same(a, b, tol=SCENE_DIGITS_M):
    return (len(a) == len(b)
            and all(any(math.hypot(p[0] - q[0], p[1] - q[1]) <= tol for q in b)
                    for p in a))


def _path_spec(angle, length=46.0, width=8.0):
    r = math.radians(angle)
    a = (-3.0, 2.0)
    b = (a[0] + length * math.cos(r), a[1] + length * math.sin(r))
    return {
        "name": "diag",
        "ground": {"size_x": 140, "size_y": 140},
        "buildings": [{"id": "p", "at": list(a), "rot": 0},
                      {"id": "q", "at": list(b), "rot": 0}],
        "paths": [{"from": "p", "to": "q", "width": width}],
    }, a, b, width


@pytest.mark.parametrize("angle", ANGLES)
def test_a_diagonal_paths_drawn_corners_are_its_intended_corners(angle):
    spec, a, b, w = _path_spec(angle)
    corners, axis = _drawn(_scene(spec))["path_0"]
    assert _same(corners, _rect(a, b, w)), (angle, corners, _rect(a, b, w))
    r = math.radians(angle)
    assert abs(axis[0] - math.cos(r)) < 1e-5 and abs(axis[1] - math.sin(r)) < 1e-5


@pytest.mark.parametrize("angle", ANGLES)
def test_the_step_gate_reads_the_path_where_it_is_drawn(angle, tmp_path):
    spec, a, b, w = _path_spec(angle)
    src = _scene(spec)
    p = tmp_path / "diag.tscn"
    p.write_text(src, encoding="utf-8")
    got = {s["name"]: s for s in site_steps.surfaces(str(p))}
    # site_steps reports Godot plan (x, z); the spec's plan is (x, -z)
    corners = [(x, -z) for x, z in got["path_0"]["corners"]]
    assert _same(corners, _drawn(src)["path_0"][0]), (angle, corners)
    assert _same(corners, _rect(a, b, w)), angle


@pytest.mark.parametrize("angle", ANGLES)
def test_the_declared_top_is_under_the_intended_path(angle):
    """Points near both ends of the spec's rectangle, off its centre line on
    both sides: the mirrored slab 0.72.0 drew misses every one of them at
    these yaws. And the declared slab is the drawn one."""
    spec, a, b, w = _path_spec(angle)
    slabs = site_surfaces.tops(spec)
    (decl,) = [s for s in slabs if s["name"] == "path_0"]
    dr = math.radians(decl["yaw_deg"])
    u, v = (math.cos(dr), math.sin(dr)), (-math.sin(dr), math.cos(dr))
    hx, hy = decl["size"][0] / 2, decl["size"][1] / 2
    cx, cy = decl["centre"]
    declared = [(cx + i * hx * u[0] + j * hy * v[0], cy + i * hx * u[1] + j * hy * v[1])
                for i in (-1, 1) for j in (-1, 1)]
    assert _same(declared, _drawn(_scene(spec))["path_0"][0]), angle
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    ux, uy, px, py = dx / ln, dy / ln, -dy / ln, dx / ln
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    for t in (-0.45 * ln, 0.45 * ln):
        for o in (-0.4 * w, 0.4 * w):
            pt = (mx + ux * t + px * o, my + uy * t + py * o)
            assert site_surfaces.surface_top(pt, slabs) == round(lot.PATH_THICK, 5), (angle, pt)


def test_cold_run_9052s_chain_path_reaches_the_building_it_names():
    spec = {
        "name": "site", "ground": {"size_x": 157, "size_y": 83},
        "buildings": [{"id": "b1", "at": [4, -10], "rot": 270},
                      {"id": "b2", "at": [45, 10], "rot": 270}],
        "paths": [{"from": "b1", "to": "b2", "width": 8.0}],
    }
    corners, _ = _drawn(_scene(spec))["path_0"]
    # 0.72.0 drew (5.754, 13.595), (2.246, 6.405), (46.754, -6.405),
    # (43.246, -13.595), read back from Godot 4.7
    assert _same(corners, [(2.246, -6.405), (5.754, -13.595),
                           (43.246, 13.595), (46.754, 6.405)])


def _road_spec(angle):
    r = math.radians(angle)
    a = (-45.0 * math.cos(r), -45.0 * math.sin(r))
    b = (45.0 * math.cos(r), 45.0 * math.sin(r))
    return {
        "name": "diag_road", "ground": {"size_x": 140, "size_y": 140},
        "buildings": [],
        "roads": [{"a": list(a), "b": list(b), "width": 10.0, "sidewalk": 3.0}],
    }


@pytest.mark.parametrize("angle", ANGLES)
def test_a_diagonal_road_its_bands_and_its_paint_lie_along_it(angle, tmp_path):
    spec = _road_spec(angle)
    (road,) = site_streets.roads(spec)
    src = _scene(spec)
    drawn = _drawn(src)
    # the carriageway: exactly the road's rectangle
    corners, _ = drawn["road_0"]
    want = _rect(road.point(road.slab[0]), road.point(road.slab[1]), road.width)
    assert _same(corners, want), (angle, corners, want)
    # every band piece: inside its own kerb's band, in the road's frame
    bands = [n for n in drawn if n.startswith(("sidewalk_0", "kerbcut_0"))]
    assert bands
    for n in bands:
        side = n.split("_")[1][-1]
        sign = road.kerb(side).sign
        inner, outer = road.width / 2, road.width / 2 + road.sidewalk
        for x, y in drawn[n][0]:
            dx, dy = x - road.a[0], y - road.a[1]
            t = dx * road.along[0] + dy * road.along[1]
            off = (dx * road.perp[0] + dy * road.perp[1]) * sign
            assert -SCENE_DIGITS_M <= t <= road.length + SCENE_DIGITS_M, (angle, n, t)
            assert inner - SCENE_DIGITS_M <= off <= outer + SCENE_DIGITS_M, (angle, n, off)
    # the paint: every marking's length runs along the road
    marks = [n for n in drawn if n.startswith("mark_")]
    assert marks
    for n in marks:
        ax = drawn[n][1]
        assert abs(ax[0] - road.along[0]) < 1e-5 and abs(ax[1] - road.along[1]) < 1e-5, (angle, n, ax)
    # and the step gate reads the road where it is drawn
    p = tmp_path / "road.tscn"
    p.write_text(src, encoding="utf-8")
    got = {s["name"]: [(x, -z) for x, z in s["corners"]]
           for s in site_steps.surfaces(str(p))}
    for n in ["road_0"] + bands:
        assert _same(got[n], drawn[n][0]), (angle, n)


def test_the_collision_reader_turns_an_instance_the_way_godot_does(tmp_path):
    """The measured literal: local +X of 9052's `path_0` is Godot
    (0.898768, 0, 0.438424)."""
    m = site_collision._godot_transform(
        "0.898768, 0, -0.438424, 0, 1, 0, 0.438424, 0, 0.898768, 24.5, 0.005, -0".split(","))
    x = site_collision.apply(m, (1.0, 0.0, 0.0))
    assert math.isclose(x[0] - 24.5, 0.898768, abs_tol=1e-9)
    assert math.isclose(x[2], 0.438424, abs_tol=1e-9)
    # a body turned a quarter (yaw 90: local +X is plan +y) with its box 2 m
    # along local +X stands 2 m NORTH of the body, site (0, 2)
    p = tmp_path / "turned.tscn"
    p.write_text(
        '[gd_scene format=3]\n\n'
        '[sub_resource type="BoxShape3D" id="B"]\nsize = Vector3(1, 1, 1)\n\n'
        '[node name="root" type="Node3D"]\n\n'
        '[node name="wall" type="StaticBody3D" parent="."]\n'
        'transform = Transform3D(0, 0, 1, 0, 1, 0, -1, 0, 0, 0, 0, 0)\n\n'
        '[node name="col" type="CollisionShape3D" parent="wall"]\n'
        'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 2, 0.5, 0)\n'
        'shape = SubResource("B")\n', encoding="utf-8")
    (box,) = site_collision.read_source(str(p)).boxes
    assert math.isclose(box.centre[0], 0.0, abs_tol=1e-9), box.centre
    assert math.isclose(box.centre[1], 2.0, abs_tol=1e-9), box.centre
