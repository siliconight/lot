"""Empty ground is the defect. Moving the enemy was never the fix.

The site these tests were written against had six enemies placed by a rule that
only knew about distance, on a street with nothing in it. Every one of them was
outside the sight range the rule checked and inside the range the fight actually
opens at, and the crew and the enemy shot each other from their spawns across
open asphalt. Pushing the spawns out trades one bad grade for another; putting
something in the asphalt is the fix, and it is Lot's to make because Lot is what
owns the geometry.

The two claims worth pinning hardest here are the ones a plausible-looking
module would get wrong. Cover has to break *both* directions of a sightline,
because the evaluator's clock starts on the first shot by either side. And a
piece that satisfies the geometry can still be the wrong piece -- on a marker,
against a wall, or touching another piece and turning a street into a wall --
so a position is only accepted if it survives the constraints as well.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import site_cover


def rect(x, y, sx, sy):
    return (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)


GROUND = rect(0.0, 0.0, 300.0, 200.0)
CREW = (-60.0, 0.0)
ENEMY = (60.0, 0.0)


def points(**over):
    base = {"LT_PlayerSpawn": CREW, "Enemy_0": ENEMY}
    base.update(over)
    return base


def breaks(a, b, plan, rects=()):
    """Is the line a-b closed once the plan's cover is standing?"""
    solids = list(rects) + [c.rect for c in plan.cover]
    return site_cover.open_span(a, b, solids) < math.dist(a, b) - 1e-6


# ---------------------------------------------------------------------------
# the height the two lines cross at
# ---------------------------------------------------------------------------
def test_the_minimum_cover_height_is_where_the_two_sightlines_cross():
    """Derived, not chosen.

    Each side sights from its eye at the other's chest, so one line descends
    while the other climbs and they meet at the mean. A solid that tall breaks
    both at that one position; anything shorter leaves one side a free shot,
    and a free shot starts the evaluator's clock just the same.
    """
    assert site_cover.MIN_COVER_HEIGHT == 1.2
    assert site_cover.required_height(0.5) == site_cover.MIN_COVER_HEIGHT
    assert site_cover.required_height(0.0) == site_cover.EYE_HEIGHT
    assert site_cover.required_height(1.0) == site_cover.EYE_HEIGHT


def test_a_solid_below_the_crossing_height_has_nowhere_to_stand():
    assert site_cover.break_interval(1.1) is None
    assert site_cover.break_interval(0.5) is None


def test_the_shortest_workable_solid_works_at_exactly_one_place():
    lo, hi = site_cover.break_interval(site_cover.MIN_COVER_HEIGHT)
    assert lo == hi == 0.5


def test_what_lot_actually_builds_breaks_the_line_over_all_of_it():
    """`COVER_HEIGHT` is above the crossing height for a reason.

    At exactly 1.2 m there is one position that works, and a piece that has to
    land within centimetres of a computed point is a piece the first clearance
    rule will veto. Two metres leaves room to satisfy everything else.
    """
    lo, hi = site_cover.break_interval(site_cover.COVER_HEIGHT)
    assert (lo, hi) == (0.0, 1.0)


# ---------------------------------------------------------------------------
# measuring the floor
# ---------------------------------------------------------------------------
def test_an_empty_street_leaves_the_whole_line_open():
    assert site_cover.open_span(CREW, ENEMY, []) == 120.0


def test_a_building_across_the_line_closes_the_part_it_covers():
    assert round(site_cover.open_span(
        CREW, ENEMY, [rect(0.0, 0.0, 20.0, 20.0)]), 6) == 100.0


def test_the_building_you_are_standing_in_is_not_cover_from_itself():
    """A marker that landed indoors would otherwise pass every test on the site."""
    hall = rect(60.0, 0.0, 40.0, 40.0)
    assert site_cover.open_span(CREW, ENEMY, [hall]) == 120.0


def test_overlapping_buildings_are_not_counted_twice():
    solids = [rect(0.0, 0.0, 20.0, 20.0), rect(5.0, 0.0, 20.0, 20.0)]
    assert round(site_cover.open_span(CREW, ENEMY, solids), 6) == 95.0


