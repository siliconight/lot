"""The ground has to be where the site is.

Every test here is a form of one question: does the plate Lot lays down carry
the buildings Lot places on it? For the whole life of the outdoor builder the
answer was "if the spec happened to centre its row on the origin", because five
separate places read `size_x / 2` and assumed the rest.

The fixture is the real one. `category5_baie_dore_001` seed 5219 placed four
44 m shells at x = -6, 39, 93 and 138 under a plate declared 232 x 100. The
centred reading laid that plate across x -116..116, the last building hung 44 m
off the +x rim, its ground hole was clipped out of existence without a word,
and the crew spawned on that building's interior floor with no site ground
within 22 m. Laser Tag correctly reported every enemy, the objective and the
extraction as unreachable and graded the map BROKEN on zero completed runs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot                     # noqa: E402
import site_extent as SX       # noqa: E402


def building(bid, at, footprint=(44.0, 44.0), rot=0):
    return {"id": bid, "at": list(at), "_footprint": list(footprint), "rot": rot}


#: The site that produced this module, as the spec Level Factory wrote it.
BAIE_DORE = {
    "name": "category5_baie_dore_001",
    "ground": {"size_x": 232, "size_y": 100},
    "buildings": [building("b0", (-6.0, 10.0), rot=180),
                  building("b1", (39.0, 5.0)),
                  building("b2", (93.0, 0.0)),
                  building("b3", (138.0, -10.0), rot=180)],
}

#: The crew spawn from that run, in site coordinates. Godot showed it at
#: (138, 1, -10); Lot's frame is (x, y) with y = -z.
CREW_SPAWN = (138.0, -10.0)


# ---------------------------------------------------------------------------
# the defect
# ---------------------------------------------------------------------------
def test_the_plate_is_extended_to_carry_the_row_it_was_built_for():
    ground = SX.resolve(BAIE_DORE)
    assert ground.extended, "the plate that broke this site came back unchanged"
    x0, y0, x1, y1 = ground.rect
    # b3 spans x 116..160; the plate has to reach past it with clearance.
    assert x1 >= 160.0 + SX.CLEARANCE
    # Growth is one-directional: the west rim was already far enough out and
    # must not be pulled in, because ground already laid is ground already
    # walked on.
    assert x0 <= -116.0
    assert y0 <= -50.0 and y1 >= 50.0


def test_the_crew_spawn_stands_on_ground():
    """The whole failure, in one assertion."""
    ground = SX.resolve(BAIE_DORE)
    assert ground.contains(CREW_SPAWN), (
        f"crew spawn {CREW_SPAWN} is off the plate {ground.rect} -- this is the "
        "island the run started on")


def test_the_declared_plate_did_not_contain_the_crew_spawn():
    """Guard the guard: if the fixture ever stops reproducing the defect, these
    tests pass for the wrong reason."""
    declared = SX.declared_rect(BAIE_DORE)
    assert declared == (-116.0, -50.0, 116.0, 50.0)
    assert not SX.contains(declared, CREW_SPAWN)


def test_the_finding_names_the_buildings_that_were_off_the_plate():
    codes = [f["code"] for f in SX.resolve(BAIE_DORE).findings]
    assert SX.CODE_EXTENDED in codes
    message = next(f["message"] for f in SX.resolve(BAIE_DORE).findings
                   if f["code"] == SX.CODE_EXTENDED)
    assert "b3" in message, message
    assert "232 x 100" in message, message


def test_a_plate_with_the_area_and_not_the_position_is_reported_separately():
    """232 x 100 was big enough for a site 192 x 68. Growing it here fixes the
    level; naming the offset is what fixes whatever wrote the spec."""
    findings = {f["code"]: f["message"] for f in SX.resolve(BAIE_DORE).findings}
    assert SX.CODE_OFF_CENTRE in findings
    assert "centred at (0, 0)" in findings[SX.CODE_OFF_CENTRE]


def test_a_plate_that_is_genuinely_too_small_is_not_called_off_centre():
    spec = {"ground": {"size_x": 10, "size_y": 10},
            "buildings": [building("b0", (0.0, 0.0))]}
    codes = [f["code"] for f in SX.resolve(spec).findings]
    assert SX.CODE_EXTENDED in codes
    assert SX.CODE_OFF_CENTRE not in codes, (
        "a 10 m plate under a 44 m building is the wrong size, not the wrong "
        "place, and saying both sends someone looking for a bug that isn't there")


# ---------------------------------------------------------------------------
# the plate that was already right
# ---------------------------------------------------------------------------
def test_a_plate_that_already_covers_its_site_is_left_exactly_alone():
    """Twenty missions in the library were built on centred rows. None of them
    may move, and none of them may acquire a finding."""
    spec = {"ground": {"size_x": 200, "size_y": 120},
            "buildings": [building("b0", (-45.0, 0.0)),
                          building("b1", (0.0, 0.0)),
                          building("b2", (45.0, 0.0))]}
    ground = SX.resolve(spec)
    assert ground.rect == SX.declared_rect(spec)
    assert not ground.extended
    assert ground.findings == []


def test_a_site_with_no_ground_declares_none_rather_than_guessing():
    ground = SX.resolve({"buildings": [building("b0", (0.0, 0.0))]})
    assert ground.rect is None
    assert ground.findings == []


def test_a_ground_with_no_content_keeps_its_declared_rect():
    spec = {"ground": {"size_x": 60, "size_y": 40}, "buildings": []}
    assert SX.resolve(spec).rect == (-30.0, -20.0, 30.0, 20.0)


def test_an_explicit_ground_position_is_honoured():
    """The convention was never written down; a spec that says where its plate
    sits should not have to fight the assumption that it is centred."""
    spec = {"ground": {"size_x": 40, "size_y": 20, "at": [100.0, 0.0]}}
    assert SX.declared_rect(spec) == (80.0, -10.0, 120.0, 10.0)


# ---------------------------------------------------------------------------
# reading the content
# ---------------------------------------------------------------------------
def test_a_quarter_turn_swaps_the_footprint_the_ground_has_to_carry():
    spec = {"ground": {"size_x": 10, "size_y": 10},
            "buildings": [building("b", (0.0, 0.0), (40.0, 10.0), rot=90)]}
    x0, y0, x1, y1 = SX.resolve(spec).rect
    assert (x1 - x0, y1 - y0) == (10.0 + 2 * SX.CLEARANCE,
                                  40.0 + 2 * SX.CLEARANCE)


def test_an_odd_angle_is_bounded_rather_than_approximated():
    rect = SX.rotated_footprint(building("b", (0.0, 0.0), (10.0, 10.0), rot=45))
    assert rect[2] > 5.0, "the enclosing box of a turned building is larger"


def test_a_building_with_no_readable_footprint_is_reported_not_assumed():
    spec = {"ground": {"size_x": 60, "size_y": 40},
            "buildings": [{"id": "b0", "at": [0, 0]}]}
    findings = SX.resolve(spec).findings
    assert [f["code"] for f in findings] == [SX.CODE_UNKNOWN_EXTENT]
    assert "b0" in findings[0]["message"]
    # Sized from the origin, so the plate is not claimed to reach walls it
    # never measured -- the caveat travels with the number.
    assert SX.resolve(spec).rect == (-30.0, -20.0, 30.0, 20.0)


def test_paths_roads_courtyards_cover_and_markers_all_count_as_content():
    spec = {"ground": {"size_x": 20, "size_y": 20},
            "buildings": [],
            "courtyards": [{"at": [40.0, 0.0], "size_x": 10, "size_y": 10}],
            "cover": [{"at": [0.0, 40.0], "size": [2.0, 1.0, 2.0]}],
            "roads": [{"a": [-60.0, 0.0], "b": [-50.0, 0.0], "width": 9.0}],
            "site_markers": [{"type": "extraction", "at": [0.0, -70.0]}]}
    x0, y0, x1, y1 = SX.resolve(spec).rect
    assert x1 >= 45.0 + SX.CLEARANCE       # courtyard
    assert y1 >= 41.0 + SX.CLEARANCE       # cover
    assert x0 <= -64.5 - SX.CLEARANCE      # road, including its width
    assert y0 <= -70.0 - SX.CLEARANCE      # extraction marker


def test_growth_lands_on_whole_metres():
    spec = {"ground": {"size_x": 10, "size_y": 10},
            "buildings": [building("b", (0.3, -0.7), (20.4, 20.6))]}
    for value in SX.resolve(spec).rect:
        assert value == int(value), f"{value} is not a whole metre"


def test_an_absurd_span_is_a_blocker_and_still_gets_its_ground():
    spec = {"ground": {"size_x": 100, "size_y": 100},
            "buildings": [building("b0", (0.0, 0.0)),
                          building("b1", (5000.0, 0.0))]}
    ground = SX.resolve(spec)
    codes = [f["code"] for f in ground.findings]
    assert SX.CODE_UNREASONABLE in codes
    assert ground.contains((5000.0, 0.0)), (
        "a blocking finding is more use than a void: the ground is still built")


# ---------------------------------------------------------------------------
# the clip that used to be silent
# ---------------------------------------------------------------------------
def test_a_hole_outside_the_plate_is_a_blocking_finding():
    findings = SX.hole_findings((-10.0, -10.0, 10.0, 10.0),
                                [(20.0, 20.0, 30.0, 30.0)])
    assert [f["code"] for f in findings] == [SX.CODE_HOLE_OUTSIDE]
    assert findings[0]["severity"] == "blocker"


def test_a_hole_straddling_the_rim_is_a_blocking_finding_too():
    """The half-outside case is the dangerous one: the clipped hole still looks
    like a hole, so the tile list is plausible and the void is real."""
    findings = SX.hole_findings((-10.0, -10.0, 10.0, 10.0),
                                [(5.0, -5.0, 15.0, 5.0)])
    assert [f["code"] for f in findings] == [SX.CODE_HOLE_OUTSIDE]


def test_the_resolved_plate_contains_every_hole_that_will_be_cut():
    floors = {b["id"] for b in BAIE_DORE["buildings"]}
    holes = lot.ground_holes(BAIE_DORE, floors)
    assert len(holes) == 4, "one hole per floored building, none dropped"
    assert SX.hole_findings(SX.resolve(BAIE_DORE).rect, holes) == []


def test_the_old_reading_dropped_a_hole_entirely():
    """What the defect looked like from inside `_ground_tiles`: cut four holes
    in the centred plate and only three survive, with nothing to say so."""
    holes = lot.ground_holes(BAIE_DORE, {b["id"] for b in BAIE_DORE["buildings"]})
    centred = SX.declared_rect(BAIE_DORE)
    survived = [h for h in holes
                if h[0] < centred[2] and h[2] > centred[0]
                and h[1] < centred[3] and h[3] > centred[1]]
    assert len(survived) == 3
    assert SX.hole_findings(centred, holes)


# ---------------------------------------------------------------------------
# the tiles, end to end
# ---------------------------------------------------------------------------
def _tile_under(tiles, point):
    return [t for t in tiles
            if t[0] <= point[0] <= t[2] and t[1] <= point[1] <= t[3]]


def _touch(a, b):
    """Do two tiles share a border of non-zero length? Corners don't count."""
    if abs(a[2] - b[0]) < 1e-9 or abs(b[2] - a[0]) < 1e-9:        # vertical seam
        return min(a[3], b[3]) - max(a[1], b[1]) > 1e-9
    if abs(a[3] - b[1]) < 1e-9 or abs(b[3] - a[1]) < 1e-9:        # horizontal seam
        return min(a[2], b[2]) - max(a[0], b[0]) > 1e-9
    return False


