"""A parking field in a gap between buildings (Lot 0.94.0)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lot  # noqa: E402
import site_extent  # noqa: E402
import site_fields as SF  # noqa: E402
import site_furniture  # noqa: E402
import site_landuse  # noqa: E402
import site_steps  # noqa: E402
import site_streets  # noqa: E402
import site_surfaces  # noqa: E402

#: A through road along x, its L kerb the north one: carriageway y -19..-9,
#: sidewalk to y = -6, the back of walk.
_ROAD = {"a": [-40, -14], "b": [40, -14], "width": 10.0, "sidewalk": 3.0}
_B0 = {"id": "b0", "at": [-25, 0], "rot": 0, "_footprint": [20, 10]}    # x -35..-15, y -5..5
_B1 = {"id": "b1", "at": [25, 0], "rot": 0, "_footprint": [20, 10]}     # x 15..35


def _site(bldgs=(_B0, _B1), roads=(_ROAD,), **kw):
    s = {"name": "t", "ground": {"size_x": 100, "size_y": 80},
         "buildings": [dict(b) for b in bldgs], "roads": [dict(r) for r in roads], "paths": []}
    s.update(kw)
    return s


def _plan(site, ground=None, standing=()):
    rects = {b["id"]: site_extent.rotated_footprint(b) for b in site["buildings"]}
    return SF.plan_fields(site, site_streets.roads(site), site_surfaces.tops(site), rects,
                          standing=standing, ground=ground)


def _with_fields(site, fields):
    site = dict(site)
    site["fields"] = fields
    site["driveways"] = [f["driveway"] for f in fields]
    return site


def test_a_gap_between_two_storefronts_takes_one_field_centred_and_as_deep_as_they_are():
    """The gap is x -15..15, 30 m; the field is 9 + 24 + 9 ft x 2 = 18.3 m
    along it, centred, and its bays run back from the walk at y = -6 until
    the buildings' back faces at y = 5 stop them: 11 m holds four 2.7 m bays."""
    (f,) = _plan(_site())
    assert f["road"] == 0 and f["side"] == "L" and f["bays"] == 4
    x0, y0, x1, y1 = f["rect"]
    assert abs(x0 + 9.15) < 1e-6 and abs(x1 - 9.15) < 1e-6
    assert abs(y0 + 6.0) < 1e-6 and abs(y1 - (-6.0 + 4 * 2.7)) < 1e-6
    d = f["driveway"]
    assert d["a"] == [0.0, -9.0] and d["b"] == [0.0, -6.0] and d["width"] == 7.3


def test_a_gap_too_narrow_takes_none():
    b1 = dict(_B1, at=[12, 0])                                     # gap x -15..2, 17 m
    assert _plan(_site(bldgs=(_B0, b1))) == []


def test_the_driveway_keeps_fifteen_metres_from_a_junction():
    """A side street ending on the road's south kerb at x = 0: its box is
    x -6..6, and a driveway anywhere in the gap is nearer than 15 m to it, so
    no field. Moved to x = -40 (box -46..-34) the driveway is 30 m off and
    the field stands."""
    south = {"a": [0, -14], "b": [0, -40], "width": 8.0, "sidewalk": 2.0}
    assert _plan(_site(roads=(_ROAD, south))) == []
    south2 = dict(south, a=[-40, -14], b=[-40, -40])
    (f,) = _plan(_site(roads=(dict(_ROAD, a=[-50, -14]), south2)))
    assert f["side"] == "L"


def test_the_plate_s_edge_a_walk_and_what_stands_bound_its_depth():
    (f,) = _plan(_site(), ground=(-50.0, -40.0, 50.0, 0.0))        # 0.5 m in from y = 0
    assert f["bays"] == 2                                          # 5.4 m of 5.5 m
    walk = {"from": "b0", "to": "b1", "a": [-15.0, 1.0], "b": [15.0, 1.0], "width": 1.5,
            "drawn": True}
    (g,) = _plan(_site(paths=[walk]))
    assert g["rect"][3] <= 0.25 + 1e-6 and g["bays"] == 2          # stops short of the walk's edge
    assert _plan(_site(), standing=[(-1.0, -4.0, 1.0, -2.0)]) == []  # a piece on its first row


def test_the_driveway_drops_the_kerb_and_is_not_a_crossing():
    site = _site()
    (f,) = _plan(site)
    rl = site_streets.roads(_with_fields(site, [f]))
    road = rl[0]
    (cut,) = [c for c in road.kerb("L").cuts if c.kind == "driveway"]
    assert abs(cut.t - 40.0) < 1e-6 and abs(cut.width - 7.3) < 1e-9
    assert road.kerb("R").cuts == []                               # it never reaches the far kerb
    assert all(c.kind != "driveway" for c in road.crossings)       # nor the centre line
    marks = site_streets.markings(rl)
    assert not [m for m in marks if m["kind"] in ("crosswalk_bar", "stop_bar")]
    for bay in site_streets.bays(road):                            # no kerb car across it
        assert bay["side"] != "L" or bay["t1"] <= 40.0 - 3.65 or bay["t0"] >= 40.0 + 3.65