def test_only_pairs_past_the_opening_range_are_reported_and_longest_first():
    pts = points(Enemy_1=(-20.0, 0.0))
    lines = site_cover.open_sightlines(pts, [], limit=45.0)
    assert [(a, b) for a, b, _pa, _pb, _d in lines] == [
        ("Enemy_0", "LT_PlayerSpawn"), ("Enemy_0", "Enemy_1")]
    assert lines[0][4] > lines[1][4]


def test_a_pair_already_behind_a_building_is_not_an_open_sightline():
    assert site_cover.open_sightlines(
        points(), [rect(0.0, 0.0, 20.0, 20.0)], limit=45.0) == []


# ---------------------------------------------------------------------------
# placing something in it
# ---------------------------------------------------------------------------
def test_cover_is_placed_and_the_line_is_actually_closed_afterwards():
    """The loop that matters: propose, place, re-measure, and it is shut.

    Without the re-measure this module is a plausible coordinate generator.
    """
    plan = site_cover.plan_cover(points(), [], GROUND, opening_range=45.0)
    assert len(plan.cover) == 1
    assert plan.open_lines == []
    assert breaks(CREW, ENEMY, plan)


def test_cover_goes_towards_the_crews_approach_rather_than_the_midpoint():
    """A line broken at its midpoint is fair to both ends, which is the problem.

    The crew walks and the enemy holds ground. Cover a third of the way along
    gives the crew something to move between on its approach.

    Which end is the crew's has to be established rather than assumed: the
    pairs come back in a stable alphabetical order, so `Enemy_0` is the first
    endpoint of this line and biasing towards it would hand the enemy the wall
    to hold and leave the crew crossing the open part.
    """
    plan = site_cover.plan_cover(points(), [], GROUND, opening_range=45.0)
    piece = plan.cover[0]
    assert CREW[0] < piece.x < 0.0, "on the crew's side of the midpoint"


def test_cover_is_never_stood_on_a_mission_marker():
    """The failure this fix could re-introduce, in the shape it would arrive in.

    A crate on a spawn is a spawn inside a solid, which Laser Tag refuses with
    UNREACHABLE_SPAWN -- the exact outcome `site_spawns` exists to prevent.
    """
    pts = points(Objective=(-40.0, 0.0), Extraction=(-38.0, 0.0))
    plan = site_cover.plan_cover(pts, [], GROUND, opening_range=45.0)
    for piece in plan.cover:
        for marker in pts.values():
            assert math.dist((piece.x, piece.y), marker) >= \
                site_cover.MARKER_CLEARANCE


def test_two_pieces_are_never_placed_close_enough_to_be_one_wall():
    """Cover that joins up is a wall, and a wall across a street is a lost route."""
    pts = {"LT_PlayerSpawn": CREW}
    pts.update({f"Enemy_{i}": (60.0, float(i * 4 - 8)) for i in range(5)})
    plan = site_cover.plan_cover(pts, [], GROUND, opening_range=45.0)
    for i, one in enumerate(plan.cover):
        for other in plan.cover[i + 1:]:
            assert math.dist((one.x, one.y), (other.x, other.y)) >= \
                site_cover.COVER_SEPARATION


def test_cover_is_kept_off_the_buildings_so_it_can_never_seal_a_gap():
    """The clearance is what guarantees a piece cannot close an alley.

    Placement runs against footprints grown by their clearance, so a lane too
    narrow to hold a piece with room either side simply refuses one -- and
    refusing is the right answer, because sealing it would cost the map a
    route.
    """
    walls = [rect(0.0, 28.0, 40.0, 40.0), rect(0.0, -28.0, 40.0, 40.0)]
    plan = site_cover.plan_cover(points(), walls, GROUND, opening_range=45.0)
    for piece in plan.cover:
        for solid in walls:
            assert not site_cover._overlaps(
                piece.rect, site_cover._grow(solid, site_cover.BUILDING_CLEARANCE))