def _reachable(tiles, start):
    """Every tile joined to `start` through shared borders."""
    seen, stack = {start}, [start]
    while stack:
        cur = stack.pop()
        for t in tiles:
            if t not in seen and _touch(cur, t):
                seen.add(t)
                stack.append(t)
    return seen


def test_the_crew_spawn_is_joined_to_the_rest_of_the_site_by_ground():
    """The end-to-end form of the fix: from the real spec, through the real hole
    policy, to a surface the crew can walk off b3 and across the site on.

    The question is not "is there ground 25 m out in each direction" -- b2 stands
    one metre west of b3, so west of the crew spawn is a neighbour's floor and
    always will be. It is whether the strip of ground the inset leaves around b3
    joins the open plate the objective and the enemies stand on.
    """
    floors = {b["id"] for b in BAIE_DORE["buildings"]}
    ground = SX.resolve(BAIE_DORE)
    tiles = set(lot._ground_tiles(ground.rect, lot.ground_holes(BAIE_DORE, floors)))
    far_west = _tile_under(tiles, (ground.rect[0] + 1.0, 0.0))
    assert far_west, "the west rim of the plate carries no ground"
    # b3 spans x 116..160, y -32..12: step off its south wall, and squeeze into
    # the one-metre gap between it and b2. Both have to lead somewhere.
    for label, probe in (("south of b3", (CREW_SPAWN[0], -33.0)),
                         ("the gap west of b3", (115.5, -19.0))):
        doorstep = _tile_under(tiles, probe)
        assert doorstep, f"no ground {label} -- the crew step into the void"
        assert far_west[0] in _reachable(tiles, doorstep[0]), (
            f"the ground {label} is an island: it does not join the ground the "
            "objective and the enemies stand on")


