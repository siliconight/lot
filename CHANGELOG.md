## [0.32.0] - the distance was the symptom, the empty ground was the defect

0.31.0 fixed an unfair opening by moving the enemy. That is the cheapest
available response to "these two can see each other" and it is almost never the
right one: push a spawn far enough and the map still grades badly, now for a
first contact past the ceiling and a crew that walks a minute before it meets
anything. The site is no better than it was. What made the opening unfair was
that two markers could see each other across ninety metres of empty ground, and
the fix for empty ground is to put something in it.

Which makes it Lot's job. A firefight evaluator can say a map plays badly and it
cannot place a crate, because it does not own the geometry. Lot does. So the
evaluator's finding is a **soft gate** here -- it never refuses a build, it
changes what the build contains.

### `site_cover.py`

Measures which pairs of mission markers can see each other across more open
ground than the engagement opens at -- the sniping question, asked of the floor
rather than of the spawns -- and then decides where along each line a solid
would break it.

A sightline is two lines, not one. Each side sights from its own eye at the
other's chest, so the crew's outgoing line descends and the enemy's incoming
line climbs and they cross in the middle. A solid tall enough to break one can
sit under the other, and half a broken sightline is not half a fix: first
contact is stamped on the first shot by *either* side. `required_height(t)` is
the taller of the two demands at each point along the line, and
`break_interval()` is the span where a piece of a given height clears both.

Placement refuses the positions that look fine on paper and are not: cover
overlapping a building, cover standing on a marker, cover inside another piece
(`COVER_SEPARATION`), cover off the walkable ground. Where nothing on open
ground will do, that is reported rather than forced -- `LOT_SIGHTLINE_UNBREAKABLE`
is a request for a building, and no amount of street furniture answers it.

Pieces land in `site_spec["cover"]`, which already had an emitter, so they reach
the `.tscn` as the same axis-aligned blockout geometry Deli Counter produces and
the navmesh bake sees them as the collision they are. Nothing new to consume
them; the geometry is real from the first run.

### `OPENING_RANGE` is 45, and it says why in the file

`SIGHT_RANGE = 35.0` was the enemy's number from
`default_laser_tag_scenario.tres`, correctly read and only half the engagement.
`LT_BotPlayerController` carries `@export var sight_range: float = 45.0`, ten
metres past the enemy it is hunting, and nothing overrides it --
`LT_MapEvalHarness` assigns `brain.sight_range` from the scenario and has no
matching line for the crew's bot. So the crew sees first, fires first, and
`LT_MetricsCollector.record_shot` stamps `time_to_first_contact` on that shot. An
enemy 39 m out was outside every number Lot was checking and inside the only one
that decided the clock.

Worse than a mis-stamped clock: `_advance_route` lives in the `else` of "can I
see an enemy". One visible enemy is 0% route completion by construction, on
every seed, which is exactly what five seeds had been reporting.

`OPENING_RANGE = 45.0` now, with the derivation written next to it. `SIGHT_RANGE`
survives as an alias so a caller that reads it gets the number that decides the
fight rather than the one that used to be there. It remains a stated assumption
in the sense `DEFAULT_FOOTPRINT` is -- Lot cannot read a `.tres` -- and Level
Factory's `lasertag_contract` now reads the real Laser Tag files and reports
drift against what is written here, so this going stale is a finding rather than
another five-seed run of wipes.

### findings

`LOT_COVER_PLACED` (minor), `LOT_SIGHTLINE_UNBREAKABLE` (moderate),
`LOT_SIGHTLINE_OPEN` (minor). All advisory, all describing a level that exists.

232 tests.

## [0.31.0] - eight metres of standoff against thirty-five metres of sight

Twenty-one of twenty-five matches ended in a team wipe inside ten seconds, on
every seed, with first contact logged at 0.02 s. The map was not hard. The crew
was being shot before it could take a step, and the number that allowed it had
been sitting in this file since enemy spawns existed:

    MIN_STANDOFF = 8.0

Eight metres was chosen by eye. `enemy_sight_range = 35.0` in Laser Tag's
`default_laser_tag_scenario.tres`, read at `LT_MapEvalHarness.gd:477` as
`brain.sight_range = scenario.enemy_sight_range`. The two numbers live in
different repos and had never been compared. Lot was placing enemies four times
closer than the distance at which they open fire and then reporting the placement
as correct, because by its own rule it was.

### the rule the number was standing in for

An opening engagement is fair iff the enemy is beyond sight range of the crew
spawn **or** a building stands between the two. Distance was never the mechanism;
it was one of two ways to get the same outcome, and the cheaper one on a dense
street is usually the wall.

`opening_engagement_is_fair()` states exactly that, and
`has_line_of_sight()` answers the second half by Liang-Barsky slab clipping of
the crew-to-enemy segment against the raw building footprints. A rect containing
either endpoint is skipped: you are not hidden by the building you are standing
in, and a crew that spawns indoors must not be scored as covered by its own
walls.

`MIN_STANDOFF` survives as a floor, no longer as the rule. `SIGHT_RANGE = 35.0`
is a stated assumption in the sense `DEFAULT_FOOTPRINT` is -- Lot cannot import
a `.tres`, so the number is written down with its source next to it rather than
guessed at again in six months.

### moving a spawn by the smallest change, not by loop order

Where the designed position is unfair there are two ways out: push the spawn
perpendicular off the route, or slide it further along the route. The first
implementation tried every perpendicular offset up to `MAX_PUSH = 80` before it
tried sliding, and that is not a tie-break, it is loop order deciding the answer
-- a spawn walked thirty-two metres out into a field to escape a sightline the
next block along would have broken for free.

`_candidates()` now prices both in the same unit, metres of deviation
(`slide + max(0, |offset| - lateral)`), and yields them cheapest first. The
placer takes the first candidate that is outdoors, clear of the standoff floor,
clear of its neighbours, and fair. On BAIE_DORE all six enemies place, none are
dropped, and the two that sit inside 35 m of the crew are both behind buildings.

`LOT_ENEMY_SPAWN_STANDOFF` (minor) reports the along-route slides separately from
`LOT_ENEMY_SPAWN_PUSHED`, because they are different facts about the level: one
says a spawn was inside a wall, the other says the opening was unwinnable.
`LOT_ENEMY_SPAWN_UNPLACEABLE` now states the full rule it failed, so a dropped
enemy says which of the two conditions no position on the route could satisfy.

### a building the spawn placer could not see

`site_spawns.footprint_rect` read `_footprint` only. `site_extent.rotated_footprint`
reads `footprint` too, and applies rotation. Two implementations of "where does
this building stand", diverged, in the same repo -- so a building described the
second way was solid to the ground plate, solid to the layout linter, and
invisible to enemy placement, which would happily drop a spawn inside it.

`footprint_rect` now delegates to `site_extent` and keeps only the margin growth.
This is not the producer/consumer double implementation the pipeline keeps on
purpose across the Level Factory gate -- both of these were consumers, in one
module, answering one question two ways.

Twelve tests: nine new under `# the opening engagement`, three rewritten because
they were asserting the old truth. `205 passed`.

## [0.30.0] - the ground was the wrong size in six places at once

The crew spawned on a floor with no site ground within twenty-two metres, and
Laser Tag was right to refuse the map. What put them there was not the spawn
placer.

`category5_baie_dore_001` seed 5219 places four 44 m shells at x = -6, 39, 93
and 138 and declares a ground plate of 232 x 100. Lot centred that plate on the
origin, so it ran x -116..116 while the row it carries runs x -28..160. The last
building overhung the east rim by 44 m. Everything downstream followed:

  - `_ground_tiles` cut b3's floor hole against the plate rect, the hole fell
    entirely outside it, and the intersection came back empty. An empty result
    is what "the hole fitted" also looks like, so no tile was laid and nothing
    was said. Silent emptiness, the same shape as every other bug in this file.
  - b3's own interior slab was the only surface under the crew spawn, with the
    plate's rim 22 m short of it. An island.
  - the perimeter wall, the streetlight ring, the enemy-spawn street search, the
    layout linter's bounds check and the enterability approach test all read the
    plate the same way, so all five agreed the site was fine.

Six call sites, one assumption, written out longhand in each of them:

    hx, hy = g["size_x"] / 2, g["size_y"] / 2

No module owned the answer, so there was nowhere for the fix to go and nowhere
for a test to point. That is the actual defect; the mis-centred plate is what it
let through.

### site_extent.py (new)

One reader for "how big is the ground and where does it sit". Takes a site spec,
returns a `Ground` with a rect in site space, and every module that used to
halve `size_x` now asks it. Pure: dicts in, rect and findings out, no bpy, no
Godot, no imports outside the stdlib.

