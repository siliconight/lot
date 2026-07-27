"""A nav hook stands on floor, not on the furniture at the same coordinates.

Guards the defect where `LT_ObjectivePoint` was written at the exact centre of a
`cashier_cage` room -- which is also the exact centre of the `cage_counter` prop
Deli Counter bakes into that room, a 6.0 x 1.0 m box 1.1 m tall. Laser Tag's
navmesh takes a cell's standing surface from the geometry under the point, so
the cell read 1.1 m up against a room floor of flat 0 with no step between it
and anything else. Against a 0.5 m climb limit no route to it existed: the bot
finished 0% of runs and the whole map came back refused, for a one-metre
placement error.

An earlier fix seated the hook's *height* on the floor and the blocker survived,
because the footprint never moved. The reader tested here is what lets Lot see
the counter at all, and the resolve is what walks the hook off it.

The four positions asserted in `test_the_real_cage_counters_land_where_they_do`
are the ones Level Factory's own independent reader recovered from the shipped
BAIE_DORE pack. Two readers, one written-down contract; if they ever disagree,
one of them is wrong and this is where it shows.
"""
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot
import site_collision
import site_ground
import site_spawns


# ---------------------------------------------------------------------------
# helpers -- a real, minimal glTF whose colliders are declared in site space
# ---------------------------------------------------------------------------
def _doc(colliders, *, named_scene=True):
    """A glTF document holding one axis-aligned box per entry.

    Entries are `(name, centre, size)` in Lot **site** space (x east, y north,
    z up); the helper writes them out Y-up the way an exporter would, so a test
    that asserts on site coordinates is exercising the conversion rather than
    restating it.
    """
    nodes, meshes, accessors = [], [], []
    for name, centre, size in colliders:
        sx, sy, sz = float(size[0]), float(size[2]), float(size[1])
        accessors.append({"type": "VEC3", "componentType": 5126, "count": 8,
                          "min": [-sx / 2, -sy / 2, -sz / 2],
                          "max": [sx / 2, sy / 2, sz / 2]})
        meshes.append({"primitives": [
            {"attributes": {"POSITION": len(accessors) - 1}}]})
        nodes.append({"name": name, "mesh": len(meshes) - 1,
                      "translation": [float(centre[0]), float(centre[2]),
                                      -float(centre[1])]})
    doc = {"asset": {"version": "2.0"}, "nodes": nodes, "meshes": meshes,
           "accessors": accessors}
    if named_scene:
        doc["scene"] = 0
        doc["scenes"] = [{"nodes": list(range(len(nodes)))}]
    return doc


def _pack(doc):
    """12-byte header + a JSON chunk: the smallest thing Godot would accept."""
    blob = json.dumps(doc).encode()
    blob += b" " * (-len(blob) % 4)
    chunk = struct.pack("<II", len(blob), 0x4E4F534A) + blob
    return struct.pack("<III", 0x46546C67, 2, 12 + len(chunk)) + chunk


def _write(tmp_path, name, doc):
    p = os.path.join(str(tmp_path), name)
    with open(p, "wb") as f:
        f.write(_pack(doc))
    return p