def test_the_old_plate_left_the_crew_spawn_surrounded_by_nothing():
    floors = {b["id"] for b in BAIE_DORE["buildings"]}
    tiles = lot._ground_tiles(SX.declared_rect(BAIE_DORE),
                              lot.ground_holes(BAIE_DORE, floors))
    assert not _tile_under(tiles, (CREW_SPAWN[0] + 25.0, CREW_SPAWN[1]))
    # and nothing to step onto off b3's south wall either
    assert not _tile_under(tiles, (CREW_SPAWN[0], -33.0))


def test_tiles_never_overlap_a_hole():
    floors = {b["id"] for b in BAIE_DORE["buildings"]}
    ground = SX.resolve(BAIE_DORE)
    holes = lot.ground_holes(BAIE_DORE, floors)
    for t in lot._ground_tiles(ground.rect, holes):
        cx, cy = (t[0] + t[2]) / 2, (t[1] + t[3]) / 2
        for h in holes:
            assert not (h[0] < cx < h[2] and h[1] < cy < h[3]), (
                f"tile {t} sits over hole {h}")


def test_the_tiles_tile_the_plate():
    """Area conservation: tiles + holes = plate, so no strip is quietly missing."""
    ground = SX.resolve(BAIE_DORE)
    floors = {b["id"] for b in BAIE_DORE["buildings"]}
    holes = lot.ground_holes(BAIE_DORE, floors)
    tiles = lot._ground_tiles(ground.rect, holes)
    area = lambda r: (r[2] - r[0]) * (r[3] - r[1])            # noqa: E731
    plate = area(ground.rect)
    covered = sum(area(t) for t in tiles) + sum(area(h) for h in holes)
    assert abs(plate - covered) < 1e-6, (
        f"plate {plate} vs tiles+holes {covered}")