The rect is derived rather than declared. `content()` collects what has to stand
on ground -- buildings and blockers by rotated footprint, courtyards, cover,
paths and roads swept by half their width, markers as points -- and
`required_rect` grows that union by `CLEARANCE = 4.0` m. Four metres because
Godot erodes the navmesh by the 0.4 m agent radius at every geometry edge
including the plate rim, so 4 m of ground outside the outermost solid leaves
~3.2 m of walkable surface rather than a ledge. When the declared plate does not
contain that, the two are unioned and the result snapped outward to whole
metres. Growth is one-directional on purpose: ground already laid is ground
already walked on, and pulling a rim in can delete a surface someone stands on,
while pushing one out can only add surface nobody has to use.

Nothing grows in silence:

  - `LOT_GROUND_EXTENDED` (moderate) names which content fell outside and by how
    much each edge moved -- "extended to 280 x 100 m (+48 m east) so b3 stands
    on ground".
  - `LOT_GROUND_OFF_CENTRE` (minor), only when the declared plate was large
    enough and merely in the wrong place. That is the producer-side bug stated as
    a sentence: sized from the building count, then assumed centred on the
    origin.
  - `LOT_GROUND_EXTENT_UNKNOWN` (moderate) when a building carries no readable
    footprint. An unmeasurable building is not a zero-sized one, and the plate
    cannot be sized for what it cannot see.
  - `LOT_GROUND_UNREASONABLE` (blocker) past a 2000 m span -- but the ground is
    still built. A blocker stops the run; it should not also cost the artist the
    scene that shows why.

### the hole gate

`hole_findings()` raises `LOT_GROUND_HOLE_OUTSIDE` (blocker) for any floor hole
the plate does not contain, straddling the rim included. The clipping in
`_ground_tiles` stays -- it is honest arithmetic once the rect is right -- but it
can no longer be the last word. A hole that would vanish now stops the run and
says which building's floor was about to be cut out of a plate that does not
reach it. `lot.py` gained `ground_holes()` so the builder and the gate compute
the same holes from the same policy instead of the gate approximating what the
builder did.

The report carries `ground_extent` with the resolved, declared and required
rects, so a reader can see the plate that was built next to the plate that was
asked for. The findings go through `tactical.findings`, which Level Factory's
Lot adapter already maps to issues, so a blocking hole reaches the pipeline
without a change on that side.

### the overlap gate

Being able to resolve the real extent of a row meant being able to look at the
row, and the row was wrong in a second way. Measuring the shipped shell gives a
44 m building; the spec spaces the origins 42 m apart. Every neighbouring pair in
every candidate had two metres of one building standing inside the other.

Nothing in Lot asked. `site_audit` compared markers against footprints,
`site_layout_lint` compared markers against bounds, `site_spawns` pushed spawns
out of footprints -- and no check anywhere compared two footprints to each other.
A row whose spacing was narrower than the buildings standing in it assembled
interpenetrating shells and reported a clean site, which is why this survived
every run so far.

`overlap_findings()` raises `LOT_BUILDINGS_OVERLAP` for each pair whose rotated
footprints intersect. Depth is the shallower of the two axis overlaps -- how far
one shell reaches into the other. Past `OVERLAP_TOLERANCE = 0.5` m it is a
blocker naming the depth ("reaching 2.0 m into each other"), because Deli
Counter's exterior walls are 0.25 m and half a metre is the width at which
"cladding is kissing" becomes a wall standing in somebody's living room. Under
the tolerance it is a minor: two shells sharing a face is a terrace, not a fault,
and a row can be tightened deliberately. A building whose footprint cannot be
read is skipped here and already reported by `LOT_GROUND_EXTENT_UNKNOWN` -- it is
not reported as clear.

### tests

`tests/test_site_extent.py` is built on the seed that produced it, not on a
synthetic square. It asserts the plate carries the row, that the crew spawn
stands on ground, and -- guarding the guard -- that the *declared* plate did not:
a fix whose fixture cannot express the old failure proves nothing. The end-to-end
test flood-fills the tile set and requires that the strip of ground beside b3
joins the ground at the far rim, because "there is a tile here" and "you can walk
from here to the objective" are different claims and only the second one is the
one Laser Tag failed. Area conservation (tiles + holes = plate) catches a strip
going missing anywhere in the decomposition.

Two existing tests had their premises dissolved by the fix and were rewritten
rather than relaxed. `test_enterability_outside_perimeter_gates` proved its point
with a building whose footprint hung 1 m off the declared rim; that plate now
grows, and the door faces ground. It is now two tests: one that the door is *not*
gated because the plate was extended and the extension was reported, and one that
keeps the gate honest with a building Lot cannot measure, where the rim really is
all there is. `test_an_enemy_that_cannot_be_placed_is_not_written` boxed a 98 m
shell into a 100 m plate; the honest plate gives it a 4 m street and all six
enemies place. The fact under test is "no clear cell within `MAX_PUSH`", so the
shell is now 400 m and the nearest street is 200 m away.

The overlap tests carry the same shape: the real row is asserted clear, a row
spaced 42 m with 44 m shells is asserted to block with the depth in the message,
shells that merely touch are asserted to report without gating, a quarter turn is
shown to separate one pair and join another, and an unmeasurable building is
asserted not to come back clean.

What this does not fix: Level Factory still writes the spec that way.
`site_variation.site_placements` anchors the row at the origin and marches +x
while `ground_size` returns a symmetric span from the building count, and its own
coverage test passes because of a `+ 90` fudge in the assertion. Lot now survives
that spec and says so on every run, and Level Factory 0.13.17 stops writing it
that way -- but the two halves stay independent on purpose. Lot's gate does not
trust the producer to have been fixed, and never will.

## [0.29.0] - the hook came down off the counter and stayed on it

0.28.0 seated `LT_ObjectivePoint` on the floor and the run came back with the
same blocker. The correction is recorded on that entry; this is what was
actually wrong.

Seating changed the marker's height. It could not change where the marker
*stands*, and Laser Tag's navmesh does not read the number in the marker -- it
reads the geometry under the point. The point was at the exact centre of a
`cashier_cage` room, which is also the exact centre of the `cage_counter` prop
Deli Counter bakes into that room: a 6.0 x 1.0 m box 1.1 m tall. So the cell
kept reporting a standing surface 1.1 m above a room floor of flat 0, with no
step between it and anything around it. Against a 0.5 m climb limit the cell is
standable and is an island. The bot has no route to it, and the whole map is
refused at 0% completion for a one-metre placement error.

It is not seed-specific. The gameplay generator places the objective marker at
its room's centre and Deli Counter places the counter at the same centre, on
every building of this archetype -- four for four on the seed that produced it.

Lot could not see any of this, because Lot could not see furniture. Its only
model of solid geometry was `site_spawns.footprint_rect`, which treats a whole
building as one block. That is right at the scale it was written for and blind
one level down, and the mission nav hooks all live inside footprints.

### site_collision.py (new)

Reads the collision the shells Lot assembles actually bring, in site space.
Godot's glTF importer generates a physics body for a node whose name ends in
the `-col` family of suffixes, and the position and extent of that body are
fully described by the file's JSON chunk -- the node hierarchy carries the
transforms and each mesh primitive's POSITION accessor carries min/max. So the
furniture inside a baked shell can be located without Blender, without Godot,
and without decoding a vertex buffer. Follows `.tscn` instances too, with their
`Transform3D`, because Deli Counter's primary output is a scene rather than a
bake. Stdlib only.

This is deliberately a *second* implementation of the contract Level Factory's
`glb_collision.py` already reads on the other side of the gate. Sharing one
reader would mean a bug in it blinds the producer and the check meant to catch
the producer at the same moment, which is the whole reason the gate exists. The
two agree because the contract is written down, not because they are the same
code -- and they do agree: run against the shipped pack, Lot recovered the four
cage counters at (-10, -22), (35, -17), (68, -17) and (151, 2), which is
exactly what Level Factory's reader found.

`Reading.complete` is the part that matters downstream. A site that parsed and
holds no furniture is a confident "nothing is in the way"; a site with one
unreadable shell is "cannot tell". Nothing here reports "clear" for geometry it
could not read -- a truncated file, a binary `.scn`, a scene declaring collider
shapes this reader does not model -- and a caller acting on a partial reading
is required to say so. That is the same silent-emptiness failure the original
ground-hole defect was made of, and it does not get to happen twice.

Boxes are axis-aligned hulls. For the slabs, walls and counters Deli Counter
bakes -- which are boxes -- the hull is the shape; for anything concave the
hull is larger, so the reader errs towards "something is solid here". That
moves a hook that did not need moving rather than leaving one stranded, and it
says how far it moved anything.

### site_spawns.seat_destinations(..., solids=...)