def test_a_driveway_gets_none_of_a_crossing_s_corner_furniture():
    """The control: a walk cutting the same kerb at the same station and
    width gets its hydrant, bin and blade post. The driveway gets none."""
    site = _site()
    (f,) = _plan(site)
    # a cut's own pieces are tagged with its station (`breaks`: crossing@t)
    walk = dict(f["driveway"], drawn=True)
    rl_walk = site_streets.roads(_site(paths=[walk]))
    with_walk = site_furniture.plan_furniture(rl_walk, site["buildings"], [], [])
    corner = sorted(p["species"] for p in with_walk if p["breaks"] == "crossing@40.0")
    assert corner == ["fire_hydrant", "litter_bin", "sign_post"]
    rl = site_streets.roads(_with_fields(site, [f]))
    got = site_furniture.plan_furniture(rl, site["buildings"], [], [])
    assert [p for p in got if str(p.get("breaks", "")).startswith("crossing@")] == []


def test_no_car_stands_within_twelve_metres_of_an_enemy_spawn():
    """4.0 m/s for 3.0 s: an enemy at the field's corner empties every bay
    whose car's edge is nearer than 12 m to it, and only those."""
    site = _site()
    (f,) = _plan(site)
    rl = site_streets.roads(_with_fields(site, [f]))
    every = SF.plan_cars([f], rl)
    enemy = (f["rect"][2], f["rect"][3])                          # the field's far corner
    kept = SF.plan_cars([f], rl, enemies=[enemy])

    def edge(c):
        sx, _h, sy = c["size"]
        dx = max(abs(enemy[0] - c["at"][0]) - sx / 2, 0.0)
        dy = max(abs(enemy[1] - c["at"][1]) - sy / 2, 0.0)
        return (dx * dx + dy * dy) ** 0.5
    assert all(edge(c) >= 12.0 for c in kept)
    assert kept == [c for c in every if edge(c) >= 12.0]
    assert len(kept) < len(every)


def test_cars_park_nose_in_in_a_share_of_the_bays_and_keep_clear():
    site = _site()
    (f,) = _plan(site)
    rl = site_streets.roads(_with_fields(site, [f]))
    cars = SF.plan_cars([f], rl)
    assert 0 < len(cars) < 16 and cars == SF.plan_cars([f], rl)
    x0, y0, x1, y1 = f["rect"]
    for c in cars:
        sx, _h, sy = c["size"]
        assert x0 - 1e-6 <= c["at"][0] - sx / 2 and c["at"][0] + sx / 2 <= x1 + 1e-6
        assert y0 - 1e-6 <= c["at"][1] - sy / 2 and c["at"][1] + sy / 2 <= y1 + 1e-6
        assert c["yaw"] in (90.0, 270.0) and c["species"] == "simple_car"
        # nose in: a car before the aisle points -x, one after it +x
        # (`site_parking.nose`: yaw 90 points plan +x)
        nose = 1.0 if c["yaw"] == 90.0 else -1.0
        assert (c["at"][0] > 0) == (nose > 0)
        assert c["dims"][1] <= 5.5 and c["dims"][0] <= 2.7
    # a marker in the field: no car within 3 m of it
    m = (cars[0]["at"][0], cars[0]["at"][1])
    for c in SF.plan_cars([f], rl, markers=[m]):
        sx, _h, sy = c["size"]
        assert not (c["at"][0] - sx / 2 - 3.0 <= m[0] <= c["at"][0] + sx / 2 + 3.0
                    and c["at"][1] - sy / 2 - 3.0 <= m[1] <= c["at"][1] + sy / 2 + 3.0)


def test_the_bay_lines_are_painted_inside_the_field():
    site = _site()
    (f,) = _plan(site)
    marks = SF.markings([f], site_streets.roads(site))
    assert len(marks) == 2 * (f["bays"] + 1)
    x0, y0, x1, y1 = f["rect"]
    for m in marks:
        along, across = m["size"]
        assert along == 5.5 and across == 0.12
        assert x0 <= m["at"][0] - along / 2 + 1e-6 and m["at"][0] + along / 2 <= x1 + 1e-6
        assert y0 <= m["at"][1] - across / 2 + 1e-6 and m["at"][1] + across / 2 <= y1 + 1e-6


def test_a_field_is_drawn_declared_walked_on_painted_and_counted():
    site = _site()
    fields = _plan(site)
    spec = _with_fields(site, fields)
    body, _sub = lot._outdoor_nodes(spec)
    assert any(line.startswith('[node name="field_0"') for line in body)
    assert sum(1 for line in body if line.startswith('[node name="fmark_')) == 2 * (fields[0]["bays"] + 1)
    (slab,) = lot.field_slabs(spec)
    assert slab["family"] == "parking" and abs(slab["top"] - lot.ROAD_THICK) < 1e-9
    assert "field_" in site_steps.WALKABLE_PREFIXES and "parking" in lot.SKIN_FAMILIES
    import test_site_surface_tops as T
    T._check_against_scene(spec)
    c = site_landuse.census(spec)
    assert abs(c["areas"]["parking"] - 18.3 * 10.8) <= 18.0        # a cell row of slack a side
    assert c["unknown_families"] == []
    man = site_streets.manifest(spec)
    assert sum(1 for m in man["markings"] if m["kind"] == "bay_line") == 2 * (fields[0]["bays"] + 1)
