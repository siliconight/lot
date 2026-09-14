"""Dressing stands on the surface under it, at that surface's height.

Cold run 9052 (`bank_block_001`, seed 9052): every one of the 4,909 surface
dressing instances in the shipped `bank_block_001_dressing.tscn` had origin
y = 0, because `site_surfaces` declared every zone at z 0 and the planner
wrote pos[2] = 0. Read back against the StaticBody3D boxes of the scene they
were placed on, 2,500 stood more than 5 mm below its top: 1,648 inside a
0.0974 m sidewalk band, 739 in the road (0.010), 64 in a path (0.012), 49 in
a kerb cut (0.010). And 627 stood on a different family's slab from the one
their zone names: placed at their zone's own surface, 618 would still have
been more than 5 mm off.

`site_surfaces.tops` declares the slabs, from the functions the scene is
drawn with. These tests hold it to the EMITTED scene, so a slab drawn and not
declared, declared and not drawn, or declared at the wrong height or place,
fails here rather than burying a pebble.

THE READER HERE IS NOT `site_steps.surfaces`, AND THAT IS A FINDING. The first
version of this file used it, and it failed on every diagonal path with the
declared slab mirrored across the plan x axis from the one it read. The two
disagreed, so one was wrong, and Godot settled it: `str_to_var` on 9052's
`path_0` literal, `Transform3D(0.898768, 0, -0.438424, 0, 1, 0, 0.438424, 0,
0.898768, 24.5, 0.005, -0)`, gives `basis.x = (0.898768, 0, 0.438424)` -- the
literal is ROW-major, local +X is (n0, n3, n6). `site_steps.surfaces` takes
(n0, n1, n2), the transpose, which for a pure yaw is the mirror. Axis-aligned
slabs are symmetric under it, which is why nothing on a street caught it.
So the reader below is row-major, as the engine is, and the declaration
follows what the engine draws.

0.72.1: `site_steps.surfaces` reads row-major too, and the drawing writes the
plan angle as its yaw, so the literal above is now written
`Transform3D(0.898768, 0, 0.438424, 0, 1, 0, -0.438424, 0, 0.898768, ...)`
and the path lies where its endpoints say. The reader below stays separate
from `site_steps` on purpose: a test that reads the scene with the checker's
own code cannot catch the checker.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_steps     # noqa: E402
import site_surfaces  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Y_ROAD = -31.150000005960464

#: `_box_node` writes with %g, six significant figures: -22.8855 is as close
#: as a scene coordinate gets to the float it came from.
SCENE_DIGITS_M = 2e-3


def spec_9052():
    """Cold run 9052's candidate, footprints annotated (as test_site_frontage)."""
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


def spec_pawn():
    """Diagonal paths, a courtyard, no roads (coldrun_pawn_job's shape)."""
    return {
        "name": "fixture",
        "ground": {"size_x": 150, "size_y": 110},
        "buildings": [
            {"id": "garage", "at": [-48, -28], "rot": 0, "_footprint": [20.0, 14.0]},
            {"id": "deli", "at": [-6, 18], "rot": 90, "_footprint": [20.0, 14.0]},
            {"id": "pawn", "at": [32, -22], "rot": 0, "_footprint": [20.0, 14.0]},
        ],
        "paths": [
            {"from": "garage", "to": "deli", "width": 5},
            {"from": "deli", "to": "pawn"},
        ],
        "courtyards": [{"at": [12, -2], "size_x": 22, "size_y": 16}],
    }