def _text(tmp_path, name, body):
    p = os.path.join(str(tmp_path), name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(body)
    return p


def _by_name(reading, needle):
    return [b for b in reading.boxes if needle in b.name]


def _round(box, places=3):
    return (tuple(round(v, places) for v in box.centre),
            tuple(round(v, places) for v in box.size))


#: The prop the whole module exists for: Deli Counter's cashier cage counter,
#: in building-local space, exactly as it comes out of the shipped shell.
CAGE = ("cage_counter_col-convcolonly", (16.0, 12.0, 0.55), (6.0, 1.0, 1.1))

#: The real seed: four shells along the main axis, three of them turned around.
BAIE_DORE_AT = {"b0": ((6.0, -10.0), 180), "b1": ((51.0, -5.0), 180),
                "b2": ((84.0, -5.0), 180), "b3": ((135.0, -10.0), 0)}


def _flat(colliders=(CAGE,)):
    """A one-source site whose four buildings all instance the same shell."""
    return {
        "name": "t", "ground": {"size_x": 232.0, "size_y": 100.0},
        "buildings": [{"id": bid, "glb": "shell.glb", "at": list(at),
                       "rot": rot, "_footprint": [44.0, 44.0]}
                      for bid, (at, rot) in sorted(BAIE_DORE_AT.items())],
    }, list(colliders)


# ---------------------------------------------------------------------------
# the container
# ---------------------------------------------------------------------------
def test_a_real_glb_yields_its_json_document():
    doc = site_collision.glb_document(_pack(_doc([CAGE])))
    assert isinstance(doc, dict) and len(doc["nodes"]) == 1


def test_a_truncated_glb_is_none_rather_than_an_exception():
    assert site_collision.glb_document(b"glTF" + b"\x00" * 8) is None
    assert site_collision.glb_document(b"") is None
    assert site_collision.glb_document(b"not a glb at all, really") is None


def test_a_glb_whose_json_chunk_is_corrupt_is_none():
    blob = b"{not json" + b" " * 3
    chunk = struct.pack("<II", len(blob), 0x4E4F534A) + blob
    data = struct.pack("<III", 0x46546C67, 2, 12 + len(chunk)) + chunk
    assert site_collision.glb_document(data) is None


def test_a_glb_holding_only_a_binary_chunk_is_none_not_empty():
    """"No JSON in this file" must not arrive as "this file has no nodes"."""
    blob = b"\x00" * 16
    chunk = struct.pack("<II", len(blob), 0x004E4942) + blob
    data = struct.pack("<III", 0x46546C67, 2, 12 + len(chunk)) + chunk
    assert site_collision.glb_document(data) is None


def test_one_reader_serves_both_modules(tmp_path):
    """`site_ground` asks the same question of the same chunk. If the envelope
    walk ever forked, "this file parses" could come out two different ways
    depending on which module asked -- and the ground policy and the collision
    reader would disagree about the same building."""
    data = _pack(_doc([CAGE]))
    assert site_ground.glb_node_names(data) == [CAGE[0]]
    assert site_ground.glb_node_names(b"glTF" + b"\x00" * 8) == []


# ---------------------------------------------------------------------------
# the suffix contract
# ---------------------------------------------------------------------------
def test_every_documented_collision_suffix_counts():
    for suffix in site_collision.COLLISION_SUFFIXES:
        assert site_collision.name_generates_collision("floor" + suffix), suffix


def test_blenders_duplicate_numbering_does_not_hide_the_suffix():
    assert site_collision.name_generates_collision(CAGE[0] + ".001")
    assert site_collision.name_generates_collision("Floor-ConvColOnly")


def test_a_name_that_merely_contains_col_is_not_a_collider():
    assert not site_collision.name_generates_collision("column_0")
    assert not site_collision.name_generates_collision("col-floor")
    # Godot matches a hyphen, so the underscore in Deli Counter's own
    # `cage_counter_col` is not the suffix -- `-convcolonly` is.
    assert not site_collision.name_generates_collision("cage_counter_col")


def test_the_two_readers_agree_on_the_contract():
    """`site_ground` decides whether to cut a hole from the same suffix list
    this module locates furniture with. They are separate implementations on
    purpose; they are not allowed to be separate *contracts*."""
    assert site_collision.COLLISION_SUFFIXES == site_ground.COLLISION_SUFFIXES
    for name in ("floor-col", "floor-col.001", "Floor-ConvCol", "column_0",
                 "col-floor", "wall-colonly", "shell"):
        assert (site_collision.name_generates_collision(name)
                is site_ground.name_generates_collision(name)), name


# ---------------------------------------------------------------------------
# Y-up out, site space in
# ---------------------------------------------------------------------------
def test_a_y_up_span_becomes_a_site_box():
    """Lot writes site (x, y, z) as Godot (x, z, -y); this is the inverse, and
    getting it backwards would move every hook along the wrong axis."""
    box = site_collision.to_site((13.0, 0.0, -12.5), (19.0, 1.1, -11.5), "c")
    assert _round(box) == ((16.0, 12.0, 0.55), (6.0, 1.0, 1.1))
    assert round(box.top, 3) == 1.1 and round(box.bottom, 3) == 0.0


def test_a_collider_survives_the_round_trip_through_a_file():
    reading = site_collision.boxes_in(_doc([CAGE]))
    assert reading.complete and len(reading.boxes) == 1
    assert _round(reading.boxes[0]) == (CAGE[1], CAGE[2])


def test_a_mesh_without_a_collision_name_is_not_a_solid():
    doc = _doc([("shell", (0.0, 0.0, 3.0), (44.0, 44.0, 6.0)), CAGE])
    assert [b.name for b in site_collision.boxes_in(doc).boxes] == [CAGE[0]]


def test_import_settings_make_every_mesh_a_solid(tmp_path):
    """A .glb whose sibling .import asks for physics gives collision to meshes
    that never carried the suffix. Reading only the suffixes there would call a
    solid building empty."""
    doc = _doc([("shell", (0.0, 0.0, 3.0), (44.0, 44.0, 6.0)), CAGE])
    assert len(site_collision.boxes_in(doc, every_mesh=True).boxes) == 2
    p = _write(tmp_path, "shell.glb", doc)
    assert len(site_collision.read_source(p).boxes) == 1
    with open(p + ".import", "w", encoding="utf-8") as f:
        f.write('[params]\n_subresources={"nodes": {"PATH:shell": '
                '{"generate/physics": true}}}\n')
    assert site_collision.import_requests_physics(p)
    assert len(site_collision.read_source(p).boxes) == 2


def test_a_node_hierarchy_composes_rather_than_flattens():
    """Deli Counter parents its furniture under a room node. Ignoring the
    parent's transform would locate every prop at the building origin -- which
    reads as "nothing is under the objective" for exactly the props that are."""
    doc = {"asset": {"version": "2.0"},
           "scene": 0, "scenes": [{"nodes": [0]}],
           "nodes": [{"name": "room", "translation": [16.0, 0.0, -12.0],
                      "children": [1]},
                     {"name": "cage_counter_col-convcolonly", "mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"min": [-3.0, 0.0, -0.5], "max": [3.0, 1.1, 0.5]}]}
    box = site_collision.boxes_in(doc).boxes[0]
    assert _round(box) == ((16.0, 12.0, 0.55), (6.0, 1.0, 1.1))


def test_a_rotated_node_is_bounded_rather_than_approximated():
    """A quarter turn about the up axis swaps the extents exactly."""
    half = math.sqrt(0.5)
    doc = {"asset": {"version": "2.0"},
           "nodes": [{"name": "bench-col", "mesh": 0,
                      "rotation": [0.0, half, 0.0, half]}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"min": [-3.0, 0.0, -0.5], "max": [3.0, 1.1, 0.5]}]}
    box = site_collision.boxes_in(doc).boxes[0]
    assert _round(box)[1] == (1.0, 6.0, 1.1)


def test_a_node_with_no_readable_bounds_makes_the_reading_incomplete():
    """The whole point of `complete`: a collider whose extent could not be read
    must not come back as an absence of colliders."""
    doc = {"asset": {"version": "2.0"},
           "nodes": [{"name": "mystery-col", "mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"componentType": 5126}]}
    reading = site_collision.boxes_in(doc)
    assert reading.boxes == () and not reading.complete
    assert "mystery-col" in reading.unread[0]


def test_a_document_with_no_node_list_is_incomplete_not_empty():
    reading = site_collision.boxes_in({"asset": {"version": "2.0"}})
    assert not reading.complete and reading.boxes == ()


def test_a_file_that_declares_no_scene_is_still_walked():
    """Exporters differ. Reading the node list only when a scene index happens
    to be present would make collision depend on the exporter's mood."""
    reading = site_collision.boxes_in(_doc([CAGE], named_scene=False))
    assert len(reading.boxes) == 1 and reading.complete


# ---------------------------------------------------------------------------
# reading a source off disk
# ---------------------------------------------------------------------------
def test_a_missing_file_is_incomplete_not_clear(tmp_path):
    reading = site_collision.read_source(os.path.join(str(tmp_path), "no.glb"))
    assert not reading.complete and reading.boxes == ()
    assert "not found" in reading.unread[0]


def test_declaring_no_geometry_at_all_is_incomplete(tmp_path):
    assert not site_collision.read_source("").complete


def test_a_binary_scene_is_incomplete_rather_than_empty(tmp_path):
    p = _text(tmp_path, "b.scn", "\x00binary")
    reading = site_collision.read_source(p)
    assert not reading.complete and "not readable as text" in reading.unread[0]


def test_an_unrecognised_format_is_incomplete(tmp_path):
    p = _text(tmp_path, "b.fbx", "whatever")
    assert not site_collision.read_source(p).complete


def test_a_tscn_carries_the_colliders_of_what_it_instances(tmp_path):
    """Deli Counter's primary output is a .tscn instancing module scenes. A
    reader that only understood .glb would see a building's furniture only when
    the building happened to be baked."""
    _write(tmp_path, "shell.glb", _doc([CAGE]))
    p = _text(tmp_path, "b.tscn",
              '[gd_scene format=3]\n'
              '[ext_resource type="PackedScene" path="res://shell.glb" id="1_a"]\n'
              '[node name="B" type="Node3D"]\n'
              '[node name="shell" parent="." instance=ExtResource("1_a")]\n')
    reading = site_collision.read_source(p)
    assert reading.complete and len(reading.boxes) == 1
    assert _round(reading.boxes[0]) == (CAGE[1], CAGE[2])


def test_an_instance_transform_moves_the_colliders_with_it(tmp_path):
    """Godot's Transform3D is basis columns then origin, and its -z is site +y.
    Getting either wrong puts the furniture in the next room."""
    _write(tmp_path, "shell.glb", _doc([CAGE]))
    p = _text(tmp_path, "b.tscn",
              '[gd_scene format=3]\n'
              '[ext_resource type="PackedScene" path="res://shell.glb" id="1_a"]\n'
              '[node name="B" type="Node3D"]\n'
              '[node name="shell" parent="." instance=ExtResource("1_a")]\n'
              'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 4, 0, -20)\n')
    box = site_collision.read_source(p).boxes[0]
    assert _round(box) == ((20.0, 32.0, 0.55), (6.0, 1.0, 1.1))


def test_a_scene_that_declares_its_own_shapes_reads_as_partial(tmp_path):
    """A CollisionShape3D in the scene text is real collision this reader does
    not turn into a box. Reporting the instanced furniture and calling the
    answer complete would let a hook be moved onto a shape nobody looked at."""
    _write(tmp_path, "shell.glb", _doc([CAGE]))
    p = _text(tmp_path, "b.tscn",
              '[gd_scene format=3]\n'
              '[ext_resource type="PackedScene" path="res://shell.glb" id="1_a"]\n'
              '[node name="B" type="StaticBody3D"]\n'
              '[node name="col" type="CollisionShape3D" parent="."]\n'
              '[node name="shell" parent="." instance=ExtResource("1_a")]\n')
    reading = site_collision.read_source(p)
    assert len(reading.boxes) == 1, "the furniture is still worth reading"
    assert not reading.complete
    assert "does not model" in reading.unread[0]


def test_an_instance_that_does_not_resolve_is_named(tmp_path):
    p = _text(tmp_path, "b.tscn",
              '[gd_scene format=3]\n'
              '[ext_resource type="PackedScene" path="res://gone.glb" id="1_a"]\n'
              '[node name="B" type="Node3D"]\n'
              '[node name="shell" parent="." instance=ExtResource("1_a")]\n')
    reading = site_collision.read_source(p)
    assert not reading.complete
    assert "gone.glb" in reading.unread[0]


def test_a_scene_cycle_terminates(tmp_path):
    for src, other in (("a.tscn", "b.tscn"), ("b.tscn", "a.tscn")):
        _text(tmp_path, src,
              '[gd_scene format=3]\n'
              f'[ext_resource type="PackedScene" path="res://{other}" id="1_a"]\n'
              '[node name="R" type="Node3D"]\n'
              '[node name="x" parent="." instance=ExtResource("1_a")]\n')
    reading = site_collision.read_source(os.path.join(str(tmp_path), "a.tscn"))
    assert reading.boxes == ()


# ---------------------------------------------------------------------------
# placing a building on the site
# ---------------------------------------------------------------------------
def test_an_unrotated_building_just_translates():
    placed = site_collision.place_boxes(
        [site_collision.Box("c", (16.0, 12.0, 0.55), (6.0, 1.0, 1.1))],
        (135.0, -10.0), 0)
    assert _round(placed[0]) == ((151.0, 2.0, 0.55), (6.0, 1.0, 1.1))


def test_a_half_turn_mirrors_the_offset_and_keeps_the_extents():
    placed = site_collision.place_boxes(
        [site_collision.Box("c", (16.0, 12.0, 0.55), (6.0, 1.0, 1.1))],
        (51.0, -5.0), 180)
    assert _round(placed[0]) == ((35.0, -17.0, 0.55), (6.0, 1.0, 1.1))


def test_a_quarter_turn_swaps_the_extents_exactly():
    """Right angles are the common case and must not accumulate the slop of a
    general rotation -- a counter that grows 40% wide pushes a hook that did
    not need pushing."""
    for rot, centre in ((90, (-12.0, 16.0, 0.55)), (270, (12.0, -16.0, 0.55))):
        placed = site_collision.place_boxes(
            [site_collision.Box("c", (16.0, 12.0, 0.55), (6.0, 1.0, 1.1))],
            (0.0, 0.0), rot)
        assert _round(placed[0]) == (centre, (1.0, 6.0, 1.1)), rot


def test_an_odd_angle_is_bounded_rather_than_approximated():
    """Larger than the prop is the harmless direction: it moves a hook that did
    not need moving, never leaves one stranded."""
    placed = site_collision.place_boxes(
        [site_collision.Box("c", (0.0, 0.0, 0.55), (6.0, 1.0, 1.1))],
        (0.0, 0.0), 45)
    assert placed[0].size[0] > 4.9 and placed[0].size[1] > 4.9
    assert round(placed[0].size[2], 6) == 1.1, "height is unaffected by yaw"


def test_the_real_cage_counters_land_where_they_do(tmp_path):
    """The four positions Level Factory's own reader recovered from the shipped
    pack, reproduced here from the shell and the site spec alone. This is the
    agreement between the two implementations, pinned."""
    spec, colliders = _flat()
    _write(tmp_path, "shell.glb", _doc(colliders))
    reading = site_collision.read_site(spec, [str(tmp_path)])
    assert reading.complete, reading.unread
    found = {b.name.split("/")[0]: _round(b)[0] for b in reading.boxes}
    assert found == {"b0": (-10.0, -22.0, 0.55), "b1": (35.0, -17.0, 0.55),
                     "b2": (68.0, -17.0, 0.55), "b3": (151.0, 2.0, 0.55)}
    print("  site read: OK (4 cage counters, positions match Level Factory)")


def test_a_building_with_no_geometry_makes_the_site_reading_partial():
    spec = {"buildings": [{"id": "b0", "at": [0, 0], "rot": 0}]}
    reading = site_collision.read_site(spec, [])
    assert not reading.complete and "b0" in reading.unread[0]


def test_one_unreadable_shell_does_not_hide_the_others(tmp_path):
    spec, colliders = _flat()
    spec["buildings"][2]["glb"] = "missing.glb"
    _write(tmp_path, "shell.glb", _doc(colliders))
    reading = site_collision.read_site(spec, [str(tmp_path)])
    assert len(reading.boxes) == 3, "the three readable shells still count"
    assert not reading.complete and "b2" in reading.unread[0]


def test_reading_a_site_is_deterministic(tmp_path):
    spec, colliders = _flat()
    _write(tmp_path, "shell.glb", _doc(colliders))
    a = site_collision.read_site(spec, [str(tmp_path)])
    b = site_collision.read_site(spec, [str(tmp_path)])
    assert a.boxes == b.boxes


# ---------------------------------------------------------------------------
# standing on it
# ---------------------------------------------------------------------------
COUNTER = site_collision.Reading(
    (site_collision.Box("cage_counter_col-convcolonly",
                        (35.0, -17.0, 0.55), (6.0, 1.0, 1.1)),))


def _obstruction(x, y, reading=COUNTER, **kw):
    kw.setdefault("floor", 0.0)
    kw.setdefault("climb", 0.5)
    kw.setdefault("agent_height", 1.8)
    return site_collision.obstruction(reading, x, y, **kw)


def test_the_counter_is_in_the_way():
    hit = _obstruction(35.0, -17.0)
    assert hit is not None and hit.name.startswith("cage_counter")


def test_a_kerb_inside_the_climb_limit_is_not_in_the_way():
    """Half a metre is a step, not a wall. Treating it as an obstruction would
    push hooks off every doorstep on the site."""
    kerb = site_collision.Reading(
        (site_collision.Box("kerb-col", (35.0, -17.0, 0.2), (6.0, 1.0, 0.4)),))
    assert _obstruction(35.0, -17.0, kerb) is None


def test_a_ceiling_above_head_height_is_not_in_the_way():
    roof = site_collision.Reading(
        (site_collision.Box("roof-col", (35.0, -17.0, 3.1), (44.0, 44.0, 0.2)),))
    assert _obstruction(35.0, -17.0, roof) is None


def test_a_low_beam_at_head_height_is_in_the_way():
    beam = site_collision.Reading(
        (site_collision.Box("beam-col", (35.0, -17.0, 1.2), (44.0, 0.4, 0.4)),))
    assert _obstruction(35.0, -17.0, beam) is not None


def test_the_tallest_solid_is_the_one_reported():
    stacked = site_collision.Reading(COUNTER.boxes + (
        site_collision.Box("crate-col", (35.0, -17.0, 0.4), (1.0, 1.0, 0.8)),))
    assert _obstruction(35.0, -17.0, stacked).name.startswith("cage_counter")


def test_clearance_keeps_a_hook_out_of_the_bakes_erosion_band():
    """Touching the geometry is not the test. Recast erodes the walkable
    surface by the agent radius from every obstacle and quantises what is left
    onto a voxel grid, and Level Factory rasterises on a coarser one still --
    so a hook a quarter of a metre off the counter has clear air around it and
    no navmesh polygon beneath it. Same refusal, more confusing route to it."""
    assert site_collision.CLEARANCE >= 0.75
    assert _obstruction(35.0, -17.75) is not None, "inside the erosion band"
    assert _obstruction(35.0, -18.5) is None, "clear of it"
    assert site_collision.obstruction(
        COUNTER, 35.0, -17.75, floor=0.0, climb=0.5, agent_height=1.8,
        margin=0.0) is None, "and margin=0 really is contact only"


def test_covering_reports_every_solid_tallest_last():
    stacked = site_collision.Reading(COUNTER.boxes + (
        site_collision.Box("crate-col", (35.0, -17.0, 0.4), (1.0, 1.0, 0.8)),))
    names = [b.name for b in stacked.covering(35.0, -17.0)]
    assert names[-1].startswith("cage_counter")


# ---------------------------------------------------------------------------
# walking off it
# ---------------------------------------------------------------------------
def test_the_lattice_is_ordered_nearest_first_and_deterministically():
    a = site_collision._lattice(2.0, 0.25)
    assert a == site_collision._lattice(2.0, 0.25)
    dists = [round(math.hypot(dx, dy), 6) for dx, dy in a]
    assert dists == sorted(dists)
    assert dists[0] == 0.25 and max(dists) <= 2.0
    assert (0.0, 0.0) not in a


def test_a_hook_on_clear_floor_is_left_exactly_where_it_is():
    out = site_collision.resolve_onto_floor((10.0, 10.0, 0.0), COUNTER)
    assert out.point == (10.0, 10.0, 0.0)
    assert not out.needed and not out.resolved and out.moved == 0.0


def test_a_hook_on_the_counter_is_walked_to_the_nearest_clear_floor():
    """The move the shipped pack needed: 1.5 m along the counter's short axis,
    which is the shortest offset that clears both the prop and the erosion
    band around it."""
    out = site_collision.resolve_onto_floor((35.0, -17.0, 0.0), COUNTER)
    assert out.needed and out.resolved
    assert (round(out.point[0], 3), round(out.point[1], 3)) == (35.0, -18.5)
    assert round(out.moved, 3) == 1.5
    assert out.blocked_by.startswith("cage_counter")
    print("  resolve: OK (objective walked 1.5 m off the cage counter)")


def test_the_hook_keeps_its_height_and_only_moves_in_the_ground_plane():
    out = site_collision.resolve_onto_floor((35.0, -17.0, 0.0), COUNTER)
    assert out.point[2] == 0.0


def test_a_room_the_hook_belongs_to_is_not_left():
    """A hook names a spot in a particular room. Walking it across the site to
    find open floor trades a blocker for a mission that no longer happens where
    it was designed to -- so being boxed in is reported, not routed around."""
    out = site_collision.resolve_onto_floor(
        (35.0, -17.0, 0.0), COUNTER, bounds=(33.0, -18.0, 37.0, -16.0))
    assert out.needed and not out.resolved
    assert out.point == (35.0, -17.0, 0.0), "left where it was"
    assert "no clear floor" in out.reason


def test_nothing_clear_within_reach_is_reported_rather_than_guessed():
    slab = site_collision.Reading(
        (site_collision.Box("mezzanine-col", (35.0, -17.0, 0.55),
                            (20.0, 20.0, 1.1)),))
    out = site_collision.resolve_onto_floor((35.0, -17.0, 0.0), slab)
    assert out.needed and not out.resolved
    assert out.blocked_by == "mezzanine-col"


def test_resolving_is_deterministic():
    a = site_collision.resolve_onto_floor((35.0, -17.0, 0.0), COUNTER)
    b = site_collision.resolve_onto_floor((35.0, -17.0, 0.0), COUNTER)
    assert a == b


# ---------------------------------------------------------------------------
# what the mission points do about it
# ---------------------------------------------------------------------------
def _route(objective=(35.0, -17.0, 0.9)):
    return {"spawn": (51.0, -5.0, 0.0), "objective": objective,
            "extraction": (117.0, -16.0, 0.0)}


def test_without_geometry_the_lateral_pass_does_not_run_or_pretend_to():
    seated, findings = site_spawns.seat_destinations(_route())
    assert seated["objective"] == (35.0, -17.0, 0.0)
    assert [f["code"] for f in findings] == ["LOT_DESTINATION_RESEATED"]


def test_the_objective_is_seated_and_then_walked_off_the_counter():
    """Both halves of the fix, in the order they happen: the marker's height
    comes down to the floor, and then its footprint comes off the prop. The
    first one alone shipped, and the blocker survived it."""
    seated, findings = site_spawns.seat_destinations(_route(), solids=COUNTER)
    codes = [f["code"] for f in findings]
    assert codes == ["LOT_DESTINATION_RESEATED", "LOT_DESTINATION_RESOLVED"]
    assert (round(seated["objective"][0], 3),
            round(seated["objective"][1], 3),
            seated["objective"][2]) == (35.0, -18.5, 0.0)
    assert "cage_counter" in findings[1]["message"]
    print("  seat + resolve: OK (objective off the counter, both findings)")


def test_a_hook_already_at_floor_height_is_still_checked_for_what_it_stands_in():
    """The exact shape of the failed fix: z was 0, so the height pass had
    nothing to say, and the hook was still standing in the counter."""
    seated, findings = site_spawns.seat_destinations(
        _route(objective=(35.0, -17.0, 0.0)), solids=COUNTER)
    assert [f["code"] for f in findings] == ["LOT_DESTINATION_RESOLVED"]
    assert round(seated["objective"][1], 3) == -18.5


def test_a_hook_with_nowhere_to_go_is_a_major_finding_not_a_silent_move():
    slab = site_collision.Reading(
        (site_collision.Box("mezzanine-col", (35.0, -17.0, 0.55),
                            (20.0, 20.0, 1.1)),))
    seated, findings = site_spawns.seat_destinations(
        _route(objective=(35.0, -17.0, 0.0)), solids=slab)
    assert [f["code"] for f in findings] == ["LOT_DESTINATION_ON_PROP"]
    assert findings[0]["severity"] == "major"
    assert seated["objective"] == (35.0, -17.0, 0.0), "left where it was"


def test_the_room_bounds_are_honoured_when_the_caller_knows_them():
    seated, findings = site_spawns.seat_destinations(
        _route(objective=(35.0, -17.0, 0.0)), solids=COUNTER,
        bounds={"objective": (33.0, -18.0, 37.0, -16.0)})
    assert [f["code"] for f in findings] == ["LOT_DESTINATION_ON_PROP"]
    assert seated["objective"] == (35.0, -17.0, 0.0)


def test_every_mission_point_is_checked_not_just_the_objective():
    solids = site_collision.Reading(COUNTER.boxes + (
        site_collision.Box("dock-col", (117.0, -16.0, 0.55), (6.0, 1.0, 1.1)),))
    _seated, findings = site_spawns.seat_destinations(
        _route(objective=(35.0, -17.0, 0.0)), solids=solids)
    assert [f["code"] for f in findings] == [
        "LOT_DESTINATION_RESOLVED", "LOT_DESTINATION_RESOLVED"]
    assert "objective" in findings[0]["message"]
    assert "extraction" in findings[1]["message"]


def test_a_partial_reading_is_declared_rather_than_trusted():
    """The reason `Reading.complete` exists. Checking hooks against geometry
    with a hole in it and reporting nothing is the same silent emptiness the
    original defect was made of."""
    partial = site_collision.Reading(
        COUNTER.boxes, False, ("b2: shell.glb: geometry file not found",))
    _seated, findings = site_spawns.seat_destinations(
        _route(objective=(35.0, -17.0, 0.0)), solids=partial)
    codes = [f["code"] for f in findings]
    assert codes == ["LOT_DESTINATION_RESOLVED",
                     "LOT_DESTINATION_COLLISION_UNREAD"]
    assert "b2" in findings[-1]["message"]


def test_an_empty_but_complete_reading_says_nothing():
    """"Nothing is in the way" and "I could not look" must never read alike --
    and the confident one has to stay quiet, or the finding means nothing."""
    _seated, findings = site_spawns.seat_destinations(
        _route(objective=(35.0, -17.0, 0.0)), solids=site_collision.Reading())
    assert findings == []


# ---------------------------------------------------------------------------
# end to end: the shape of the shipped failure, through assemble()
# ---------------------------------------------------------------------------
#: The gameplay generator puts the objective marker at its room's exact centre;
#: Deli Counter puts the cage counter at the same centre. That coincidence is
#: the defect, and it is not seed-specific -- it recurs on every building of
#: this archetype, on every seed.
def _cage_site(tmp_path, counter=True):
    half_x, half_y = 12.0, 9.0
    colliders = [("floor-col", (0.0, 0.0, -0.05), (24.0, 18.0, 0.1))]
    if counter:
        colliders.append(("cage_counter_col-convcolonly", (0.0, 0.0, 0.55),
                          (6.0, 1.0, 1.1)))
    _write(tmp_path, "shell.glb", _doc(colliders))
    with open(os.path.join(str(tmp_path), "b0.gameplay.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "level": "b0", "mode": "assault",
            "footprint": [half_x * 2, half_y * 2],
            "markers": [{"name": "attacker_spawn", "type": "attacker_spawn",
                         "x": 0.0, "y": -half_y + 1.0, "z": 0.0},
                        {"name": "objective_0", "type": "objective",
                         "x": 0.0, "y": 0.0, "z": 0.9}],
            "rooms": [{"id": "cashier_cage", "story": 0,
                       "bounds": [-half_x, -half_y, half_x, half_y],
                       "role": "entry"}],
            "objectives": [{"id": "vault", "room": "cashier_cage"}],
            "loot": [], "zones": [], "vertical_links": [], "openings": [],
            "surfaces": [{"node": "slab_0", "material": "Concrete"}],
            "surface_roles": {"slab_0": "floor"}}, f)
    spec = {"name": "cage", "ground": {"size_x": 80, "size_y": 60},
            "buildings": [{"id": "b0", "glb": "shell.glb",
                           "gameplay": "b0.gameplay.json",
                           "at": [0, 0], "rot": 0}],
            "perimeter": {"height": 3},
            "site_markers": [{"type": "extraction", "at": [20, 0]}],
            "mode": "heist", "spawn": "b0", "objective": "b0",
            "extraction": "b0"}
    return _text(tmp_path, "cage.json", json.dumps(spec))


def _hook(walk_text, name):
    """The Godot (x, y, z) of a named LT_* hook in a walk scene."""
    block = walk_text[walk_text.index(f'name="{name}"'):]
    line = [l for l in block.splitlines() if l.startswith("transform")][0]
    nums = [float(v) for v in
            line[line.index("(") + 1:line.rindex(")")].split(",")]
    return tuple(nums[9:12])


def test_assemble_walks_the_objective_off_the_counter_and_says_so(tmp_path):
    """The whole chain in one run: read the shell, find the counter under the
    objective, move the nav hook to floor the bake will agree is walkable, and
    put the reason in the gameplay file the adapter normalises into findings.

    This is the run that used to come back as JOB_PREFLIGHT_REFUSED with
    "LT_ObjectivePoint is sealed off from the crew spawn" -- one blocker, a
    whole evaluation spent, for a marker a metre from where it could stand.
    """
    spec_path = _cage_site(tmp_path)
    out = os.path.join(str(tmp_path), "out")
    result = lot.assemble(spec_path, out, walkable=True)

    data = json.load(open(result["gameplay"], encoding="utf-8"))
    codes = [f.get("code") for f in data["tactical"].get("findings", [])]
    assert "LOT_DESTINATION_RESEATED" in codes, codes
    assert "LOT_DESTINATION_RESOLVED" in codes, codes
    assert data["collision"]["complete"] and data["collision"]["colliders"] == 2

    objective = result["walk_positions"]["objective"]
    assert (round(objective[0], 3), round(objective[1], 3), objective[2]) == (
        0.0, -1.5, 0.0)
    print("  assemble: OK (objective seated and walked 1.5 m off the counter)")


def test_the_scene_carries_one_answer_for_the_objective_not_two(tmp_path):
    """The secondary defect found while wiring this: the walk scene wrote the
    *unseated* point into `objective_pos` and the Player capsule while the LT_*
    hooks got the seated one, so the beacon the player walks to and the point
    the bot paths to were metres apart in a scene that looked internally
    consistent."""
    spec_path = _cage_site(tmp_path)
    out = os.path.join(str(tmp_path), "out")
    result = lot.assemble(spec_path, out, walkable=True)
    text = open(result["walk_scene"], encoding="utf-8").read()

    # lot._v3 maps site (x, y, z) -> Godot (x, z + lift, -y); lift 0 for a
    # destination hook.
    hook = _hook(text, "LT_ObjectivePoint")
    assert hook == (0.0, 0.0, 1.5), hook
    assert "objective_pos = Vector3(0, 0, 1.5)" in text
    # Route_1 IS the objective -- lot builds route = [spawn, objective,
    # extraction]. A waypoint left on the counter fails traversal just as hard.
    route = text[text.index('name="LT_PlayerRoutePoints"'):]
    lines = [l for l in route.splitlines() if l.startswith("transform")]
    assert lines[1].endswith("0, 0, 1.5)"), lines[1]
    print("  walk scene: OK (one seated objective everywhere)")


def test_a_room_with_no_counter_in_it_leaves_the_objective_alone(tmp_path):
    """The control. If the resolve fires on a clear room too, it is not reading
    geometry -- it is just moving things."""
    spec_path = _cage_site(tmp_path, counter=False)
    out = os.path.join(str(tmp_path), "out")
    result = lot.assemble(spec_path, out, walkable=True)
    data = json.load(open(result["gameplay"], encoding="utf-8"))
    codes = [f.get("code") for f in data["tactical"].get("findings", [])]
    assert "LOT_DESTINATION_RESOLVED" not in codes, codes
    assert "LOT_DESTINATION_ON_PROP" not in codes, codes
    assert result["walk_positions"]["objective"] == (0.0, 0.0, 0.0), (
        "seated for height, unmoved in the ground plane")
