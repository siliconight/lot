"""Roadmap item 54, the Lot half: every VISUAL mesh Lot draws obeys the tile
law. The first honest per-mesh census (2026-08-23, lot_demo_001's walk
preview) put `path_0/mesh` -- one 65 x 8 m BoxMesh -- under 58 positional
lights against Godot's per-mesh budget of 8. Ground plates, paths, roads and
perimeter walls are Lot's room-spanning plates; `_mesh_tiles` cuts their
visuals, and the BoxShape3D collider stays ONE shape because a collider has
no light budget.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot


def test_a_small_box_tiles_to_itself():
    assert lot._mesh_tiles(1.2, 0.8) == [("", 0.0, 0.0, 1.2, 0.8)]
    assert lot._mesh_tiles(8.0, 8.0) == [("", 0.0, 0.0, 8.0, 8.0)]


def test_the_measured_path_becomes_budget_sized_meshes():
    """The census's worst path: 65 m long, 8 m wide, 58 lights on one mesh."""
    tiles = lot._mesh_tiles(65.0, 8.0)
    assert len(tiles) == 9                      # ceil(65/8) x 1
    for _sfx, _dx, _dz, tx, tz in tiles:
        assert tx <= lot.MESH_TILE + 1e-3       # mm-snapped interior cuts
        assert tz <= lot.MESH_TILE + 1e-3
    assert round(sum(t[3] * t[4] for t in tiles), 6) == 65.0 * 8.0


def test_tiles_reassemble_the_exact_footprint():
    tiles = lot._mesh_tiles(62.9, 22.8)
    lo_x = min(dx - tx / 2 for _s, dx, _dz, tx, _tz in tiles)
    hi_x = max(dx + tx / 2 for _s, dx, _dz, tx, _tz in tiles)
    lo_z = min(dz - tz / 2 for _s, _dx, dz, _tx, tz in tiles)
    hi_z = max(dz + tz / 2 for _s, _dx, dz, _tx, tz in tiles)
    assert (round(hi_x - lo_x, 6), round(hi_z - lo_z, 6)) == (62.9, 22.8)
    assert round(lo_x + hi_x, 6) == 0.0 and round(lo_z + hi_z, 6) == 0.0


def test_no_sliver_tiles():
    tiles = lot._mesh_tiles(8.05, 3.0)
    assert len(tiles) == 2
    assert all(t[3] > 1.0 for t in tiles)


def test_suffixes_are_unique_and_deterministic():
    tiles = lot._mesh_tiles(65.0, 22.0)
    sfx = [t[0] for t in tiles]
    assert len(sfx) == len(set(sfx))
    assert all(s.startswith("_t") for s in sfx)
    assert tiles == lot._mesh_tiles(65.0, 22.0)


# --------------------------------------------------------------------------- #
# the two writers
# --------------------------------------------------------------------------- #

def test_a_small_box_node_is_byte_identical():
    """Every kerb, cover box and crossing must come out exactly as before --
    node names, line order, sub_resources, all of it."""
    body, sub = lot._box_node("cover_3", (1.2, 1.1, 0.8), (4.0, 0.55, -6.0))
    assert body == [
        '[node name="cover_3" type="StaticBody3D" parent="."]',
        'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 4, 0.55, -6)',
        '',
        '[node name="mesh" type="MeshInstance3D" parent="./cover_3"]',
        'mesh = SubResource("BoxMesh_cover_3")',
        '',
        '[node name="col" type="CollisionShape3D" parent="./cover_3"]',
        'shape = SubResource("BoxShape_cover_3")',
        '',
    ]
    assert sub == [
        '[sub_resource type="BoxMesh" id="BoxMesh_cover_3"]',
        'size = Vector3(1.2, 1.1, 0.8)', '',
        '[sub_resource type="BoxShape3D" id="BoxShape_cover_3"]',
        'size = Vector3(1.2, 1.1, 0.8)', '',
    ]


def test_a_big_box_node_tiles_its_mesh_and_keeps_one_shape():
    body, sub = lot._box_node("Ground", (40.0, 0.5, 24.0), (0.0, -0.25, 0.0),
                              (0.3, 0.32, 0.34))
    meshes = [ln for ln in body if 'type="MeshInstance3D"' in ln]
    shapes = [ln for ln in body if 'type="CollisionShape3D"' in ln]
    assert len(meshes) == 5 * 3                 # ceil(40/8) x ceil(24/8)
    assert len(shapes) == 1
    # one BoxShape at the FULL size -- the collider did not move
    assert 'size = Vector3(40, 0.5, 24)' in sub
    assert sum(1 for ln in sub if 'type="BoxShape3D"' in ln) == 1
    # every tile mesh gets the one shared material
    overrides = [ln for ln in body
                 if ln == 'material_override = SubResource("Mat_Ground")']
    assert len(overrides) == 15
    assert sum(1 for ln in sub if 'type="StandardMaterial3D"' in ln) == 1
    # every BoxMesh is budget-sized (the BoxShape line is NOT a mesh -- pair
    # each declaration with its own size line rather than grepping sizes)
    import re
    for decl, size_ln in zip(sub, sub[1:]):
        if not decl.startswith('[sub_resource type="BoxMesh"'):
            continue
        m = re.match(r'size = Vector3\(([\d.]+), 0\.5, ([\d.]+)\)', size_ln)
        assert m, (decl, size_ln)
        assert float(m.group(1)) <= 8.001 and float(m.group(2)) <= 8.001


def test_a_yawed_path_tiles_in_its_local_frame():
    """Tiles ride the parent's yaw: child transforms are identity rotation
    plus a local x/z offset, so the nine meshes lie exactly where the one
    mesh lay."""
    body, sub = lot._yaw_box_node("path_0", (65.0, 0.12, 8.0),
                                  (10.0, 0.03, -5.0), 30.0,
                                  (0.53, 0.47, 0.4))
    meshes = [ln for ln in body if 'type="MeshInstance3D"' in ln]
    assert len(meshes) == 9
    kid_xforms = [ln for ln in body
                  if ln.startswith('transform = Transform3D(1, 0, 0, 0, 1, 0, '
                                   '0, 0, 1, ')]
    assert len(kid_xforms) == 9                 # offsets only, no rotation
    assert sum(1 for ln in body if 'type="CollisionShape3D"' in ln) == 1
    assert 'size = Vector3(65, 0.12, 8)' in sub  # the one full-size shape


def test_a_small_yawed_box_is_byte_identical():
    body, sub = lot._yaw_box_node("road_0", (6.0, 0.1, 4.0),
                                  (0.0, 0.05, 0.0), 90.0)
    assert '[node name="mesh" type="MeshInstance3D" parent="./road_0"]' in body
    assert all("_t0_0" not in ln for ln in body + sub)