After the height pass, each hook is moved sideways off whatever it stands in,
the shortest distance to floor an agent can both stand on and reach. Bounded to
the hook's own room when the caller knows it (`lot._destination_bounds`), and
to 6 m regardless: a hook names a spot in a particular room, and walking it
across the site to find open floor would trade a blocker for a mission that no
longer happens where it was designed to. Boxed in with nowhere to go is
`LOT_DESTINATION_ON_PROP` (major) and the hook is left where it was -- a move
Lot cannot defend is worse than a move Lot did not make. A successful move is
`LOT_DESTINATION_RESOLVED` (minor) naming the prop and the distance. A partial
reading is `LOT_DESTINATION_COLLISION_UNREAD` (moderate) naming the sources.

Without `solids` the lateral pass does not run and nothing pretends it did.

The clearance is 0.75 m, not contact. Recast erodes the walkable surface by the
agent radius from every obstacle during the bake (Lot authors 0.4 m) and
quantises what is left onto a 0.15 m voxel grid, and Level Factory rasterises
on a coarser 0.5 m grid still. A hook a quarter of a metre off a counter has
clear air around it and no navmesh polygon beneath it -- the same refusal,
reached more confusingly. The first working version of this fix moved the
objective 0.75 m, landed inside that erosion band, and still failed.

### The scene carried two answers for the same destination

Found while wiring the above. `write_walk_scene` wrote the *unseated* positions
into `spawn_pos` / `objective_pos` / `extraction_pos` and the player capsule,
while the `LT_*` hook nodes got seated ones -- so the beacon the player walks
to and the point the bot paths to were metres apart in a scene that looked
internally consistent. Seating now happens once at the top of that function and
the seated positions are written everywhere, including the return value.

### Verified

Level Factory's production `check_spawn_placement`, unmodified, against the
byte-verified `site_walk.tscn` and `shell.glb` from the shipped pack:

    --- as shipped
      findings: 1
       * 1 of 3 mission destination(s) cannot be walked to from the player
         spawn: LT_ObjectivePoint is sealed off from the crew spawn ...
    --- objective resolved 1.5 m
      findings: 0

Plus 60 tests in `tests/test_site_collision.py` covering the container walk,
the suffix contract against `site_ground`'s independent copy of it, the Y-up to
site conversion, node and instance transform composition, every way a source
can come back incomplete, the clearance band, lattice determinism, and the
whole chain through `assemble(..., walkable=True)`. Suite: 163 passing.

### Still open on this site

Unchanged from 0.28.0: the enemies reach the crew and the fight is bad.
INSTANT_CONTACT at 0.0 s, average survival 4.6 s, OVEREXPOSED, blind across 68%
of positions. `place_enemies` pushes each spawn to the *nearest* open ground,
which on this site is the same stretch of street for all six. `MIN_STANDOFF` of
8 m is too close for an open street, `MIN_SEPARATION` of 4 m is too tight to
call six positions a sequence, and neither knows anything about cover or line
of sight. `site_collision` is the capability that was missing to fix it: cover
and line of sight are questions about where the solids are, and Lot can now
answer those.

## [0.28.0] - a nav hook is not a prop, and Route_1 was the objective all along

The run from 0.27.0 came back blocked, and the blocker was the defect that
entry had already named as still open: `LT_ObjectivePoint` standing 0.9 m up on
a 1.1 m `cage_counter_col`, in a room whose floor is 0, with no step between.
Against LaserTag's 0.5 m climb limit there is no route to it, so the bot
completed 0% of runs.

The reading that fixes it is that `LT_ObjectivePoint` is a *navigation* target,
not the objective prop. A till, a safe, a case in a display cabinet is meant to
be up on the counter; the point the bot walks to is not. Two of the three
mission points were already read this way -- a site-level `crew_spawn` and
`extraction` both resolve to `(x, y, 0.0)` no matter what height their marker
carries -- and the objective was the one that took its marker z verbatim.

`site_spawns.seat_destinations` makes the third consistent with its siblings:

- at or below `AGENT_CLIMB` (0.5 m) the marker is standing on a kerb and is
  left alone;
- between there and `FURNITURE_MAX` (2.0 m) it is on a counter, a crate or a
  desk, so the nav hook is seated on the floor beneath it and Lot reports
  `LOT_DESTINATION_RESEATED`. The prop is unmoved;
- above 2.0 m the drop is a storey, and Lot has no storey model. Seating a
  second-floor objective to z = 0 would put the hook in the room below -- a
  worse defect, and a silent one -- so Lot moves nothing and reports
  `LOT_DESTINATION_ABOVE_FLOOR` (major): either the marker's z is wrong, or the
  stair that reaches it is missing.

Seating runs before the route is built, so the route points and the cover ring
derived from the objective inherit the seated position rather than each needing
their own fix.

Verified on the seed that produced it: objective (35, -17, 0.9) -> (35, -17,
0.0).

**Correction (0.29.0).** This entry originally continued "and Level Factory's
spawn-placement check goes from three findings to none on the rebuilt scene".
That was measured against a Python reconstruction of the seed's geometry, not
against the scene Lot shipped, and it was wrong. The next real run came back
with the same blocker: `LT_ObjectivePoint is sealed off from the crew spawn`.
The seating above is correct and necessary; it was not sufficient. Dropping the
hook's z to the floor left its *footprint* on the counter, and the navmesh
takes a cell's standing surface from the geometry under the point, not from the
number in the marker. 0.29.0 is the half that was missing.

### Still open on this site

The enemies now reach the crew, and that turns out not to be the same thing as
a good fight. The one candidate that completed a full 25-run evaluation came
back INSTANT_CONTACT at 0.0 s, average survival 4.6 s, OVEREXPOSED, and blind
across 68% of its positions. `place_enemies` pushes a spawn to the *nearest*
open ground, which on this site is the same stretch of street for all six --
clustered, in the open, with clean sight lines to a crew that has not moved
yet. `MIN_STANDOFF` of 8 m is too close for an open street, `MIN_SEPARATION` of
4 m is too tight to call six positions a sequence, and neither knows anything
about cover or line of sight. Reachability was the right first thing to fix and
it is not the last one.

## [0.27.0] - the enemies were placed by arithmetic that had never heard of the buildings

`_lasertag_hook_nodes` sampled the straight line crew-spawn -> objective ->
extraction, kicked each sample 1.5 m to one side, and lifted it a metre above a
height interpolated between the two ends of the segment it fell on. On an empty
field that is a reasonable engagement sequence. This site has four 44 m shells
strung along that exact line.

All six enemies landed indoors. Every one of them had a slab beneath it, so
nothing that asked "is this floored" objected. Laser Tag asked the question
that decides the map -- can each enemy path to the crew -- refused it with
`UNREACHABLE_SPAWN` x6, and reported `runs: 0, grade BROKEN` after the full
900-second timeout. The interpolated heights left five of the six markers
hanging 1.3 to 1.8 m in mid-air as well, because the objective they were blended
toward sits on a 1.1 m counter.

### site_spawns.py

Placement now runs against the geometry Lot has already decided on. A spawn
goes on the street: outside every building footprint by `WALL_MARGIN` (1.0 m,
which is more than the 0.4 m the navmesh bake erodes from every solid), inside
the ground rect, at least `MIN_STANDOFF` (8 m) from the crew, at least
`MIN_SEPARATION` (4 m) from its neighbours, and at the ground plane rather than
at a blended height. The engagement spread along the route is unchanged -- only
the collisions with it are new, and a sample that lands in a building is pushed
perpendicular, nearest side first, until it clears one.

Where no such position exists the enemy is not written and Lot says which one
and why (`LOT_ENEMY_SPAWN_UNPLACEABLE`). A spawn Lot cannot defend is worse
than a spawn Lot does not write, because the first one costs a full evaluation
to discover. Enemies that had to be moved off the route are reported too
(`LOT_ENEMY_SPAWN_PUSHED`), as is a site that declares neither ground nor
footprints and therefore could not be checked at all
(`LOT_SPAWN_PLACEMENT_UNCHECKED`) -- an unchecked placement must not be able to
pass as a checked one.

The same call runs in `build_site` and in `write_walk_scene` -- same inputs,
same answer -- because the walk scene is written after the tactical report
closes, and a placement Lot could not honour has to travel with the site rather
than sit silently in a `.tscn` nobody diffs.

On the seed this was written for, all six spawns move from inside b1/b2 to the
street south of them, and Level Factory's `check_spawn_placement` goes from
three findings to none.

### Still open on this site