# ---------------------------------------------------------------------------
# one extent, read by everyone
# ---------------------------------------------------------------------------
def test_the_spawn_placer_reads_the_same_extent_as_the_scene_builder():
    import site_spawns
    inset = site_spawns.ground_rect(BAIE_DORE, margin=1.0)
    rect = SX.resolve(BAIE_DORE).rect
    assert inset == (rect[0] + 1.0, rect[1] + 1.0, rect[2] - 1.0, rect[3] - 1.0)


def test_the_perimeter_wall_rings_the_ground_that_was_built():
    spec = dict(BAIE_DORE, perimeter={"height": 3.0})
    body, _sub = lot._outdoor_nodes(spec, self_flooring=set())
    text = "\n".join(body)
    x0, _y0, x1, _y1 = SX.resolve(spec).rect
    assert f"{x1:g}," in text and f"{x0:g}," in text, (
        "the wall is still drawn at plus or minus half the declared size")


# ---------------------------------------------------------------------------
# two shells on the same ground
# ---------------------------------------------------------------------------
def test_the_real_row_does_not_overlap_itself():
    assert SX.overlap_findings(BAIE_DORE) == []


def test_a_row_spaced_narrower_than_its_shells_is_blocked():
    """44 m shells 42 m apart interpenetrate by 2 m. Nothing in Lot compared two
    footprints before, so this assembled and reported a clean site."""
    tight = dict(BAIE_DORE, buildings=[building("b0", (0.0, 0.0)),
                                       building("b1", (42.0, 0.0))])
    found = SX.overlap_findings(tight)
    assert [f["severity"] for f in found] == ["blocker"]
    assert found[0]["code"] == SX.CODE_OVERLAP
    assert "b0" in found[0]["message"] and "b1" in found[0]["message"]
    assert "2.0 m into each other" in found[0]["message"]


def test_shells_that_merely_touch_are_reported_not_gated():
    """A terrace is a choice. The gate is for a wall standing in a room."""
    grazing = dict(BAIE_DORE, buildings=[building("b0", (0.0, 0.0)),
                                         building("b1", (43.8, 0.0))])
    found = SX.overlap_findings(grazing)
    assert [f["severity"] for f in found] == ["minor"]


def test_neighbours_that_clear_each_other_say_nothing():
    clear = dict(BAIE_DORE, buildings=[building("b0", (0.0, 0.0)),
                                       building("b1", (45.0, 0.0))])
    assert SX.overlap_findings(clear) == []


def test_a_quarter_turn_can_separate_two_shells_or_join_them():
    """Overlap is measured on the rotated footprint, not the declared one."""
    pair = [building("b0", (0.0, 0.0), (40.0, 10.0)),
            building("b1", (0.0, 20.0), (40.0, 10.0))]
    assert SX.overlap_findings(dict(BAIE_DORE, buildings=pair)) == []
    pair[1]["rot"] = 90                       # now 10 wide and 40 deep
    found = SX.overlap_findings(dict(BAIE_DORE, buildings=pair))
    assert [f["severity"] for f in found] == ["blocker"]


def test_an_unmeasurable_building_is_not_reported_as_clear():
    """The overlap check can only speak about footprints it can read; the extent
    resolver is where an unreadable one is named, and it still is."""
    murky = dict(BAIE_DORE, buildings=[building("b0", (0.0, 0.0)),
                                       {"id": "b1", "at": [1.0, 0.0], "rot": 0}])
    assert SX.overlap_findings(murky) == []
    assert any(f["code"] == SX.CODE_UNKNOWN_EXTENT
               for f in SX.resolve(murky).findings)


if __name__ == "__main__":
    import traceback
    failed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok  {name}")
            except Exception:
                failed += 1
                print(f"  FAIL {name}")
                traceback.print_exc()
    print("site_extent:", "OK" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