def test_measuring_and_placing_are_asked_of_different_rects():
    """The defect that made this module report nine unbreakable lanes on a site
    that was almost entirely empty ground.

    `open_span` ignores a rect containing an endpoint, because a marker indoors
    can see out of its own building. Grow the footprints before measuring and a
    spawn standing a metre clear of a wall falls inside that wall's rect, so the
    building stops counting as an occluder -- a line running straight through
    two of them measures as seventy metres of open street, and then every
    position on it is refused for standing in a building.

    So the caller hands over the walls as built and the room beside them is
    added here. An enemy a metre off the corner of a building the crew is behind
    is not in an open sightline, and cover is not owed for one.
    """
    wall = rect(0.0, 0.0, 30.0, 30.0)
    near = (16.0, 0.0)                      # a metre outside the 15 m half-width
    pts = {"LT_PlayerSpawn": (-60.0, 0.0), "Enemy_0": near}
    assert site_cover.open_sightlines(pts, [wall], limit=45.0) == []
    plan = site_cover.plan_cover(pts, [wall], GROUND, opening_range=45.0)
    assert plan.cover == [] and plan.unbreakable == []


def test_a_lane_with_no_room_in_it_asks_for_a_building_instead_of_a_crate():
    """Silence here would read as "nothing to do" for the worst case there is.

    Two rows of buildings leave a two-metre lane between their clearances, and
    a three-metre piece cannot stand in it anywhere without its face inside the
    band Godot erodes off the navmesh. Squeezing one in would break the
    sightline and cost the map the street, so the answer is a building.
    """
    walls = [rect(0.0, 23.0, 240.0, 40.0), rect(0.0, -23.0, 240.0, 40.0)]
    pts = {"LT_PlayerSpawn": (-60.0, 0.0), "Enemy_0": (60.0, 0.0)}
    plan = site_cover.plan_cover(pts, walls, GROUND, opening_range=45.0)
    codes = [f["code"] for f in site_cover.findings(plan, opening_range=45.0)]
    assert plan.cover == []
    assert len(plan.unbreakable) == 1
    assert "LOT_SIGHTLINE_UNBREAKABLE" in codes


def test_one_piece_is_credited_against_every_line_it_happens_to_break():
    """Re-measuring after each placement is what keeps the street walkable.

    Three enemies clustered behind one another share a lane; a producer placing
    one piece per line would put three crates in it and narrow the route for
    nothing.
    """
    pts = {"LT_PlayerSpawn": CREW}
    pts.update({f"Enemy_{i}": (60.0 + i, 0.0) for i in range(3)})
    plan = site_cover.plan_cover(pts, [], GROUND, opening_range=45.0)
    assert len(plan.cover) < 3
    for name in ("Enemy_0", "Enemy_1", "Enemy_2"):
        assert breaks(CREW, pts[name], plan)


def test_nothing_open_is_nothing_placed():
    plan = site_cover.plan_cover({"LT_PlayerSpawn": CREW, "Enemy_0": (-40.0, 0.0)},
                                 [], GROUND, opening_range=45.0)
    assert plan.cover == []
    assert site_cover.findings(plan, opening_range=45.0) == []


def test_the_budget_is_a_cap_and_what_it_left_open_is_said_out_loud():
    """A silent cap reads as "covered everything" when it was not."""
    pts = {"LT_PlayerSpawn": CREW}
    pts.update({f"Enemy_{i}": (60.0, float(i * 12 - 60)) for i in range(11)})
    plan = site_cover.plan_cover(pts, [], GROUND, opening_range=45.0, limit=2)
    assert len(plan.cover) == 2
    assert plan.open_lines
    codes = [f["code"] for f in site_cover.findings(plan, opening_range=45.0)]
    assert "LOT_SIGHTLINE_OPEN" in codes


# ---------------------------------------------------------------------------
# what gets said about it
# ---------------------------------------------------------------------------
def test_the_placement_finding_names_the_consequence_it_prevented():
    """"Cover placed" is a fact nobody acts on; why it was needed is the finding."""
    plan = site_cover.plan_cover(points(), [], GROUND, opening_range=45.0)
    found = site_cover.findings(plan, opening_range=45.0)
    assert [f["code"] for f in found] == ["LOT_COVER_PLACED"]
    message = found[0]["message"]
    assert "45 m" in message
    assert "first contact" in message
    assert "route" in message