The objective marker stands on top of a `cage_counter_col` -- a 1.1 m counter in
a room whose floor is at 0, with no step between. Neither a bot nor the player
can climb 1.1 m against a 0.5 m limit, so the route to it does not exist. That
is a marker-placement defect upstream of Lot, and Lot does not move a designed
objective to hide it; Level Factory reports it as an unreachable mission
destination.

## [0.26.0] - the walkthrough bake raced the evaluator and both lost

`lot_site_walk.gd::_ready()` called `nav.bake_navigation_mesh()` on every load.
That bake is threaded and returns immediately, which is fine for the human
walkthrough it was written for and wrong for every other caller.

Laser Tag loads the same `level.tscn` headless and bakes navigation itself,
against its own agent parameters. Both bakes targeted the same
`NavigationMesh` resource, so the second one was refused --
`ERROR: NavigationMesh is already baking. Wait for current bake to finish.` --
and left the region with zero polygons. Downstream that is indistinguishable
from a map with no collision at all: the harness reported `NAVIGATION_MISSING`
on a fully walkable four-building site, fell back to direct movement, and spent
900 seconds watching bots walk into walls before Level Factory's timeout killer
ended it. Sixteen findings came back about pacing, cover, traversal and stuck
enemies. All of them were artifacts of the refused bake.

The bake now returns early when `DisplayServer.get_name() == "headless"`.
Headless means nobody is walking this scene -- it was loaded by an evaluation
runner or CI, and that caller owns navigation. When there is no walker, the
right amount of baking is none.

Pinned by `test_walk_scene_does_not_race_an_external_navmesh_bake`, which reads
the shipped `.gd` and asserts the guard sits before the call and leaves without
baking. Reading the source text rather than running Godot keeps the guard
testable in the same suite as everything else, and this is a defect that lives
in three lines of script that no Python test would otherwise ever look at.

## [0.25.0] - A hole is cut in the ground only where a building floors itself

- **The ground policy checked its own premise.** Lot cut an inset hole in the
  site ground under every building, on the reasoning that a solid slab through
  a footprint seals the basement stairwell and the building's own slabs floor
  the interior. The second half of that is a premise, not a fact: Godot's glTF
  importer generates collision only for nodes whose names carry the `-col`
  family of suffixes (or when the `.import` file asks for physics), so a baked
  `shell.glb` arrives as MeshInstance3D and brings nothing. A site of plain
  shells cut a hole under each building and put nothing in it; four adjacent
  footprints merged into one contiguous void with the spawn, the objective, the
  extraction and every enemy standing over it. Nothing in Lot said so -- the
  scene loaded, the street ring was there, and the first mention of the problem
  was Laser Tag rejecting the map with `NO_WORLD_COLLISION` and completing zero
  runs, four steps and fifteen minutes downstream.
- **New `site_ground.py`** answers one question -- does this building's geometry
  bring collision? -- from the bytes on disk: glTF node names (including
  Blender's `.001` duplicate form and the sibling `.import` file), and `.tscn`
  collision bodies followed through instanced sub-scenes. A missing or
  unreadable source is `unknown`, never `absent`: "the file is not there" and
  "the file has no collision" are different problems and only one of them is
  the operator's to fix. Only a demonstrated collider earns a hole, so an
  unchecked site cuts none -- keeping ground can never create a fall.
- **Both write paths audit.** `assemble()` decides before the gameplay file is
  written, so `merged["ground"]` and the `LOT_SHELL_NO_COLLISION` /
  `LOT_SHELL_COLLISION_UNKNOWN` findings travel with the site into Level
  Factory's Validation Center. `package.py` audits the assets it has already
  resolved, so a shipped pack cannot carry a void to whoever opens it.
- The findings are `major` and `moderate`, not blockers: filling the hole stops
  the fall, but it does not make the shell solid -- those buildings are still
  pass-through until Deli Counter exports them with `-col` nodes.
- Tests: `tests/test_site_ground.py` (23), including
  `test_no_mission_point_stands_over_a_hole`, which assembles a four-building
  block of collisionless shells and asserts every LaserTag hook in the walk
  scene stands on a ground slab. Removing the guard fails it at 12 of 15.

## [0.24.0] - Walk scenes are legal in Godot and playable by Laser Tag

- **Node names are sanitized to Godot's own rule at write time.** Godot 4's
  `String::invalid_node_name_characters` is `. : @ / " %`, and `set_name()`
  silently rewrites each to `_` on load. Ladder volumes are named from
  building-namespaced markers (`b0/LADDER_0`), so the node arrived in the
  engine as `b0_LADDER_0_climb` while its child's `parent="b0/LADDER_0_climb"`
  was parsed as a *path*, matched nothing, and the CollisionShape3D was
  dropped. Every ladder Lot emitted was unclimbable, and nothing said so.
  `_node_name()` now applies the rule before the name is written, so the name
  and every reference to it agree. Test: `test_node_names_are_legal_in_godot`
  asserts no emitted node name contains a character from the invalid set.
- **Walk scenes now meet the LaserTag map contract** (LaserTag TDD 8).
  LaserTag discovers its fixtures by node name -- `LT_PlayerSpawn`,
  `LT_EnemySpawnPoints`, `LT_ObjectivePoint`, plus the optional
  `LT_PlayerRoutePoints` / `LT_CoverTestPoints` -- and short-circuits before a
  single run when the required three are absent. Lot carried spawn/objective/
  extraction as script properties only, so the evaluator read the map as empty
  and reported a grade for a match it never played (`runs: 0`, grade BROKEN).
  `_lasertag_hook_nodes()` emits the nodes from the positions Lot already
  computes; enemies are sampled along the spawn -> objective -> extraction
  polyline and kicked alternately to either side, so they are an engagement
  sequence rather than one stacked encounter. Tests:
  `test_walk_scene_meets_the_lasertag_map_contract`,
  `test_enemy_spawns_spread_along_the_route`, and
  `test_walk_scene_load_steps_still_match` (the header count survives).

## [0.23.0] - Phase 4 missions: 8/8 full green first pass -> 20/20 library

- **8 new missions all FULL green on the first engine batch** (walktest
  proofs + physical walkers + 4-player mp_smoke): Citizens Bank Park,
  Rivers Casino, PHL Airport, Center City Bank Tower heroes (the LARGE
  40-min slate tier) + Xfinity Center, Reading Terminal, Independence
  Mall, SEPTA Yard standards. Library: 20 missions / 8 heroes.
- Offline sandbox assembly caught all four authoring defects before the
  engine leg (2x spawn-separation, 2x single-approach objective): the
  pvp gates in lot.py are doing their job pre-hardware.

## [0.22.0] - Phase 3 missions: 6/6 full green, smoke walker detour

- **6 missions all FULL green** (proofs + physical walkers + mp_smoke):
  SEPTA Station hero, Main Line Mansion hero (Vinny rehearsal), Museum Row,
  Port Row, Storage Row, Brewery Block. Library missions now 12/12 with 4/4
  heroes -- every hero physically walked.
- **Smoke-walker stall detour:** the smoke client has no pathing by design;
  a straight beeline into a corner must not false-fail a good site (the
  pathing walktest passed storage_row while the beeline ground on a wall).
  On stall it steers ~60 deg off-line, alternating sides.

## [0.21.0] - Phase 2 missions + the walker slope fix

- **Walker floor angle now matches the bake's agent_max_slope** (agent
  contract, DC_NAV_SLOPE + 1 deg) in BOTH harnesses (nav_qa_director,
  mp_smoke_node). Tall-story basement ramps (4.2-4.5 m stories, ~49-52 deg)
  exceeded the 45 deg default and the engine classified the ramp as a WALL:
  every walker jammed at the stair mouth while all path proofs passed.
- **3 Phase 2 missions, all FULL green** (proofs + physical walkers +
  mp_smoke): MSN_STRIP_MALL_01, MSN_WALKUP_SIEGE_01, and the
  MSN_WAREHOUSE_DISTRICT_01 hero -- 4 players x 14/14 targets, ~770 m each,
  202 s spine-scaled sim, 12/12 bots. First hero to fully pass the physical
  walktest.

## [0.20.0] - Phase 1 missions: standard green, hero on proofs + smoke

- **MSN_DELI_BLOCK_01 (standard)** fully green: 15 path proofs + physical
  walkers complete the spine + 4-player mp_smoke, all PASS.
- **MSN_CENTRAL_VAULT_01 (hero)**: all 18 path proofs PASS (navmesh proven
  walkable end to end) + mp_smoke PASS. The simplified QA-walker bot sticks
  at one interior pinch on the 18-stop multi-building spine; accepted on the
  authoritative proofs + smoke (levels-as-input: the level is proven walkable;
  QA-bot spine locomotion is harness scope, filed as backlog).
- **Ground slab tiling.** lot.py cuts the shared ground AROUND building
  footprints (inset) instead of one solid box -- a solid slab through a
  footprint welds its basement shut (site walktests proved basements island
  otherwise).
