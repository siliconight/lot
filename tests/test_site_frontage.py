"""A building close to a sidewalk meets it: the walk is paved to the face.

The fixture is cold run 9052's candidate site (`bank_block_001`, seed 9052) as
Level Factory 0.84.0 wrote it, footprints as `merge_gameplay` annotates them
from Deli Counter's gameplay files: a bank 2.15 m behind the sidewalk's back
edge, a strip-retail shop 4.15 m behind it and a country club 13.15 m behind
it, each with a 4 m door spur. Before the frontage, the plate between the bank
and its sidewalk was bare asphalt except for the spur, and the walker read the
spur's edges as a dogleg in the paved edge.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_steps     # noqa: E402
import site_streets   # noqa: E402
import site_surfaces  # noqa: E402

Y_ROAD = -31.150000005960464
WALK_BACK = Y_ROAD + 5.0 + 3.0          # -23.15: the north band's back edge


def spec_9052():
    return {
        "name": "site",
        "ground": {"size_x": 157, "size_y": 83},
        "buildings": [
            {"id": "b0", "at": [-51, -10], "rot": 0, "_footprint": [30.0, 22.0]},
            {"id": "b1", "at": [4, -10], "rot": 270, "_footprint": [18.0, 14.0]},
            {"id": "b2", "at": [45, 10], "rot": 270, "_footprint": [40.0, 28.0]},
        ],
        "paths": [
            {"from": "b1", "to": "b2", "width": 8.0},
            {"a": [-51.0, -22.150000005960464], "b": [-51.0, -23.600000005960464], "width": 4.0},
            {"a": [4.0, -20.150000005960464], "b": [4.0, -23.600000005960464], "width": 4.0},
            {"a": [45.0, -11.150000005960464], "b": [45.0, -23.600000005960464], "width": 4.0},
        ],
        "roads": [
            {"a": [-78.5, Y_ROAD], "b": [78.5, Y_ROAD], "sidewalk": 3.0, "width": 10.0},
            {"a": [-19.5, Y_ROAD], "b": [-19.5, 39.5], "sidewalk": 3.0, "width": 10.0},
        ],
    }


def _rect(fr, roads_list):
    road = next(r for r in roads_list if r.index == fr.road)
    return tuple(round(v, 6) for v in fr.rect(road))


def test_the_close_buildings_get_a_frontage_and_the_set_back_one_does_not():
    spec = spec_9052()
    rl = site_streets.roads(spec)
    found = []
    frs = site_streets.frontages(spec, rl, found)
    assert found == []
    got = {fr.building: (fr.road, fr.side, _rect(fr, rl), round(fr.depth, 6))
           for fr in frs}
    assert len(frs) == 2
    # the bank's south face is y = -21, the shop's y = -19; both run the
    # building's full width from the band's back edge to the face
    assert got["b0"] == (0, "L", (-66.0, round(WALK_BACK, 6), -36.0, -21.0), 2.15)
    assert got["b1"] == (0, "L", (-3.0, round(WALK_BACK, 6), 11.0, -19.0), 4.15)
    # 13.15 m is deeper than a parked car's space: a lot, with its door path
    assert "b2" not in got
    assert site_streets.FRONTAGE_MAX == site_streets.BAY_LENGTH


def _paved(tscn):
    """Walkable boxes the scene wrote, less the plate itself, in Godot plan."""
    return [s for s in site_steps.surfaces(tscn) if not s["name"].startswith("Ground")]


def _inside(px, pz, corners):
    sign = 0
    for i in range(4):
        (ax, az), (bx, bz) = corners[i], corners[(i + 1) % 4]
        cross = (bx - ax) * (pz - az) - (bz - az) * (px - ax)
        if abs(cross) < 1e-9:
            continue
        s = 1 if cross > 0 else -1
        if sign and s != sign:
            return False
        sign = s
    return True


def _write_scene(spec):
    body, sub = lot._outdoor_nodes(spec)
    fd, path = tempfile.mkstemp(suffix=".tscn")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write('[gd_scene format=3]\n\n' + "\n".join(sub) + "\n"
                 + '[node name="Site" type="Node3D"]\n\n' + "\n".join(body))
    return path


def test_the_strip_in_front_of_a_close_building_is_paved_edge_to_edge():
    """Read off the EMITTED scene: every point between the sidewalk's back
    edge and the bank's face, across the bank's width, stands on a paved
    surface, and the same for the shop. On Lot 0.70.0 only the spurs did:
    244 of these 276 samples were bare plate."""
    path = _write_scene(spec_9052())
    try:
        paved = _paved(path)
    finally:
        os.remove(path)
    bare = []
    for bid, x0, x1, face in (("b0", -66.0, -36.0, -21.0), ("b1", -3.0, 11.0, -19.0)):
        x = x0 + 0.5
        while x < x1:
            y = WALK_BACK + 0.05
            while y < face:
                if not any(_inside(x, -y, s["corners"]) for s in paved):
                    bare.append((bid, round(x, 2), round(y, 2)))
                y += 0.5
            x += 1.0
    assert bare == [], f"{len(bare)} bare samples, first {bare[:5]}"
    tops = {s["name"]: s["top"] for s in paved if s["name"].startswith("frontage_")}
    assert len(tops) == 2
    assert all(abs(t - lot.FRONTAGE_THICK) < 1e-6 for t in tops.values())


def test_between_buildings_the_paved_edge_steps_square_at_the_corner():
    """Beside the shop the plate is still the lot: the paved edge follows the
    sidewalk's back edge, and turns 90 degrees at the building's side."""
    path = _write_scene(spec_9052())
    try:
        paved = _paved(path)
    finally:
        os.remove(path)

    def on(x, y):
        return any(_inside(x, -y, s["corners"]) for s in paved)

    y = WALK_BACK + 1.0
    assert on(10.9, y) and not on(11.1, y)          # the shop's east side
    assert on(-2.9, y) and not on(-3.1, y)          # its west side
    assert not on(20.0, y)                          # the lot beyond it


def test_no_frontage_where_a_face_does_not_run_along_the_road():
    spec = spec_9052()
    spec["buildings"][0]["rot"] = 45                # an enclosing box is not a face
    assert "b0" not in {f.building for f in
                        site_streets.frontages(spec, site_streets.roads(spec))}
    spec = spec_9052()
    spec["roads"][0]["b"] = [78.5, Y_ROAD + 20.0]   # a road off the plan axes
    assert all(f.road != 0 for f in
               site_streets.frontages(spec, site_streets.roads(spec)))
    spec = spec_9052()
    for b in spec["buildings"]:
        b.pop("_footprint")                         # nothing measured, nothing paved
    assert site_streets.frontages(spec, site_streets.roads(spec)) == []


def test_a_frontage_that_would_overlap_something_else_is_dropped_and_said():
    spec = spec_9052()
    # a kiosk standing in the bank's frontage strip
    spec["buildings"].append({"id": "kiosk", "at": [-50, -22.2], "rot": 0,
                              "_footprint": [2.0, 1.0]})
    found = []
    frs = site_streets.frontages(spec, site_streets.roads(spec), found)
    assert "b0" not in {f.building for f in frs}
    assert any("LOT_FRONTAGE_BLOCKED" in f and "b0" in f and "kiosk" in f
               for f in found)


def test_a_frontage_is_offered_to_dressing_as_sidewalk():
    spec = spec_9052()
    zones, _ = site_surfaces.zones(spec)
    fz = [z for z in zones if z["surface_zone_id"].startswith("frontage_")]
    assert len(fz) == 2
    assert all(z["kind"] == "sidewalk" and "zone_family:sidewalk" in z["tags"]
               for z in fz)
    b0 = next(z for z in fz if "building:b0" in z["tags"])
    x0, y0, _z0, x1, y1, _z1 = b0["aabb"]
    assert (round(x0, 6), round(y0, 6), round(x1, 6), round(y1, 6)) == \
        (-66.0, round(WALK_BACK, 6), -36.0, -21.0)


def test_the_markings_manifest_names_each_frontage():
    m = site_streets.manifest(spec_9052())
    assert [(f["building"], f["depth"]) for f in m["frontages"]] == \
        [("b0", 2.15), ("b1", 4.15)]


def test_a_corner_building_has_its_corner_paved():
    """A shop east of the cross street, 2.15 m behind the through road's
    sidewalk and 3.0 m beside the cross street's: both strips, and the
    square between them behind both bands, so the walk wraps the corner."""
    spec = spec_9052()
    # the cross street's east band's back edge is x = -11.5; the shop's west
    # face 3.0 m from it, its south face at y = -21.0
    spec["buildings"] = [{"id": "corner", "at": [0.5, -10.0], "rot": 0,
                          "_footprint": [18.0, 22.0]}]
    spec["paths"] = []
    rl = site_streets.roads(spec)
    frs = site_streets.frontages(spec, rl)
    rects = sorted(_rect(fr, rl) for fr in frs)
    assert rects == [
        (-11.5, round(WALK_BACK, 6), 9.5, -21.0),       # along road 0, run on to the cross street's band
        (-11.5, -21.0, -8.5, 1.0),                      # along the cross street
    ]
    path = _write_scene(spec)
    try:
        paved = _paved(path)
    finally:
        os.remove(path)
    y = WALK_BACK + 1.0
    x = -11.4
    while x < -8.5:                                     # the corner square
        assert any(_inside(x, -y, s["corners"]) for s in paved), (x, y)
        x += 0.25