def test_every_cover_finding_is_advisory():
    """Laser Tag is a soft gate. It changes what gets built; it does not refuse.

    A firefight evaluator grading a map down is a design signal, and a producer
    that turned it into a blocker would stop levels existing over tactics.
    """
    pts = {"LT_PlayerSpawn": CREW}
    pts.update({f"Enemy_{i}": (60.0, float(i * 12 - 60)) for i in range(11)})
    plan = site_cover.plan_cover(pts, [], GROUND, opening_range=45.0, limit=2)
    for finding in site_cover.findings(plan, opening_range=45.0):
        assert finding["severity"] in ("minor", "moderate")
        assert finding["category"] == "cover"


# ---------------------------------------------------------------------------
# the site that actually gets built
# ---------------------------------------------------------------------------
import json
import re
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot            # noqa: E402
import site_spawns    # noqa: E402


def _write_glb(tmp_path, name, node_names):
    """A minimal but real .glb: 12-byte header + a JSON chunk."""
    doc = json.dumps({"asset": {"version": "2.0"},
                      "nodes": [{"name": n} for n in node_names]}).encode()
    doc += b" " * (-len(doc) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    blob = struct.pack("<III", 0x46546C67, 2, 12 + len(chunk)) + chunk
    path = os.path.join(str(tmp_path), name)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def _open_site(tmp_path, ids=("b0", "b1"), at=((-70.0, 30.0), (70.0, 30.0))):
    """Two small buildings pushed off to one side of a wide empty plate.

    The shape of the defect this exists for: plenty of ground, nothing standing
    on the part of it the mission crosses.
    """
    half = 8.0
    spec = {"name": "yard", "ground": {"size_x": 220, "size_y": 140},
            "buildings": [{"id": b, "glb": f"{b}.glb",
                           "gameplay": f"{b}.gameplay.json",
                           "at": list(p), "rot": 0}
                          for b, p in zip(ids, at)],
            "paths": [{"from": "b0", "to": "b1", "width": 4}],
            "mode": "heist", "spawn": "b0", "objective": "b1",
            "extraction": "b0"}
    for b in ids:
        _write_glb(tmp_path, f"{b}.glb", ["Shell", "floor-col"])
        with open(os.path.join(str(tmp_path), f"{b}.gameplay.json"), "w",
                  encoding="utf-8") as f:
            json.dump({
                "level": b, "mode": "assault", "footprint": [half * 2, half * 2],
                "markers": [{"name": "objective_0", "type": "objective",
                             "x": 0, "y": 0, "z": 0}],
                "rooms": [{"id": "main", "story": 0,
                           "bounds": [-half, -half, half, half], "role": "entry"}],
                "objectives": [{"id": "vault", "room": "main"}],
                "loot": [], "zones": [], "vertical_links": [], "openings": [],
                "surfaces": [{"node": "slab_0", "material": "Concrete"}],
                "surface_roles": {"slab_0": "floor"}}, f)
    spec_path = os.path.join(str(tmp_path), "yard.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    return spec_path


def _cover_rects_from_scene(text):
    """Cover footprints in *site* space, read back out of the written .tscn.

    Read from the file rather than from the plan on purpose. `_box_node` writes
    a site point as Godot ``(x, height/2, -y)``, and a sign lost in that mapping
    puts every piece on the far side of the street from the line it was placed
    to break -- a mistake the plan cannot see and only the emitted scene shows.
    """
    sizes = {}
    for sid, vec in re.findall(
            r'\[sub_resource type="BoxShape3D" id="([^"]+)"\]\s*\n'
            r'size = Vector3\(([^)]*)\)', text):
        sizes[sid] = [float(v) for v in vec.split(",")]
    out = []
    for name, tr, shape in re.findall(
            r'\[node name="(cover_\d+)" type="StaticBody3D" parent="\."\]\s*\n'
            r'transform = Transform3D\(([^)]*)\)'
            r'[\s\S]*?shape = SubResource\("([^"]+)"\)', text):
        nums = [float(v) for v in tr.split(",")]
        sx, _sy, sz = sizes[shape]
        x, y = nums[9], -nums[11]
        out.append((x - sx / 2, y - sz / 2, x + sx / 2, y + sz / 2))
    return out


def test_the_cover_that_was_planned_is_in_the_scene_that_gets_shipped(tmp_path):
    """End to end, through the emitter, in site space.

    `plan_cover` deciding correctly is worth nothing if the box lands somewhere
    else. This reads the crate back out of the written scene, converts it out of
    the Godot frame, and re-measures the sightlines against it.
    """
    spec_path = _open_site(tmp_path)
    out = os.path.join(str(tmp_path), "out")
    result = lot.assemble(spec_path, out, walkable=True)

    text = open(result["scene"], encoding="utf-8").read()
    rects = _cover_rects_from_scene(text)
    assert rects, "an open yard was built with nothing standing in it"

    spec = json.load(open(spec_path, encoding="utf-8"))
    walk_pos = result["walk_positions"]
    enemies = site_spawns.place_enemies(spec, walk_pos).positions
    crew = tuple(walk_pos["spawn"][:2])
    solids = rects + site_spawns.footprints(spec, margin=0.0)
    for i, (ex, ey, _ez) in enumerate(enemies):
        span = site_cover.open_span(crew, (ex, ey), solids)
        assert span < math.dist(crew, (ex, ey)) - 1e-6, (
            f"Enemy_{i} still sees the crew spawn down {span:.1f} m of open "
            f"ground in the scene that shipped")


def test_the_cover_is_collision_and_not_decoration(tmp_path):
    """A mesh with no shape is a crate the bots walk through and the rifle
    shoots through, which grades exactly like the empty street it replaced."""
    spec_path = _open_site(tmp_path)
    result = lot.assemble(spec_path, os.path.join(str(tmp_path), "out"))
    text = open(result["scene"], encoding="utf-8").read()
    names = re.findall(r'\[node name="(cover_\d+)" type="StaticBody3D"', text)
    assert names
    for name in names:
        assert f'[node name="col" type="CollisionShape3D" parent="./{name}"]' in text
        assert f'[sub_resource type="BoxShape3D" id="BoxShape_{name}"]' in text


def test_the_cover_stands_high_enough_to_break_a_standing_sightline(tmp_path):
    """The height is the whole reason a crate is cover rather than a kerb."""
    spec_path = _open_site(tmp_path)
    result = lot.assemble(spec_path, os.path.join(str(tmp_path), "out"))
    spec = json.load(open(result["gameplay"], encoding="utf-8"))
    placed = spec["cover_plan"]["placed"]
    assert placed
    for piece in placed:
        assert piece["height"] >= site_cover.MIN_COVER_HEIGHT


def test_the_producer_says_what_it_put_in_the_street(tmp_path):
    """Geometry that appears in a scene with no finding behind it reads as a
    bug to the next person who opens it."""
    spec_path = _open_site(tmp_path)
    result = lot.assemble(spec_path, os.path.join(str(tmp_path), "out"))
    codes = [f["code"] for f in result["tactical"]["findings"]]
    assert "LOT_COVER_PLACED" in codes


def test_cover_never_moves_the_ground_it_was_placed_on(tmp_path):
    """`site_extent` sizes the plate from every rect on the site, cover
    included, so a piece placed outside the plate would grow the plate under
    it. Placement keeps the whole footprint inside the ground it was given, and
    this is the assertion that the two modules agree about which rect that is.
    """
    import site_extent
    spec_path = _open_site(tmp_path)
    before = site_extent.resolve(
        json.load(open(spec_path, encoding="utf-8"))).rect
    result = lot.assemble(spec_path, os.path.join(str(tmp_path), "out"))
    text = open(result["scene"], encoding="utf-8").read()
    x0, y0, x1, y1 = before
    for cx0, cy0, cx1, cy1 in _cover_rects_from_scene(text):
        assert x0 <= cx0 and cx1 <= x1 and y0 <= cy0 and cy1 <= y1