- **Spine-scaled walktest clock.** nav_qa_director sizes the sim cap to the
  measured spine length (the hero's 18-target spine ran the old fixed 120 s
  cap out at exactly WALK_SPEED x 120 -- a capacity limit, not a nav failure).
- Backlog: story1-objective delis (A02/A03) descend fine at building scale
  but their single 0->1 flight voids at site scale -- the hero uses the
  basement-objective DELI_A01 (site-scale robust). Revisit with a live loop.

## [0.19.0] - Walktest + mp_smoke prove the site (engine leg green)

Both site-level engine gates now PASS on Godot 4.7 stable (reference pvp
site: 15/15 path proofs, 4 players x 8/8 targets + 12 bots physically
walking; 4-peer multiplayer smoke connect/move/verdict PASS).

- **walktest.py + heist_nav_qa/nav_qa_director.gd.** Path proofs with
  VERTICAL-access classification (ladder/drop gaps are intel for game code,
  not navmesh failures) and coordinate diagnostics. Physical walkers:
  waypoint paths via map_get_path (NavigationAgent3D does not path
  headless), waypoint-PROGRESS stall detection (raw movement lies --
  wall-sliding registers as motion), repath-on-stall with bounded
  navmesh reseat, kinematic step-up from the agent contract's max_step_up
  (replaces the blind hop that wedged walkers under stair flights), 3D
  path-following on climbing segments, spawn snap-to-mesh, walkers collide
  with world only. Verdict accepts every ok-flavored status; timeout
  walkers report their position.
- **lot_navqa_setup.gd:** synchronous bake, NavigationServer cell-size
  match + map_force_update (async region commits leave the map empty),
  deferred director add (add_child during _ready).
- **mp_smoke.py / mp_smoke.gd / mp_smoke_node.gd.** Host + N-1 clients on
  loopback: per-process LOG FILES (an undrained stdout pipe fills its 64KB
  buffer and blocks the host mid-scene-load -- the beacon then appears
  minutes late), readiness beacon, host PID print + netstat/tasklist socket
  forensics on failure (the Windows *_console.exe is a WRAPPER; the engine
  child owns the socket, and the firewall allow rule must name the child),
  45 s connect window, clients treat the host's early-PASS teardown as
  success, deferred _setup (root.multiplayer is null during _initialize),
  scene load before peer creation, report-required verdict.
- **Agent-contract bridge:** lot.py bakes walk/navqa NavigationMesh params
  from deli_counter/agent_contract.json ($DC_AGENT_CONTRACT overrides);
  walktest.py/mp_smoke.py pass the env through to GDScript.
- **specs/ref_pvp:** 3-building reference pvp site (site gates pass, two
  approaches, defender spawns, protected hold).
- site_tactical.py: pvp_heist gate() branch + gate_merged() post-merge
  checks (defender spawns, 25 m spawn separation, protected rotation).

## [0.18.6] - Footprint-true site layout (the "floating bars" fix)

### Fixed
- **night_strip.site.json spacing**: the v0.18.1 spec placed stores 24 m
  apart assuming ~20 m storefronts; the real presets measure deli 38x38
  (corner-lot L), pawn 16x14, auto 26x18 — buildings interpenetrated by
  ~14 m and crossed the street line. The "floating bars" seen in the walk
  were the NEIGHBORING building's DC roof furniture (parapet_N/S/E/W, roof
  slab rim, ladder_rung, stair treads) poking through shared volume. New
  layout derives from MEASURED bounds: fronts aligned on the sidewalk line,
  6.7 m real alleys, nothing crossing the street; validated against the
  real shells with real lot.py (gates pass, 43 streetlight poles, pawn sign
  on the line; the deli sign sits 4.8 m back — its corner wing is proud of
  the storefront wing, honest corner-lot urbanism).
- STORES transforms + shot list resynced across walk_night_strip.gd,
  visual_night_strip.gd, visual_night_strip_dressed.gd; walk spawn moved to
  the west street end.

### Notes
- Positions changed -> the full chain must re-run: night_strip.ps1 (Lot
  re-assemble + fixture rebuild), then night_strip_dress.ps1, then walk.
