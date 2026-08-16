"""Enemy spawns go on the street, not through the middle of the block.

Guards the defect where Lot's half of the Laser Tag map contract placed enemies
by sampling the straight line crew-spawn -> objective -> extraction and kicking
each sample 1.5 m to the side. On a site with four 44 m shells strung along that
line, all six enemies landed indoors. Every one of them had a slab beneath it,
so nothing that asked "is this floored" objected; Laser Tag asked whether each
one could path to the crew, refused the map with UNREACHABLE_SPAWN, and reported
zero runs after the full 900-second timeout.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot
import site_spawns


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def building(bid, at, footprint=(44.0, 44.0), rot=0):
    return {"id": bid, "at": list(at), "_footprint": list(footprint),
            "rot": rot}


def site(buildings=(), gx=232.0, gy=100.0):
    return {"name": "t", "ground": {"size_x": gx, "size_y": gy},
            "buildings": list(buildings)}


def route(spawn=(51.0, -5.0, 0.0), objective=(35.0, -17.0, 0.9),
          extraction=(117.0, -16.0, 0.0)):
    return {"spawn": spawn, "objective": objective, "extraction": extraction}


def crew_path(positions):
    """The window the opening is judged over, derived the way the search does.

    `opening_engagement_is_fair` takes the stretch of route the crew covers in
    its first second, not the tile it starts on, and `place_enemies` builds
    that with `crew_reaction_path` off the same route it spreads the enemies
    along. A read-back that passed `[spawn]` instead would ask an easier
    question than the search did, and would therefore report a clean opening on
    exactly the maps the search had just been too generous about -- which is
    the one class of defect these read-back tests exist to catch.
    """
    return site_spawns.crew_reaction_path(
        [positions[k] for k in ("spawn", "objective", "extraction")])


#: The real seed the module was written for: four shells along the main axis,
#: the crew starting inside the second one, the objective inside the first.
BAIE_DORE = site([building("b0", (6.0, -10.0), rot=180),
                  building("b1", (51.0, -5.0), rot=180),
                  building("b2", (84.0, -5.0), rot=180),
                  building("b3", (135.0, -10.0))])


# ---------------------------------------------------------------------------
# footprints and ground
# ---------------------------------------------------------------------------
def test_a_footprint_rect_is_the_rect_the_ground_hole_is_cut_from():
    rect = site_spawns.footprint_rect(building("b", (10.0, 20.0), (8.0, 4.0)))
    assert rect == (6.0, 18.0, 14.0, 22.0)


def test_a_quarter_turn_swaps_the_footprint():
    rect = site_spawns.footprint_rect(
        building("b", (0.0, 0.0), (8.0, 4.0), rot=90))
    assert rect == (-2.0, -4.0, 2.0, 4.0)


def test_an_odd_angle_is_bounded_rather_than_approximated():
    """Larger than the building is the harmless direction: it keeps a spawn
    further from a wall than strictly necessary, never closer."""
    rect = site_spawns.footprint_rect(
        building("b", (0.0, 0.0), (10.0, 10.0), rot=45))
    assert rect[2] > 5.0 and rect[3] > 5.0


def test_a_building_with_no_footprint_has_no_rect():
    assert site_spawns.footprint_rect({"id": "b", "at": [0, 0]}) is None


def test_the_ground_rect_is_centred_and_inset():
    assert site_spawns.ground_rect(site(gx=100.0, gy=40.0), margin=1.0) == (
        -49.0, -19.0, 49.0, 19.0)


def test_a_site_with_no_ground_declares_none_rather_than_guessing():
    assert site_spawns.ground_rect({"buildings": []}) is None


# ---------------------------------------------------------------------------
# the defect
# ---------------------------------------------------------------------------
def test_no_enemy_is_left_standing_inside_a_building():
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    rects = site_spawns.footprints(BAIE_DORE)
    assert len(plan.positions) == 6
    for i, (x, y, _z) in enumerate(plan.positions):
        inside = [r for r in rects if r[0] <= x <= r[2] and r[1] <= y <= r[3]]
        assert not inside, f"Enemy_{i} at ({x:.1f}, {y:.1f}) is in {inside}"


def test_every_enemy_stands_on_the_site_ground():
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    ground = site_spawns.ground_rect(BAIE_DORE)
    for i, (x, y, _z) in enumerate(plan.positions):
        assert ground[0] <= x <= ground[2] and ground[1] <= y <= ground[3], (
            f"Enemy_{i} at ({x:.1f}, {y:.1f}) is off the site")


def test_a_spawn_stands_on_the_ground_plane_not_at_an_interpolated_height():
    """The old code took the height from a linear blend of the route's ends, so
    an objective on a 1.1 m counter lifted every enemy between it and the
    extraction off the floor -- markers naming positions in mid-air."""
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    assert {z for _x, _y, z in plan.positions} == {site_spawns.GROUND_Z}


def test_moving_an_enemy_off_the_route_is_reported():
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    codes = [f["code"] for f in plan.findings]
    assert "LOT_ENEMY_SPAWN_PUSHED" in codes
    moved = {i for i, _ in plan.pushed} | {i for i, _ in plan.slid}
    assert moved == set(range(6)), "all six samples fell indoors on this site"


def test_an_enemy_that_cannot_be_placed_is_not_written():
    """A spawn Lot cannot defend is worse than a spawn Lot does not write: the
    first one costs a full evaluation to discover.

    The premise is a shell so large that the nearest street is further out than
    the placer will ever push. It used to be a 98 m shell on a 100 m plate, which
    stopped being unplaceable once the plate grew to carry its content: a 4 m
    street appeared around the building and all six enemies found a home. The
    fact under test is "no clear cell within MAX_PUSH", so the fixture now states
    that in a way no amount of honest ground can undo.
    """
    boxed_in = site([building("b", (0.0, 0.0), (400.0, 400.0))],
                    gx=100.0, gy=100.0)
    plan = site_spawns.place_enemies(
        boxed_in, route(spawn=(0.0, 0.0, 0.0), objective=(10.0, 0.0, 0.0),
                        extraction=(20.0, 0.0, 0.0)))
    assert plan.positions == []
    assert [f["code"] for f in plan.findings] == ["LOT_ENEMY_SPAWN_UNPLACEABLE"]
    assert "6 of 6" in plan.findings[0]["message"]


def test_no_enemy_starts_in_the_crews_lap():
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    spawn = route()["spawn"][:2]
    for i, (x, y, _z) in enumerate(plan.positions):
        assert math.dist((x, y), spawn) >= site_spawns.MIN_STANDOFF, (
            f"Enemy_{i} is on top of the crew")


def test_enemies_are_a_sequence_rather_than_one_stacked_encounter():
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    for i, a in enumerate(plan.positions):
        for b in plan.positions[i + 1:]:
            assert math.dist(a[:2], b[:2]) >= site_spawns.MIN_SEPARATION


def test_an_empty_field_buys_the_crew_its_reaction_time_with_distance():
    """A field with no buildings has no cover to put an enemy behind, so the
    only fair opening left is range. The enemies still spread along the route;
    they just start beyond what a Laser Tag enemy can see."""
    open_site = site()
    plan = site_spawns.place_enemies(open_site, route())
    spawn = route()["spawn"][:2]
    for i, (x, y, _z) in enumerate(plan.positions):
        assert math.dist((x, y), spawn) >= site_spawns.OPENING_RANGE - 1e-6, (
            f"Enemy_{i} can see the crew spawn across open ground")
    xs = sorted(x for x, _y, _z in plan.positions)
    assert xs[0] < 45.0 and xs[-1] > 95.0, "still spread along the route"


def test_a_site_with_no_geometry_at_all_says_it_could_not_check():
    plan = site_spawns.place_enemies({"buildings": []}, route())
    assert "LOT_SPAWN_PLACEMENT_UNCHECKED" in [
        f["code"] for f in plan.findings]
    assert len(plan.positions) == 6, "and still emits the contract"


# ---------------------------------------------------------------------------
# the opening engagement
# ---------------------------------------------------------------------------
def test_a_wall_between_two_points_breaks_the_line():
    rects = [(-5.0, -5.0, 5.0, 5.0)]
    assert not site_spawns.has_line_of_sight((-20.0, 0.0), (20.0, 0.0), rects)
    assert site_spawns.has_line_of_sight((-20.0, 20.0), (20.0, 20.0), rects)


def test_a_building_you_are_standing_in_is_not_your_cover():
    """The crew spawns inside a shell on this site. Counting that shell as an
    occluder would pass every enemy on the map as out of sight, which is the
    reading that let six enemies line up on an open street."""
    rects = [(-5.0, -5.0, 5.0, 5.0)]
    assert site_spawns.has_line_of_sight((0.0, 0.0), (20.0, 0.0), rects)


def test_an_enemy_down_an_open_street_inside_sight_range_is_not_fair():
    """The measured defect. Seed 5320 put Enemy_0 23.0 m from the crew with
    nothing between them; `enemy_sight_range` in the scenario Level Factory runs
    is 35 m, so first contact landed at 0.02 s and 21 of 25 runs ended in a team
    wipe inside ten seconds. Eight metres of MIN_STANDOFF never had a chance."""
    assert not site_spawns.opening_engagement_is_fair(
        (23.0, 0.0), [(0.0, 0.0)], [])


def test_the_same_enemy_behind_a_building_is_fair():
    assert site_spawns.opening_engagement_is_fair(
        (23.0, 0.0), [(0.0, 0.0)], [(10.0, -5.0, 14.0, 5.0)])


def test_and_so_is_one_further_off_than_either_side_can_open_fire():
    """Forty metres used to read as safe, and it is the distance that wiped the
    crew.

    The number this is measured against is the crew's reach, not the enemy's:
    ``LT_BotPlayerController`` carries ``sight_range = 45.0`` and nothing in the
    harness overrides it, so an enemy standing at 40 m in the open is inside the
    range at which the *crew* opens fire -- and Laser Tag stamps first contact on
    the first shot by either side.
    """
    assert not site_spawns.opening_engagement_is_fair(
        (40.0, 0.0), [(0.0, 0.0)], [])
    assert site_spawns.opening_engagement_is_fair(
        (52.0, 0.0), [(0.0, 0.0)], [])


def test_the_sight_range_itself_is_not_a_standoff():
    """45 m used to pass, and it is the same fight as 44 m.

    An enemy at exactly the distance at which the crew acquires it is acquired,
    on the frame the map starts, in both directions. The rule is not "outside
    the range" but "outside it by the ground the crew covers in the second it
    is being given" -- ``LT_BotPlayerController.move_speed = 4.5``, so 4.5 m.
    """
    assert not site_spawns.opening_engagement_is_fair(
        (site_spawns.OPENING_RANGE, 0.0), [(0.0, 0.0)], [])
    assert site_spawns.opening_engagement_is_fair(
        (site_spawns.OPENING_RANGE + site_spawns.OPENING_CLEARANCE, 0.0),
        [(0.0, 0.0)], [])
    assert site_spawns.OPENING_CLEARANCE == (
        site_spawns.CREW_SPEED * site_spawns.REACTION_SECONDS)


def test_no_enemy_can_shoot_the_crew_before_it_has_moved():
    """The whole rule, on the site it was written for."""
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    spawn = route()["spawn"][:2]
    # The window the search used, not the tile. `spawn` is kept because the
    # failure message measures distance from it.
    path = crew_path(route())
    occluders = site_spawns.footprints(BAIE_DORE, margin=0.0)
    assert len(plan.positions) == 6
    for i, (x, y, _z) in enumerate(plan.positions):
        assert site_spawns.opening_engagement_is_fair((x, y), path, occluders), (
            f"Enemy_{i} at ({x:.1f}, {y:.1f}) has the crew in the open "
            f"{math.dist((x, y), spawn):.1f} m away")


def test_moving_an_enemy_for_the_opening_is_reported_separately():
    """Pushed sideways to get out of a building and slid down the route to get
    out of a sightline are different repairs with different causes, and one
    finding covering both would name the wrong one."""
    plan = site_spawns.place_enemies(BAIE_DORE, route())
    standoff = next(f for f in plan.findings
                    if f["code"] == "LOT_ENEMY_SPAWN_STANDOFF")
    assert plan.slid, "this site puts the opening engagement in the open"
    assert "45 m" in standoff["message"], "the range that decides the fight"
    assert "INSTANT_CONTACT" in standoff["message"]


# ---------------------------------------------------------------------------
# what the report says about the map, as opposed to about the placer
# ---------------------------------------------------------------------------
#: Seed 5320 of ``category5_baie_dore_001``, in site space: four 44 m shells
#: along the main axis and a crew spawn sitting on the exact centre of the last
#: one. Read off ``jobs/...lot_assemble...seed_5320/out/site.tscn`` (building
#: origins, Godot ``(x, ., -y)``) and the walk scene's own route markers.
SEED_5320 = site([building("b0", (-103.0, -10.0), rot=180),
                  building("b1", (-38.0, -5.0)),
                  building("b2", (36.0, 0.0)),
                  building("b3", (101.0, 10.0), rot=180)],
                 gx=260.0, gy=100.0)
SEED_5320_ROUTE = route(spawn=(101.0, 10.0, 0.0), objective=(-22.0, 5.5, 0.0),
                        extraction=(-56.0, -11.0, 0.0))


def test_the_standoff_finding_measures_the_map_and_not_only_what_it_moved():
    """The reassuring number was true and about the wrong population.

    ``nearest`` was the minimum over the enemies the placer had *slid*. An
    enemy that never needed moving could not appear in it, however close to the
    crew it stood -- so the one statistic in the report whose job is to say the
    opening is safe was computed over precisely the enemies that were not the
    problem. The run that wiped 25 crews out of 25 carried "nearest now 45.0 m"
    against a scene with an enemy 23 m from the spawn.

    Built with the two populations disjoint on purpose: Enemy_0 is the nearest
    on the map and was never touched, Enemy_1 is the only one that slid. A
    finding that reads either one for the other passes on a site where they
    coincide, which is most of them.
    """
    spawn = (0.0, 0.0)
    occluders = [(14.0, -10.0, 18.0, 10.0)]      # Enemy_0 is behind this
    plan = site_spawns.Placement(
        positions=[(20.0, 0.0, 0.0), (60.0, 0.0, 0.0)],
        slid=[(1, 60.0)])
    standoff = next(
        f for f in site_spawns._findings(plan, 6, site_spawns.MIN_STANDOFF,
                                         spawn, occluders)
        if f["code"] == "LOT_ENEMY_SPAWN_STANDOFF")

    assert "nearest of those now 60.0 m" in standoff["message"], (
        "what the placer moved, still worth saying")
    assert "Enemy_0 at 20.0 m" in standoff["message"], (
        "and what the map is, which is the half that was missing")


def test_the_standoff_finding_still_reports_the_seed_it_was_written_for():
    plan = site_spawns.place_enemies(SEED_5320, SEED_5320_ROUTE)
    spawn = SEED_5320_ROUTE["spawn"][:2]
    standoff = next(f for f in plan.findings
                    if f["code"] == "LOT_ENEMY_SPAWN_STANDOFF")
    index, closest = site_spawns.nearest_enemy(plan.positions, spawn)
    assert f"Enemy_{index} at {closest:.1f} m" in standoff["message"]


def test_the_nearest_enemy_is_the_nearest_enemy_written():
    plan = site_spawns.place_enemies(SEED_5320, SEED_5320_ROUTE)
    spawn = SEED_5320_ROUTE["spawn"][:2]
    index, closest = site_spawns.nearest_enemy(plan.positions, spawn)
    by_hand = min(math.dist(p[:2], spawn) for p in plan.positions)
    assert math.isclose(closest, by_hand)
    assert math.isclose(math.dist(plan.positions[index][:2], spawn), by_hand)


def test_an_empty_plan_has_no_nearest_enemy_rather_than_a_wrong_one():
    assert site_spawns.nearest_enemy([], (0.0, 0.0)) == (None, math.inf)


def test_the_written_positions_are_read_back_and_not_taken_on_trust():
    """The post-condition the run that produced this file did not have.

    `place_enemies` refuses to place an enemy that can see the crew spawn from
    inside the crew's own firing range. This asserts that the positions which
    came *out* of it satisfy the same rule -- the check the search cannot
    perform on itself, because a search whose model of cover is wrong passes
    every candidate on the way in and still writes a map that opens with a shot.
    """
    plan = site_spawns.place_enemies(SEED_5320, SEED_5320_ROUTE)
    spawn = SEED_5320_ROUTE["spawn"][:2]
    # Same window the search judged these candidates against, so this reads
    # back the question that was asked rather than an easier one.
    path = crew_path(SEED_5320_ROUTE)
    occluders = site_spawns.footprints(SEED_5320, margin=0.0)
    assert plan.positions
    for i, point in enumerate(plan.positions):
        assert site_spawns.opening_engagement_is_fair(
            point[:2], path, occluders), (
            f"Enemy_{i} at {point[:2]} is "
            f"{math.dist(point[:2], spawn):.1f} m from the crew in the open")
    assert "LOT_ENEMY_SPAWN_IN_THE_OPEN" not in [
        f["code"] for f in plan.findings]


def test_an_enemy_left_in_the_open_is_reported_as_a_major_rather_than_implied():
    """The finding the seed 5320 run should have carried.

    Built by handing the reporter a plan whose positions did not come from the
    search, which is the shape of every way this can go wrong: a placer with a
    different idea of cover, a scene written by an older build, a later pass
    that moves a spawn after placement. What they have in common is that the
    positions are wrong and nothing upstream knows it.
    """
    spawn = SEED_5320_ROUTE["spawn"][:2]
    occluders = site_spawns.footprints(SEED_5320, margin=0.0)
    plan = site_spawns.Placement(
        positions=[(77.9785, 10.6588, 0.0), (54.7375, 17.3135, 0.0)],
        slid=[(1, 48.4)])
    findings = site_spawns._findings(plan, 6, site_spawns.MIN_STANDOFF,
                                     spawn, occluders)
    exposed = next(f for f in findings
                   if f["code"] == "LOT_ENEMY_SPAWN_IN_THE_OPEN")
    assert exposed["severity"] == "major"
    assert "Enemy_0" in exposed["message"]
    assert "23.0 m" in exposed["message"]


def test_a_fair_opening_that_depends_on_one_wall_says_so():
    """Behind a building at 20 m is fair, and it is fair for a reason that can
    stop being true. The distance belongs in the report either way."""
    spawn = (0.0, 0.0)
    occluders = [(8.0, -10.0, 12.0, 10.0)]
    plan = site_spawns.Placement(positions=[(20.0, 0.0, 0.0)])
    codes = [f["code"] for f in
             site_spawns._findings(plan, 1, site_spawns.MIN_STANDOFF,
                                   spawn, occluders)]
    assert codes == ["LOT_ENEMY_SPAWN_CLOSE"]


def test_a_map_whose_nearest_enemy_is_out_of_range_says_nothing():
    plan = site_spawns.Placement(positions=[(90.0, 0.0, 0.0)])
    assert site_spawns._findings(plan, 1, site_spawns.MIN_STANDOFF,
                                 (0.0, 0.0), []) == []


def test_a_route_that_offers_no_fair_opening_drops_the_enemy_rather_than_lying():
    """A crew spawning in the middle of a bare plate smaller than sight range
    has nowhere fair to put an enemy. Writing one anyway buys a team wipe at
    5 s; writing none says so before the evaluation is spent."""
    bare = site(gx=40.0, gy=40.0)
    plan = site_spawns.place_enemies(
        bare, route(spawn=(0.0, 0.0, 0.0), objective=(5.0, 0.0, 0.0),
                    extraction=(0.0, 5.0, 0.0)))
    assert plan.positions == []
    assert [f["code"] for f in plan.findings] == ["LOT_ENEMY_SPAWN_UNPLACEABLE"]
    assert "45 m" in plan.findings[0]["message"]


def test_a_building_described_by_a_site_record_is_not_invisible():
    """`footprint_rect` read `_footprint` only, while `site_extent` -- the
    reader that sizes the ground and cuts the holes -- also accepts the
    `footprint` key a site record carries. A building described the second way
    had no rect here, so it was neither avoided nor counted as cover."""
    bdef = {"id": "b", "at": [10.0, 20.0], "footprint": [8.0, 4.0]}
    assert site_spawns.footprint_rect(bdef) == (6.0, 18.0, 14.0, 22.0)


def test_zero_enemies_is_zero_enemies_and_no_complaint():
    plan = site_spawns.place_enemies(BAIE_DORE, route(), enemy_count=0)
    assert plan.positions == [] and plan.findings == []


def test_placement_is_deterministic():
    a = site_spawns.place_enemies(BAIE_DORE, route()).positions
    b = site_spawns.place_enemies(BAIE_DORE, route()).positions
    assert a == b


# ---------------------------------------------------------------------------
# what the walk scene actually gets
# ---------------------------------------------------------------------------
def _enemy_vectors(text):
    out = []
    block = text[text.index('name="LT_EnemySpawnPoints"'):
                 text.index('name="LT_ObjectivePoint"')]
    for line in block.splitlines():
        if line.startswith("transform = Transform3D("):
            nums = line[len("transform = Transform3D("):-1].split(",")
            out.append(tuple(float(n) for n in nums[9:12]))
    return out


def test_the_walk_scene_carries_the_placed_positions(tmp_path):
    """The scene is the artifact Laser Tag reads; the plan is only useful if it
    is what got written."""
    body = lot._lasertag_hook_nodes(route(), BAIE_DORE)
    text = "\n".join(body)
    written = _enemy_vectors(text)
    # The plan the TOOL used, asked of the tool. Planning from `route()` here
    # planned against a route `_lasertag_hook_nodes` never uses: it seats the
    # hooks and clears the crew spawn first, and on BAIE_DORE that moves the
    # spawn 23.5 m out of the shell it starts inside, taking all six enemies
    # with it. The 18.5 m disagreement that followed read as the scene losing
    # the plan, and was this line.
    planned = lot._lasertag_hook_plan(route(), BAIE_DORE)["enemies"]
    assert len(written) == len(planned) == 6
    for (gx, gy, gz), (sx, sy, sz) in zip(written, planned):
        # lot._v3 maps site (x, y, z) -> Godot (x, z + lift, -y), lift 1.0 for
        # a spawn marker so a dropped capsule settles rather than clips.
        #
        # Compared to a tolerance rather than by equality because `_v3` writes
        # through `{:g}`, which keeps six significant figures. On a coordinate
        # tens of metres out that is a tenth of a millimetre, and rounding an
        # already-rounded number to three places disagrees with rounding the
        # original whenever the seventh figure sits on a half. The contract is
        # that the scene carries the planned position, not that a float
        # survives two roundings in the same direction.
        for got, want in zip((gx, gy, gz), (sx, sz + 1.0, -sy)):
            assert math.isclose(got, want, abs_tol=1e-3), (got, want)


def test_a_hook_body_without_a_site_spec_still_meets_the_contract():
    """`_lasertag_hook_nodes` is called from more than one place and must not
    require geometry it might not be given."""
    text = "\n".join(lot._lasertag_hook_nodes(route()))
    for hook in ("LT_PlayerSpawn", "LT_EnemySpawnPoints", "LT_ObjectivePoint",
                 "LT_PlayerRoutePoints", "LT_CoverTestPoints"):
        assert f'name="{hook}"' in text
    assert text.count('parent="LT_EnemySpawnPoints"') == 6


# ---------------------------------------------------------------------------
# nav hooks stand on the floor, props do not have to
# ---------------------------------------------------------------------------
def test_a_marker_on_the_floor_is_left_alone():
    pos = route(objective=(35.0, -17.0, 0.0))
    seated, findings = site_spawns.seat_destinations(pos)
    assert seated == pos and findings == []


def test_a_kerb_height_marker_is_left_alone():
    """Half a metre is a step, not a counter -- an agent walks onto it."""
    seated, findings = site_spawns.seat_destinations(
        route(objective=(35.0, -17.0, 0.5)))
    assert seated["objective"] == (35.0, -17.0, 0.5)
    assert findings == []


def test_an_objective_on_a_counter_is_seated_on_the_floor():
    """The real defect: a 0.9 m marker on a 1.1 m counter in a room whose
    floor is 0, with no step between, and a 0.5 m climb limit."""
    seated, findings = site_spawns.seat_destinations(
        route(objective=(35.0, -17.0, 0.9)))
    assert seated["objective"] == (35.0, -17.0, site_spawns.GROUND_Z)
    assert [f["code"] for f in findings] == ["LOT_DESTINATION_RESEATED"]
    assert "0.90 m above the floor" in findings[0]["message"]


def test_seating_moves_the_hook_and_not_the_x_and_y():
    """It is the same objective, reachable -- not a different objective."""
    seated, _ = site_spawns.seat_destinations(
        route(objective=(35.0, -17.0, 1.4)))
    assert seated["objective"][:2] == (35.0, -17.0)


def test_a_storey_up_is_reported_rather_than_dropped_through_the_floor():
    """Lot has no storey model. Seating a second-floor objective to z=0 would
    put the nav hook in the room below -- a worse defect, and a silent one."""
    seated, findings = site_spawns.seat_destinations(
        route(objective=(35.0, -17.0, 4.2)))
    assert seated["objective"] == (35.0, -17.0, 4.2), "unmoved"
    assert [f["code"] for f in findings] == ["LOT_DESTINATION_ABOVE_FLOOR"]


def test_every_mission_point_is_checked_not_just_the_objective():
    """An extraction on a loading dock strands the crew at the end of the run
    exactly as an objective on a counter strands it in the middle."""
    seated, findings = site_spawns.seat_destinations(
        route(spawn=(0.0, 0.0, 1.1), objective=(35.0, -17.0, 0.0),
              extraction=(117.0, -16.0, 1.1)))
    assert seated["spawn"][2] == site_spawns.GROUND_Z
    assert seated["extraction"][2] == site_spawns.GROUND_Z
    assert seated["objective"][2] == 0.0, "already floored, left alone"
    assert [f["code"] for f in findings] == [
        "LOT_DESTINATION_RESEATED", "LOT_DESTINATION_RESEATED"]


def test_the_walk_scene_objective_hook_is_the_seated_one():
    """The scene is the artifact Laser Tag reads."""
    text = "\n".join(lot._lasertag_hook_nodes(
        route(objective=(35.0, -17.0, 0.9)), BAIE_DORE))
    block = text[text.index('name="LT_ObjectivePoint"'):]
    line = [l for l in block.splitlines() if l.startswith("transform")][0]
    # lot._v3 maps site (x, y, z) -> Godot (x, z + lift, -y); lift 0 here.
    assert line.endswith("35, 0, 17)"), line


def test_the_route_point_that_is_the_objective_is_seated_too():
    """Route_1 IS the objective: lot builds route = [spawn, objective,
    extraction]. If seating missed it, Laser Tag would still fail traversal on
    a waypoint standing on the same counter."""
    text = "\n".join(lot._lasertag_hook_nodes(
        route(objective=(35.0, -17.0, 0.9)), BAIE_DORE))
    block = text[text.index('name="LT_PlayerRoutePoints"'):]
    lines = [l for l in block.splitlines() if l.startswith("transform")]
    assert lines[1].endswith("35, 0, 17)"), lines[1]