def spec_kerb_probe():
    with open(os.path.join(HERE, "specs", "coldrun_kerb_probe.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _scene_surfaces(spec):
    """Walkable boxes of the emitted scene: {name, top, corners}, corners in
    Godot plan (x, z), reading `Transform3D(...)` ROW-major as Godot does."""
    body, sub = lot._outdoor_nodes(spec)
    src = ('[gd_scene format=3]\n\n' + "\n".join(sub) + "\n"
           + '[node name="Site" type="Node3D"]\n\n' + "\n".join(body))
    shapes = {m.group(1): [float(v) for v in m.group(2).split(",")]
              for m in site_steps._SHAPE.finditer(src)}
    out = []
    for m in site_steps._BOX.finditer(src):
        name = m.group(1)
        if not name.startswith(site_steps.WALKABLE_PREFIXES):
            continue
        n = [float(v) for v in m.group(2).split(",")]
        rows, o = (n[0:3], n[3:6], n[6:9]), n[9:12]
        if abs(rows[1][1] - 1.0) > 1e-9:
            raise AssertionError(f"{name}: basis is not a pure yaw")
        hx, hy, hz = (v / 2 for v in shapes[m.group(4)])
        corners = []
        for sx in (-hx, hx):
            for sz in (-hz, hz):
                corners.append((rows[0][0] * sx + rows[0][2] * sz + o[0],
                                rows[2][0] * sx + rows[2][2] * sz + o[2]))
        out.append({"name": name, "top": o[1] + hy, "corners": corners})
    assert out, "no walkable boxes read; the scene shape was not recognised"
    return out


def _slab_corners(s):
    """Plan corners of a declared slab, by `TOPS_RULE`'s axes."""
    import math
    r = math.radians(s["yaw_deg"])
    u = (math.cos(r), math.sin(r))
    v = (math.sin(r), -math.cos(r))
    hx, hy = s["size"][0] / 2, s["size"][1] / 2
    cx, cy = s["centre"]
    return [(cx + a * hx * u[0] + b * hy * v[0], cy + a * hx * u[1] + b * hy * v[1])
            for a in (-1, 1) for b in (-1, 1)]


def _same_corners(a, b):
    return all(any(abs(p[0] - q[0]) <= SCENE_DIGITS_M and abs(p[1] - q[1]) <= SCENE_DIGITS_M
                   for q in b) for p in a)


def _check_against_scene(spec):
    drawn = _scene_surfaces(spec)
    declared = site_surfaces.tops(spec)
    by_name = {s["name"]: s for s in declared}
    plates = [s for s in declared if s["family"] == "ground"]
    assert len(plates) == 1
    plate = plates[0]
    names = set()
    for d in drawn:
        # the scene's plan is Godot (x, z); the declaration's is spec (x, y)
        corners = [(x, -z) for x, z in d["corners"]]
        if d["name"].startswith("Ground"):
            assert abs(d["top"] - plate["top_m"]) < 1e-6, d["name"]
            xs = [c[0] for c in _slab_corners(plate)]
            ys = [c[1] for c in _slab_corners(plate)]
            assert all(min(xs) - SCENE_DIGITS_M <= x <= max(xs) + SCENE_DIGITS_M
                       and min(ys) - SCENE_DIGITS_M <= y <= max(ys) + SCENE_DIGITS_M
                       for x, y in corners), d["name"]
            continue
        names.add(d["name"])
        assert d["name"] in by_name, f"{d['name']} is drawn and not declared"
        s = by_name[d["name"]]
        assert abs(d["top"] - s["top_m"]) < 1e-5, (d["name"], d["top"], s["top_m"])
        assert _same_corners(corners, _slab_corners(s)), (d["name"], corners, _slab_corners(s))
    undrawn = {s["name"] for s in declared if s["family"] != "ground"} - names
    assert not undrawn, f"declared and not drawn: {sorted(undrawn)}"
    return drawn, declared


def test_every_slab_the_street_draws_is_declared_where_and_as_high_as_it_is():
    drawn, declared = _check_against_scene(spec_9052())
    fams = {s["family"] for s in declared}
    assert {"road", "sidewalk", "kerbcut", "path", "frontage", "ground"} <= fams


def test_diagonal_paths_and_courtyards_are_declared_as_drawn():
    """The declaration follows the slab the scene holds, yaw included --
    not a re-derivation from the path's endpoints."""
    _, declared = _check_against_scene(spec_pawn())
    assert any(s["family"] == "path" and s["yaw_deg"] % 90 for s in declared)
    assert any(s["family"] == "courtyard" for s in declared)


def test_the_kerb_probe_spec_is_declared_as_drawn():
    _check_against_scene(spec_kerb_probe())


def test_the_top_under_a_point_is_the_surface_a_body_would_stand_on():
    """Points on cold run 9052's bank front, plan metres."""
    slabs = site_surfaces.tops(spec_9052())
    top = lambda x, y: site_surfaces.surface_top((x, y), slabs)   # noqa: E731
    assert top(-60.0, -24.65) == round(lot.SIDEWALK_H, 5)        # north band
    assert top(-19.5, -24.65) == round(lot.ROAD_THICK, 5)        # its kerb cut
    assert top(0.0, Y_ROAD) == round(lot.ROAD_THICK, 5)          # the road
    assert top(-60.0, -37.65) == round(lot.SIDEWALK_H, 5)        # south band
    assert top(-26.0, 0.0) == round(lot.SIDEWALK_H, 5)           # cross street band
    assert top(-60.0, -22.0) == round(lot.FRONTAGE_THICK, 5)     # bank frontage
    # the door spur runs under the band and inside the frontage: the highest
    # face is what shows, and what a pebble lies on
    assert top(-51.0, -23.4) == round(lot.SIDEWALK_H, 5)
    assert top(-51.0, -22.5) == round(lot.FRONTAGE_THICK, 5)
    assert top(-70.0, 30.0) == round(lot.PLATE_TOP, 5)           # bare plate
    assert top(500.0, 500.0) is None                             # off the site


def test_a_zone_names_the_top_of_its_own_surface():
    zones, _ = site_surfaces.zones(spec_9052())
    step = site_surfaces.capsule_block()["unassisted_step_max_m"]

    def lo(prefix):
        got = {z["aabb"][2] for z in zones if z["surface_zone_id"].startswith(prefix)}
        assert len(got) == 1, (prefix, got)
        return got.pop()

    assert lo("sidewalk_") == round(lot.SIDEWALK_H, 5)
    assert lo("frontage_") == round(lot.FRONTAGE_THICK, 5)
    assert lo("road_") == round(lot.ROAD_THICK, 5)
    assert lo("path_") == round(lot.PATH_THICK, 5)
    assert lo("open_ground") == round(lot.PLATE_TOP, 5)
    for z in zones:
        assert abs(z["aabb"][5] - z["aabb"][2] - step) < 1e-5


def test_the_surfaces_file_carries_the_slabs_and_the_rule(tmp_path):
    spec_path = tmp_path / "site.json"
    spec_path.write_text(json.dumps(spec_9052()), encoding="utf-8")
    out = tmp_path / "surfaces.json"
    assert site_surfaces.main([str(spec_path), "--out", str(out),
                               "--base-dir", ""]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["tops_rule"] == site_surfaces.TOPS_RULE
    assert {"name", "family", "centre", "size", "yaw_deg", "top_m"} == set(doc["tops"][0])
    assert any(s["family"] == "sidewalk" and s["top_m"] == round(lot.SIDEWALK_H, 5)
               for s in doc["tops"])