- Backlog: Lot should GATE building-AABB overlap (it currently trusts the
  spec author, and shouldn't).

## [0.18.5] - Walk the strip

- tools/walk_night_strip.gd + tools/walk_night_strip.ps1: first-person walk
  of the staged night strip inside the lux project — patina shells +
  dressing + (branded) fixtures at site transforms, merged manifest baked
  through LuxRoot, Blue Hour grade, source-built player controller
  (keycode-only, no input map): WASD/SHIFT/SPACE, F cuts and restores
  building power live, G cycles the grade, ESC/F8. Runner completes any
  missing staging from the newest _runs artifacts (prefers zoo_skinned
  branded fixtures). Selftested against real Godot: 3/3 shells, 58 rigs
  baked, player compiled, clean exit.

## [0.18.4] - Dress runner wires the signage packs

- tools/night_strip_dress.ps1: when the Pixelcoat signage library exists at
  `_runs\skins\delco_signage` (or via -Skins), fixtures are rebuilt with
  `zoo --skins` before staging — sign cabinets come out BRANDED (Zoo v0.31
  sign-pack resolver: deterministic per anchor, glowing letterforms, power
  cut still kills them). No library -> prior behavior untouched.

## [0.18.3] - Run artifacts land in _runs\

- `tools/night_strip.ps1` + `tools/night_strip_dress.ps1` (dress runner also discovers prior runs under `_runs\`, factory-root fallback) write run folders and results zips under the factory's `_runs\`
  directory instead of the factory root — tool repos and the coordination
  files stay alone at the top level. No behavior change.

## [0.18.2] - Night strip art pass (the A/B against the reel)

- tools/night_strip_dress.ps1: consumes a night_strip run's work dir and
  applies the certified art chain per store — Patina procedural surfacing
  (delco_1997_gas_station theme, dressing anchors emitted; validated against
  the real strip shells: 37.5k/10.9k/14.2k tris, collision untouched) ->
  Zoo kit modules from the DC slots + Zoo dressing from Patina's json (real
  Blender; no --skins: that flag takes a Pixelcoat pack FOLDER and no pack
  run exists yet — Patina carries the surfacing). Restages and re-shoots the
  IDENTICAL seven framings for a pure graybox-vs-dressed A/B.
- tools/visual_night_strip_dressed.gd: per-store asset stacks (patina shell
  + kit + dressing) at the site transforms; fixtures + bake unchanged.

## [0.18.1] - The DELCO night strip (streetlight coverage + reel-target look)

- specs/night_strip.site.json: three DC storefront presets (corner_deli /
  pawn_shop / auto_shop) along a lit street. Heist-routed (deli -> pawn ->
  auto), 84x44 ground, one street path + two building links -> Lot derives
  ~7 streetlight rows (26 poles) plus the perimeter ring. Spec structure
  validated end-to-end against real lot.py (mode gates passed, walkable
  scene emitted, merged manifest carried all five anchor types).
- tools/night_strip.ps1: end-to-end runner - DC x3 (real Blender) -> Lot
  assemble + lights merge -> Zoo fixture build (all species incl. the
  streetlight leg, LuxEmit markers) -> Lux headless harness (bake + marker
  gates, first hardware run of LuxStreetlightRig at site scale) -> windowed
  night visual pass -> results zip.
- tools/visual_night_strip.gd: reel-comparison shot list (down-street, pawn
  storefront, streetlight row, wide, deli corner, the power-cut beat, and a
  Gas Station Fluorescent contrast frame), Blue Hour grade.

## [0.18.0] - Site lighting: merge building lights + exterior streetlights

- merge_lights(): merges every building's <name>.lights.json into one
  <site>.site.lights.json -- each anchor offset to world space and id-namespaced
  by building (mirrors merge_gameplay's offset+rotation+namespacing), plus the
  exterior lights Lot owns. Deterministic; consumed by Lux's light-anchor loader
  exactly like a single building's manifest. Written in assemble() next to
  .site.gameplay.json and .tscn.
- Exterior streetlights Lot derives (Deli Counter can't see outdoors): a
  streetlight row down each path (angle + count from the road), and a ring
  around the ground perimeter (one row per edge).
- Building lights resolved via each building's 'gameplay'/'glb' ref
  (<name>.lights.json), or an explicit 'lights' field; missing files skip
  cleanly. specs/bank.lights.json + warehouse.lights.json added for the demo.
- 4 new tests (35 total).

## [0.17.2] - primos_demo: the showcase site (Deli Counter PoC staging)
- specs/primos_demo.json + specs/primos_demo_buildings/: "Primo's Pizza &
  Social Club" (DC 0.59.0's showcase spec) staged as a one-building demo
  site. All green in preview end-to-end: site_audit 0 HIGH / 0 MED (three
  responder waves at true thirds around the building, backstopped spawn
  and exfil on opposite corners, parked-car cover along both legs), heist
  gates passed, pacing within target, walk scene emits all three climb
  volumes (cellar, dumbwaiter, roof), drift check clean vs DC.
- DEMO_PRIMOS.md: the one-command recipe -- cater --package cuts the
  shareable pack (dist/primos_demo_pack_v0.1.0.zip) on any machine with
  Blender.

## [0.17.1] - Spec drift guard + the gs_auto_shop copy actually synced
Found in the wild: the Lot copy of gs_auto_shop.json was still the
pre-0.56.0 spec (swapped story-1 axis, 1.1 m door, no parapet) -- the DC
fix never crossed the manual copy step, and the pipeline rebuilt and even
PACKAGED the broken upper floor without a peep. Two fixes:

- specs/gs_heist_buildings/gs_auto_shop.json is now the fixed DC spec
  (axis X, 1.4 m upper door, roof parapet). Run cater with --force-build
  so the auto_shop glb rebuilds from it.
- cater now hash-compares every building/blocker spec in the site folder
  against Deli Counter's spec of the same name and prints a loud SPEC
  DRIFT warning with the exact copy command when they differ. Warning,
  not a gate: freezing a level is a valid choice, but it should be a
  choice, not an accident.

## [0.17.0] - site_audit.py: the genre grammars between the buildings
Deli Counter 0.58.0 gave buildings the PayDay 2 / Ready or Not / L4D2 rule
packs; this is the same idea at site scale -- the run across open ground.
Report-only, printed at the end of every lot.py assembly; the walked
gs_heist sweeps 0 HIGH / 0 MED (calibration), with three fair INFOs (two
road crossings, few horde spawns).

- S_BACKTRACK (PayDay exfil shape): extraction within 18 m of the crew
  spawn AND within 35 deg of the entry bearing = the escape rewinds the
  entry. Same-side-different-corner passes (gs_heist does).
- S_RESPONDER_ARC / S_RESPONDER_CAMP (PayDay pressure): all responder
  spawns inside one arc = one-note waves; a responder spawn within 12 m of
  an anchor = spawn camping by construction.
- S_NAKED_ANCHOR (L4D2 safe anchors): spawn/extraction with no cover or
  building/blocker edge within 8 m. Blockers use their real size_x/size_y
  extents (the gs spawn alcove's south wall counts, as it should).
- S_BARE_LEG (L4D2 rhythm): critical legs >= 20 m with zero cover in a
  6 m corridor are sprints, not fights.
- S_STREET_CROSS (CQB at site scale, INFO): every road crossing on a
  critical leg is an exposure moment, reported per crossing.
- S_HORDE_ARC / S_FEW_HORDE and S_ONE_APPROACH (site-graph route
  diversity via site_tactical) where they apply.
- Wired into lot.py after pacing; standalone CLI: python site_audit.py
  specs/x.json [--json]. Tests: 30 -> 31.

## [0.16.1] - Ladders work in the site walk (Lot adopts its half of the contract)
Stairs worked, ladders didn't -- and it was NOT the .glb. DC's ladder contract
has three legs: DC bakes the LADDER_ anchor + climb metadata into the
glb/gameplay (working); a post-import turns the anchor into an Area3D climb
volume (only runs in projects with the DC addon -- cater projects don't have
it); the player implements climb mode (lot_player had none). Stairs are pure
geometry (the DC 0.51 ramp collider rides inside the glb), which is exactly
why they worked and ladders didn't.

- The generated walk scene now emits an Area3D climb volume (group "ladder")
  per gameplay ladder marker, placed through the building transform, sized
  like deli_counter_postimport.gd (+1 m dismount lip, base-anchored,
  generous square footprint so building rotation can't turn it edge-on).
- lot_player.gd gains climb mode, ported from DC's reference player: climb
  along where you LOOK (look up + W ascends, look down descends, look level
  + W steps off at the top), no gravity on the ladder, Space drops.
- Preview parity: preview.gameplay_from_spec synthesizes ladder markers from
  the spec's ladders array (mirrors deli_counter.py _ladders), so ladders
  work in --preview too, not just after a Blender build.
- Tests: 29 -> 30 (preview synthesis, volume placement/sizing/load_steps,
  player climb present).

## [0.16.0] - Site packs: the shareable deliverable for collaborators
`package.py` cuts a drop-anywhere folder-of-source (zipped) that a
collaborator can put at ANY path inside their own Godot project and instance
-- deliberately NOT a .pck (that's Godot's opaque runtime-DLC container;
teammates need inspectable, re-importable source).

- `python package.py specs/<site>.json` -> `dist/<site>_pack_<ver>.zip`
  containing: the composed `<site>.tscn` with RELATIVE ext_resource refs
  (works at res://levels/, res://maps/x/, anywhere), every instanced .glb
  (buildings + facade shells, resolved from next-to-spec then DC build/),
  `<site>.site.gameplay.json` (the integration contract), a PACK_README.md
  stating the contract (marker/opening/rarity semantics, axis mapping, the
  once-per-building reveal rule), and a self-contained QA walk scene with
  its two scripts copied in -- F6 with zero addon install.
- New `portable=True` mode on `write_godot_scene` / `write_walk_scene` /
  `write_navqa_scene`: relative refs instead of res://. Defaults unchanged.
- Missing .glbs fail loudly with the cater command that produces them; no
  --preview on purpose (a pack of massing boxes is not a deliverable).
- `cater.py --package`: cut the pack in the same one command, after the
  builds + assemble.
- **Reproducible releases:** the site spec gains a per-LEVEL `"version"`
  field -> pack named `<site>_pack_v<site_version>.zip` (bump it per walked
  release; the tool nudges if unset). Every pack carries
  `pack.manifest.json`: site spec sha256, per-file sha256 + sizes, each
  .glb's Deli Counter build provenance chained through (kit_version, spec
  hash, built_utc from the sibling DC manifest), the gate summary
  (pacing status, entries clear), and an optional `--note` ("walked full
  route ..."). The zip itself is DETERMINISTIC -- sorted entries, fixed
  timestamps, no build-time stamp anywhere -- so identical inputs give a
  byte-identical zip; a sidecar `.sha256` identifies the release.
- `cater.py --package --note "..."` passes the release note through.
- `gs_heist` site spec versioned `0.1.0` (first walked cut).
- Tests: 26 -> 29 (portable ref emission; pack contents + relative refs +
  missing-asset gate; deterministic release: byte-identical rebuilds,
  manifest hash integrity, provenance chain, sidecar).

## [0.15.1] - Lit walk/nav-QA scenes (the runtime was rendering unlit)
The generated `*_walk.tscn` / `*_navqa.tscn` carried no light and no
environment — in the editor the preview sun hid it, but at F6 the whole site
rendered as near-black flat mush (real .glb materials under zero light). DC's
own walk harness has always carried a proper rig, which is why solo building
walks looked right and site walks didn't.

- Both generated scenes now embed the exact rig from DC's
  `template/level_test.tscn`: shadowed `DirectionalLight3D` (same transform) +
  `WorldEnvironment` (ProceduralSky, sky ambient 0.6, filmic tonemap) — a Lot
  site walk lights identically to a DC building walk.
- `lot_site_walk.gd` HUD title is no longer a hardcoded "VAULT JOB": new
  `site_title` export, baked in by Lot from the site's name.
- Tests: 25 -> 26 (rig present in both scenes; load_steps stays in sync with
  the resource count; title baked).

## [0.15.0] - `cater.py`: site spec -> walkable Godot project, one command
The whole gs_heist hand-flow, codified. `python cater.py specs\<site>.json
"C:\path\to\GodotProject"` does everything the hands did: finds the Deli
Counter repo (--dc / $DELI_COUNTER / sibling ../deli_counter /
C:\Projects\deli_counter), builds every stale building AND every
blocker-referenced facade shell in headless Blender (incremental: only when
the .glb is missing or older than its spec; --force-build overrides), copies
each .glb into the project and each .gameplay.json next to the site spec,
syncs godot/addons/lot, writes a minimal Godot 4.7 project.godot into a fresh
folder, and runs lot.py (--walkable --navqa).

- `--preview` skips Blender + copies entirely — the same one command works on
  a machine with no Blender at all.
- `--skip-build` copies existing DC outputs + assembles (no Blender launch).
- Blocker shells map by stem (gs_facade_storefront.glb -> DC
  specs/gs_facade_storefront.json); a ref with no matching DC spec is assumed
  hand-made and reported, not fatal. Reused shells dedupe to one build.
- Missing outputs after the build phase fail loudly with the exact filenames;
  a failed Blender build stops the pipeline without touching what's already
  fresh.
- Tests: 23 -> 25 (incremental build decision; facade shell job mapping).

## [0.14.0] - Site-level heist staging + preview parity (rarity, openings) + `gs_heist`
Where the crew stages, where the cops arrive, and how long the route takes are
SITE concerns — a building's own spec shouldn't have to know street layout.
Plus two preview gaps closed: preview now speaks the same gameplay contract a
Blender build does, so the rarity index and the walled-in gate work in exactly
the mode where you're shuffling placements.

- `site_markers` gain `crew_spawn`: overrides building spawn markers for the
  walk scene (symmetric with the existing site-level `extraction` marker) and
  joins the nav-QA player proxies.
- `site_markers` gain bot spawns (`responder_spawn` / `horde_spawn` /
  `defender_spawn`): cop pressure arrives from the STREET — road ends, alleys —
  and now feeds the nav-QA harness without touching any building spec.
- `site_pacing` travel legs honor the site-level `crew_spawn` / `extraction`
  markers as route endpoints (building `at`s remain the fallback, so sites
  without the markers estimate byte-identically). Fixes the degenerate 0 m legs
  when spawn/objective/extraction all name the same building.
- `preview.gameplay_from_spec` stamps building `rarity` + `rarity_color`
  (mirror of the published DC contract table, docs/RARITY.md) and synthesizes
  exterior-wall `openings` from the spec (per-kind defaults mirror
  `spec_types.Opening.resolved()`), each carrying the building rarity. The
  site rarity index + `site_enterability`'s walled-in gate now work
  pre-Blender.
- New shipped site: `specs/gs_heist.json` — gas-station street-corner heist
  (2 enterable buildings, 2 facade-shell blockers, road + sidewalks, extraction
  pocket + spawn alcove in the south street wall, 10 cover pieces, 5 street bot
  spawns). Assembles clean: gates pass, 10+12 valid entries all clear, rarity
  `very_rare` on the auto shop end-to-end.
- Tests: 21 -> 23 (site crew_spawn resolution + nav-QA proxies; preview rarity
  contract).


## [0.13.0] - lot_player step-up (curbs, ledges, steep stairs)
- lot_player.gd now auto-steps short near-vertical obstacles after move_and_slide:
  raised sidewalks/curbs (0.11 roads), ledges, and steep stair noses it used to
  catch on. Raycast-probe step-up with a valid-direction check (only steps when
  walking INTO a face, not along it) and a head-clearance check (won't climb under
  low geometry). `max_step_height` export (default 0.45 m). Adapted from the
  standard FPS step-climbing approach; the DC stair RAMP collider (DC 0.51) still
  carries normal stairs, so this is for the curbs/ledges/steep cases.
## [0.12.0] - Blocker facade-shell hook (ready for the art pass; dormant now)
- A `blocker` may now carry an optional `glb` or `scene` ref (a DC facade shell),
  exactly like a real building. When present it's instanced at the blocker's
  placement instead of drawing a plain box; when absent it falls back to the box
  you have today, so every existing blocker is byte-identical.
- In `--preview` the shell is ignored and the blocker boxes — preview stays
  Blender-free and blockout-honest.
- Nothing in the shipped `vault_job.json` uses this yet. It's the hook so that,
  at art-pass time, DC can make a small family of cheap exterior-only facade
  shells (rowhome / storefront / industrial wall — collision + walls + windows,
  no interior, no gameplay markers, no nav) and the street's filler reuses them
  by reference, themed to match the heist buildings. DC makes the shells; Lot
  places them. Box-vocab stays Lot's; facade detail stays DC's.
- Additive; 21 tests unchanged.

## [0.11.0] - City grain: `roads` + `blockers` (street walls that guide the player)
- `roads`: flat asphalt strips with optional raised concrete `sidewalk`s, drawn
  between two points (`a`/`b` or `from`/`to` building ids). The street spine the
  block fronts onto -- DELCO/Philly grain instead of buildings floating in a
  field. `{ "a": [-90,-28], "b": [90,-28], "width": 10, "sidewalk": 3 }`.
- `blockers`: non-interactable filler buildings -- SOLID collision massing you
  cannot enter (`{at, size_x, size_y, height, rot?, color?}`). They wall the
  street and channel the player toward the real, enterable heist buildings. The
  deliberate contrast does the guiding: solid block = context you route around,
  see-through massing = a building you go into.
- `_box_node` / `_yaw_box_node` gained an optional `color` (a StandardMaterial3D
  override); roads/sidewalks/blockers are tinted, existing ground/path/cover are
  byte-identical (color defaults off).
- `specs/vault_job.json` rebuilt as a real city block: the three heist buildings
  front a main street; a row of rowhome blockers walls the far side and the backs,
  with alley gaps aligned to the building fronts so you're funneled down the
  street and into the heist buildings. Zero footprint overlaps; gates pass; 2
  objective approaches.
- All additive: composition, `--walkable`, `--navqa`, `--preview`, and 21 tests
  unchanged.

## [0.10.0] - `--preview`: walk the level with no Blender, one command
- `python lot.py <site>.json <out> --preview` composes the site with each
  building as labeled greybox **massing** (a walkable footprint pad + a
  see-through box you walk through + a floating id label) instead of a real
  `.glb`. The heist's real anchors (crew spawn / vault / extraction / cover /
  cop spawns) come from each building's Deli Counter **spec** via a bpy-free
  shim (`preview.py`), so `--walkable` and `--navqa` work fully — you walk the
  *level* (placement, routes, scale, nav, the flow) before building any geometry.
- Collapses the old five-step "build 3 buildings in Blender, shuffle 6 files,
  assemble, copy addons, open" down to: copy the addon once, run one command,
  open the scene. See `QUICKSTART.md`.
- A building record may now carry `"spec": "<dc_spec>.json"` (the JSON
  `new_level.py` writes without Blender). `--preview` reads it, synthesizes a
  `<id>.preview.gameplay.json` next to it (never clobbers a real `.gameplay.json`
  from a Blender build), and boxes the footprint. `specs/vault_job_buildings/`
  ships the three 0.49 building blockouts for the flagship example.
- `preview.py` is the one place Lot peeks at Deli Counter's authoring *spec*
  rather than the public `gameplay.json` contract — preview-only, mirrors the
  marker/room/objective shape, no acoustic surfaces, not authoritative. Swap in
  the Blender builds (set `glb`/`scene`, drop `--preview`) for the real walk.
- Non-preview composition, `--walkable`, `--navqa`, and all 21 tests are
  unchanged; `--preview` is purely additive.

## [0.9.0] - Feed the Heist Nav QA addon (`--navqa`): bots stress-test the site
- `python lot.py <site>.json --navqa` emits `<name>_navqa.tscn` — the composed
  site under a baked `NavigationRegion3D` plus a `NavQASetup` node that tags the
  heist's real anchors into the [Heist Nav QA] addon's groups and runs the bot
  pass: crew_spawn / objective / loot / extraction -> `navqa_player_proxy`,
  cover_low / cover_high -> `navqa_cover`, responder/horde/defender spawns ->
  `navqa_bot_spawn`. So 16 mock cops stress-test the actual heist (where the crew
  stands, the real cover, the cop ingress) with zero hand-placement.
- Ships `godot/addons/lot/lot_navqa_setup.gd` (bakes nav, spawns the grouped
  anchor markers, then loads + runs the QA director). **Decoupled**: if the Heist
  Nav QA addon isn't installed the scene still opens and walks — you get a
  warning instead of a bot run. Lot never hard-depends on the third-party addon;
  it just feeds it if present. The addon itself stays standalone (it QAs single
  buildings too, so it isn't a Lot feature — it's the in-engine validator Lot's
  offline intel defers to).
- On the vault job (real 0.49 buildings) the feed resolves to 11 player proxies,
  12 cover points, 1 cop spawn. Cop spawns are thin because Deli Counter heist
  branches emit few responder/horde markers (the director rings the rest around
  the crew start) — first-class cop-ingress markers on the DC side would sharpen
  pressure-direction QA. Cover count reflects DC 0.49's cover enrichment.
- Base `<name>.tscn` and the `--walkable` scene are unchanged; `--navqa` is a
  separate additive scene.

## [0.8.0] - Walkable sites (`--walkable`): drop in and play the heist
- `python lot.py <site>.json --walkable` now also emits `<name>_walk.tscn` — a
  press-play scene that instances the composed site under a baked
  `NavigationRegion3D`, spawns a first-person player at the crew start, and
  beacons the objective + extraction. This is the missing in-engine piece between
  "Lot composes a heist" and "walk the heist start to finish."
- Ships `godot/addons/lot/lot_player.gd` (a self-contained FPS walker — WASD /
  mouse / sprint / jump, no project input map needed) and
  `godot/addons/lot/lot_site_walk.gd` (bakes site nav, drops waypoint beacons +
  a HUD). Copy `addons/lot/` into your Godot project; the walk scene references
  `res://addons/lot/`.
- Crew-spawn / objective / extraction world positions are resolved at assemble
  time from the merged site gameplay and baked into the walk scene, so it needs
  no JSON parsing at runtime. Robust to heist branches that emit only
  objective/loot *arrays* (no objective marker): falls back to the array entry
  offset by the objective building's placement.
- `specs/vault_job.json` — flagship 3-building heist example: gas_station
  (approach/staging) -> bank (the vault) -> warehouse (escape), with a path
  triangle giving the objective two approaches. Heist gates pass; pacing reads
  short (intel only — the felt length is the vault-drill duration + AI pressure,
  which arithmetic can't see).
- The one thing only your in-engine walk confirms: navmesh quality across
  instanced buildings + outdoor, and multi-floor linking (a single baked region
  is ground-plane biased — upper floors need stairs bridged with nav-link
  anchors, the known Deli Counter caveat). `lot_site_walk.gd` documents the bake
  knobs to turn if AI nav looks wrong.
- Base `<name>.tscn` (composition) is unchanged — `--walkable` is purely
  additive.

## [0.7.0] - Compose .tscn buildings (scene-referenced, not just baked .glb)
- A building in the site spec may now be referenced by `scene` (a Godot `.tscn`
  that instances shared modules) instead of `glb` (a baked file). `scene` wins
  when both are given. Both are instanced the same way (a PackedScene
  ExtResource), so the site .tscn composes either.
- Why: Deli Counter's primary output is now the `.tscn` (greybox scene that
  references shared `res://art/zoo/` modules). Composing those at the site level
  means editing one shared module propagates across every building in the site,
  and theming applies at compound scale — the .glb path stays for self-contained
  shippable buildings.
- Backward compatible: `glb`-only specs are unchanged and byte-identical. The
  merged record now carries `source` (the resolved file) and preserves
  `glb`/`scene` as given. A building with neither is a spec error.
- gameplay.json merge, tactical, pacing, and enterability are untouched — they
  read merged data + footprints, not the geometry file. +2 tests (21 total).

## [0.6.0] - Site enterability gate (can you REACH the doors?)
- New site_enterability.py + a gate in assemble(): the approach-side sibling of
  site_tactical's connectivity gate. A building that's enterable on its own can
  be unenterable in a compound — its only door faces the perimeter, or a
  neighbour is parked against that face, or no path leads to it. Only Lot can see
  this, because only Lot knows the placements.
- GATE THE CLEAR-CUT CASE, WARN THE REST: HARD GATE (assemble refuses) when a
  building has real entries but EVERY one's approach is blocked by a neighbour's
  footprint or the perimeter — walled in. WARN when it's reachable but no
  authored path/courtyard leads to a clear entry, or when a building's own
  gameplay.json has no usable entry (a Deli Counter problem to fix there).
- Never auto-fixes (doesn't move buildings or reroute paths) and doesn't claim a
  clean pass means walkable — swing/vault clearance stays a walk-test fact. The
  per-building approach report attaches to the site gameplay.json under
  "enterability".
- Building records now carry `footprint` (from Deli Counter's gameplay.json) so
  the neighbour-overlap test works. Body-fit thresholds mirror Deli Counter's
  enterability.py.
- 3 new tests (walled-in gate, outside-perimeter, no-route warning); 19 pass.

## [0.5.1] - Rarity multi-entry follow-through
- Tracks Deli Counter 0.33.0: every opening (door/window/breach) now carries the
  building's rarity + a `building` id, so a building's multiple entry points all
  resolve to the same building + rarity through the merge. Lot already namespaced
  and building-tagged openings + markers, so this needed no core change — the
  newly-stamped windows simply flow through.
- Test updated: the window in the carry-through fixture is now stamped (a window
  breach is a valid entry attempt), and asserts its `building` tag survives.
- Tier name in test fixture aligned to `very_rare` / `legendary` (gold). 16 tests
  pass.

## [0.5.0] - Carry building rarity through the site merge
- A building's optional `rarity` (from Deli Counter) now lands on its record in
  the merged `<site>.site.gameplay.json`: each `buildings[]` entry gains
  `rarity` + `rarity_color` when the building declares one (clean/absent when it
  doesn't). So a compound carries a per-building rarity index — every door on the
  block its own reveal.
- The breachable door/breach openings Deli Counter already stamps with the
  rarity colour pass through the openings merge untouched, so a networked door in
  the assembled site pops the right colour with no extra work here.
- Lot does not assign rarities across a run — each building's rarity comes from
  its own spec. Deterministic per-run assignment from the site seed remains a
  possible future feature.
- New test: rarity carry-through (record + stamped openings). 16 tests pass.

## [0.4.0] - Pacing estimate + structural encounter intel
- New site_pacing.py. Two offline STRUCTURAL analyses over the declared site.
  Neither predicts "fun" (fun is a feel property only a playthrough reveals);
  both describe structure, with every number shown as an estimate from declared
  inputs, never a verdict.
- PACING: estimates time-to-complete for the mode's critical route as a
  min/expected/max range, checked against a target window (default 7-15 min,
  overridable). Heist = spawn->objective(+dwell)->extraction; assault =
  spawn->objective + resolution; survival = reach holdout + waves x wave length.
  Timings DERIVED from mode + distances (move_speed, objective_secs, wave_secs,
  etc.), each overridable per-spec under "pacing". Emits a transparent phase
  breakdown that sums to the estimate, into the site gameplay.json under
  "pacing", and a one-line status (within / too short / too long / straddles).
- ENCOUNTER INTEL: per-leg geometric FACTS about combat opportunity (route
  length, distinct approaches, open-ground distance, nearby cover count) under
  "encounters". Describes opportunity, NOT quality - explicitly never a score.
- Not a simulation, not an AI, not a fun-meter. No agents move, no shots fire.
  The in-engine walk remains the only thing that tells you if it's actually fun.
- Tests: too-short detection, breakdown-sums-to-estimate, overrides, encounter-
  facts-not-score (15 tests total, all offline).

## [0.3.0] - Site tactical layer (pathing + 3 modes, at site scale)
- New site_tactical.py: the site-scale echo of Deli Counter's tactical layer.
  Reasons about reachability and the three modes ACROSS the site (over buildings
  and declared paths), as Deli Counter does WITHIN a building (over rooms and
  doors). Intel + light gates, deterministic, offline - analyzes what you
  DECLARED (building-to-building paths + merged markers), not a computed navmesh.
- INTEL (never fails): site connectivity graph, isolated-building detection
  ("no isolated buildings" - the site echo of "no isolated rooms"),
  spawn->objective distance, count of distinct objective approaches. Emitted
  into the site gameplay.json under "tactical".
- GATES (fail the build) only when a site "mode" is declared:
  assault = objective building reachable by >=2 distinct approaches;
  heist = spawn -> objective -> extraction path-connected;
  survival = safe building -> holdout path-connected.
- New optional site-spec fields: mode, objective, spawn, extraction, safe
  (building-id designations). No mode => pure intel, no gates. The designations
  also resolve "which building's objective is THE site objective."
- Tests: tactical intel + all three mode gates (11 tests total, all offline).

# Changelog — Lot

## [0.2.0] — Phase 2: box-vocabulary outdoor
- Generate outdoor connective geometry as Godot primitive nodes (BoxMesh +
  BoxShape3D collision), NOT a baked .glb — keeps Lot offline (no Blender) and
  blockout-honest. Strictly axis-aligned boxes / flat regions; no terrain.
- New optional site-spec fields: `paths` (flat strips between buildings or
  explicit endpoints, with width), `courtyards` (flat rectangular regions),
  `perimeter` (four walls around the ground at a height), `cover` (crates).
- Ground is now a real slab mesh (was an empty StaticBody in Phase 1).
- Tests: outdoor node generation, path-length geometry, load_steps sanity
  (7 tests total, all offline).

## [0.1.0] — Phase 1: placement + merge
- Deterministic placement of built Deli Counter buildings on a shared site.
- Merged, world-offset, namespaced site `gameplay.json` (markers/rooms/
  objectives/loot/zones/surfaces/surface_roles), so buildings don't collide.
- Generated Godot `.tscn` instancing each building `.glb` at its placement.
- Buildings stay separate assets — rebuild one and the site picks it up.
- Tests: determinism, world offset+rotation, namespacing, valid scene.
