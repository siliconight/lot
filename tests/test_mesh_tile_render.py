"""Roadmap 231, the second lever: the plate families cut to a bigger tile
where the package bakes its lights (0.115.0). Godot 4.7's culler pairs no
BAKE_STATIC light with a lightmapped mesh, so the 8 m tile -- priced
against LIVE lights on 2026-08-23 -- cost cold run 9233 521 of its 795
boxes for a cap that no longer binds through the plate. The spec says
whether the lights bake (`render.lights_baked`, Level Factory 0.178.0) or
names the tile outright (`render.mesh_tile_m`); a spec that says nothing
draws exactly as before.
"""
import copy
import inspect
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")


def _spec():
    with open(os.path.join(SPECS, "example_compound.json"), encoding="utf-8") as f:
        return json.load(f)


def test_a_spec_that_says_nothing_keeps_the_live_light_tile():
    assert lot.mesh_tile({}) == lot.MESH_TILE == 8.0
    assert lot.mesh_tile({"render": {}}) == 8.0
    assert lot.mesh_tile({"render": {"lights_baked": False}}) == 8.0


def test_a_baked_package_takes_the_baked_tile_and_a_named_tile_wins():
    assert lot.mesh_tile({"render": {"lights_baked": True}}) == lot.MESH_TILE_BAKED == 32.0
    assert lot.mesh_tile({"render": {"lights_baked": True, "mesh_tile_m": 16}}) == 16.0
    assert lot.mesh_tile({"render": {"mesh_tile_m": 24.5}}) == 24.5
    with pytest.raises(ValueError):
        lot.mesh_tile({"render": {"mesh_tile_m": 0.5}})


def _box_meshes(sub):
    """(width, depth) of every BoxMesh, each declaration paired with its own
    size line -- the BoxShape line is NOT a mesh."""
    out = []
    for decl, size_ln in zip(sub, sub[1:]):
        if decl.startswith('[sub_resource type="BoxMesh"'):
            m = re.match(r'size = Vector3\(([-\d.]+), [-\d.]+, ([-\d.]+)\)', size_ln)
            assert m, (decl, size_ln)
            out.append((float(m.group(1)), float(m.group(2))))
    return out


def test_the_plate_families_cut_to_the_spec_tile_and_nothing_else_moves():
    spec = _spec()
    body0, sub0 = lot._outdoor_nodes(copy.deepcopy(spec))
    baked = copy.deepcopy(spec)
    baked["render"] = {"lights_baked": True}
    body1, sub1 = lot._outdoor_nodes(baked)
    m0, m1 = _box_meshes(sub0), _box_meshes(sub1)
    assert len(m1) < len(m0), (len(m0), len(m1))
    assert all(w <= 32.0 + 1e-3 and d <= 32.0 + 1e-3 for w, d in m1)
    assert any(w > 8.0 + 1e-3 or d > 8.0 + 1e-3 for w, d in m1), "no plate grew"

    def bodies(body):
        return [ln for ln in body if 'type="StaticBody3D"' in ln]

    def shapes(sub):
        return [(d, s) for d, s in zip(sub, sub[1:])
                if d.startswith('[sub_resource type="BoxShape3D"')]

    def materials(sub):
        return [ln for ln in sub if ln.startswith('[sub_resource type="StandardMaterial3D"')]

    # the bodies, their one shape each at its full size, and the one material
    # a family: none of them moved -- only the visual's cut
    assert bodies(body0) == bodies(body1)
    assert shapes(sub0) == shapes(sub1)
    assert materials(sub0) == materials(sub1)


def test_a_spec_without_render_is_byte_identical_to_before():
    """The empty `render` and the absent one draw the same lines: nothing
    moves for a caller who has not asked (every Lot consumer before Level
    Factory 0.178.0)."""
    spec = _spec()
    a = lot._outdoor_nodes(copy.deepcopy(spec))
    spec["render"] = {}
    b = lot._outdoor_nodes(spec)
    assert a == b


def test_the_writers_take_a_tile():
    body, _sub = lot._box_node("Ground", (40.0, 0.5, 24.0), (0.0, -0.25, 0.0),
                               (0.3, 0.32, 0.34), tile=32.0)
    assert sum(1 for ln in body if 'type="MeshInstance3D"' in ln) == 2      # ceil(40/32) x 1
    body, _sub = lot._yaw_box_node("path_0", (65.0, 0.12, 8.0), (10.0, 0.03, -5.0), 30.0,
                                   (0.53, 0.47, 0.4), tile=32.0)
    assert sum(1 for ln in body if 'type="MeshInstance3D"' in ln) == 3      # ceil(65/32)
    # and with no tile, the law as it was
    body, _sub = lot._yaw_box_node("path_0", (65.0, 0.12, 8.0), (10.0, 0.03, -5.0), 30.0,
                                   (0.53, 0.47, 0.4))
    assert sum(1 for ln in body if 'type="MeshInstance3D"' in ln) == 9


def test_the_per_marking_quad_writer_is_gone():
    """`_yaw_quad_node` wrote a node and a material a marking; 0.114.0 moved
    the paint into one mesh a colour and left it with no caller. A writer
    nothing calls is an unfinished thought, so it is gone, with the
    material's `uv_offset` only it passed."""
    assert not hasattr(lot, "_yaw_quad_node")
    assert "uv_offset" not in inspect.signature(lot._mat_sub).parameters
