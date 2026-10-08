## 0.98.0 - the getaway van at the spawn: the crew starts at it and the job ends at it

The walker, 2026-10-07:
- "the default is they have to leave the building and return to the
  'getaway' car or vehicle to leave the scene";
- the vehicle "a Box Truck. Like a Chevrolet P30 ... Matte Black" -- Zoo's
  `step_van`, 1.82.0 to 1.85.0;
- "location of the getaway vehicle should be the same as the missions spawn
  point. you spawn, do the job, then return to the car".

2026-10-08: "go ahead, place it at the spawn". Roadmap 206, phase 2.

### `site_getaway`: where the van stands and where the crew does

**The van.** It parks in two adjacent parking bays, because a van is longer
than one 6.0 m bay. The pair is chosen on a kerb that a door of the spawn
building faces, as the one that puts the van's own door nearest that door,
within `MAX_REACH` (30 m).
- It faces the way its lane travels, as `site_parking`'s cars do, so its
  kerb side -- Zoo's -X, with the crew's door -- is against the kerb.
- Its body stands `KERB_GAP` (0.20 m) off the kerb line, so the slot, which
  runs out to the mirror heads, stops just short of it.
- It is a cover record (`source: getaway_van`, Zoo's genome dims
  2.6 x 6.8 x 3.05), so the site kit builds it, the walk scene's navmesh
  carves it, and every planner after it stands round it.

**The crew's point.** One point on the sidewalk outside the van's kerb-side
door:
- `DOOR_AHEAD` (1.65 m, pinned from Zoo's `van_forms.layout` because Lot does
  not import Zoo) toward the nose, and `SPAWN_OFF_KERB` (1.2 m) in from the
  kerb;
- it is both the site's `crew_spawn` marker and its `extraction` marker, the
  latter carrying `getaway: step_van`;
- `_walk_positions` takes a site-level marker over a building's own, so the
  crew leaves from it and the job ends at it.

**What gets no van, and says why** (`LOT_GETAWAY_NONE`):
- a site that is not a heist;
- a spawn building not on the site;
- a site that already declares its own start or exit -- a designer's
  site-level marker stands;
- no pair of free bays within reach of a door facing a road.

Without a van the spawn and the extraction are what they always were.

**No enemy stands in it**, by arithmetic rather than a rule. Every point of the
van lies within `site_spawns.MIN_STANDOFF` (8.0 m) of its door's spawn --
6.35 m at the far corner -- and `place_enemies` keeps every enemy that far
out.

### `assemble`

The van is planned before anything reads where the crew stands: after the
collision reading, before `_walk_positions`. It joins `cover` and its markers
join `site_markers`, which `merge_gameplay` copies only when the spec carried
the key, so both lists are kept. The plan travels in the gameplay JSON as
`getaway_plan`, and `LOT_GETAWAY_PLACED` says where the van went.
`COVER_MATERIALS["step_van"]` is `paint_matte`, Zoo's one option for it.

On the kerb probe the van takes bays L7-8 at (-62.0, 3.65), with the crew at
(-63.65, 6.2). That is 23.9 m from the garage's south door, which stands well
back from its road. The pair nearest the door's line lay inside a crossing's
setback.

### The enemies along one leg

With the van the extraction is the crew's spawn, and the route goes there and
back. `place_enemies` spread its samples over spawn -> objective ->
extraction, and the return leg is the outbound one backwards. Measured on an
open field:
- two enemies landed mirrored at one point;
- one was pushed 43.5 m off the route;
- three crowded the middle.

A route whose extraction stands within `THERE_AND_BACK` (3.0 m) of its spawn
now spreads the enemies along its one leg. All six land within 6.5 m of it,
and the crew passes them going in and coming out.

### The audit

- **`S_BACKTRACK`** ("the exfil rewinds the entry") fired at 0 m and 0
  degrees on every level built the walker's way. When the extraction marker
  names a getaway van it is `S_GETAWAY_AT_SPAWN`, INFO: the second half of
  the heist is the walk back to the van, by design. Without the van's mark,
  the same geometry is still `S_BACKTRACK`.
- **Two anchors at one point are judged once.** `S_RESPONDER_CAMP` and
  `S_NAKED_ANCHOR` checked the crew spawn and the extraction separately, and
  reported one problem twice when the two are one point.

### Tests

**`tests/test_site_getaway.py`: 9.** They cover:
- the kerb the spawn building faces, and a pair of free adjacent bays;
- one point as spawn and extraction, at the door, clear of the slot;
- no enemy inside the van;
- every refusal saying why;
- determinism;
- `assemble` writing the van as a `paint_matte` slot, with the markers in the
  drawn spec and every parked car outside it;
- the audit's INFO, and its single camp line;
- the enemies along one leg. With `THERE_AND_BACK` 0 this test FAILS, on the
  enemy 43.5 m off the route.

**Suite:** 678 passed (669 and the 9).

## 0.97.4 - the root test moves under tests/, and the `--out-dir/` directory goes

Repo hygiene (`docs/findings/repo_hygiene_2026-10/` at the factory root).
- `test_ladders_reach_the_site.py` stood at the root beside `tests/`. It is
  under `tests/` now, with `HERE` pointing at the repo root as the other
  tests' path line does; it ran 5 passed there and the suite 669.
- A tracked directory literally named `--out-dir/` held one assembled
  `example_compound.tscn`: an `assemble` run given the flag's name as its
  value. Nothing read it (the tests assemble `specs/example_compound.json`
  into a temp dir). Removed.

**Suite:** 669 passed, as 0.97.3.

## 0.97.3 - no spawn inside an Empty, and no enemy behind an Empty row's front line

**Every refusal was the same defect.** Laser Tag refused four candidates in
cold runs 9164 to 9186 on `UNREACHABLE_SPAWN`: seed_9061 in 9170 and 9174,
and seed_9205 in 9179 and 9186. In each, Enemy_5 stood inside an Empty, e15
or e9 (`docs/findings/enemy_inside_an_empty/` at the factory root).
- **The control:** the other 17 enemies of 9186's candidates stand in the
  open, and so do all 18 of 9187's.
- An Empty is a house with its doors shut. Nothing inside one can reach the
  street.

**How.**
- `place_enemies` pushes a route sample sideways until `outdoors()` calls it
  open ground. `outdoors()` asked `footprints()`, which reads `buildings`,
  and an Empty is a blocker.
- 9186's Enemy_5 is 24.00 m off the route's last leg, the run's own
  `LOT_ENEMY_SPAWN_PUSHED` figure.
- With the collision reading `assemble` passes, 0.97.2 reproduces every
  shipped enemy on six candidates.
- `plan_fences` never strands a marker behind a row's front line, but it
  skips one inside a house. 9186's fence went up around an enemy already
  shut in.

**Why the band too.**
- On 9186's seed_9205, keeping the Empties out is enough. Enemy_5 goes to
  1.33 m clear of the row's front line.
- On 9174's seed_9061 it is not. Kept out of the Empties alone, Enemy_4 and
  Enemy_5 land behind the front line, on ground the row's fences shut off
  out to the plate's edge.
- With the band kept out as well, they stand in open ground on the far side
  of the route, pushed 50.0 and 45.0 m. The moves are large, and
  `LOT_ENEMY_SPAWN_PUSHED` reports them.
- On the runs in flight, the rule moves no enemy on any candidate of cold
  runs 9187 and 9178.

**Refuted, kept.** The first comparison measured on the declared-footprint
occluders without saying so. It quoted "Enemy_4 pushed through its house" as
Lot's placement for 9186. That is the fallback's placement; under the
collision reading, 9186's Enemy_4 never moves.

**What changed:**
- `site_extent.blocker_rect`: one reader for a blocker's plan rect (world
  extents, 12 m when unsaid). The ground, the fences and the spawns ask it;
  three copies of the rule existed.
- `site_fences.shut_band` / `shut_bands`: the band behind a row's front line,
  which `plan_fences` computed inline. The fences and the enemies now ask one
  function.
- `site_spawns.blocker_rects` and `solid_rects` (the footprints and the
  blockers): `crew_spawns`, `clear_crew_spawn` and `place_enemies` ask
  `outdoors()` of them. `place_enemies` also keeps out of
  `shut_band_rects`.
- **Not changed:** `plan_cover`'s sightline occluders and the pylons'
  keep-out read `footprints()` alone. Whether an Empty is cover to the cover
  planner is another question, with a visible effect.

**Tests:** `tests/test_spawns_keep_out_of_empties.py`, 5, on
`tests/fixtures/restaurant_row_001_seed_9205.site.json`. That is 9186's site
as drawn, byte for byte.
- It runs on the declared-footprint fallback, where 0.97.2 puts Enemy_4 in
  e13 and Enemy_5 in e9.
- What the tests hold:
  - the fixture is the refused site;
  - no enemy stands in a blocker;
  - none stands behind the row's front line;
  - the crew keeps out of a blocker;
  - the fences and the enemies ask one band.
- Blockers and the front line are read by the test's own arithmetic. Four
  fail on 0.97.2 on where the enemies stand; the fixture check passes on
  both.

**Suite:** 669 passed (0.97.2's 664 and these 5).

## 0.97.2 - the walk test decides ladder access from the anchor, not from where Godot's path stopped

**Cold run 9185, roadmap 189 at the factory root**
(`docs/findings/stairwell_on_one_grid_in_four/`). One anchor in one navmesh
got two verdicts.
- The anchor is deli_a03's objective, upstairs and off the main network.
- From `proxy_1` it passed as "VERTICAL access (ladder/drop)". From `home`
  it failed as "path stops 60.99 m short (disjoint islands)".
- 9179 had passed it from both starts, on identical islands.
- Two candidates of three were lost to it.

**The mechanism.** `_prove_path` asks Godot for a path to the anchor.
- For an unreachable target, Godot returns a path to the nearest point it
  reached. The leg passed when that point lay under or over the anchor.
- In 4.7 that fallback can fail inside the engine: "It's not expect to not
  find the most reachable polygons" (`nav_mesh_queries_3d.cpp:404`).
- It then returns a path that stops beside the START: 2.9 m from home in
  seed_9003 and 4.2 m in seed_9205.
- In both, the job log shows the engine's error on the call immediately
  before each FAIL.

**Now `_vertical_access` asks the question of the anchor.** It samples the
anchor's column height by height, nearest first, from 1.5 m out to
`VERTICAL_REACH_M`. That reach is the library's longest ladder (8.0 m,
measured over deli_counter's gameplay files) plus a storey band. A surface
counts when:
- it lies inside the old concession's window: within 1.5 x `SNAP_MAX`
  across, and more than 1 m up or down;
- and a strict route from the start reaches it.

`_prove_path` and the non-strict `_reaches` both use it. Neither reads the
end of a failed path any more.

**Superseded, kept** (`patch_lot_vertical_access.py`, then
`_column.py`). The first version asked for the single point closest to the
whole column.
- That is the floor under the anchor's own foot every time.
- So it failed `proxy_2 -> proxy_3`: a drop from the deli's upstairs edge to
  the street, 2.7 m out and 3.3 m down, which the old rule passed in both
  9179 and 9185.
- The second version keeps the old window, and passes it.

**Proven on a copy of 9185's staged seed_9003:**
- `home->proxy_2` and `proxy_1->proxy_2` agree: both walk to (-54.0, 0.3,
  12.5), the floor under the objective.
- `proxy_2->proxy_3` passes as before.
- `ok: true`, 0 proof failures. The anchor is still reported stranded, as
  information.
- The engine still logs its error 10 times, from the census's strict
  queries. No verdict reads it now.

**Tests:** `tests/test_nav_qa_vertical_access.py`, 3. The director is
engine-bound, so it is read as source:
- `_vertical_access` samples the column inside the old window and reaches
  strictly;
- neither verdict reads a failed path's end;
- the reach is derived, and says from what.

All three fail on 0.97.1.

**Suite:** 664 passed (0.97.1's 661 and these 3).

## 0.97.1 - a fence does not grow the plate it marks the edge of

**Cold run 9183, measured on its own scenes.** The greybox `site.tscn` and
the themed one both stood `perim_S` at 254 m. 9182, the same candidate
without fences, stood it at 246 m.

**The mechanism** (`site_extent.required_rect`). The ground carries the union
of everything on the site grown by `CLEARANCE` (4 m), and every cover piece
is in that union.
- 0.97.0's end runs reach the plate's edge by design.
- Re-resolved with the fences standing, the plate grew 4 m past each one.
- Each end fence then stopped 4 m short of the perimeter wall. That left a
  walk-around at both ends of the row, which is exactly what the end runs
  were for.
- The `LOT_GROUND_EXTENDED` line still said 246 m, because it was printed by
  the resolve before the fences stood.

**The fix:** `content` leaves out cover that `site_fences` placed. A fence
marks the playable edge; it is not content the ground has to carry clearance
around.

**Re-assembled** with this checkout on 9183's own `site.json` (seed_9181):
`perim_S` is 246 m, and the 13.0 m end run stops at x -123.0, where
`perim_W` stands.

**Tests:** `tests/test_site_fences.py::test_the_fence_does_not_grow_the_plate_it_marks`.
It resolves the ground, plans the fences, resolves again with them standing,
and asserts the rect is unchanged and the end runs still reach it. It fails
on 0.97.0.

**Suite:** 661 passed (0.97.0's 660 and this test).

## 0.97.0 - the fence at the playable edge: an Empty row's gaps

**The walker, 2026-10-04:** "I like the idea of a fence between playable
areas and non playable areas, thats good feedback to the player". A fence
goes wherever playable ground meets an Empty's back, a vacant lot or the
backdrop. Zoo 1.77.0's `chain_link_fence` is the fence.

**Phase one: an Empty row's gaps** (`site_fences.plan_fences`).
- The Empties stand in rows across the street, doors shut, backs to the
  plate's edge.
- Every gap a body fits through between two of them is a way behind the row,
  onto ground nothing was built for. So is the ground from each end of a row
  to the plate's edge.
- A fence closes each, along the row's front line, flush with the facades.
  From the street the row reads as one frontage with its alleys gated.

**What a body fits through is the player's capsule:**
`characters.player.radius_m` twice, 0.7 m, read from the contract.
- The navmesh's own narrowest gap (`site_cover.min_passable_gap`) is wider.
- A gap between the two is one a player squeezes through and a QA walker
  cannot. That makes it exactly the gap the walk tests would never report.

**The front line** is the row's long edge nearer a road.

**Never across a way, and never around a marker.**
- A run out from a row's end stops at the first road (with its sidewalks),
  path, building or blocker it would cross.
- A gap between two houses that anything crosses is not fenced.
- A run that would stand on a mission marker is not placed.
- A row with a marker anywhere behind its front line is left open, because
  fencing it would strand the marker.
- Each is said (`LOT_FENCE_SKIPPED`), never forced.

**Assembled on cold run 9180's site** with this checkout, against its
`site.json`:
- `LOT_FENCE_PLACED` three times: the 3.0 m alley between the seventh and
  eighth houses, and 13.5 m and 22.0 m from the row's ends to the plate.
  The plate is the extended 134 m, not the declared 115.
- All three reach `site.slots.json` as `chain_link_fence` prop slots, for
  the Zoo kit build to make.

**`COVER_MATERIALS`:** `chain_link_fence` is `metal_bare`, galvanised. The
fabric is its own kind in Zoo.

**Tests** (`tests/test_site_fences.py`), 9:
- a gap a body fits through is fenced along the front line;
- a gap too narrow is left alone;
- a run out from the row stops at a road;
- a gap a path crosses is not fenced, and is said;
- a fence never stands on a marker;
- a row with a marker behind it is left open;
- a row facing x runs along y;
- cold run 9180's row: 3.0, 4.0 and 12.5 m on its declared plate;
- the body is the player's capsule, 0.7 m.

Choosing the wrong long edge as the front line fails four of them. The
file cannot be collected on 0.96.0.

**Suite:** 660 passed. That is 0.96.0's 651 (counted in a worktree at
`main`) and the 9 above.

## 0.96.0 - a standing piece keeps dressing out of its own footprint

`site_surfaces.exclusions` gave every cover piece a `cover_edge` exclusion
of `site_cover.MARKER_CLEARANCE` (3 m) from its centre: "a cover piece
whose base is buried in scatter stops reading as cover". The rule never ran
in the pipeline -- the surfaces job read the authored spec, which carries no
cover -- until 0.95.0 made it read the site as drawn. On cold run 9143 it met
164 pieces (lamps, trees, benches, hydrants, bins, the kerb lane's cars and
the fields'), exclusion refusals went 493 -> 2,061, and every kerb line
became a 3 m clear ring: the sidewalk under each lamp bare in the frames
where 9141's carried litter.

The premise does not hold for dressing: a dressing piece is at most the
`low` band (0.30 m) and the shortest cover piece is `site_cover.
MIN_COVER_HEIGHT` (1.3 m), so scatter cannot bury cover. What a standing
piece needs is no dressing INSIDE it. Its exclusion is now its own
footprint (`size` in plan, as `assemble` stands it; `lot.COVER` when it
carries none), no radius; the markers keep `MARKER_CLEARANCE`.

MEASURED by re-running cold run 9143's surfaces and dressing jobs on its own
inputs with this (`_runs/dressing_096`), beside what 9142 and 9143 shipped:

                              9142        9143        this
    pieces                    5,232       2,226       3,566
    on another zone's ground  1,430       0           0
    sidewalks                 1,822       351         1,421
    roads (low)               1,071       331         477
    fields, a m2              0.288       0.065       0.080
    exclusion refusals        493         2,061       540

What remains of the drop from 9142 is the double dressing Patina 0.23.0
stopped: open ground's scatter on roads, sidewalks, the perimeter and the
fields.

`tests/test_site_surfaces.py`: the markers keep site_cover's circle and a
cover piece is a footprint; a 4.3 x 1.75 m car excludes a point on its
roof and not one 0.5 m off its side, which the 3 m circle reached
(literals).

## 0.95.0 - the dressing reads the site as drawn, and a field is its own zone

TWO FIXES, ONE CAUSE: the surface dressing was planned on a site that is
not the one in the scene.

THE SITE AS DRAWN. Level Factory's surfaces job runs `site_surfaces.py` on
the AUTHORED spec, while `assemble` draws something else -- walks
re-routed to real doors and some not drawn at all (0.88.0-0.91.0), the pads
(0.93.0), the fields and driveways (0.94.0). Measured on cold run 9142's
shipped site: the dressing was told of 6 walk slabs at the old
centre-to-centre stations (`path_0` at (30.5, 7.5), a walk between two
buildings 0.91.0 stopped drawing); the scene holds 9, none at those
stations; no pad or field reached `tops` or `zones`. So 54 low-density walk
zones dressed ground that is not a walk, and the real walks took open
ground's scatter. `assemble` now writes the spec it drew,
`<name>.site.drawn.json`, beside the scene, and `site_surfaces.py`'s CLI,
handed that out dir as `--base-dir` (Level Factory already passes it), reads
it in place of the authored spec and says so (`LOT_SURFACE_SPEC_AS_DRAWN`,
info). An out dir with none -- an older assembly, a probe -- reads as before.

A FIELD IS ITS OWN ZONE. 0.94.0 gave the fields no zone, so the ground
scatter dressed them as open ground at MEDIUM: on cold run 9141 all 256
pieces on the fields came from `open_ground` (0.29 a m2), the walker's
"pebbles on the aisles". A lot's aisle is a carriageway, and the guide's
reading of a road's centre is LOW. Each field now declares a `parking`
zone at its own top (`FIELD_THICK`), LOW, ranked after the road and ahead
of the courtyard, the perimeter and open ground. With Patina 0.23.0 (a zone
dresses only the ground it owns) the field's own zone is the one that
decides. Measured on cold run 9143 (`docs/cold_runs/cold_9143/NOTES.md`).

`tests/test_site_surfaces_field_zone.py`: a field declares a low zone at
its own height over its own rect; it owns its aisle ahead of open ground; a
site with no fields declares none; `assemble` writes the site it drew (the
fields, driveways, cover and footprints the authored spec lacks); and the
CLI plans on it and says so -- the control, the same spec with no drawn
site beside it, reads as before.

## 0.94.0 - a parking field in a gap between buildings

Step 4 of `docs/proposals/LAND_USE_DESIGN.md` (open land gets a role, the
land-pressure guide's 5.4), agreed by the walker 2026-10-03; its second use,
and the one sized to move the remainder. A gap between two storefronts was
bare plate. In a suburban strip -- the guide's "broad gaps often occupied by
parking or circulation" -- it is the lot the customers park in.

`site_fields.plan_fields`: along each road with a sidewalk, on each side a
building fronts, the gaps between the fronting buildings' spans (and from
the road's drawn ends to the first and last) take one field each when they
hold it. A field is one module from common practice: a two-way aisle
(24 ft, 7.3 m) square to the road and 90-degree bays (9 x 18 ft, 2.7 x
5.5 m) both sides of it, so 18.3 m along the road, 1.0 m clear of the
buildings either side. Its driveway keeps 15 m (50 ft) from any junction,
sliding along the gap when it can. It is as deep as it can be, two to six
bays, while it stays clear of every drawn surface (separating axes), of
what stands, of the plate's edge, and no deeper than the buildings beside
it. Gaps on the lots on disk run 10-37 m (`patches/lot_fields/
gap_survey.py`).

THE DRIVEWAY is a new crosser kind in `site_streets.kerb_crossings`,
`driveway`: from the carriageway's edge to the back of walk, so it drops
the one kerb it crosses and never meets the centre line -- no crosswalk, no
stop bar -- and `site_furniture` gives it none of a crossing's corner
pieces (no hydrant, bin or blade post; the test's control is a walk cutting
the same kerb, which gets all three). The kerb lane's bays already skip
every cut, so no kerb car parks across it.

THE CARS: a seeded share of the bays (`site_parking.OCCUPANCY`, a SHA-1 of
the bay) holds one of `site_parking.CARS`, nose in, as a cover record --
the same collision piece a kerb car is, standing in the cover planner's
measurement. A car keeps `site_cover.MARKER_CLEARANCE` from every marker,
1.5 m from every door's approach point, and `ENEMY_CLEAR` (12 m) from every
enemy spawn -- see below for why that last rule exists.

The field is a `parking` slab (`field_slabs`, `field_<i>`) at the road's own
height, so the asphalt runs from the carriageway through the dropped kerb
into the field, skinned from `ground_skins["parking"]` (Level Factory
0.134.0: the theme's asphalt). Its bay lines are the road's paint, drawn as
the road's marking quads (`fmark_<n>_bay_line`) and carried in
`<site>.markings.json`. `tops` declares the slab, `site_steps` walks on it,
the census counts it as `parking`. `assemble` plans the fields BEFORE the
street's furniture, so lamps, trees and kerb bays step round the driveway,
and the pylons, dumpsters and pads planned after keep off the fields. The
gameplay records the fields, their cars and the cars' `cover_<i>` nodes
(`field_plan`).

MEASURED (`patches/lot_fields/before_after.sh`, `docs/findings/
landuse_fields_before_after.txt`), the nine candidates of 0.93.0's
before/after, built fresh by this:

    fields a lot          1-4 (23 in all, every one six bays deep)
    parking               288-1,176 m2 a lot
    cars in the fields    6-30 a lot (before the enemy rule)
    remainder             down 1.5-6.1 points; gas_block_001 seed 9080
                          59.90 % to 55.17 %, its largest piece
                          10,544 to 9,664 m2

A REGRESSION FOUND, AND ANSWERED BY A DERIVED RULE. The first build had no
enemy rule. On gas_block_001 Laser Tag added four findings, every marker
unmoved. Three were seed 9181's: four field cars stood 4-10 m from Enemy_0,
the crew's survival fell from 70.6 s to 5.5 s and the enemies fired first
(1.9 s against the crew's 4.0 s). `site_cover` already states the
principle -- cover is biased to the crew's end, because a piece at the
other "hands the enemy the wall to hold" -- and the field's cars ignored
it. `ENEMY_CLEAR` = Laser Tag's enemy speed (4.0 m/s) x its instant-contact
window (3.0 s): all the ground an enemy reaches before the gate calls the
contact instant. Rebuilt with it (`patches/lot_fields/enemy_rule_check.sh`,
`docs/findings/fields_enemy_rule_check.txt`), seed 9181 has 19 field cars
not 25, the crew fires first again (2.93 s, the enemy 3.19 s; 3.13 / 3.66
with no fields), route progress 0.61 (0.65 with no fields, 0.35 without the
rule), and OVEREXPOSED, NO_REACTION_TIME and INSTANT_CONTACT are gone.

NOT answered, and said: seed 9181's survival recovered to 37.3 s, not to
70.6 s, and it gained LT_MAP_ENEMY_STUCK, whose events carry no position.
Seed 9080's INSTANT_CONTACT stays: no car there is within 14 m of a marker
and the rule removes none, the first enemy shot moved 3.06 to 2.86 s
across the 3.0 s line, the crew still fires first (2.47 s), and its
survival rose 12.7 to 13.7 s; the build also lost five kerb cars to the
driveways' cuts (34 to 29), which is the other thing that changed on its
ground. Seed 9282 read identically in all three builds -- the bot sim is
deterministic, so the differences above are the geometry's. Findings
43 / 43 / 42 to 45 / 42 / 42.

`tests/test_site_fields.py`: one field centred in a 30 m gap, four bays to
the buildings' backs (literals); none in a 17 m gap; none within 15 m of a
junction and one when the junction moves; the plate's edge, a walk and a
standing piece bound its depth; the driveway drops one kerb, is no
crossing, paints nothing and takes no kerb bay; it gets no corner
furniture where a walk does; no car within 12 m of an enemy, and only
those removed; cars nose in, inside the field, clear of a marker, the same
twice; bay lines inside the field; and a field is drawn, declared where it
is drawn, walked on, painted, counted and in the markings manifest. The
kerb probe's own `assemble` test now plans a field and its manifest
carries `bay_line`.

## 0.93.0 - a concrete pad under each dumpster

Step 4 of `docs/proposals/LAND_USE_DESIGN.md` (open land gets a role, the
land-pressure guide's 5.4), agreed by the walker 2026-10-03; its first use,
the one the site already implied. 0.90.0 stood a dumpster on the bare
plate, and a real one stands on a pad: it is heavy, the truck's forks drop
it on every lift, and the ground in front of it is where the truck works.

`site_yards.plan_yards` gives each dumpster a pad, from the wall's face
outward, centred along the wall on the container and never past the
wall's ends: `PAD_ALONG` 3.7 x `PAD_OUT` 3.0 m (a single-container
enclosure, about 12 x 10 ft) and an `APRON` of 3.0 m beyond, where a
front-load truck's forks reach -- the commonly published figures, read as
typical. It shrinks, apron first in 0.5 m steps, then width down to 0.3 m
beyond the container's sides, until it is clear of every surface Lot
already draws (`site_surfaces.tops`), of the other buildings by 0.3 m, of
what already stands but its own dumpster, of the other pads, and inside
the plate by 0.5 m; of the sizes that fit, the largest area wins. Overlap
with a drawn surface is decided by separating axes, not bounding boxes, so
a diagonal walk passing a pad's corner does not cost it its apron. A
dumpster whose pad cannot cover its own footprint is said
(`LOT_YARD_NO_ROOM`) and stands on the plate as before.

The pad is a `yard` slab (`yard_slabs`, `yard_<i>`), a courtyard's shape,
at `YARD_THICK` -- the courtyard's tier, since a pad never overlaps another
drawn surface. Drawn in the greybox at `YARD_COLOR` and skinned from the
spec's `ground_skins["yard"]` (Level Factory 0.133.0 names the theme's
concrete). `site_surfaces.tops` declares it, so dressing stands on it;
`site_steps` walks on it (`yard_`); the land-use census counts it as `yard`.
`assemble` plans the pads right after the dumpsters and records them in the
gameplay (`yard_plan`), where `tools/landuse_census.py` reads them.

MEASURED (`patches/lot_yards/before_after.sh`, `docs/findings/
landuse_yards_before_after.txt`): the three briefs of Level Factory
0.132.0's before/after (gas_block_001, club_block_014, crossroads_9600),
three candidates each, built fresh by this and compared with 0.92.0's
builds of the same seeds. Every one of the 27 dumpsters got a pad, none
said no room, 25 at full depth (3.37 x 6.0 m, clipped at the wall's end
because a dumpster stands 0.6 m in from its corner) and two at 5.5 m.
That is 58-60 m2 a lot, and the remainder falls by 0.25-0.32 points
(gas_block_001 seed 9080: 60.22 % to 59.90 %). Small, and said as small:
the remainder is the ground behind and around the row, not under the bins,
and the parking fields are the use sized to move it.

Findings 43 / 45 / 43 to 43 / 43 / 42, none gained. The three lost are
Laser Tag's bot-sim verdicts (club_block_014 seed 9282's TRIVIAL_ENCOUNTER
and LOW_COVER, crossroads_9600 seed 9701's TRIVIAL_ENCOUNTER) and are NOT
attributed to this: a pad is 14 mm of flat concrete and stands in no
sightline. The bots' outcomes on those seeds move run to run.

`tests/test_site_yards.py`: a pad runs from the back wall under the
dumpster and out past it, clipped at the wall's end (literals, not module
constants); its apron gives way to a walk, and a walk over the container's
own front leaves it none, said; a diagonal walk off its corner is cleared by
shape, and moved 0.1 m in, is not; the plate's edge and a neighbour bound
it; a row of buildings gets a pad each, none overlapping, the same twice;
and a pad is drawn, declared where it is drawn (`test_site_surface_tops`'s
own check), walked on and counted.

## 0.92.0 - what the ground is for, measured

The walker, 2026-10-03, filing `docs/reference/LAND_PRESSURE_AND_SPATIAL_LOGIC.md`:
"this should directly inform Lot". The guide's rules -- every piece of open
land has a visible role, frontage is used, variation is correlated, the
tools state their measurements -- had no measurement here. `site_landuse.
census(site_spec, merged)` is one, and changes nothing.

One boundary, the resolved plate, on a 0.5 m grid; each cell takes the
first use whose DRAWN geometry holds it: a building's footprint, then the
slabs `site_surfaces.tops` declares (road, kerb cut, sidewalk, frontage,
walk or landing, courtyard); the rest is `remainder`, ground with no role.
Reported: each use's area and share, the largest connected piece of
remainder, coverage, each building's nearest neighbour exterior to
exterior, and per road the buildings that front it (within `FRONT_REACH`,
30 m), their setback from the back of walk and its spread, the frontage
they occupy on each side, and whether each has a ground door facing it. A
surface family it does not know is listed, not silently counted.

`tools/landuse_census.py` (at the factory root) runs it over every lot on
disk. The 36 distinct lots: remainder median 68 % of the plate (53-88 %),
coverage median 14 %, a building line spreading up to 26 m along one road,
and a ground door facing the road on 67 of 126 fronting buildings. The plan
these numbers lead to is `docs/proposals/LAND_USE_DESIGN.md`.

`tests/test_site_landuse.py`: every cell one use and the building its
footprint; a road and its sidewalks counted as theirs (the first draft of
this test expected the road to span the plate, and the census was right:
the plate runs on past a road's ends); the building line and door facing
read per road; separation exterior to exterior; an unknown family said.
Suite 628.

## 0.91.0 - a walk leads to a door, and a side door gets a landing

The walker, 2026-10-03, walking 0.90.0, with a frame of the bank's west
wall: "still have sidewalks going to walls", and of 0.89.0's square walk
between the gas station's east door and the terminal's west door, "looks
better, but you should do some research as to what looks more natural on a
path between the sides of 2 buildings (not the normal path that customers
would likely take)".

THE WALL WAS A BREACH. The bank's west wall has no door: it has a breach
(a wall a team blows through) and a high window, and 0.88.0 snapped to any
opening `site_enterability` counts as a way in -- a door, a garage, a
breach, a vaultable window. A walk now leads only to an opening of kind
`door` a body fits through.

WHAT THE RESEARCH SAID (sources and readings in
`docs/findings/entry_paths/NOTES.md`): design codes ask for a continuous
walk along a facade with a customer entrance, tied to the street sidewalk;
a site walk crosses open pavement only where it must, square to the aisle,
which is never itself the walkway; building codes put a level landing
outside every exterior door, at least the door's width and 36 in deep, 60 x
60 in where accessible, with the lot's own pavement past it. Two separate
businesses' side doors are not joined by a walk.

So `site_paths.snap_to_doors` now:

  * slides a door spur to the nearest DOOR facing the way it leaves and
    runs its near end up to the wall, `DOOR_BURY` (5 cm) into it, where it
    stopped a metre short;
  * leaves a spur that meets no door UNDRAWN (`drawn: False`) and says so
    (`LOT_PATH_END_OFF_DOOR`) -- the record stays, because the street graph
    reads it to know the building meets that road;
  * leaves every building-to-building path undrawn, record kept for the
    connectivity graph;
  * gives every door no walk reaches a LANDING: a slab from the wall out
    `LANDING_DEPTH` (1.525 m, 60 in) along the door's normal, the door's
    width plus `LANDING_SIDE` (0.3 m) each side, never under `LANDING_MIN`
    (1.525 m), appended as a point path naming its building in
    `landing_of`.

`site_paths.drawn(site_spec)` is the list the six readers that draw or
measure a walk now iterate: the slabs, the surface zones, the step gate,
the kerb crossings, the furniture keep-out, and the enterability route
check (which also skips landings, so its "no authored path leads to a clear
entry" warning keeps meaning that). The connectivity graph and the plate's
extent read every record, so which buildings connect and how big the
ground is do not move.

0.89.0's legs (`_walk_legs`, `WALK_WIDTH`, `ALIGNED_TOL`) are gone with the
walk they drew.

`tests/test_site_paths.py`, nine tests: a spur slides to its door and runs
to the wall; a breach, a vaultable window and a garage are not doors to
walk to; two neighbours' side doors get a landing each and no walk; a
narrow door's landing is still 60 in wide; a rotated building's landing
points out of its own wall; the street graph still joins buildings whose
walk is not drawn; endpoints; the route check counts a walk and not a
landing; every drawing reader reads the drawn list.

## 0.90.0 - a dumpster at each building's service side

The walker, 2026-10-03, with two photographs of front-load containers: "we
should have some trash dumpsters next to buildings (sides or back where its
not in the way of where customers would naturally walk into the building)".
Zoo 1.58.0 builds the species; this decides where one stands.

`site_dumpsters.plan_dumpsters`, called in `assemble` after the street and
the pylons and before the cover planner: one a building, against a wall
that is not a street face. A wall is a STREET FACE when a road's band lies
in front of it within `FRONT_REACH` (30 m: Level Factory stands a face 2 m
from its sidewalk and a forecourt put one 15 m back on cold run 9139). The
BACK -- the wall opposite the nearest road -- is tried first, then the
others in an order the building's id picks, so a row does not put every
dumpster on its east side. Along the wall it stands toward a corner,
`CORNER_IN` from the end, stepping in a metre at a time until the station
is clear: `DOOR_CLEAR` (2.5 m) along the wall from any way in,
`WINDOW_CLEAR` (0.5 m) from any other ground opening, `APPROACH_CLEAR`
(1.5 m, the enterability gate's staging depth) from every entry's approach
point including the ones round the corner, off every path and walk
(`site_furniture.path_corridors`, which since 0.89.0 is the legs), off
every road band, clear of the other buildings, of what already stands and
of the mission's markers, and on the plate. Its back is `WALL_GAP` (0.25 m)
off the wall and its front faces away from the building.

A building with no wall that takes one prints `LOT_DUMPSTER_NO_ROOM` and
gets none; each one stood prints `LOT_DUMPSTER_PLACED`. The piece is cover
like the street's: a slot Zoo builds to, a box in the greybox, a solid in
the navmesh, and the cover planner counts it.

THE HAULER IS THE PIECE'S `variant`, picked by the building's id, and it
needed two rungs that cover did not have: `write_site_slots` writes a
piece's `variant` onto its slot (non-zero only, as Zoo spells `_n<v>`), and
`cover_module_refs` asks for the variant's module before the plain one, so
the second hauler's dumpster falls back to the first's and never to a box.

`DOOR_CLEAR` and `FRONT_REACH` are chosen and say so; neither has been
walked.

`tests/test_site_dumpsters.py`, nine tests: the back first, facing away, a
gap off the wall, toward a corner; never a street face; clear of a back
door and out from under a window; a neighbour's door across a gap not
boxed in; off walks, off what stands, on the plate; no room said and nothing
stood; a row gets one each, no two sharing a station, the same every run;
the slot carries the hauler and the module's name does; Lot knows the
species.

## 0.89.0 - a walk between two doors is drawn square to the buildings

The walker, 2026-10-03, walking 0.88.0's lot, with two frames of the band
between the gas station's east door and the terminal's west door, and of
the same band's end against the bank: "these look goofy". 0.88.0 moved a
building path's ends to the doors and kept everything else about it: the
authored 8 m width (Level Factory's `STREET`, the clear ground its layout
reserves between two neighbouring shells) and one straight slab between the
ends. Between neighbours 8 m apart that fills an alley. Between two side
doors 18 m apart and 20 m offset it is a plaza laid across the lot on a
diagonal, with its squared ends cocked against both walls.

A building path whose two ends BOTH found a door is now drawn as a walk:
legs at the sidewalk's width (`_walk_width`: the narrowest `sidewalk` the
site's roads declare, 3.0 where there is none, never wider than authored),
out from each door along the axis the first door faces, and one jog on the
line halfway (`_walk_legs`). Doors within `ALIGNED_TOL` (0.25 m) of each
other across the walk get one straight leg; an offset under the walk's own
width gets one leg down the middle widened to reach both, not a kink. The
legs that run out from the doors own the corner squares and the jog is
drawn between them, so no two slabs lie coplanar over the same ground.

The authored record keeps its ids, takes the first leg's points and width,
and records what it was authored at as `route_width`; the further legs
follow it in the spec's list as plain point paths naming the route in
`leg_of`. Every reader already resolves a record through
`site_paths.endpoints`, so the surface zones, the step and kerb gates and
the route check follow the legs with no change of their own.

Left as they were: a path with an end that found no door (one straight band
at the authored width, as 0.88.0 and before), and two doors closer along
the leaving axis than the walk is wide (no room to run out and turn).

## 0.88.0 - a path meets a door, not the middle of a wall

The walker, 2026-10-03, on cold run 9139's lot: "sidewalks don't
consistently lead up to doors which seems random", and after the first look,
"lot still not drawing walkways to open doorways". Read off the spec: the
door spur Level Factory authors for each building runs at the building's
centre x (`road_grammar._spurs`: ``{"a": [x, face - 1.0], ...}``), and the
bank's two south doors sit metres from its centre, so the spur met a blank
wall between them; the 8 m paths between buildings ran centre to centre and
met each facade wherever the centre line crossed it. Seven readers in this
repo resolved ``from``/``to`` to the centres, each in its own line.

`site_paths.snap_to_doors(site_spec, merged)`, run once in `assemble` after
the gameplay merge and before anything reads a path: for every path end that
belongs to a building, the storey-0 exterior entries that face the way the
path leaves (`site_enterability._approach_points`, the gate's own reading,
dot with the leaving direction at least `FACING_DOT` 0.7) are the doors on
the facade the path meets, and the nearest to the path's line wins. A spur
slides sideways along the facade to run at that door, its authored standoff
kept; a building path's end becomes the point `DOOR_STANDOFF` (1.0 m, the
spur's own figure) in front of the door. The resolved ``a``/``b`` are
written into the spec's path record beside its ids, with ``snapped`` naming
the wall, so the connectivity graph and the surface labels do not move. A
facade with no door is said (`LOT_PATH_END_OFF_DOOR`) and the end stays:
inventing a door is not this module's to do.

`site_paths.endpoints(p, bld)` is now the one reader -- ``a``/``b`` when a
record carries both, else the centres -- and `path_slabs`,
`site_enterability._near_route`, `site_surfaces._path_segments`,
`site_steps.routes`, `site_streets._endpoints` (which `site_furniture` and
`kerb_crossings` use) and `site_extent` call it. A hand-authored spec with
no resolved points reads exactly as before.

MEASURED (`patches/lot_door_paths/snap_census.py`, which snaps a copy of
every site spec on disk that has its merged gameplay beside it and writes
nothing). The walker's lot, gas_block_001 seed 9080: all 8 building-owned
ends snap -- the bank's spur slides 9.0 m, from x 62 to its south door at
x 53 (the walker stood at x 54.2 looking at the blank wall the old spur
met); the gas station's 3.5 m; the terminal's none (its door is on its
centre line); the two 8 m building paths end a metre in front of the
facing east and west doors instead of under the buildings.

Every site on disk -- 204 specs, 36 distinct lots:

    building-path ends          468    left at the centre    36
    door spurs                  920    left at a blank wall  312  (177 sites)

THE 312 ARE NOT THIS MODULE'S TO FIX, AND THEY ARE THE BIGGER FINDING. A
third of all door spurs run to a facade with no ground door on it at all:
Level Factory's road grammar authors a spur from a building to every road
it faces, and rotates buildings, without reading where the doors are (a
credit union turned 90 has doors east, north and south and a spur to the
west; strip clubs, funeral homes and gas stations lead the list). Before
this release that was silent; now each prints `[lot] LOT_PATH_END_OFF_DOOR:
...` and rides the tactical report as a minor finding. Closing them is a
Level Factory change -- face a door to the street, or do not draw a walk to
a wall -- and is recorded as open in
`docs/findings/entry_paths/NOTES.md`.

`tests/test_site_paths.py`: the spur slides and keeps its standoff; a
building path ends in front of both facing doors; a rotated building's door
is found in world space; a blank facade is said and the end stays;
`endpoints` prefers the resolved points; the slab and the enterability route
check read the snapped ends (0.83.0 had left "whether a route drawn centre
to centre is the right model" as a separate question -- this is the answer,
and the route check's warning now means what it says). All six fail against
0.87.0.

## 0.87.0 - an alley's poster runs are not all pasted at one height

The poster pass the walker queued 2026-09-30 ("we can make them better later
right?"), Lot's part. Every wall run was pasted with its centre on the
camera's eye, 1.6 m -- the placement guide's "identical spacing, height,
rotation, or mounting pattern on every wall". The poles already start their
tiers at different heights; the walls did not.

`site_posters.wall_height(name)`: the eye plus one of `WALL_STEPS` (-0.30 /
-0.15 / 0 / +0.09), by the run's own name. The highest puts the band's top
at 2.097 m, under `REACH` 2.1. Nothing else about a run moves.

Tests: the steps include level, none passes reach or drops to the ground,
48 names draw every step, and a planned run is at its own name's height.

## 0.86.1 - a third of the poles papered, not four in five

The walker, after cold run 9119 stood flyers on 22 of 28 poles: "tune it down
50%...not every pole should have posters". `TIER_SHARE` halves the papered
tiers and keeps their mix (pair 35 -> 17.5 %, stack 22 -> 11, wrap 13 ->
6.5; bare 30 -> 65). Halving alone was not enough: with 30 % of poles at a
junction, measured over 4,000 names, 79 % were papered before and 54 % after,
because the junction rule turned a bare corner pole into a pair. A junction
now makes a PAPERED pole one tier denser and leaves a bare one bare: 34 %,
junction or not.

Tests: a junction pole denser but a bare one bare; about a third of poles
papered (30-40 %), junction or not.

## 0.86.0 - poles papered in tiers, with sleeves of flyers

Cold run 9118 stood one flat 0.30 m bill on every other 0.12 m pole, and it
read as a small sign. The walker sent six photographs of flyers on real poles
and the placement guide asks for "a loose vertical stack"; Zoo 1.34.0 drew
`pole_flyers`, a sleeve of handbills curved round a pole. This hangs them.

TIERS, BY POLE. Each streetlight and sign post is `bare`, a `pair`, a
`stack` or a `wrap`, by a hash of its name (30/35/22/13 %), one tier denser
within `JUNCTION_M` (10 m) of another road -- the corner poles are "a known
place for flyers". The sleeve is centred on the pole; its diameter clears the
pole with Zoo's four layers of paper (a sign post's clearance is its
u-channel's half-diagonal, 0.0707 m, not its half-width).

NO SHARED CENTRELINE, WITHIN REACH. The placement guide calls "a repeated
perfect centerline across all buildings" a procedural tell, and every piece
0.84.0 hung was centred at the eye. A pair starts at the head (1.22 m), a
stack at the chest (0.86), a wrap at the knee (0.36), each moving by up to
0.1 m pole to pole; paper stops at 2.1 m ("Posters placed far above reach
need a reason"), and on a sign post a hand under its blade. A sleeve's
centre is rounded DOWN, because rounded to nearest it lifted a top 0.4 mm
past the blade's limit (caught by the reach test).

THE FRONT FACES THE MOON, by 0.85.0's rule, for the pair's and the stack's
front sheets; a wrap is paper all round.

Replaced: the flat pole bill, `SHEET_W`, `BAND_POLE`, `POLE_EVERY`. The wall
runs are unchanged. Every number mirrored from Zoo is pinned when Zoo is
beside this repo: the sleeve's layers, the tiers against Zoo's forms, the stem
`plan_kit` builds for every pole species x tier, and Zoo's planner filling
every slot shape Lot writes, the innermost paper clear of the pole.

Tests (`tests/test_site_posters.py`, 25): the front on the sidewalk face when
lit and round the pole when not; every front faces the light; poles papered
in all three tiers with some bare; a junction pole one tier denser; tiers on
different centrelines, every top within reach and under a blade; the pins.
Against 0.85.0's module, 8 fail.

## 0.85.0 - a pole's handbill goes on the face the moon lights

Cold run 9117 stood all 21 hung posters and measured them at night: every
one facing south or west read 43-101 luma at its centre, every one facing
north 0.0, and one of three facing east was lit (by something other than
the moon). The walker, from three options: "Lot picks a lit face for the
pole bills".

THE LIGHT, DERIVED. `delco_night` sets the key light -- the moon -- at
elevation 38, azimuth 300 (`NIGHT_ELEVATION_DEG`, `NIGHT_AZIMUTH_DEG`, pinned
against the preset file when Lux is beside this repo). `light_from` is Lux's
own convention (`lux_root._preset_key_dir`), with plan = Godot (x, -z): the
plan direction toward the moon is (-0.866, -0.500), west-south-west -- which
lights south and west faces and not north or east, exactly what 9117
measured (a test holds the derivation to that measurement).

THE FACE. A pole has four; in order of preference the sidewalk side, the two
along the road, the road side, and the first turned to the light by
`LIT_MIN` (0.25; 9117's least-lit measured faces were 0.50, its dark ones
-0.50 and below) takes the bill. A pole south of an east-west road keeps its
sidewalk face; one north of it, whose sidewalk face points north, puts the
bill round the pole on its west face. Each record says which (`face`) and by
how much (`lit`).

Wall runs are unchanged: a building's back wall is the wall it has, and the
walker's call was for the poles.

Tests (`tests/test_site_posters.py`): the sidewalk face kept when lit; the
bill turned to the west when the sidewalk face is dark; every bill faces the
light by `LIT_MIN`; the light lights what 9117 measured lit; the two numbers
are Lux's. Against 0.84.1's module the new ones fail.

## 0.84.1 - a pole's handbill is one sheet tall

Cold run 9116, the first to build 0.84.0's hung posters: the six wall runs
built and stood, and all four pole modules FAILED Zoo's exact fit --
"height=0.420m != exact target 0.520m" -- so no pole carried a bill. The
slot asked for `band_height("alley", 1)`, which is a sheet plus the wander a
run of several spreads down a band; one sheet cannot fill it without being
stretched, and Zoo refused rather than stretch. `BAND_POLE` is now one
sheet's own height, `poster_art.SIZES_M["alley"][1]` (0.42). Measured in
Zoo's planner: a lone sheet misfits 0.52 in 12 of 12 variant/key cases and
fits 0.42 in all of them.

New test, `test_zoo_fills_every_slot_lot_asks_for`: Zoo's planner must fill
both slot shapes Lot writes -- the pole's, and every wall run 0.9-3.0 m --
in every variant, within Zoo's fit tolerance. It fails on 0.84.0's 0.52; it
is the test that would have caught this before a run instead of in one.

## 0.84.0 - handbills on the back-of-house walls and the poles

The walker, 2026-09-29, choosing where posters go: "exterior alley walls and
poles" among four places; 2026-09-30, "do the alley walls and poles next".
Zoo draws them (`poster_wall` in its `alley` form: day-glo handbills, two
courses on a wall, torn and taped); Deli Counter 0.163.0 hung the three
interior families. This is the outdoor one. New: `site_posters.py`.

HUNG, NOT COVER. Everything in `site_spec["cover"]` is read as something a
body hides behind -- pacing counts it, the cover test points come from it,
the audit and the layout lint read it -- so a poster in that list would have
been a tactical object. The runs go to `site_spec["hung"]`, which only three
places read: `write_site_slots` (a `hung_<i>` slot at the record's own mount
height, collision none, the family as `form`, the sheet order as `variant`),
`cover_module_refs(key="hung")`, and `_outdoor_nodes` (the module, or nothing:
a centimetre box on a wall stands in for no poster). A hung piece's module
ladder stops at its form, because `poster_wall` with no form is the club's
art. `cover_module_stem` spells Zoo's `_n<variant>`, added only when
non-zero, so no existing name moves (pinned: the sign post's).

WHICH WALLS, MEASURED FIRST. Lot had no word for an alley or a rear facade.
The first rule -- a side facing another building across 1.5-12 m of walkable
ground with no road in it -- placed ZERO runs over Lot's 28 site specs and
Level Factory's `club_block_014` lot: generated lots stand buildings in a row
25-45 m apart or offset on both axes, and the "commercial -> alley ->
rowhomes" seam is unimplemented (docs/LEVEL_RECIPE.md). A rule that cannot
fire is indistinguishable from one that passed, so an alley wall is read as a
building's BACK-OF-HOUSE wall: a true alley first (up to two runs), then the
rear (opposite the side the sign faces, `sign_placement`'s rule), then a side
wall; two runs a building in all. Never the street facade; never a stretch
with under 1.5 m in front of it (a neighbour or the plate's edge); never over
a storey-0 opening, read through `site_enterability.wall_of` (0.83.0). Over
the 28 specs: 142 runs on 24 sites, 0 of them true alleys; the four without
any carry no footprints to read.

THE POLES: every other streetlight and sign post (a hash of the piece's name,
so adding a pole moves no other), one alley sheet at the eye on the face away
from the road, 4 mm off the pole (Zoo's streetlight pole is a 0.06 m cylinder
at the slot's centre, the sign post a 0.10 m channel).

FACING, from the measured convention: a run faces plan `(sin yaw, -cos yaw)`
(`site_furniture.plate_facing`, read in Godot 4.7), and Zoo's poster run faces
local -y like a blade (its front quad sits at y = -d/2); `facing_yaw` is the
inverse, tested against `plate_facing` itself.

Numbers mirrored from other repos, each pinned when that repo is beside this
one: Zoo's bands (`band_height("alley", 2)` 0.814, `("alley", 1)` 0.52) and
sheet width 0.30; the stem `plan_kit` builds for a hung slot; Deli Counter's
eye height 1.6 and wall thickness 0.3 (not pinned: Lot imports nothing of
Deli Counter's, as `site_enterability`'s body-fit numbers).

Assembled end to end on deli_block into a scratch directory: 6 wall runs, 7
pole bills, 13 `hung` slots beside 50 cover slots. No hung node is drawn
until Zoo has built the modules: the cold run is the first place they stand.

Tests: `tests/test_site_posters.py` (17): a true alley papered on the facing
stretch and split by the door (worked by hand, and the door's control); the
street facade never papered, the rear first; a party wall left bare; a road
makes it a street; pole bills away from the road on the pole's face; hung
slots with no collision at their own height and a manifest unchanged without
them; the stem and its variant; no fallback to another family's art; the
bands, sheet and stem are Zoo's.

## 0.83.0 - an entry is read off the wall label a build writes

Found surveying Lot for poster placement: `site_enterability` looked an
opening's wall up in `{"N","S","E","W"}`, and Deli Counter's build writes
`ext_<story>_<side>` and `int_<story>_<n>`. Only `preview.py`'s synthesized
openings carry the bare side. Read off every gameplay.json in this repo (86
files, 1,253 openings): 738 `ext_*`, 430 `int_*`, 85 bare.

WHAT IT COST. A built entry's outward normal was (0, 0), so its approach point
was the doorway itself, and the walled-in gate asked whether a DOORWAY stood
inside a neighbour's footprint -- never whether the 1.5 m in front of it did.
And every partition door counted as an entry: its doorway is inside its own
building, which the neighbour test skips, so it always read as clear. A
building whose every exterior door was blocked passed on an interior one.

NOW `wall_of` reads all three spellings into (exterior, storey, side), and an
entry is a storey-0 exterior opening -- Deli Counter's own rule
(`enterability.ground_entries`). A label it cannot read is not guessed at: it
is left out and named in a warning.

MEASURED over the 28 site specs through `merge_gameplay`, 0.82.0 against
0.83.0: entries counted 929 -> 420, all of them clear before and after; 420
approach points moved 1.5 m out in front of their doors; no walled-in verdict
changed. 26 "no authored path leads to a clear entry" warnings appear on 18
sites, and each is attributed: on 22 only partition doors had ever satisfied
the route check (a partition doorway sits near the building's centre, where
the authored paths start), on 2 an upper-storey door and partition doors, on
2 a ground door whose approach, 1.5 m out, is off the path. They are warnings
the check always owed and never gave. Whether a route drawn centre to centre
is the right model for "a path leads to the door" is a separate question.

Tests (`tests/test_lot.py`): the three spellings and six it must refuse; a
door whose doorway is clear and whose approach is not (walled in; 0.82.0
passed it); a blocked building with a partition door (walled in; 0.82.0
passed it); upper-storey doors are not ground entries; an unreadable label is
named, not counted. All five fail against 0.82.0's module.

## 0.82.0 - a cover's test point is where a body takes cover

Cold run 9109 FAILED: the art leg ended blocked, JOB_PREFLIGHT_REFUSED --
Level Factory's ground-contact pre-flight found `LT_CoverTestPoints/Cover_147`
with no ground beneath it, and Laser Tag would have refused the map. That
point is the price pylon's. `_lasertag_hook_nodes` wrote every cover's test
point at half the COVER's height; 0.81.0's 9 m pylon put it 4.5 m up, over
the pre-flight's `MAX_DROP` of 4.0. At 2.4 x 6.5 it had been 3.25 m up and
passed -- a defect every cover under 8 m hid.

WHAT THE POINT IS FOR decides its height. Laser Tag's bot walks to the
nearest cover point under fire (`LT_BotPlayerController`, nearest by 3-D
distance from its body), so the point is where a BODY takes cover, not the
cover's centre: half of min(the cover's height, a player's height from the
agent contract, `_player_metric("height_m")`). Every cover no taller than a
body is unchanged; the planner's 2.0 m blocks move from 1.0 to 0.9 m, and a
tall piece -- the pylon, a street tree -- stands its point at a body's centre.

`tests/test_cover_hooks.py`: a cover taller than a body puts its point at a
body's centre, at 3 m and at the pylon's 9 m (superseding the pinned 1.5 m
for a 3 m cover, recorded in the test); the other tests derive their heights
from the same rule. Without the change three fail.

## 0.81.0 - the price pylon Lot asks for is 3.4 m wide

The walker, 2026-09-29: "yes, make the pylon bigger". `SPECIES["price_pylon"]`
follows Zoo 1.26.0's genome default, 2.4 x 0.5 x 6.5 -> 3.4 x 0.7 x 9.0 --
the width the name needs to read past ~14 m (Zoo 1.25.0 measured the limit
of a 2.4 m face). Placement is unchanged in rule: behind the sidewalk band,
`PYLON_SETBACK + w / 2` off its back edge (0.5 m further back now), along
the road, clear of cuts, footprints, corridors and pieces.

`tests/test_site_furniture.py`: the assembled pylon slot carries the
table's dims and stands on the ground at half its height, read from the
table rather than pinned to 1.19.0's numbers; the table-equals-genome test
caught the change before this release (it failed against Zoo 1.26.0).

## 0.80.0 - a gas station's price pylon stands at its road frontage

The walker, 2026-09-28: "do the price pylon next". Zoo 1.19.0 grew the
species -- FLAPPHAS in lights over three grades to the nine-tenths, both
faces lit -- and docs/SET_DRESSING_REFERENCES.md names the owners: "Zoo (a
species) plus Lot (at the frontage, facing the road)". Planned read-only
first (docs/proposals/PRICE_PYLON_PLACEMENT.md) against Lot's source and
cold run 9101's package.

WHICH SITES: every building whose lights manifest carries a `canopy_lights`
anchor (`forecourts`) -- Deli Counter derives one from a `canopy_roof`
volume, so it is Deli Counter's own gas-station test -- read from the JSON
the greybox and themed runs share, not from GLB solids, which the two read
differently (906 against 1,742 colliders on 9101).

WHERE (`site_furniture.plan_pylons`): on the road nearest the canopy, on the
kerb of the canopy's side, at the station the canopy's centre projects to,
BEHIND the sidewalk band by `PYLON_SETBACK` 0.3 m -- a 2.4 m face across a
3 m band would leave 0.6 m, under `site_cover`'s 1.2 m passable gap -- on the
ground (`base: "plate"`; `_piece` writes "sidewalk", which would float it
0.11 m). Turned `yaw_extra` 90, so its two faces point along the road, one
to each direction of traffic (`plate_facing . along = +/-1`). Stepped along
by up to 12 m when a dropped kerb, a building footprint, a path's corridor
(`path_corridors`), a standing piece (+ `PIECE_GAP`) or a mission marker is
in the way; otherwise `LOT_PYLON_NO_ROOM` (or `_NO_FRONTAGE`), never forced.
THE PATH CHECK IS EXPLICIT because `LOT_STEP_BLOCKS_A_ROUTE` reads walkable
prefixes only and cannot see a prop: a pylon across a door path would have
passed silently.

It joins the kerb line's cover before parking and the cover planner read
what stands, so the slot, the Zoo kit build, the module resolution and the
navmesh take it with no further change. `COVER_MATERIALS["price_pylon"]` is
the genome's own `metal_painted`, so the stem carries no `_m`.

MEASURED on cold run 9101's site spec: gas_station_a02's pylon at (92.0,
-33.5), road 0's north kerb, t 198, yaw 90, face . along = 1.0 -- where the
plan predicted. `tests/test_site_furniture.py`: behind the band facing along
the road, steps off a door path or is refused and said, Lot's dims are
Zoo's genome's, and `assemble` writes the slot (dims, convex, z 3.25, turned
90). 4 of the new tests fail without the change; suite 572 passed.

NOT MEASURED: that it reads from down the road at night, and what it costs
in draws -- the next cold run.

## 0.79.0 - a streetlight shines out of the pole that is standing there

MEASURED FIRST, on cold run 9087's walk copy, with `pole_vs_light.gd`:

    POLE/LIGHT: 54 streetlight light(s), 48 streetlight prop mesh(es)
       min 3.50 m   median 24.93 m   mean 30.62 m   max 93.68 m
       lights with a pole within 1.0 m: 0 of 54

Not one exterior light in the level came out of a lamp. The walker found it
from the inside -- standing at the map edge in two hard cone edges washing the
boundary wall: "a reminder that light should comes from light sources, i don't
know where this light is coming from", and then "it could be that there is a
mismatch of placement because it looks like the street lamps dont have that
light coming from them".

IT IS ONE REPO WITH TWO FUNCTIONS THAT DO NOT READ EACH OTHER, which is worth
saying because the first diagnosis was that this needed a new site-level Zoo
fixture stage in Level Factory. `site_furniture.plan_furniture` stands
`streetlight` cover pieces along the kerb bands, nudged clear of the dropped
kerbs and the mission markers; `lot._streetlight_anchors` derived light ROWS
from the path graph and from a ring 2 m inside the ground rect. Both are Lot.
`merge_lights` already runs after `plan_furniture` has extended
`site_spec["cover"]`, so the poles were sitting in the same dict the whole
time.

So the poles ARE the anchors now: one light per lamp, at the lamp's plan
point, at the lamp's yaw, at the height of its lens. Coincident by
construction rather than by two formulas agreeing.

* `STREETLIGHT_H = 6.0` is gone. A pole's height comes from the piece.
* `STREETLIGHT_LENS_DROP = 0.175` is new, and derived rather than chosen:
  `zoo/zoo_keeper/recipes/streetlight.py` builds the species centred, and in
  a SLOT (`fit_exact`, which is how the site kit stands these) the pole top
  is at local `h/2 - 0.18`, the shoebox head fills the last 0.18 to the
  module's top, and the lens protrudes to `h/2 - 0.175`. A light at the
  module top would be inside the head, and the head would shadow its own
  spot. Zoo's `tests/test_streetlight_lens_drop.py` fails if that moves, and
  checks this file for the matching number when both repos are present.
* the anchor carries `"hardware": "slot:cover_<i>"`, naming the slot that
  stands its pole. Zoo 1.6.0 reads it and skips the anchor, so the day a
  site-level fixture job exists it does not stand a second pole inside the
  first.
* `row` is `{count: 1, spacing: 0}`. A row cannot describe these: `_nudged`
  moves a pole clear of a kerb cut or a marker, so the spacing along a kerb
  is not constant, and a `{count, spacing}` pair would put most of the
  lights back off the poles again.

WHAT WENT AWAY WITH THE ROWS, said here rather than discovered later:

* the PERIMETER RING lit the boundary wall from nothing. That is the frame
  the walker was standing in. The map edge is now lit by the moon alone.
  Standing poles out there is a placement decision for `site_furniture`, and
  it is the right way to light a boundary; faking it from the light side is
  not, and is what this release removes.
* the PATH ROWS lit the path graph, which is not where the street furniture
  is -- that is the 24.93 m median above.
* a site whose roads carry no sidewalk band stands no lamps and so now gets
  no exterior lighting at all. `write_site` prints `LOT_NO_EXTERIOR_LIGHTS`
  saying so, because that is a real state and a row of lights from nowhere is
  not a fix for it.

Light count on the shipped kerb line goes 54 -> 48, each one on a pole.

Tests: `test_lights_stand_on_the_poles_the_site_stands` is the walk-copy
probe as a unit test -- it plans the kerb line from `coldrun_kerb_probe.json`,
merges, and asserts every light is within 1 mm of a pole, at the lens height,
carrying a `hardware` tag that names a slot the manifest actually writes.
`test_lights_no_pole_means_no_exterior_light_rather_than_a_row` asserts the
removed behaviour is gone. Both fail against 0.78.0's `lot.py`.

## 0.78.0 - the ground gets wet, because the ground is Lot's

`ground_skins` honours `wet_ground` on a site spec: `albedo` and `roughness`
point at the pack's `wet_albedo` and `wet_roughness` where it has them.

WHERE THIS BELONGS WAS ESTABLISHED BY COLD RUN 9079, not by reasoning. The
chooser was wired into Zoo first (Zoo 1.3.0, LF 0.113.0) on the assumption that
wetting Zoo's packs wets the road. The shipped package refuted it: 170 distinct
`M_Skin` materials across 247 GLBs and ZERO ending `_wet`, because Zoo skinned
24 kinds -- canvas, carpet, ceiling tile, concrete, drywall, glass, leather,
metal, plaster, plastic, rubber, tile, vegetation, velvet, wallpaper, wood and
the rest -- and not one is a ground kind. `--wet` was passed, was honoured, and
had nothing to choose. The brief said `weather: rain`, Lux rained, the road
shipped dry.

`site.tscn` carries that road: `StandardMaterial3D` nodes whose
`albedo_texture` is an `ExtResource` pointing at `skins/asphalt_delco_albedo
.png` and `skins/sidewalk_delco_albedo.png`, written from the records this
function builds by reading the pack manifest directly. So the substitution has
to exist here as well. Lot imports nothing of Zoo's and vice versa; what must
not drift between them is the map NAMES Pixelcoat writes, and those are the
pack contract, asserted by a test in each.

COSTS NOTHING. `_copy_maps` copies whatever the record names, so the wet PNG
lands in `skins/` and the material samples it -- same slots, same
`meters_per_tile`, same `alpha_mode`, no extra texture, no extra material, no
extra draw call. Tests assert the record is otherwise identical field for
field.

A FAMILY WHOSE PACK HAS NO WET MAPS IS UNTOUCHED, so `wet_ground` is safe to
set for a whole site: on a delco_1997 library the ground and path move and the
courtyard's brick does not. Which families are wet is Pixelcoat's decision,
carried in the grammar.

AND IT SAYS SO EITHER WAY. `LOT_GROUND_SKIN_WET` reports what was substituted,
and a site that asked for wet ground and got NONE is reported too -- because
that is a level raining on a dry road, and it shipped once without a word.

`tests/test_wet_ground.py`, 13 tests; 5 fail against the unfixed resolver.
Suite 567 passing.

## 0.77.1 - a door can name its own building

`street_members` inferred which building a door path belonged to from the
nearest centre, requiring it to be twice as close as the runner-up so an
ambiguous end joined nothing. That rule cannot answer for a wide shell: on
`crossroads_9600`, b1 is 56 m across, so its own doorstep sits 29 m from its
centre while its neighbour's centre is 39 m away. The door was dropped and the
cross street kept only one of its two addresses.

Level Factory 0.109.2 names the owner in a `building` key and this prefers it,
falling back to inference for hand-authored specs that predate it.

NOT `from`, and the difference is a shipped defect. `site_streets._endpoints`
resolves `from` to the building's CENTRE, so a door carrying it would start
inside the building, run out across the sidewalk, and `kerb_crossings` would
read it as a street crossing -- every door dropped-kerbed, crosswalked and
signed, which is cold run 9048 exactly. `building` is inert to that resolver.
Checked after the change: kerb cuts on the first crossroads stayed at 3 for a T
and 4 for an X, unmoved by five door paths.

    street_members before   {0: [b0, b1, b2], 1: []}
    after LF 0.109.2        {0: [b0, b1, b2], 1: [b0]}
    after this              {0: [b0, b1, b2], 1: [b0, b1]}

554 passed.

## 0.77.0 - the site graph includes the street, because the buildings do

`build_graph` used building-to-building paths only and said so: "paths to raw
points don't connect buildings and are ignored here". Level Factory emits a
chain of those and DELIBERATELY drops any segment crossing a road -- cold run
9049, where one cut across a cross street mid-block and read as a fake
crosswalk -- giving every building a door path to the sidewalk instead. The
street carried the connection and this function could not see it.

Measured over every candidate site spec on disk before the change, by
`tools/level_recipe_census.py`:

    sites reporting an isolated building   65 of 79  ->  0 of 79
    objective_approaches 0                 38 specs  ->   2
    objective_approaches 1                 37 specs  ->   6
    objective_approaches 2                  4 specs  ->  71

Cold run 9077's shipped package -- a run reported as a genuine zero -- had
`{b0: [b1], b1: [b0], b2: []}`, `isolated_buildings: ['b2']`, and printed
"buildings with no declared path-route from 'b0': b2". It now reads a full
triangle, no isolation, two approaches.

WHAT COUNTS AS MEETING A STREET is the declared door path, not proximity. Lot
already treats a path as where a building meets the ground -- `kerb_crossings`
drops a kerb where one crosses a kerb line -- so a raw-point path with one end
in a road's band (carriageway plus sidewalks) and the other at a building is
that building's door onto that road. Proximity was the alternative and is
worse: it needs a footprint the spec does not carry, and would connect a
building that merely sits near a road it has no way onto.

UNAMBIGUOUS OR NOT AT ALL. A path end matches a building only when the nearest
centre is within half the distance to the runner-up. A tie means the spec does
not say whose door it is, and an edge nobody declared is worse than a missing
one.

A CLIQUE PER ROAD, with the limit stated: it says these buildings share a
street, not that they are adjacent along it. `street_members` carries the road
index and a measure that needs "next door" will need distance along `t`.

STRICTLY MORE PERMISSIVE, checked before writing and asserted in the tests:
`gate()` raises BELOW two approaches, and `isolated_buildings` reports an
absence. The street graph is a superset of the path graph, edge for edge.

NOT A GATE. The recipe's `approaches: min 3` is still unmet on all 79 specs,
and that reading is now about the level: three buildings on one street afford
two directions to come from. A third needs a fourth building or a second street
the buildings front -- and `_street_for` addresses every door to the front
road, so a generated cross street has no addresses on it at all.

542 + 12 passed.

## [0.76.0] - a building's ladders reach the site

COLD RUN 9075 FALSIFIED Dispatch 0.5.0's claim that a ladder's off-mesh nav
link reaches the package. That release taught Dispatch's DELI COUNTER importer
to carry them. A SITE mission runs the LOT importer, whose manifest is
`lot.gameplay.json` -- and this file concatenated its buildings'
`interactives` while dropping their `ladders` entirely. Measured on that
package: 23 `gb_ladder` surfaces, `market_hall_a01` carrying a ladder with a
`nav_link` in its shell, and `navigation_hints.json` reading `links: []`.

Both sides' unit tests had passed. Nothing tested the seam.

### Every position moves, or none should

A ladder record carries twelve three-component points and a four-point plan
rect, all in the building's own frame:

    lower_anchor, upper_anchor
    route_nodes/{lower_approach, lower_mount, climb_start, climb_end,
                 upper_dismount, upper_route}
    traversal_component/climb_axis[0..1]
    nav_link/{start_position, end_position}
    geometry/climb_rect[0..3]                    (x, y plan pairs)

A nav link in site space beside route nodes in building space is worse than
shipping nothing: an AI would path to where the ladder is not. They are listed
explicitly rather than found by walking the record, and `_ladder_to_site`
REFUSES on a numeric triple that is not in the list, so a field Deli Counter
adds later cannot ride into the site untransformed. Verified by injecting one:
it raises rather than carrying it.

The record is deep-copied: `merge_gameplay` reads each building's file for
several passes, and a shared nested dict would write site coordinates into the
building's own gameplay.json.

### Tested at the seam this time

`test_ladders_reach_the_site.py` runs `merge_gameplay` against the real shell
that shipped the ladder in 9075, and asserts the foot of the climb agrees
across `lower_anchor`, `route_nodes.lower_approach` and
`traversal_component.climb_axis` -- three independent routes through one
record -- AND that it moved at all, since a pass that transformed nothing would
satisfy the agreement. One test pins that the fixture shell still has a
ladder, because its absence would make the rest pass vacuously; the first
draft of those tests did exactly that, silently, because a building record
without a `gameplay` key places fine and contributes nothing.

## [0.75.0] - every stage copies its siblings, and a GLB's siblings grew

`cover_module_refs` stages a cover piece's module into `<out>/cover/` and
references it beside the scene. Its docstring already carries the rule and
the cold run that bought it: "0.59.0 referenced them by absolute path; cold
run 9019 showed what that costs one stage on ... Every stage that loads a Lot
scene copies its siblings."

A GLB's siblings grew. Zoo 1.2.0 stopped embedding a module's images in its
binary chunk and began writing them beside it, named by a relative glTF
`images[].uri`. `shutil.copyfile` on the `.glb` went on moving one file where
there were several, and every cover piece in Level Factory cold runs 9067,
9068 and 9069 stood in the level naming a texture the package did not carry.
(9066 is clean: it was built three hours before the externalisation landed.)
Measured 2026-09-22 on 9068's shipped package: 128 dead references out of
this line, in a level the walker reported as "around 90% graybox".

### Whose defect it was, said plainly

NOT THIS REPO'S, on that run. Level Factory's job store publishes a job's
outputs by file SUFFIX, so Zoo's `.png` files never left the attempt
directory and the kit this staging was pointed at had no textures in it to
copy. Fixed in Level Factory 0.105.0. This line would have dropped them
anyway the moment they arrived, which is why it is fixed here too: leaving
one copy site right and the other wrong is how the next one gets written
wrong.

### What changed

`glb_deps` is new -- read a GLB's JSON chunk, list what it names beside
itself, copy a GLB with its dependencies, and report every unresolved
reference under a directory. It is a duplicate of the file in `deli_counter`
and deliberately so: neither repo imports the other and neither imports Zoo,
and two spellings of one contract is the price of that. The gate that catches
a drift between them reads the shipped package rather than either copy:
`level_factory.packages.exporting.glb_refs`.

`cover_module_refs` uses `copy_with_deps`. `_same_bytes` is no longer the
skip test there: a `.glb` can be byte-identical while a texture beside it is
absent, which is precisely the state those three packages shipped in.
`copy_with_deps` does its own per-file skip, by the hash Zoo already put in
each texture's name.

`package.py`'s pack assembly copies a `.glb` the same way. That path is not
on Level Factory's pipeline and was never measured shipping broken; it is
fixed for the same reason.

### Keyed on the document, not on a folder name

`_tex` appears in `glb_deps` nowhere. The next asset class Zoo externalises
is carried on the day it appears.

### The `.glb` stubs in the tests

Six fixtures wrote `b"glTF"` -- four bytes that begin with the magic and are
not a container -- and became `GlbUnreadable` the moment the staging read
them. A fixture that is not the format under test proves nothing about the
format, so `tests/glb_fixture.write_glb` emits real minimal GLBs, and
`test_a_built_module_stands_where_the_box_stood` now stages a module shaped
the way Zoo 1.2.0 emits one and asserts the texture arrives beside it.

## [0.74.0] - the blade gets a box, and the name it is built under

0.73.0 named the legend every `sign_post` carries and said the two halves
change together. This is Lot's side of that, and it lands FIRST on purpose --
see below, because the order is the part of this change that could have gone
wrong and 0.73.0 had only half the reason.

THE SLOT WAS THE PLACEHOLDER'S BOX. `SPECIES["sign_post"]` is 0.10 x 0.10 x
2.40 m, and its comment says what it is: "Dims are the Zoo genomes'
defaults". Zoo's default was the pole `tools/new_species.py` minted, so the
slot every post wrote was a pole-shaped hole -- and Zoo's `fit_exact` maps a
module's bounds onto its slot exactly. A 30-inch pedestrian diamond built
into that comes out ten centimetres across: the same defect as a bare pole,
and harder to see in a frame than the bare pole was.

`BLADE_DIMS` is the slot each blade asks for, and every number in it is a
standard plus a mounting height rather than a choice:

    no_parking     0.3048 x 0.060 x 2.4384   R8-3a at 12 x 12 in, bottom 7 ft
    ped_crossing   1.0776 x 0.060 x 3.2112   W11-2 at 30 x 30 in over the
                                             W16-7P plaque at 24 x 12 in,
                                             bottoms at 7 ft and 5 ft
    bus_stop       0.3048 x 0.060 x 2.5908   a 12 x 18 in transit flag, 7 ft

Mounting heights are MUTCD Section 2A.18 (7 ft to the bottom of a major sign
where parking or pedestrian movements occur, 5 ft to a plaque under it). **A
30 x 30 in diamond is a 30 in SQUARE on its point**, so it needs 30 * sqrt(2)
= 42.43 in of box and its top lands at 10.5 ft -- the crossing sign is three
and a half times the width of the parking sign and a third again as tall,
which is what those two signs are. Zoo's `core.sign_blade_forms.MODULE_DIMS`
is this table; neither repo can import the other, so both pin the numbers to
literals in their own tests.

THE MODULE GREW; NOTHING MOVED. `FOOTPRINT["sign_post"]` is the pole, the way
`FOOTPRINT["traffic_signal"]` has been since 0.72.0 for an 8 m mast arm whose
slot box would otherwise lie across the carriageway. `_free`,
`_clear_of_cuts` and a piece's `along` all read the footprint, so a 1.08 m
diamond changes no station on any kerb and no line of the census; only `dims`
(the slot Zoo builds to) and the module's height take the blade.
`test_a_wider_blade_does_not_move_a_single_post` checks that against the
pole's own numbers rather than against a recorded baseline, because a
baseline is a copy of the thing under test.

`cover_module_stem` SPELLS `_f<form>` NOW, and the other two mirrors did not
have to change: `zoo_keeper.core.kit.module_stem` and
`deli_counter.themed_tscn.module_stem` have both written it since Zoo 0.84.0.
Checked rather than assumed -- Deli Counter 0.138.0 untouched resolves a
sign-post slot to `prop_sign_post_delco_1997_01_w30_d6_h244_fno_parking`.
This was the only one of the three that never grew it.

WHY THIS SIDE GOES FIRST, AND WHY IT CARRIES A LADDER. 0.73.0's reason for
holding back was sound: spelling `_f<form>` against a genome listing no forms
resolves a name Zoo has not built, and every post falls to greybox. What it
did not say is that landing ZOO first breaks it the other way round -- Zoo's
`plan_kit` then builds ONLY the dressed name while this file asks for the
plain one, and every post falls to greybox again. Both single-repo orders are
worse than the bare pole they replace, so "they change together" is not an
order, it is a hope.

`cover_module_refs` asks for the dressed name and then the undressed one --
the same ladder `deli_counter.themed_tscn.resolve_slot_choice` already climbs,
cited there as the reason a resolver that cannot read a genome can still name
every module the kit could have built. With that rung in, this release
against Zoo 0.95.0 resolves the plain module and stands the bare pole that
was there yesterday, and against Zoo 0.96.0 it stands the sign. The window
between the two costs nothing and the order stops being load-bearing -- which
is the point, because a cold run hashes both repos at `--begin` and nobody
gets to sequence them by hand.

A blade nobody has drawn gets the same treatment rather than a greybox: a
street-name plate (MUTCD D3-1), when `roads[].name` exists to carry one, will
drop through Zoo's `honour_dressing` into its `dressing_fallbacks` report and
through this ladder onto the bare pole.

MEASURED END TO END, through both repos: `central_vault`, `septa_station` and
`warehouse_district` (12, 8 and 10 posts, all three blades between them). The
stems Zoo's `plan_kit` plans and the stems `cover_module_stem` resolves are
the same list on all three, with no species fallbacks and no dressing
fallbacks. On the single-road `coldrun_kerb_probe` all 11 posts carry a blade
and agree.

Four tests fail on 0.73.0: the slot carries the blade's own box and the stem
spells it, the blade table is the MUTCD arithmetic, a wider blade moves no
post, and the resolver falls back from the dressed name to the plain one in
both directions. Suite 536 passing.

NOT VERIFIED HERE. Zoo 0.96.0 draws the blades and its own frames show the
four posts against a ground plane; nothing has stood a street of them, and no
walk package has been rebuilt. The `LOT_STOP_SIGN_OFFSET_SHORT` findings on
`central_vault` are 0.73.0's and unrelated -- a 1 m sidewalk band, not a sign.

## [0.73.0] - a corner is one place, and a post carries a legend

The walker, cold run 9060 (`club_block_001`, `_runs/walk_9060_rain`), on one
screenshot of the sidewalk beside `office_stepped`: "no signs on the stop
signs here anymore?" and "we wouldn't have fire hydrants that close to each
other". Two findings, one corner, one cause underneath both.

MEASURED FIRST, off that run's own `site.tscn` and reproduced by re-running
`lot_assemble`'s themed spec through 0.72.2 into a scratch project -- same
node ids, same coordinates, so the before frames are the shipped build and
not a lookalike. The site stands 5 `sign_post`, 1 `traffic_signal` and NO
`stop_sign`. At the T's north-east corner `fire_hydrant` cover_12 (-17.20,
-24.60) and cover_92 (-17.95, -23.85) stand **1.06 m** apart, and `sign_post`
cover_14 and cover_93 the same 1.06 m apart. A third post, cover_86, stands
1.6 m from the signal mast on the west corner.

WHY THIS SITE HAS NO STOP SIGN, since the screenshot's word for the poles was
"stop signs". `tools/probe_street_control.py` reports 3 junction legs, all
three `signal`: road 1 ends on road 0, so the stem yields, and road 0 is an
arterial (sidewalks and parking lanes), so `site_streets.approaches` puts the
junction under a signal and no leg carries a stop sign. That is
docs/STREET_RULES.md working, not failing. Across the 24 road specs in
`specs/` there are 15 approaches -- 3 signal, 6 stop, 6 through -- and 6 stop
signs, one per stop-controlled approach. The poles the walker photographed
were never stop signs; they are the blank blade 0.69.4 left at a kerb cut.

THE CORNER WAS PLANNED TWICE. Where two roads meet, each road's kerb is cut
by the other, and `plan_furniture`'s per-cut loop furnished both cuts while
`_free` looked only at the band the piece stood on. Nothing in the module had
ever been asked a question about another road. `corner_key` now names a
corner by the junction's own plan point and which plan quadrant of it a piece
stands in -- both roads compute the same key from the same junction, so no
distance threshold has to guess how big a corner is -- and a corner carries
one hydrant, one bin, and ONE POST. A signal mast, a stop sign and a blade
post are all posts; where one already stands the blade is not given a second
pole a metre away. Every junction's control is now planned before any band,
across the whole site, because the post that owns a corner is often the other
road's.

FIRE HYDRANT SPACING, derived and cited. NFPA 1 Table 18.5.1.1 and AWWA M17
both state hydrant spacing as an AVERAGE for the district -- 500 ft (152 m)
residential, and about 300 ft (91.4 m) in the commercial or high-value
district ISO's grading schedule works to, which is what a Delco strip is.
`HYDRANT_MIN_SPACING` is half that, 45.7 m: the least separation that can
still be read as a spacing rather than as one hydrant written twice. No
standard names a minimum because no engineer needs telling.

The minimum alone is half a standard, and measured across the 24 specs it
took the library from 92 hydrants to 43 -- which reads as the fix deleting
hydrants. So the corner pass is followed by one that STANDS a hydrant
wherever a street runs further than the design spacing from the nearest, and
the library settles at 61 with no pair under 10 m (was 6 pairs, closest 1.06
m). A road left with none by the corner rule is not silently emptied: its
piece is MOVED to the first station on its own kerb at least a minimum from
the rest, and a road that holds no such station says `LOT_HYDRANT_NONE_ON_ROAD`
with the distance to the hydrant that covers it. On 9060 the side street's
corner hydrant moves 51 m up its own L kerb; the census goes 2 -> 3 hydrants
and 5 -> 3 posts.

EVERY POST NAMES ITS BLADE. Zoo's `sign_post` recipe is still the placeholder
box `tools/new_species.py` minted on 2026-09-12 -- a 0.10 x 0.10 x 2.40 m
galvanised pole with nothing on it, which is what the walker saw. Lot's half
is to say what each post is for, in the piece's `blade` field and on the slot
as Zoo's dressing `form` (0.84.0): `no_parking` at a junction corner (no
parking within 30 ft of a signal or stop sign, 75 Pa.C.S. 3353, MUTCD R7/R8 --
the one corner sign that needs no street name), `ped_crossing` at a footpath
cut Lot paints a crosswalk across and nothing controls (MUTCD W11-2 with the
W16-7P arrow), and `bus_stop` on the stop's flag. A street-name blade (D3-1)
is what a corner really carries and Lot cannot post one: no spec in `specs/`
names a road, so a `roads[].name` branch would be a branch that cannot fire.

`cover_module_stem` deliberately does NOT yet spell `_f<form>`. Zoo's genome
lists no forms for `sign_post`, so `honour_dressing` drops the field and
builds the plain module; spelling it here first would make Lot resolve a name
Zoo has not built and send every post back to its greybox. The two change
together. Until then the ask lands in Zoo's `dressing_fallbacks` report,
which is where a gap belongs.

THE BLADE FACES THE DRIVER IT IS FOR. Every corner blade was written at
yaw_extra 90, which `plate_facing` turns into +along -- right for the L kerb,
edge-on-behind for the R kerb, whose lane carries the +t driver. Nothing saw
it because the post is a bare pole. `_driver_on` reads
`site_streets.KEEP_RIGHT` and the yaw comes from `_facing_driver`, the same
derivation `_stop_sign` uses. The bus stop's flag keeps its 90: it is a flag,
not a sign for a driver, and it was also called `StopSign_` until now, which
is exactly the kind of name that gets read back as evidence of traffic
control it is not. It is `StopFlag_`.

Five tests fail on 0.72.2: the corner stands one hydrant, the spacing rule
leaves every road one AND no pair inside the minimum (the conjunction is the
claim -- 0.72.2 passes the first half), a short stem that holds no station
says so, every post names a known blade and no corner holds two posts, and
the slot carries the blade as `form` while the stem stays `_f`-free. Suite
534 passing.

NOT VERIFIED. No blade exists to look at: the frames show one post where
there were two, not a post with a sign on it, and they will not until Zoo
draws the four legends. The before/after pair was shot through Lot's own
`site_walk.tscn` (its WorldEnvironment and Sun, gl_compatibility), not
through the shipped walk package, whose `mission.tscn` loads the Lux-lit
`presentation/lux.applied.tscn` -- re-running Lux is another stage and
another instrument. One residue is left standing and named rather than
fixed: on `central_vault` two litter bins sit 3.56 m apart, attributed to a
junction and a footpath crossing 14 m apart on the same street, each placing
its bin toward the other. That is two crossings too close together, not one
corner furnished twice, and a second constant for bins would be chosen rather
than derived.

## [0.72.2] - a hydrant turns its pumper outlet to the road

Zoo 0.85.0 rebuilt `fire_hydrant` as an American dry-barrel hydrant with its
4 1/2 in pumper outlet on the module's -Y, the face `plate_facing` reads, and
said what stood between it and a street of them: Lot. The per-cut loop in
`plan_furniture` wrote every hydrant at the road's own angle on both kerbs.
At that yaw -Y points `(sin a, -cos a)`, which is `-perp`: toward the road
from the L kerb (`sign` +1, left of travel) and toward the buildings from the
R kerb. Cold run 9052's only hydrant, `fire_hydrant_37` (`cover_81`), stands
on road 1's R kerb, so in the walk copy its pumper faced the shop fronts.

The R kerb now turns the hydrant round, the same 180 degrees the bus
shelter's `back` already carries. The footprint is unchanged (a half turn
keeps the box). `test_every_hydrant_turns_its_pumper_outlet_to_the_road`
checks every hydrant on `coldrun_kerb_probe` (both kerbs) points
`plate_facing` at the road's centre line; it fails on 0.72.1.

Not verified: no Godot frame of a turned hydrant yet; the next cold run's
walk copy is the first.

## [0.72.1] - a diagonal path reaches the building it names

Cold run 9052's chain path `path_0`, `b1` at plan (4, -10) to `b2` at
(45, 10), 8 m wide. The walk copy `_runs/walk_9052_rain` writes it
`Transform3D(0.898768, 0, -0.438424, 0, 1, 0, 0.438424, 0, 0.898768, 24.5,
0.005, -0)`. Read back in Godot 4.7, headless, on a scratch copy of that
package: `str_to_var` on the literal and the instantiated node's
`global_transform` both give `basis.x = (0.898768, 0, 0.438424)`, and the
collision box's plan corners are (5.754, 13.595), (2.246, 6.405),
(46.754, -6.405), (43.246, -13.595). The path ran from (4, 10) to (45, -10):
the spec's path mirrored across its own centre line, its far end 20 m from
the building it was drawn to reach. Of that package's 4,909 dressing
instances, 58 have their origin inside the path the spec asks for; 0.72.0's
`tops` puts 42 of them on the plate and 16 on the path.

Two defects, one class, and they hid each other.

- **The writers passed the mirror of the angle.** Godot reads the nine
  basis numbers as ROWS, so `c, 0, s, 0, 1, 0, -s, 0, c` sends local +X to
  Godot (c, 0, -s), plan (cos r, sin r): the yaw a slab is written with is
  its counterclockwise plan angle. `path_slabs`, `street_slabs` (road slabs,
  sidewalk and kerb-cut pieces), `frontage_slabs` and the markings all passed
  `-angle`. Axis-aligned slabs are symmetric under that, so no street ever
  showed it; every diagonal path did. `lot.yaw_basis_text` now writes the
  basis for every yawed node (boxes, paint quads, shop signs -- the signs'
  text is unchanged) and says what the number means; the four slab
  functions and the markings pass the plan angle.
- **`site_steps.surfaces` read the literal as COLUMNS** -- the transpose,
  which for a yaw is the mirror. So the step gate saw 0.72.0's diagonal slab
  where the spec meant it and not where it was drawn: the two errors
  cancelled into a checker that agreed with the spec and not with the scene.
  It reads rows now. `test_site_steps.test_a_rotated_road_does_not_touch_the_whole_site`
  had been "corrected" once by the same misreading: its ground tile was moved
  from Godot (-60, -60), called ON the 45-degree road's centreline, to
  (-60, 60) -- which is where the engine puts that centreline. The tile is
  back, and the retraction is kept in the docstring.

Same misreading, different reader: `site_collision._godot_transform`
documented the literal as "basis columns" and built the transpose, which
turns every yawed instance in a Deli Counter building scene the other way
(`tscn_export.godot_basis` writes `basis.rows`). It reads rows now. Measured
by running `read_source` both ways over 9052's three themed building scenes
in the walk copy: 38 of 1,435 colliders change, none by more than 0.010 m in
plan.

`site_surfaces.tops` needed no change: it takes the yaw the slab is drawn
with, so it moves with the drawing, and `TOPS_RULE` (which Patina matches
verbatim) is unchanged. Only its docstring, which described the mirror as
current, is rewritten.

**What moves.** `_outdoor_nodes` on all 28 specs under `specs/` and 9052's
candidate spec, with 0.72.0 against this, corners read row-major: 1,867
top-level nodes with a transform, 1,466 with changed transform text, 78 with changed
geometry -- every one a path. The other 1,388 are axis-aligned slabs whose
yaw flipped by a half turn and draw the same rectangle; no spec there has a
diagonal road, band, marking or frontage. A `--walkable --portable` assemble
of 9052's themed spec writes identical outputs except `site.tscn`, and that
differs in 106 `transform =` lines. Read back in Godot 4.7 after Lux's own
`run_lux_apply.gd` on a scratch copy of the staging project, swapped into a
copy of the walk package, `path_0`'s plan corners are (2.246, -6.405),
(5.754, -13.595), (43.246, 13.595), (46.754, 6.405): b1 to b2. The 58
dressing origins on the intended path all read the path's top from the new
`tops`. `site_steps` on the themed scene reports the same 19 transitions and
no findings before and after (path_0 meets no raised slab either way).
Frames from a given plan station over the path, `tools/look_shots.py`, show
the slab on bare plate north of b1 before and between the two buildings'
faces after.

NOT REPRODUCED: this Lot's 0.72.0 does not rebuild the cold run's own
`site.tscn` byte for byte today (4,654 diff lines, the parking bays among
them), so every before/after above is 0.72.0 against 0.72.1 on today's
inputs, not the shipped scene against a rebuild.

Nav-QA walktest, 9052's candidate spec `--walkable --navqa --portable`,
staged into a copy of the run's own walktest staging project, Lot's
`walktest.py --require`: PASS with 0.72.0 and PASS with this. Every proxy leg
and every bot walker reports the same; three of the four player walkers
differ by at most 0.3 m (274.1/275.6/277.1 m against 274.0/275.9/277.2 m).
Neither rebuild matches the cold run's own walktest: both report proxy_2 and
proxy_10 off the main network behind 3.6 m and 3.9 m vertical legs, a
~302 m spine against the run's ~405 m, and players at 273-277 m against
365-368 m. That difference is between today's inputs and the run's and is
not measured further here.

Tests (`test_diagonal_slabs.py`, reading the emitted scene row-major with
its own parser rather than `site_steps`'): a diagonal path's drawn corners are
its intended corners at 26, 63, 117, 153, 207, 243, 297 and 333 degrees; the
step gate reads that path where it is drawn; `tops` declares the drawn slab
and the path's top is under points near both ends of the intended rectangle;
9052's chain path lands on b1 and b2; a diagonal road's slab is its
rectangle, every band piece lies in its own kerb's band and every marking
runs along the road, and the step gate reads all of them as drawn; the
collision reader turns an instance the way Godot does. 34 cases, plus the
restored rotated-road step test: all 35 fail on 0.72.0. 528 passed, 1
skipped.

## [0.72.0] - dressing is told how high the ground is

Cold run 9052's walk copy (`_runs/walk_9052_rain`): every one of the 4,909
instances in `bank_block_001_dressing.tscn` has origin y = 0.0. Read against
the StaticBody3D boxes of the `site.tscn` it was placed on (byte-identical to
that run's `themed_site_assemble` output), 2,500 stand more than 5 mm below
the top of the slab under them: 1,648 inside a 0.0974 m sidewalk band, 739 in
the road (0.010), 64 in a path (0.012), 49 in a kerb cut (0.010). By zone
kind: `sidewalk` 1,531 of 1,550, `ground` 968 of 3,306, `wall_base` 1 of 53.

Where the height was lost, stage by stage. `site_surfaces.zones` declared
every zone from `z_lo = 0.0` and nothing anywhere declared how high a surface
was; Patina's planner wrote `"pos": [x, y, 0.0]`; Level Factory's
`dressing_scene` carries pos[2] to Godot y faithfully (it reproduces the
shipped scene byte for byte from the shipped manifest); Zoo's clutter has its
origin at the contact point (`connectors.anchor` type `surface`, extracted
mesh bases at -0.006 to 0). So the number belongs to Lot, which draws the
slabs, and to the planner, which picks the point.

A zone could not carry it. Zones are boxes over surfaces they do not name --
a sidewalk corridor runs on over its kerb cut and past the road's end, the
open-ground remainder covers the whole plate -- and on 9052, 627 instances
stood on a different family's slab from the one their zone names. Placed at
their own zone's surface, 618 would still have been more than 5 mm off.

**`site_surfaces.tops`**, and `surfaces.json` carries it with `tops_rule`:
every flat slab Lot draws outdoors, in plan, `{name, family, centre, size,
yaw_deg, top_m}`, plus the plate at `PLATE_TOP` (-`GROUND_SINK`). The height
under a point is the largest `top_m` of the slabs holding it. The slabs come
from the functions the scene is now drawn with -- `path_slabs`,
`courtyard_slabs`, `street_slabs`, `frontage_slabs` in `lot.py`, which
`_outdoor_nodes` iterates -- so the declaration and the drawing are one
computation. `_outdoor_nodes` output is byte-identical to 0.71.0's on all 28
specs under `specs/` that have buildings and on 9052's candidate and themed
specs, and a full `--walkable --portable` assemble of 9052's themed spec
writes identical `site.tscn`, `site_walk.tscn`, gameplay, lights, slots and
markings.

A zone's aabb z now runs from the top of the surface its family names
(`sidewalk` SIDEWALK_H, `frontage` FRONTAGE_THICK, `road` ROAD_THICK, `path`
PATH_THICK, `courtyard` COURT_THICK, the rest the plate) to one unassisted
step above it. Nothing reads it; it had said 0 for a band 0.0974 m tall.

Measured after, through the pipeline's own stages on scratch copies (this
Lot's `site_surfaces` on 9052's candidate spec, Patina 0.22.0's planner,
Level Factory's `dressing_scene` writer, swapped into a copy of 9052's walk
package rebuilt on Lot 0.71.0 geometry, which this Lot reproduces): 4,690
instances, 0 more than 5 mm off the slab under them in the Lux-applied scene
that renders, split `ground` 0 of 3,206, `sidewalk` 0 of 1,432 (frontage 0 of
52), `wall_base` 0 of 52. The same stages with 0.71.0 and Patina 0.21.1:
4,948 instances, 2,587 off (`sidewalk` 1,587 of 1,606 including all 56 on
frontages, `ground` 990 of 3,289, `wall_base` 10 of 53). Frames from given
low stations along the north band show it bare before and dressed after.

Found on the way and NOT changed here, both about diagonal slabs:

- The drawn diagonal path is mirrored. `_yaw_box_node` is called with
  `-ang`, and Godot reads the `Transform3D(...)` literal row-major:
  `str_to_var` on 9052's `path_0` gives `basis.x = (0.898768, 0, 0.438424)`,
  so its far end is at plan (44.5, -9.75) while `b2` stands at (45, 10). On
  9052, 42 dressing instances within 4 m of the b1 -> b2 centreline stand on
  bare plate, and 32 stand on the drawn path away from that centreline. `tops`
  follows the drawing, as dressing must.
- `site_steps.surfaces` reads the same literal column-major -- the
  transpose, which for a yaw is the mirror -- so the step gate sees a
  diagonal slab where the spec meant it rather than where it is drawn.
  Axis-aligned slabs are symmetric under it. `test_site_surface_tops` reads
  the scene row-major for that reason and says why.

Tests (`test_site_surface_tops.py`): every walkable box `_outdoor_nodes`
draws for 9052's spec, a spec with diagonal paths and a courtyard, and
`specs/coldrun_kerb_probe.json` is declared with its name, top and plan
corners, and nothing is declared that is not drawn; the top under points on
9052's bank front (band, kerb cut, road, cross-street band, frontage, spur
under the band, spur inside the frontage, plate, off the site); each zone's
z_lo is its own surface; the CLI writes `tops` and `tops_rule`. All six fail
on 0.71.0. `test_zone_ceiling_is_the_step_limit` now holds the box to one
step above its floor rather than above 0.

## [0.71.0] - a building close to the sidewalk meets it

The walker, cold run 9052 (rain), at the foot of the bank: the edge between
the light paving and the dark ground runs straight, kinks on a diagonal, and
runs on at a different offset -- "pathing here seems kind of random?".
Measured before anything moved. This Lot's `assemble` on that run's candidate
spec reproduces its `lot_assemble` scene byte for byte, and on the themed spec
its `themed_site_assemble` scene, which is the `site.tscn` in the walk copy.
Every paved polygon on the bank's front, in plan metres:

- the north sidewalk band of road 0, y -26.15 to -23.15, x -78.5 to -25.1
  (then the junction's dropped kerb to -13.9, then the band again);
- the bank's door spur, `path_1`, x -53 to -49, y -23.6 to -22.15: 0.45 m of
  it under the raised band, 1.0 m showing;
- and nothing else. The bank's face is y -21.0 (`_footprint` 30 x 22), so the
  2.15 m between it and the band was ground plate, and the plate wears the
  lot's `asphalt_delco`.

So the dogleg is the spur: 4 m of sidewalk skin standing 1.0 m proud of the
band and stopping a metre short of the wall, whose side edges read as
diagonals from eye height. The shop next door is the same shape deeper
(`path_2`, 3.0 m showing in a 4.15 m strip).

**The walk is paved to the face** (`site_streets.frontages`). A building face
parallel to a sidewalk band, behind its back edge, less than `FRONTAGE_MAX`
from it, gets the strip between them across the building's width: from the
band's back edge to the face, within the stretch the band is drawn over (the
slab, less its gaps and the junction boxes of roads crossing that kerb). The
art direction's point 4 is the rule: commercial buildings meet the sidewalk,
with parking beside or behind. `FRONTAGE_MAX` is `BAY_LENGTH`, 6.0 m -- a
strip that cannot hold a parked car's length is residue, and a deeper one is
the lot in front of a building, whose door path keeps meeting the sidewalk
square. On 9052 the bank (2.15 m) and the shop (4.15 m) get one and the
country club (13.15 m) keeps its lot and its 12.45 m spur.

A corner building with a frontage on each of two crossing roads has the
square between the strips, behind both bands, paved too, so the walk wraps
the corner rather than leaving a notch of lot there (on cold run 9051's first
candidate, the arena's corner at the cross street). A face that does not run
along the road (a building at 45 degrees, whose footprint is an enclosing
box, or a road off the plan axes), and a building with no measured footprint,
get nothing. A strip that would overlap another building or another road is
dropped and says so, `LOT_FRONTAGE_BLOCKED`; nothing on any cold-run
candidate since 9040 (39 specs) raises it.

The strip is drawn flush, `frontage_<road><side>_<n>`, at `FRONTAGE_THICK`
(one surface tier above the courtyard, so a spur inside it is covered rather
than z-fighting), in the sidewalk's skin. Flush rather than at kerb height so
every door threshold and the navmesh stay where they were: the riser at the
band's back edge is still there. `site_steps` counts `frontage_` as a walked
surface, `site_surfaces` offers each strip to dressing as a `sidewalk` zone
tagged `frontage`, and `site.markings.json` lists them.

Measured after, cold run 9052's candidate: the greybox scene adds two
`frontage_0L` bodies and changes nothing else -- `site_walk.tscn`,
`site_navqa.tscn`, the gameplay, lights and slot manifests are byte-identical
to 0.70.0's, and the assemble log is identical but for its output paths. The nav-QA walktest on
the rebuilt scene: PASS, 3,149 navmesh polygons, every walker the distance
the cold run's own walktest reported (players 364.6-368.1 m, 12/12). Lux
re-applied (Heavy Rain) to both scenes and photographed with
`tools/look_shots.py` from the same given stations: the bank's front is one
straight edge from the band to the wall.

Not changed, and said: the chain path b1 -> b2 still runs centre to centre at
26 degrees across the lot between them; it is Level Factory's route, not a
paved edge along the street, and not what the walker photographed. A path
through a footprint was suspected of showing on the floors it runs under;
frames inside both buildings show no band, so that is not a visible defect.
Surface dressing is placed at y = 0 whatever the surface: on 9052, 1,549
dressing instances already lie inside the raised sidewalk bands, and 39 more
now lie under the 16 mm frontages -- that is the dressing layer's
height, not this change's to fix.

Tests (`test_site_frontage.py`, on 9052's spec): the bank and the shop get
the exact strips and the club none; every sample between band and face
across both buildings stands on a paved surface read back off the emitted
scene (on 0.70.0, 244 of 276 were bare plate); beside the shop the paved edge
turns square at its sides; a 45-degree building, an off-axis road and an
unmeasured footprint get nothing; a kiosk in the strip drops it and says so;
dressing sees the strips as sidewalk; the markings manifest names them; a
corner building's corner square is paved. All eight fail on 0.70.0, and the
corner test fails with the corner step removed. `test_step_thresholds` holds
`FRONTAGE_THICK` to the walk ceiling beside the other flush slabs.

## [0.70.0] - a street of different cars, each facing the way its lane travels

Zoo 0.79.0 rebuilt `simple_car` in four body styles and said what stood
between it and a street of them: Lot. Measured before anything moved, by
re-running this Lot's `assemble` on cold run 9050's candidate spec
(`bank_block_001/candidate_seed_9050/site.json`) and checking the parking
plan against that run's own `lot_assemble` output (Lot 0.69.4, commit
2a689ff): identical, 42 cars. Every one was `site_parking.CAR`, 1.75 x 4.30
x 1.45, and `write_site_slots` wrote `"style": 1` on every slot, so Zoo's
`plan_kit` planned ONE car module for 42 bays (43 slots with the cover
planner's car) and the street was one car forty-two times.

And 19 of the 42 faced into the traffic. `plan_parking` gave both kerbs
`road.angle_deg + 90`. Zoo's car is nose -Y (its recipe; and the built
1.80 x 4.70 x 1.73 module puts the windshield at glTF +Z, the tail lamps and
plate at -Z), and a slot yaw is a counterclockwise plan rotation (0.69.4,
measured in Godot 4.7 on the sign blade, which faces -Y too), so the nose
of a car at yaw is `(sin yaw, -cos yaw)` and at `angle + 90` it points +t
on BOTH kerbs. Traffic keeps right: +t drives the R half, so every car on an
L kerb pointed against its lane. Two instruments agree on the count: a probe
reading the written slots against `site_streets.right_side` (19), and a
sweep that uses no street table at all -- the car's offset from the centre
line against its nose's right-hand normal -- which also found 4 of 11 on
`coldrun_kerb_probe`, 11 of 22 on `gs_heist` and 17 of 36 on `vault_job`.

**A car faces its lane.** `plan_parking` takes the lane's travel from the
kerb (`lane_travel`: the kerb on a +t driver's right is `right_side(+1)`)
and turns the nose along it (`yaw_facing`, the inverse of `nose`). On an
east-west road the R kerb stays 90 and the L kerb is 270; on a north-south
road 180 and 0. A left-hand site is still one table away. Lot has no
perpendicular or lot bays -- `site_streets.bays` makes parallel bays only --
and the cars the cover planner stands (`across_yaw`, turned across the
sightline they break) are not parked in a lane and keep their rule.

**A car per bay from a table.** `site_parking.CARS` holds four shapes --
hatchback 1.60 x 3.80 x 1.40, the old default 1.75 x 4.30 x 1.45, sedan
1.75 x 4.80 x 1.42, SUV 1.80 x 4.70 x 1.73, weighted 2:3:3:2 -- and
`STYLES` is 2. Each shape is inside the bay (under 6.0 long, under 2.2
wide), over `MIN_COVER_HEIGHT`, inside the genome's ranges, and -- read off
Zoo 0.79.0's `car_forms.FORMS` -- the first, third and fourth each lie in
exactly one body-style window (hatchback, sedan, SUV) while the default
lies in two and Zoo's seed picks. The sizes are the ones Zoo's changelog
proposed, near a Metro, a Taurus-class sedan and a first Explorer; they
are not measurements of those cars. `car_for_bay` draws the row and the
style from a SHA-1 of the road's index, its end points to the centimetre,
the kerb and the bay -- not `hash()`, which is salted per process, and not
the occupancy hash, whose value for the bay already decided the bay is
occupied. A car that does not fit its bay (it would overlap what stands, or
a marker's clearance) takes the longest smaller row that does and the
record says `car_asked`; every smaller row lies inside the default car's
rect, so every bay 0.69.4 filled is still filled -- on 9050 the same 42
bays in the same order, and the furniture and cover plans equal to 0.69.4's.

Why 8. Zoo seeds a module from its stem, and the stem is species, theme,
style and dims -- nothing else Lot writes -- so a second car of one shape
needs a second style, and the table times the styles bounds the parked-car
modules at 8. Each is a Blender kit build and about 3,000 tris of unique
mesh (Zoo measured 2,884-3,328 per style); instance tris are what they
were, since the car count does not change. On 9050's 42 cars that is 8
modules, 2 to 12 uses each. Zoo's own `plan_kit`, run on the slot manifest
this writes, plans exactly the 8 stems `cover_module_refs` now resolves, no
species fallbacks and no stem collisions. Zoo's pure `car_forms.resolve`
predicts the eight as a two-door and a four-door hatchback, sedans at 4.30
(style 1) and 4.80 (both), a hatchback at 4.30 (style 2) and two SUVs; the
four style-1 builds Zoo made for its own changelog match that prediction in
door count and cladding.

**The slot contract.** A parked car's cover record carries `style` and
`car` (and `car_asked` when it swapped). `write_site_slots` writes a piece's
own style on its slot (1 when it has none, as before). `cover_module_refs`
resolves a piece at its own style, falling back to the site's: at the
site's one style a style-2 car asks for the style-1 file, which is another
car. Zoo needs nothing new -- `plan_kit` already reads a slot's style into
the stem (`int(s.get("style") or style or 1)`).

Measured after, plan only (nothing standing, no markers), every Lot spec
with parked cars: `coldrun_kerb_probe` 11 cars, 7 modules; `gs_heist` 22, 6;
`vault_job` 36, 8; none against its lane.

Not verified: no kit build of the eight and no Godot frame of the street;
the facing is derived from 0.69.4's Godot measurement and the built GLB's
node positions, not from a render of a parked car. Frame cost of eight
unique car meshes on the walker's machine is not measured. A bay on a
diagonal road still takes a footprint quantised to 0/90
(`site_cover.footprint`), as it did.

Tests (`test_site_parking.py`): every bay picks the same car, style and yaw
in this process and in two interpreters at different `PYTHONHASHSEED`s; a
street of six or more cars parks more than one module, counted on the slot
manifest and bounded by the table; a parked car's kerb is on its nose's
right on both kerbs of roads running each way and at 30 degrees, from
geometry alone; every car lies inside its painted bay with a collision box
of its own dims; the mix fills the bays the single car filled and says what
it swapped; a piece resolves to the module of its own style. Against
0.69.4's `site_parking.py` and `lot.py` all six fail -- the module, facing
and style-resolution tests on the defect itself, the other three first on
fields and a table that did not exist. Each was also broken deliberately
against the new code and failed: a salted `hash()` for the SHA-1, a 6.2 m
row, the default car's footprint for every car, no smaller car on a misfit,
one yaw for both kerbs, the travel sign flipped, one shape at one style.
Two 0.69.4 tests pinned the single car (yaw 90 on both kerbs, a 0.725 m
slot centre) and now read the car's own dims and kerb.

## [0.69.4] - stop signs stand at junctions, by the street rules

The walker, cold runs 9046 and 9048: stop signs in pairs at footpath
crossings. `tools/probe_street_control.py` (new) reports every stop sign and
every junction leg on a spec. On cold run 9049's generated site 0.69.3 placed
seven (the assemble's own `furniture_plan`; eight re-planned without its
markers): one at each 4 m door spur, one or a pair at the 8 m building path
across the side street, and a pair on the side street's own kerbs INSIDE a
signalised junction. All three are one rule: any kerb cut 3.5 m or wider was
read as a driveway and signed, and a road's mouth is a cut too. None of them
served an approach; every one faced along its road.

Stop signs now follow docs/STREET_RULES.md (MUTCD). `site_streets.approaches`
models every leg of every road-road junction and which road yields: a T's stem
yields; at an X or an L corner the lower rank (arterial, then width) yields,
and equal roads all yield. A yielding road that meets an arterial is under a
signal and carries no stop sign. `plan_traffic_control` stands one sign per
stop-controlled approach on the driver's right (traffic keeps right,
`site_streets.KEEP_RIGHT`), the plate 1.2 m before the leg's painted
crosswalk, stepping back up the leg past a dropped kerb, a mid-block
crosswalk, a piece or a marker, never more than 15.2 m from the crossing
road's travelled way (`LOT_STOP_SIGN_NO_ROOM` when nothing fits). The post
stands on the furniture line when that keeps the plate's near edge 1.83 m off
the pavement; a band under 2.58 m cannot, so the sign stands as far out as the
band holds and `LOT_STOP_SIGN_OFFSET_SHORT` says by how much (central_vault's
and warehouse_district's 1 m bands both do). A second sign on the left only
when an approach carries two lanes. A cut, whatever its width, keeps the
blank blade. The control is planned before the band furniture, so a lamp
steps aside for a sign rather than the reverse.

THE FACING WAS MEASURED, not recalled. Godot 4.7 parses a `Transform3D(...)`
text as basis ROWS (`str_to_var` on the text `_godot_transform` writes), so a
slot yaw is a counterclockwise plan rotation and a Zoo blade, facing Blender
-Y, faces plan `(sin yaw, -cos yaw)`. 0.69.3's junction signs, at the road's
angle plus 0 or 180, stood edge-on to the driver they were for.

The stop bars were on the wrong half. `markings` painted the +t driver's bar
on the L half -- the lane leaving the junction -- while the sign stood on the
right. They follow `right_side` now. The crosswalks at the signalised
junctions were already right: the probe finds every leg of cold runs 9046,
9048 and 9049's junctions marked, and a test holds it.

Paint wear no longer repeats between crosswalks. Paint projects in world
space, and on cold run 9044's markings 5 of 210 bar pairs still wore
matching scuffs under Pixelcoat 0.39.0's 8 m tile. Each marking's material
now carries a `uv1_offset` from a SHA-1 of its road, kind and plan position.
The knob was confirmed in Godot 4.7's shader template (read from the binary):
`uv1_triplanar_pos = world * uv1_scale + uv1_offset`, and an upward face
samples `.xz`, so a flat marking is shifted by the offset's X and Z.

THE SHOP SIGNS ON AN EAST OR WEST FACADE FACED THE WALL. `sign_facing`
(0.69.2) derived `r = -(t + 90)` by reading the transform text as basis
columns; Godot reads rows, which makes the answer `r = t + 90`. The two agree
modulo 360 for a north or south facade and are a half turn apart for east and
west, so on those facades the lit QuadMesh stood against the wall with the
dark can toward the street. The 0.69.2 test read the numbers the same wrong
way (the third row, not the third column) and passed. Measured in Godot 4.7
by parsing `_sign_node`'s own cabinet and face-child text with `str_to_var`
and carrying the QuadMesh's normal through it, as plan vectors (outward
normal; face normal; face offset from the cabinet centre):

    facade  outward   0.69.3 face    offset          0.69.4 face    offset
    N       (0, 1)    (0, 1)         (0, 0.112)      (0, 1)         (0, 0.112)
    S       (0, -1)   (0, -1)        (0, -0.112)     (0, -1)        (0, -0.112)
    E       (1, 0)    (-1, 0) WALL   (-0.112, 0)     (1, 0)         (0.112, 0)
    W       (-1, 0)   (1, 0) WALL    (0.112, 0)      (-1, 0)        (-0.112, 0)

The test now reads the third column, runs once per facade, and also holds the
face child forward of the can. Against 0.69.3's `sign_facing` it failed for E
and W and passed for N and S; it passes on all four now. The shop sign's
light is not keyed off this yaw: Lux 0.33.0 lights `sign` anchors that come
from the buildings' own `lights.json` (Deli Counter walls, merged with the
placement's `rot`), not from `sign_placement` or `sign_facing`, so this
change does not move any light.

## [0.69.3] - the sign's face is a quad, so the whole name is on it

Cold run 9042, with the facing fixed: the bands face the road and the name
on them is CROPPED. `sign_b1` carries a centred 512 x 128 pack reading
KEYSTONE SAVINGS; the rendered band showed the top border, a field of green,
and the tops of the last four letters cut off at the bottom edge.

Measured off the frame rather than recalled from the engine's docs: the
visible sub-rectangle is about u in [0, 0.90] and v in [0, 0.62]. The box is
9 x 1.5 x 0.22, and 9 / (9 + 2 * 0.22) = 0.95 with 1.5 / (1.5 + 2 * 0.22) =
0.77. A BoxMesh's unwrap has extents PROPORTIONAL TO THE BOX, not normalised
per face, so a face shows part of its texture and how much depends on the
other two dimensions. No fixed `uv1_scale` corrects that, because the
correction would differ for every sign size.

So the cabinet is now what a cabinet is. The BoxMesh keeps the silhouette
and the 22 cm of depth, wearing a plain dark colour; a QuadMesh of exactly
the band's width and height sits 2 mm proud of its front and carries the
pack, the emissive and the nearest filter. A QuadMesh spans the full 0..1
across its one face by construction, which is the property this needed and
the box never had.

Two frame sets, two defects in the same thirty lines, neither visible to any
gate: the first pointed the sign at the wrong wall, the second showed two
thirds of its name.

## [0.69.2] - the sign faces the road

Cold run 9041 scored zero and shipped three signs as blue slivers a few
pixels wide. `sign_placement` chose the right facade -- that is tested and
the test was right -- but the yaw it returns is the PLAN-space angle of the
facade's outward normal, counterclockwise from +x, and the scene writer
handed it to `_sign_node` as a Godot rotation about Y with only the
handedness flipped. Every one of the four sides was a quarter turn off, so
every sign on every street since 0.69.0 stood edge-on to the road it was
hung for.

`sign_facing` now does the conversion and carries the derivation: the
cabinet's face is its local +Z, pointing at `(-sin r, 0, cos r)`; plan maps
to Godot as `(x, -y)`; an outward normal `(cos t, sin t)` therefore needs
`r = -(t + 90)`, which is the only angle in the circle satisfying both
components. The new test asserts the emitted basis for all four sides
rather than the intermediate number, because the intermediate number was
already correct.

No gate saw this. The walker's frames did.

## [0.69.1] - the sign is legible

Cold run 9040's frames: the band over the door was blown to white and the
shop's name could not be read. Its emission multiplier was 1.6 on top of
the Lux spot that already lights a facade sign; a lit cabinet is brighter
than its wall and no brighter. 0.65.

## [0.69.0] - a lit sign over every shop's door

Roadmap 153. The spec names a Pixelcoat sign pack per building
(`{"signs": {"b0": "<pack dir>"}}`, the way it names a ground skin) and
`building_signs` resolves it into the maps a material needs, reporting
`LOT_SIGN_PACK_MISSING` for a pack it cannot read rather than leaving a
blank facade in silence -- a strip with no signs and a strip whose signs
failed to load look identical from the sidewalk.

A SHOP SIGN IS A BAND ACROSS ITS FRONTAGE, not a plaque on a wall: the
walker's reference frames show the store's name running the full width of
the storefront above the glazing. `sign_placement` picks the facade the
nearest road lies off -- the side whose outward normal points most nearly
at the road's closest point -- and `sign_size` takes 72 percent of that
facade's width, between 2.4 m and 9 m, six times as wide as it is tall,
which is the shape Pixelcoat renders a sign pack at. The band is drawn
as a lit double-sided quad 3.6 m up with the pack's emissive map, no
collision and no triplanar: a sign's face is its texture once across, not
a tiled surface. The maps travel beside the scene like a ground skin's.

## [0.68.1] - a driveway gets a stop sign

Cold run 9036 shipped no stop sign at all: the generated spec's only
junction is a signalised arterial, so `plan_traffic_control` never had one
to place. A 1990s American parking lot exits onto the street under a stop
sign, and the cut a SPUR makes in the kerb IS that driveway -- Level
Factory's spur is 4 m wide and a footpath is narrower, so the blade at a
corner is a `stop_sign` at a cut of `DRIVEWAY_WIDTH` or more and the blank
`sign_post` below it. On 9036's own site that is six stop signs, two blank
blades and the signal.

## [0.68.0] - the 1990s American street on the kerb line

Roadmap 153. Zoo 0.72.0 mints the kit; `site_furniture` puts each piece
where that decade's street carried it.

TRAFFIC CONTROL AT THE JUNCTION MOUTHS. A road that ends on another has a
mouth at one end of its slab, and the driver approaching it has one kerb
on their right (Lot's `perp` is left of travel, so a driver going +t has
the R kerb and one going -t has the L). `plan_traffic_control` stands a
`traffic_signal` there when the road this leg meets is an ARTERIAL --
sidewalks and parking lanes both, which is a Delco side street meeting a
commercial strip -- and a `stop_sign` facing the driver otherwise. The
signal's pole stands ON the corner: measured on cold run 9035's site, a
2.2 m setback left the arm's tip over the sidewalk, because the arm has to
cross the setback and the band before it reaches the carriageway at all;
at 0.4 m the tip lands 1.6 m past the kerb, over the near lane. The
signal's greybox box is the POLE's footprint, not the slot's 8 m of arm.

A `parking_meter` at every parking bay, near the kerb edge -- a row of
single-space meters is half of what dates a street -- and the `mailbox`,
two `newspaper_box`es and a `payphone` at the bus stop, where people
already stand, each stepped along the band like a lamp when something is
in the way.

AND TWO ROADS THAT MEET NO LONGER DRAW THE SAME TREE. `tree_for` hashes
one road, so a two-road site draws one species twice about one time in
five -- cold run 9035 was one of those, and a junction where the avenue
and the side street are the same tree is the one place it would be seen.
A road keeps its own hash unless a road already planted has it.

## [0.67.0] - a street plants one species per road

Roadmap 153. Zoo 0.71.0 mints five street trees; `site_furniture.tree_for`
decides which one a road carries -- a stable hash of the road's own
endpoints, rounded to the metre, so a mission's avenue is maples and its
cross street pin oaks, the same spec plants the same street every run, and
two missions do not always get the same tree. Five species scattered tree
by tree would read as an arboretum; one per road reads as a street
somebody planned. Measured over the last three cold runs' specs: five of
six candidates plant two different species, one plants London planes on
both roads.

`SPECIES` carries each tree at its own Zoo genome's default dims (a
callery pear is 3.0 m across at planting, a London plane 5.0 m), and a
test asserts that against the sibling zoo checkout rather than against
the comment that says so. Every tree's greybox footprint is still the
grate's 1.2 m, and `COVER_MATERIALS` names them wood.

## [0.66.1] - the kerb line keeps clear of the mission markers

Cold run 9030's third seed stood a lamp on Enemy_4, and the Laser Tag
preflight refused that candidate for an enemy inside solid geometry: the
kerb line had never looked at the markers (the cover planner and the cars
always had). `site_furniture` now keeps every piece
`site_cover.MARKER_CLEARANCE` from every marker's edge -- a lamp or a tree
steps along its band by up to 4 m to do it, a corner piece or a bus stop
is skipped -- and a station over a dropped kerb is still skipped, not
nudged, so the spacing rule stays the spacing rule.

## [0.66.0] - the street is planned before the cover, and an X has one surface

Roadmap 153 residue. THE CARS FIRST: `assemble` plans the kerb line and
parks the cars before the cover planner runs, and hands both to
`plan_cover(standing=...)`, where they occlude a sightline the way a placed
piece does and a piece keeps its own daylight from them -- so a truck or a
container is stood in the road only for a line the street's own furniture
left open. Measured before: cold run 9028 stood a container at the
junction with 28 cars parked, because the cars were planned after. AN X
CROSSING: where a lower-index road crosses THROUGH another, that road owns
the junction's surface; the higher road carries `gaps` (the lower's box)
and `drawn_spans` is its slab less those, so its slab and band pieces stop
at the box's edges and resume past them -- no two slabs or dropped kerbs
lie coplanar. `Cut.crosser` names the crossing road; the manifest carries
`gaps`. Tested on a two-road X and on the kerb probe.

## [0.65.1] - the paint pack reaches the scene

Cold run 9028 named the road-paint pack in the themed spec, `ground_skins`
resolved it, and the scene shipped flat markings: `write_godot_scene`
declares only the skin families a body will reference, from a table of
families it knows, and `paint` was not in the table. It is now, wherever
there is a road; tested end to end on a tee spec with a stub pack.

## [0.65.0] - intersections, and the paint as a decal

Roadmap 153. INTERSECTIONS: a road crossing is a BOX -- the crosser's
width plus its sidewalk band each side (`Cut.sidewalk`, `crossing_box`) --
and the paint answers it: a crosswalk at each end of the box in line with
the crosser's sidewalks (a path's crosswalk is still the path), the stop
bar only on the leg that ENDS at the junction (`Cut.terminal`, judged
where the crosser meets the road's centre line: a T leg stops, the through
road keeps its right of way; a path crossing keeps both bars), the centre
line and the edge lines broken over the box -- the edge line over a road's
mouth only, whole over a dropped kerb -- and parking clear of the box. A
road that ends on another begins its slab at that road's band edge
(`Road.slab`, `_slab`), so two slabs never lie coplanar over the mouth and
the through road's dropped kerb is the mouth's surface; the writer draws
the slab and clips the band pieces to it. The manifest carries `slab` per
road and `sidewalk`/`terminal` per cut. Residue: two roads CROSSING (an X,
neither ending) still overlap their slabs; the generated spec makes a T.

THE PAINT AS A DECAL (152 step 2): a `paint` skin family. A Pixelcoat
`road_paint` pack (0.31.0) whose import hints ask for alpha scissor gets
`transparency = 2` on the marking quads' material, and the quad is tinted
by the marking's own colour -- so the white lines are worn through to the
road in patches and the centre line is the same paint in yellow. Without
the pack the quads are the greybox's flat read, as before.

## [0.64.0] - the waiting places: a tree between the lamps, a bus stop per road

Roadmap 153, the third layer. `site_furniture` now plants a `street_tree`
halfway between every two lamp stations on the outer half of each band,
and stands one bus stop per road -- a `bus_shelter` open to the kerb with
a `bench` inside it against its back and a `sign_post` a metre before it
-- on the kerb the buildings face (`_facing_kerb`, the sign of the mean
building offset in the road's frame), at the midpoint of the longest
stretch between two crossings, nudged in 3 m steps clear of whatever
already stands there (`_free`). Every piece is the same prop-slot record
as the kerb line, so the site kit builds it and the themed site stands it.

A tree's SLOT is its crown (4 x 4 x 6, what Zoo builds to) and its
FOOTPRINT is its grate (1.2 x 1.2, what the greybox draws and the navmesh
carves): `FOOTPRINT` separates the two, `size` is the footprint, `dims`
the slot, and the record carries `t` and `along` so a planner can ask what
already stands on a band. The kit index's `warn` rows now stand (a built
module with an advisory against it); only `fail` keeps the box. The greybox over-blocks the trunk by the grate's
margin and never under-blocks it. `plan_furniture` lost the `sidewalk_h`
it never read and gained the spec's buildings; `COVER_MATERIALS` names
the three species' kinds.

## [0.63.0] - cars parked in the kerb lanes, and the index's verdict read

Roadmap 153, the cars in order. `site_streets` gains parking lanes: 6.0 m
bays in a 2.2 m lane along each kerb of a road with sidewalks (the low end
of parallel-parking practice, so a 10 m road keeps two 2.8 m driving
lanes), none within 6 m of a crossing (the 20 ft no-parking rule) or over
a kerb cut; the edge lines move to the driving lanes' edge and every bay
edge gets a tick. `site_parking` parks a `simple_car` in 60 percent of the
bays by a stable hash of (road, side, bay) -- the same spec parks the
same cars every run -- along the road, clear of every mission marker and
of every piece already standing by the cover planner's own two rules. A
parked car is cover, and it is the same prop-slot record: the site kit
builds it, the themed site stands it. `parking_plan` in the gameplay
file, `LOT_PARKING_PLACED` on stdout.

THE INDEX, READ. Zoo writes `site_kit.built.json` beside the modules with
a `status` per row, and Lot stood a module by file: cold run 9024 shipped
the lamp at 6.18 m against a 6.00 m slot and the car at 4.36 against 4.30
with both rows `fail`. A module whose row is not `pass` keeps its box
under `LOT_COVER_MODULE_FAILED`, naming the status; no index stands
everything that exists, as before.

## [0.62.0] - the kerb line

Roadmap 153, the second layer. `site_furniture` places, along every
sidewalk band of every road in `site_streets`, a streetlight every 25 m
(IES RP-8's residential spacing at the low end, for a 6 m lamp) and at
every crossing a fire hydrant 2.5 m past the dropped kerb, a litter bin
1.5 m before it and a stop-sign post at its edge facing the road -- each
on the band's outer half so the kerb edge stays clear for a body stepping
off at a cut, none inside a cut's span plus a clearance. They are the
same prop-slot records the cover planner writes, with a `base` of
`sidewalk`: the manifest's translation and the scene's instance both
stand the module on the band's top (`SIDEWALK_H`) rather than the plate,
box and module alike. Every species is taller than the step limit and
carries collision, so the honesty rule holds by species. The plan is
written to the gameplay file as `furniture_plan` and said as
`LOT_FURNITURE_PLACED`.

## [0.61.0] - the street is a model, and it carries its paint

Roadmap 153, the walker's "does Lot need to evolve now": yes, in this way.
A road lived inline in `_outdoor_nodes` -- one yawed box, two sidewalk
bands split at the crossings, the crossing arithmetic beside them -- and
every next step of the street asked the same questions of the same
geometry. `site_streets` answers them once: a `Road` with its kerbs, each
kerb's cuts and spans, the crossings of the centre line, and `point(t,
offset)` for anything that needs a place on it. The writer draws what the
model says, byte for byte what it drew before (measured on the kerb-probe
spec: 792 road-family node lines and 184 sub-resource lines identical
before and after), and the shallow-crossing warning is a finding the
model returns rather than a print inside the writer.

THE PAINT. `site_streets.markings` puts a rectangle where each mark goes:
an edge line each side (0.12 m, 0.3 m in from the kerb face), a dashed
centre line (3 m on, 9 m off, yellow) that stays clear of the crossings
and their stop bars, a continental crosswalk at every crossing of the
centre line (0.5 m bars, 0.5 m apart, one station per crossing --
stationing at the kerbs gave 14 crosswalks for 8 crossings on a road the
paths meet at an angle), and a stop bar per lane before each crosswalk.
The scene draws them as flat quads one surface tier above the road, tiled
like every surface and with NO collision (a marking is not a thing a body
meets); `assemble` writes the same rectangles to `<site>.markings.json`
(`site-markings/1`) for the decal layer to carry as decals when it can.
Widths from the MUTCD's normal line and continental crosswalk; colours
the greybox's flat reads until Pixelcoat has a marking texture.

THE ZONES. `site_surfaces` declares a `road` family (density low) for the
strip and a `sidewalk` family (high, a seam, kind `sidewalk`) for each
kerb band, from the same model, ahead of wall bases and behind paths in
precedence. A road was open ground to the dressing planner before.

## [0.60.0] - a road and its sidewalks wear their own skins

Roadmap 153. `ground_skins` gains two families: `road` for the strip and
the kerb cuts (road at road height), `sidewalk` for the raised kerb bands.
Declared only when the spec names a road, like every other family. The
road, sidewalk, kerb and crossing geometry itself is unchanged and has
existed for hand-authored specs since the kerb work; Level Factory 0.78.0
is what puts a road in a generated spec for the first time.

## [0.59.2] - the cover modules live beside the scene

Cold run 9019: three modules built, three boxes replaced in Lot's scene,
none in the level. 0.59.0 referenced each module by absolute path, the Lux
stage stages the scene into a throwaway project, Godot has no loader for a
glb outside it ("No loader found for resource"), and the applied scene the
package ships came back without the cover nodes. The skins had taught this
one stage earlier (0.58.0). The modules are now copied to `cover/` beside
the scene and referenced as siblings -- `cover/<stem>.glb`, `res://cover/`
off portable mode -- which every stage that loads a Lot scene carries.

## [0.59.1] - marker clearance is measured from the piece's edge

Cold run 9018, the first with species pieces: the chain worked -- Zoo built
the truck and the container from the site's manifest, Lot stood both where
their boxes were -- and Laser Tag's preflight refused the candidate:
"Enemy_2 is sealed off from the crew spawn". Measured: the container's end
stood 0.25 m from Enemy_2, beside a building. `_usable` kept a marker
`MARKER_CLEARANCE` from the piece's CENTRE, which left a 3 m cube 1.5 m
clear and a 6 m container nothing at all. The clearance is now the piece's
rect grown by the same 3 m; a marker inside it refuses the spot. The export
gate (Level Factory 0.76.0) held on the blocker, which is the first time a
cover defect was stopped before it shipped.

## [0.59.0] - cover is a species-shaped slot, not a cube

Roadmap 22, open since August: the cover this module places to break
sightlines was a 3 m green cube in every package, and the site had no slot
manifest for anything to replace it through. The walker, 2026-09-12: "the
green boxes should be larger props with collision to offer cover between
buildings to force creative traversal."

`site_cover` now places SPECIES pieces -- `COVER_SPECIES`: a box truck
(2.4 x 6.0 x 2.8), a cargo container (2.44 x 6.06 x 2.59), a car (1.75 x
4.3 x 1.45), the Zoo genomes' own defaults -- turned so the length lies
ACROSS the sightline (yaw 0 keeps Zoo's frame, length along Y; 90 turns
it), quantised to 0/90 so the axis-aligned break and pinch arithmetic
measure the piece and not its bounding box. The table is walked from the
piece's own index, so a street gets a truck, a container, a car, not one
truck five times, and each piece takes the largest that fits its lane. The
centre-to-centre separation the squares were placed by is joined by the
edge-to-edge gap it implied (`COVER_EDGE_GAP`, 3 m): measured the day the
trucks arrived, two of them six metres apart centre to centre stood 0.78 m
apart and `pinches` reported the lane the planner had just sealed. The
square form is untouched for any caller that passes no species.

`assemble` writes `<site>.slots.json` beside the scene: one prop slot per
species piece in Deli Counter's slot-manifest shape (species, exact dims,
transform with the yaw, convex collision), so the same Zoo kit build that
dresses a building builds the street's cover. A themed spec that names
`cover_modules` (the build directory, theme, style) gets each module
instanced where its box stood -- centre for centre, the module's own
collision, by the stem `cover_module_stem` mirrors from Deli Counter and
Zoo and pins by literal -- and every piece whose module is not there keeps
its box under `LOT_COVER_MODULE_MISSING`, with the stem it looked for.

## [0.58.0] - the skins live beside the scene

0.57.0 wrote each map's absolute path and copied nothing, on the theory
that a consumer bundles what a scene references. Level Factory's export
does; Godot does not: a `.png` outside a project has no importer, so the
first thing to load the scene -- the Lux stage, which stages it into a
throwaway project -- failed to parse it ("No loader found for resource
... expected type: Texture2D"), exited 2, and cold run 9015 shipped a
package with no lighting at all. Everything that loads a Lot scene copies
the scene's siblings, so the maps are now copied to `skins/` beside the
scene and referenced as siblings, the way a staged building is:
`skins/<map>` in portable mode, `res://skins/<map>` otherwise. Byte-equal
copies are not rewritten. Tests cover both modes.

## [0.57.1] - a skin is declared only where a body will wear it

Measured on cold run 9014's themed spec with all three families named: the
spec has no courtyard, and the header declared the courtyard's two maps
anyway -- resources nothing referenced. Families without a body in the spec
now get no ext_resource lines.

## [0.57.0] - the ground plate wears the theme's skin

Roadmap 152. Measured on cold run 9014: the exterior plate shipped as one
untextured 0.52 grey, so the only detail outdoors was Layer 3's clutter on
it, and 2,708 pieces of clutter read as defects in a texture that was not
there. The walker: "it looks like unintentional defects on the texture."

A site spec may now name `ground_skins`: a Pixelcoat pack DIRECTORY per
outdoor family (`ground`, `path`, `courtyard`). `ground_skins()` reads the
pack manifest (stdlib json, nothing from Pixelcoat imported) and the
material every tile of that body shares carries the albedo, roughness and
normal maps as `Texture2D` ext_resources, projected in WORLD space
(`uv1_world_triplanar`) at the pack's own `meters_per_tile` -- the same
projection `zoo_worldskin.gd` gives the kit at import, so an 8 m mesh tile
and a yawed path read as one continuous surface; nearest filtering when the
pack's import hints ask for it. Texture paths are written absolute; Lot
does not copy what it does not own, and a consumer that ships the scene
bundles what it references (Level Factory's export already rewrites every
absolute ref into its package).

A pack that cannot be read -- no directory, no manifest, no albedo, no tile
period -- is `LOT_GROUND_SKIN_MISSING` on stdout and the family stays its
flat greybox colour: a plate nobody asked to skin and a plate whose skin
went missing look identical from the walker's side, and the difference is
the whole answer to "why is the ground grey". A spec without the key writes
the scene it always wrote, byte for byte (test). Perimeter walls stay flat
and bright on purpose: they are the edge of the world.

## [0.56.0] - a building's floor plan is not ground

The walker, on cold run 9012's bank lobby: "are these grey blobs the
surface dressing?" They were. Patina's `surface_dressing` placed 185 of its
3,643 pieces -- pebbles, litter scraps, rubble, weed tufts -- inside the
bank's footprint, on the carpet, and every one of them was allowed by the
zones this module declared: 159 from `wall_base_b0`, 17 from `open_ground`,
9 from the `path_b0_b1` corridor. Three causes, one module.

The wall base was `grow(footprint, band)` -- the whole floor plan plus one
agent radius -- called a seam. It is now the four strips of that box MINUS
the plan, `_annulus_strips`, the same shape the perimeter already used; a
building with a readable footprint declares `wall_base_<id>_0..3`, and no
square metre of the plan is in any of them (test).

The open-ground remainder is the whole plate, and a path corridor from a
building starts at the building's centre, so both also cover interiors --
and nothing had said an interior is not ground. `exclusions()` now emits one
`building` box per footprinted building (schema tag added in
`level_factory/schemas/surface_dressing.v1.json`); Patina's `excluded()`
already honours `aabb` exclusions, so nothing downstream changes. Interiors
are Deli Counter's layer, dressed at the shell's request.

A raw spec carries no footprints, emits no boxes and no bands, and
`LOT_SURFACE_FOOTPRINT_UNKNOWN` says so, as before.

## [0.55.2] - site_surfaces --strict fails on what went wrong, not on what went right

`site_surfaces.py --strict` exited non-zero on ANY finding, and the tool
reports its own success as one: `LOT_SURFACE_FOOTPRINTS_MERGED`, severity
info, "read footprints for 1 of 1 buildings". The first pipeline run of the
stage (Level Factory 0.68.0's `lot_site_surfaces`, roadmap 110) therefore
failed a clean result -- 6 zones, 3 exclusions, every footprint read. Strict
now ignores `info`; the unreadable-footprint warn it was written for still
fails, and its test still holds.

## [0.55.1] - the served line says a fresh project needs an import pass

Roadmap 25. `cater` closed with "SERVED -> open <site>_walk.tscn in Godot,
F6" and nothing else, and a project Godot has never opened parses with 59
errors until the editor has imported it -- `lux_root.gd` and `lux_preset.gd`
fail to load because `class_name` resolution needs the editor's scan, and
every building reports its `.glb` as vanished. Harmless for a person, who
opens the project first; a silent trap for anything scripted. Every pipeline
stage that launches a served project runs `--import` itself now (Level
Factory's staging, export and portability check, the Lux adapter, Lot's
`package.py` and `walktest.py`, the factory's walk tools); the one thing left
was the line a person reads. It says so, with the command.

## [0.55.0] - the site light envelope is stamped from the files it merges

Roadmap 95. `merge_lights` wrote `"light_manifest_version": "1.0.0"` as a
literal while Deli Counter's `lights.py` stamped 1.1.0 on every building
manifest it merged, and the anchors were copied wholesale -- so the site file
declared one contract and satisfied a later one. Reproduced on cold run 9005's
build of 2026-09-10: building envelope 1.1.0, site envelope 1.0.0, `drop` (a
1.1.0 field) on the ceiling anchors. Nothing read the field, which is why it
survived; the `--art --unlit` handoff is documented as "a contract another
lighting system can read", and the version is the field that makes that safe.

### Fixed
- The envelope is the HIGHEST version among the merged building manifests,
  because that is the contract the anchors actually need a reader to
  understand. The full set is recorded as `light_manifest_versions_merged`, so
  a mix is visible rather than averaged away. A file with no version predates
  the field and is 1.0.0 by definition; a site with no building manifests is
  Lot's streetlights alone and stays 1.0.0. `_version_key` compares as
  integers, so 1.10.0 sorts above 1.9.0.
- `test_lights_manifest_shape` asserted `== "1.0.0"` -- the same bare literal
  as the defect, one file over. It now asserts against the merged set, and a
  new test merges a 1.0.0 and a 1.1.0 building and checks both fields.

## [0.54.0] - the carried sight heights are the evaluator's, and now they are checked

Roadmap 131. `site_cover` derives `MIN_COVER_HEIGHT` -- how tall a solid must
be to break a MUTUAL sightline -- from `EYE_HEIGHT` and `CHEST_HEIGHT`, which
it carries as a stated assumption because Lot cannot read the Laser Tag
checkout. Its own comment has said since it was written that Level Factory's
`lasertag_contract` reports drift on them. `Engagement` carried only the
engagement RANGES, so the two constants that comment is attached to were the
two nobody checked.

### Changed
- `EYE_HEIGHT` 1.4 -> 1.6 in both `site_cover` and `site_spawns`, so
  `MIN_COVER_HEIGHT` moves 1.2 -> 1.3.

  THE 1.4 WAS NOT STALE, IT WAS ONE OF SEVEN. Laser Tag used seven different
  heights to describe one firefight and no two agreed: the crew saw from a
  hardcoded 1.4 and fired from 1.55, the enemy saw from 1.5 and fired from
  1.3, its target selection sighted from 1.4 again, and the map sampler
  measured cover from a 1.5 of its own. A producer carrying "the" eye height
  was carrying one of seven, correctly sourced and still wrong. Laser Tag
  0.20.0 gives each body one eye; both are 1.6 and the crossing is 1.3.
- `test_the_minimum_cover_height_is_where_the_two_sightlines_cross` asserted a
  bare `== 1.2`, which is the defect its own docstring complains about: when
  the evaluator moved, the constant correctly followed and the test failed for
  being right. It now asserts the DERIVATION, and pins the value separately
  with the version that produced it.

### Consequence
Cover built to the old number is 10 cm short and leaves one side a free shot
over it -- and `time_to_first_contact` is stamped on the first shot by EITHER
side, so half a broken sightline starts the clock exactly where none would.
`COVER_HEIGHT` stays 2.0 and is unaffected; what moves is the floor below
which `break_interval` returns `None`.

## [0.53.0] - the opening is judged against an enemy that moves

Roadmap 127, the cheap half.

### Fixed
- `opening_engagement_is_fair` judges occlusion against the ground an enemy can
  reach in `REACTION_SECONDS`, not against the tile it starts on.
  `enemy_opening_positions` returns the candidate plus an eight-point ring at
  `ENEMY_SPEED * REACTION_SECONDS`, dropping samples that stand inside a
  building.

  THIS IS THE CORRECTION THE CREW SIDE ALREADY HAD. The docstring records
  making `crew_path` a stretch of route instead of a spawn tile, because "the
  crew does not spend that second standing on the spawn". The enemy stayed a
  point, and `LT_EnemyMovement.move_speed` is 4.0 m/s -- within 12% of
  `CREW_SPEED`. The corner that hides an enemy from the crew's first second is
  a corner the enemy walks out of in that same second.

  HOW IT WAS ESTABLISHED, because Lot was not wrong about what it measured.
  Raycasting a staged copy of restaurant_row_001 seed 9003 at the 1.6 m eye:
  standing on the spawn, every enemy inside the 35 m it can see is blocked by
  real collision and the only clear line is 59.1 m away. The occlusion credit
  was honest. Stepping the crew alone, the first in-range clear line is 2.75 s
  out; stepping both at 4.0 m/s it is 1.5 s. Laser Tag measured 0.73 s,
  identical in all 25 runs of that candidate.

### Measured, on cold run 9003's three candidates, same seeds either side

        seed        contact        survival     enemy_stuck   score
        9003    0.73 -> 1.53    3.81 -> 5.58        0 -> 0    50 -> 50
        9104    0.27 -> 1.40    3.71 -> 5.38        0 -> 0    50 -> 50
        9205    0.27 -> 1.47    2.40 -> 3.71        0 -> 0    50 -> 50

  `enemy_stuck_events` STAYING AT ZERO IS THE RESULT THAT MATTERS, and it is
  the one the previous attempt at a stricter placement failed. `ENEMY_SIGHT_RANGE`
  records that run: refusing occlusion inside 35 m took `enemy_stuck_events`
  from 34 to 75 because enemies were pushed onto ground they could not path
  off, and the score did not move. Here nothing was dropped
  (no `LOT_ENEMY_SPAWN_UNPLACEABLE`) and `ENEMY_PATHING` reports PASS.
  `LOT_ENEMY_SPAWN_STANDOFF` no longer fires at all -- the search now finds
  fair ground first time rather than sliding onto it.

### What it did NOT do, stated rather than left to be noticed
- THE SCORE DID NOT MOVE: 50 on all three, before and after.
  `first_contact_min_seconds` is 3.0 and `min_reasonable_survival_seconds` is
  10.0, so 1.5 s and 5.6 s are better numbers on the same side of both
  thresholds. INSTANT_CONTACT and NO_REACTION_TIME still fire.
- A NEW WARNING APPEARED. `BLIND_MAP` at 52% -- more than half of walkable
  positions can now be seen from no enemy spawn at all, where before the run
  did not raise it. Overexposure fell the other way, 28% to 19%. Enemies that
  keep their cover through the opening are enemies further out of the crew's
  path, and that is a trade this change makes without deciding it is right.
- The DISTANCE branch is untouched and still understates. `clearance` is the
  ground the CREW covers, so it models a closing speed of `CREW_SPEED` alone
  when both sides close at about 4 m/s. Widening it in the same change would
  have moved two axes at once, which is what went wrong last time.

## [0.52.0] - the crew spawned inside the walkthrough's player

Roadmap 122. `route_completion_rate` has been 0.0 in 31 of the 33 Laser Tag
reports on disk -- every workspace, every cold run, highest ever 0.16 -- and
the cause was in this repo.

### Fixed
- `lot_site_walk.gd` frees its preview `Player` when the scene is loaded
  headless, instead of parking it on the crew spawn.

  WHAT WAS HAPPENING. The walk scene ships a `Player` -- a CharacterBody3D on
  collision layer 1, the World layer, with a 1.8 m capsule -- and `_ready`
  moved it to `spawn_pos`. That is the entire point of a walkthrough and fatal
  to an evaluation: Level Factory stages this same scene as Laser Tag's map,
  and Laser Tag spawns its own pill at that identical coordinate. The pill
  materialised INSIDE this capsule, was depenetrated onto the top of it, and
  came to rest 1.547 m above the navmesh with `is_on_floor()` true. From there
  `get_next_path_position()` returns the bot's own XZ, `_advance_route`
  flattens it to a zero vector, and the body never takes a step. The bot was
  not failing to navigate; it was standing on the walkthrough's player.

  MEASURED on market_row_001 seed 7503, one run, identical seed either side of
  the change, with a probe reading `map_get_closest_point` at each trace mark:

        body_y            1.797  ->  0.001
        gap to navmesh   +1.547  -> -0.499
        route index         0/3  ->    2/3
        movement           none  ->  ~20 m over 14.9 s

  The before column is constant for the whole 10.7 s run -- same position,
  zero velocity, `on_floor` true -- which is what a body resting on an
  obstacle looks like rather than one that cannot path.

  WHY NOTHING CAUGHT IT. Laser Tag's own demo greybox carries no such node, so
  its CI bot always walked. The harness does check the spawn for obstruction,
  but with a single point at `spawn + UP * 0.9`, which clears an obstacle
  topping out at 1.797. And `ground_contact` tolerates up to `MAX_DROP = 4.0`
  because it was built to catch spawns over a HOLE, not spawns in the air.

  This is the same rule `_bake_nav` already applied one function below, and
  the comment there states it: headless means nobody is walking. When there is
  no walker, the right number of preview players is none.

### Added
- `test_walk_scene_removes_its_preview_player_when_headless`, a sibling of the
  existing headless-bake guard, asserting the free happens before the branch
  that parks the player on the spawn. Verified to fail on the pre-fix script.

## [0.51.0] - two implementations of one overlay, and the export layer wins

0.50.0 gave the walk harness its own position readout, not knowing Level
Factory had shipped a better one since 2026-08-08 in
`assets/godot/debug_overlay.gd`. Two implementations of the same idea is worse
than either, and Level Factory is the dominant export layer -- the walk project
is a scratch preview, and a preview should show what the export shows.

### Removed
- The `x y z` / facing / beacon-range readout added in 0.50.0. `walk_themed.py`
  now carries LF's `debug_overlay.gd` into the walk project instead, which says
  strictly more: position, the instanced BUILDING under the crosshair by its own
  `scene_file_path`, and the COLLIDER being looked at with its distance -- so a
  screenshot of a defect names the building and the surface, not just a point in
  space. It also toggles on F3 and paints its own light plate, which 0.50.0's
  green-on-sky text did not.

  The HUD's four control lines stay here. Those are about the harness, and the
  harness is Lot's.

## [0.50.0] - you could see the problem and not say where it was

Roadmap items 74-79, the part that was slowing all of them down. Every finding
this week arrived as a screenshot and had to be argued back to a place -- and
"the seam on the left" is not somewhere a second person can stand, nor
somewhere the same person can stand again tomorrow.

### Added
- The walk HUD carries a position readout: `x y z`, facing in degrees, and
  range to the objective and extraction beacons. The Label and the Player are
  resolved once in `_hud()` and held as members, so `_process` does no
  per-frame scene lookup.

  Facing is read from the BODY, not the camera. `lot_player.gd` writes look yaw
  straight onto `rotation.y` and leaves only pitch on the Camera3D, so the
  body's yaw IS the facing; reading the camera would report pitch-coupled
  nonsense.

  Costs the instruments nothing. `look_shots.py` hides every non-Lux
  CanvasLayer before it measures -- white HUD text clips and biases every
  exposure statistic -- so the measured shots are unchanged.

## [0.49.0] - one path was one light budget for sixty-five metres

Roadmap item 54, the Lot half. Godot's GL Compatibility renderer budgets
positional lights PER MESH (`max_lights_per_object`, engine default 8), and
the first honest per-mesh census (2026-08-23, `tools/mesh_light_census.py`
on lot_demo_001's walk preview) put `path_0/mesh` -- one 65 x 8 m BoxMesh --
under 58 lights, `path_1` under 52, `path_3` under 44. Ground plates, paths,
roads and perimeter walls are the same room-spanning plates Zoo 0.49.0 and
Deli Counter 0.96.0 just tiled, drawn by Lot instead.

### Changed
- `_box_node` / `_yaw_box_node` emit their VISUAL as `MeshInstance3D` tiles
  no wider than `MESH_TILE` (8 m; same law as zoo `core.arch.PLATE_TILE`
  and deli_counter `floors.SLAB_TILE`, duplicated deliberately across pure
  repos and cross-named). Tiling lives in `_mesh_tiles` + one shared child
  emitter so the two writers cannot drift: equal-cell division (no sliver
  tiles -- item 41's counter-pressure), millimetre-snapped interior cuts so
  abutting tiles meet at one coordinate, and a body already inside the tile
  emits byte-identical output -- every kerb, cover box and crossing is
  untouched, proven by exact-lines tests. The yaw'd writer tiles in the
  body's LOCAL frame, so the parent transform carries the rotation and a
  65 m path becomes nine ~7.2 m meshes lying exactly where the one lay.
  COLLISION IS NOT TILED: the `BoxShape3D` stays one shape -- a collider
  has no light budget, and every height/step check reads the shape.
- `tests/test_lot.py::test_outdoor_nodes`: the old `n_mesh == n_shape`
  assertion was the room-spanning-mesh defect stated as an invariant; it
  now asserts one shape per body, at least one mesh per shape, and no
  BoxMesh wider than the tile on either horizontal axis.
- `LOT_VERSION` re-coupled to the release number in BOTH copies (lot.py had
  0.17.2, version.py -- the one `package.py` stamps into every pack
  manifest -- had 0.18.0, the VERSION file said 0.48.0: three answers to
  one question). Same re-coupling deli_counter's `KIT_VERSION` got.

### Added
- `tests/test_mesh_tiles.py`: the tile law (measured 65 x 8 path -> nine
  budget-sized meshes, exact reassembly, no slivers, deterministic
  suffixes), byte-identity for small boxes on both writers, one-full-size-
  shape-per-body, local-frame tiling under yaw.

The item closes when the census re-reads zero meshes over 8 on a recomposed
package and level_factory deletes `PER_OBJECT_CEILING`.

## [0.48.0] - the interactives finally leave the building

Roadmap item 46, step 1. Deli Counter emits one replicable state machine per
interactive fixture (INTERACTIVES.md); `merge_gameplay` carried markers,
rooms, objectives, loot, zones, vertical_links, openings and surfaces -- and
dropped `interactives`, so the shipped site never contained the netcode's
input. "The key is simply absent" is fixed at the seam it named.

### Added
- `merge_gameplay` carries `interactives`: ids VERBATIM (they are the network
  handle, already globally unique as `<building>:if:<hash>` -- a
  concatenation, not a merge; namespacing would break the correlation with
  slots.json and the composed scene's `metadata/interactive_id`), the
  building tag added, `slot_ref` left building-local, and transforms offset
  to world space exactly like markers (Z-up yaw + translate; `rot_y`
  accumulates the placement rotation). The site key exists even when every
  building lacked one -- absent-vs-empty is the ambiguity item 46 exists to
  kill.
- Run summary and `[lot] assembled` line report the interactive count.
- Package README documents `interactives` in the integration contract.
- `tests/test_interactives_carry.py`: ids verbatim, marker-law transforms,
  no-transform and no-key cases. Proven end-to-end on cr_deli's real
  gameplay.json: 23/23 carried, byte-identical machines.

## [0.47.0] - site_surfaces reads footprints, so wall bases get dressed

`site_surfaces` reported `LOT_SURFACE_FOOTPRINT_UNKNOWN` for every building on
every real spec, and emitted zero wall_base zones. The guide says the wall seam
is where dressing density should be HIGHEST; it was the one band getting
nothing.

### Fixed
- **`annotate_footprints()` and `--base-dir`.** `merge_gameplay` writes
  `b["_footprint"]` onto the spec IN MEMORY during a Lot run and nothing
  persists the annotated spec, so a spec read off disk never has footprints
  and `rotated_footprint` returns None for every building. `site_surfaces`
  now calls Lot's own function to fill them in before computing zones.
  `--base-dir` defaults to the spec's own directory, which is where the
  gameplay files sit for every spec in `lot/specs`, so the common case needs
  no flag; pass an empty string to skip the merge.

  Measured on `coldrun_pawn_job` end to end: 79 zones and 0 wall bases before,
  82 zones and 4 after, and the plan goes from 3,745 placements with no wall
  seams to 4,374 with 1,033 of them carrying `anchor_cause: "wall base"`.

### Found while doing it
- **`merge_gameplay` is all-or-nothing on a spec.** It raises ValueError on
  the first building declaring no `glb` or `scene` -- reasonable for its own
  job, since it is assembling geometry -- and every building AFTER that one
  goes unannotated. Measured on a four-building spec with one geometry-less
  entry: the first building annotated, then a raise, then three left bare,
  which reads on the output as a site whose walls mostly do not exist.

  `annotate_footprints` therefore merges each building through its own
  single-entry spec, so a refusal costs only the building that caused it and
  says which. `merge_gameplay` itself is UNCHANGED -- being strict about
  geometry is right for what it is for, and this is a different caller wanting
  a different thing from it.

## [0.46.0] - site_surfaces has a command line

level_factory adapters invoke tools as COMMANDS. A module the pipeline needs
to run has to be one, and `site_surfaces` was importable only.

### Added
- **`python site_surfaces.py <spec> --out <surfaces.json>`**, with
  `--radius-m` / `--floor-max-angle-deg` for a different agent contract,
  `--nav-bake` for the real agent radius, and `--strict`.
- **`--strict`** turns findings into an exit code. Unreadable building
  footprints stay a warn by default -- a raw site spec legitimately has none,
  the annotation comes from `merge_gameplay` -- but inside a pipeline that
  warn means every wall seam silently went undressed, and silence is what this
  module exists to avoid. 3 CLI tests, 32 in the file.

## [0.45.0] - Lot says where dressing may go

Layer 3 surface dressing needs to know which regions of an assembled site are
dressable, how much of each must stay legible, and what is off limits. The
schema (`level_factory/schemas/surface_dressing.v1.json`) is explicit that Lot
answers: zones are "semantic regions from Deli Counter / Lot -- not invented
here", `traversed` is "taken from Lot's walkable surfaces, not asserted by the
dressing planner", and "an exclusion nobody declared is a preference".

### Added
- **`site_surfaces.py`** — dressable zones and exclusions for a site spec.
  Every zone traces to a spec key and every number to a module that already
  derived it; nothing here invents a fact about the site.

      spec key      becomes
      ------------  ------------------------------------------------------
      ground        open ground, via site_extent.resolve (the module that
                    decides the real plate rect, because five places used
                    to assume it was centred and all five were wrong)
      paths         a gameplay_path corridor per path, at its own width
      courtyards    a play_space zone each, at their own size
      buildings     a wall_base band around each footprint, one agent
                    radius wide -- read from the nav bake, not chosen
      perimeter     everything outside site_extent.required_rect, which is
                    by definition content plus clearance
      cover         cover_edge exclusions at site_cover.MARKER_CLEARANCE
      spawn /       spawn and objective exclusions on the named buildings
      objective /
      extraction

  `capsule_block()` carries `unassisted_step_max` from
  `site_steps.unassisted_step_max_m` so a later gate checks the honesty rule
  without re-deriving it, and a plan made for one body is obviously a plan for
  that body when someone changes the capsule. Zone boxes are capped at exactly
  that height.

  `zone_for()` resolves overlap by a documented precedence (path, wall_base,
  courtyard, perimeter, open) and lives beside the data, so the planner and
  any later gate cannot disagree about which budget a placement counts
  against. `excluded()` returns the tags it tested, so a caller can record
  `cleared_exclusions` honestly — the schema warns that an empty array means
  untested, not clean.

- **`tests/test_site_surfaces.py`** — 29 tests on the real
  `coldrun_pawn_job` shape.

### Notes
- **A corridor is not a box, and being conservative is not free.** The first
  version emitted one AABB per path. On the fixture, three diagonal 5 m paths
  produced boxes of 1,935 m2 each — 12% of a 16,500 m2 site apiece — so
  nearly every square metre came back `gameplay_path`, the strictest
  visibility class, and the density variation the guide asks for (sidewalk
  centre low, wall seam high, abandoned corner very high) collapsed into one
  uniform sparse scatter. Corridors now ship as `width x width` boxes stepped
  along the centreline at half a width. `test_a_diagonal_path_does_not_
  swallow_the_site` caps a path zone at 1% of the site and fails the old
  construction outright.
- The perimeter is an annulus and ships as the four strips it is made of, for
  the same reason: emitting the whole plate would have made very_high density
  the reading for the entire site.
- Unreadable building footprints are REPORTED
  (`LOT_SURFACE_FOOTPRINT_UNKNOWN`), not skipped. A raw site spec carries no
  footprint — the annotation comes from `merge_gameplay` — and silently
  emitting no wall bases looks exactly like a site with no walls.
- Path segments are built in SPEC space here, deliberately not via
  `site_steps.routes`, which negates y because its caller works in Godot
  space. The manifest declares `spec/Blender Z-up raw coords` and mixing the
  two is a bug this repo has already paid for.
- This module places nothing. Patina's planner, the level_factory job and the
  Presentation consumer are still to come (`docs/SURFACE_DRESSING.md` section 2).

## [0.44.0] - cover stops paying for enemy-to-enemy lines

`open_sightlines` is all-pairs over the marker dict, and `lot.py` builds that
dict as three mission markers plus one `Enemy_{i}` per placed enemy. K enemies
therefore contribute C(K,2) lines describing enemies shooting each other, and
`plan_cover`'s twelve-piece opening budget was buying cover for them.

The exclusion sits in `plan_cover`'s nested `outstanding()` -- the point of
spend -- and NOT in `open_sightlines`, which is byte-identical. Laser Tag and
`level_factory/packages/validation/` still see every pair.

### This REVERSES a call the roadmap had already made

Roadmap 52 retired exactly this change on 2026-08-16, because
`LT_OPEN_SIGHTLINE` reports those lines with coordinates and a remedy, so
excluding them deletes cover the grader asks for. That reasoning is not
refuted here. It is overruled: Laser Tag is advisory, Lot builds the level,
and `Enemy_*` is leaving Lot for the gameplay layer, so a request phrased in
enemy markers cannot bind Lot's budget.

The change was re-derived from scratch and shipped before item 52 was read.
The item already carried the "before" numbers that were then re-measured with
a full pipeline run.

### Measured, seed-matched, in both directions

    seed   before (placed, route_open)   after
    5017   (9, 3)                        (8, 3)    waste removed, no cost
    5118   (9, 0)                        (9, 0)    freed slot went to the
                                                   route: enemy-route 4 -> 5
    5219   (16, 14)                      (14, 15)  one route stretch left open

15 of the 16 pieces in the previous export were placed against an `Enemy_*`
point. Only one would survive without enemies at all.

The cost is real. On seed_5219 `route_open` goes 14 -> 15, because one
enemy-enemy crate was incidentally blocking a route line and the route pass
did not replace it -- its density cap (`ROUTE_METRES_PER_PIECE`) was already
met. Mission findings went 51 -> 50. Which finding disappeared was NOT
isolated, and `LT_OPEN_SIGHTLINE` was NOT counted before-versus-after per seed.

Reverting and re-applying reproduced the patched numbers exactly, every stage
cache-hitting, so these are not rebuild artifacts.

Suite: 336 passed / 0 failed.

## [0.43.0] - the enemies are placed once

Roadmap 3 -- "Lot places enemies twice, and nothing checks the two agree" --
asked for one of two things: place once and thread the result through, or
assert the two agree. Neither had been done. 0.42.0 made the two calls agree by
handing them identical inputs, which restored the "same inputs, same answer"
claim the item calls untested rather than removing it.

`place_enemies` now runs ONCE, in `assemble`, before the site report closes.
The result is handed down through `write_walk_scene` -> `_lasertag_hook_nodes`
-> `_lasertag_hook_plan`, which places only when `enemies=None` so the
standalone callers behave as they always have. There is no second call left to
drift, which is a stronger guarantee than an assertion that a drift occurred.

The ordering constraint that justified the second placement is intact.
`lot.py`'s own comment says the walk scene is written after the report closes,
and a placement Lot could not honour has to travel with the site rather than
sit in a `.tscn` nobody diffs. The placement still happens in `assemble`. Only
the re-placement is gone.

### Verified on the artifact, not the fixture

A fixture licenses nothing about a mission. `lot_demo_001` was re-run under
this build and its three navqa scenes hashed against the pre-threading run:

    5017  e9177e9be4c3d78ad4634aad99517473e25c29fb95bd156f6c55d09023a8af23
    5118  25bdce90e97acfade19b9b0f5554df3b4c374ab56bc7d23daaa5bba831a644e7
    5219  b3bd2815f3f57a735014d0adde87237ba128339d468357485ee694b8b4f6f773

All three identical. `seed_5219`'s cover plan unchanged at `placed 16,
route_open 14, unbreakable 0, pinches 0`, and `laser_tag_evaluate` cache-hit on
all three candidates -- the correct answer when the inputs did not move.

Suite: 336 passed / 0 failed.

### What this did not change, which is worth recording

`walktest_navqa` re-executed on all three candidates despite byte-identical
input, while `laser_tag_evaluate` cached. Same unchanged upstream, two
different answers. Wasted work rather than wrong output, and another face of
roadmap 39's `upstream_artifact_hashes` -- a field in the build fingerprint
that nothing populates.

## [0.42.0] - the cover was planned for a crew standing somewhere else

`lot`'s own suite had been red through every certification this month -- 328
passed, 8 failed. Three defects, and the two that mattered were both one tool
re-deriving another's inputs instead of asking for them.

**The cover was planned from a crew spawn the scene does not ship.** `assemble`
seated the mission points and never cleared the crew spawn, so it planned cover
from (-70.0, 30.0) -- the dead centre of a 16 x 16 shell -- while
`write_walk_scene` cleared it to (-60.5, 30.0) and shipped that. From inside a
building almost every sightline reads as already broken, so `plan_cover`
reported `open_lines=0`: it believed it had covered a map it had never
correctly measured, and the shipped scene opened with a clear 51.9 m lane to
the nearest enemy.

That also explains a disagreement that looked like a broken instrument. Two
`place_enemies` calls fire inside one `assemble` -- one for the cover plan, one
for the scene -- and they returned different six-enemy sets, both numbered from
zero. Nothing was mismeasured. There were two different `Enemy_5`s.

**And then the opening cover budget never reached the crew.** With the inputs
corrected the planner became honest -- `open_lines` 0 -> 1 -- and the real
defect showed. `open_sightlines` returns every marker pair over the opening
range, longest first, and `plan_cover` takes twelve. On the test yard, ZERO of
those twelve involved the crew spawn and SIX broke enemy-to-enemy sightlines --
cover so one enemy cannot see another, which says nothing about who opens fire
on the crew, since they are the same team. The crew had seven open lines
(130.5, 115.9, 106.4, 77.3, 67.8, 53.9, 51.9 m) and got none of the budget.
`unbreakable` was 0 throughout, so a placeable spot existed the whole time.

Serving the crew's lines first fixes it on the SAME budget. The longest-first
heuristic is kept inside each group by sorting stably on one boolean:

                        opening pieces  touching crew  total  open_lines
    longest first                   12              0     23           1
    crew lines first                12              3     23           0

Three pieces close all seven crew lines.

### What else is in here

`_lasertag_hook_plan` returns the positions, route and enemies the walk scene
is written from. `_lasertag_hook_nodes` did its own seating and clearing and
returned only the scene body, so the one question worth asking of it -- are the
positions in the scene the positions that were planned -- could be asked only
by re-running its derivation by hand. `tests/test_site_spawns.py` did exactly
that, drifted, and reported an 18.5 m gap as the scene losing the plan. The
scene had carried its plan exactly, to 0 of 18 failing coordinate pairs; the
plan the test held was of a route the tool never uses. The scene body is
unchanged by the refactor, asserted by executing both versions and comparing.

Six tests were still passing a spawn POINT where `opening_engagement_is_fair`
now requires a crew PATH. The predicate's refusal to default that parameter
worked exactly as designed; only the follow-through was missing.

### What this did not fix, which is worth recording

`assemble` and `write_walk_scene` still derive the mission points twice,
independently. This makes the two agree; it does not make there be one.

Enemy-to-enemy pairs still consume opening budget once the crew is served.
Excluding them outright measured 7 opening pieces and 18 total -- fewer pieces
for the same zero open lines -- and is a separate decision about what
`open_sightlines` should return at all.

Cover planning still derives its priorities from `place_enemies`. That is
awkward if enemy placement is leaving this pipeline for the gameplay layer,
because `plan_cover` would lose the input it currently ranks everything by.

Every measurement above is from a two-building yard fixture. `lot_demo_001`
has not been re-exported under any of this.

Suite: 328 passed / 8 failed -> 336 passed / 0 failed.

## [0.41.0] - the ground plate and the ground floor were the same plane

Every per-building z-fight gate ran clean and the composed site still reported
`site <-> building` pairs, because no per-building check can see a pair whose
two halves come from different emitters.

Lot's ground plate topped out at y = 0. So does a building's ground-floor slab.
And `GROUND_HOLE_INSET = 0.45` deliberately leaves a ring of plate underneath
every footprint rather than cutting the hole flush -- so each 38 x 28 m building
sat on roughly **59 m2 of coplanar up-facing surface**, two solids claiming the
same plane with nothing between them.

`GROUND_SINK` drops the plate one tier below the floor datum, and extends roads,
paths and courtyards downward by the same amount so that **no top face moves**.
The surfaces a body walks on are where they were; only the underside changed.
Verified by reading the generated scene rather than the intent:

    Ground   [-0.5000, -0.0020]
    path_0   [-0.0020, +0.0120]     tops unchanged

Composed result: **zero `site <-> building` pairs.**

### What this did not fix, which is worth recording

This landed as part of chasing a flickering band along wall-to-floor junctions,
and it was not the cause of it. The composed gate read 961 solids in one frame
and found no coplanar pair anywhere near a wall meeting a floor; turning the
sun's shadow off made the band vanish. It was shadow acne, cross-hatched by two
directional lights **one degree apart in elevation** -- a Lux defect, fixed in
Lux 0.16.0 and `tools/lux_inject.py`.

The geometry above is real and was worth doing. It was not what was on screen,
and a changelog that let those two run together would be the reason somebody
later believes a sunk ground plate fixes shadow acne.

## [0.40.0] - the walker could not climb a legal stair

The library sweep left one class of failure across three sites -- central_vault,
walkup_siege, ref_pvp -- every path proof passing, all four walkers stopped on
one coordinate. 0.39.0 let the contact list out of the serializer, and it named
the thing:

    walker bot_1 STUCK at (35.8, -2.3, -14.9) 0.75 m from waypoint 2/18;
    on_floor=true on_wall=true; touching: stair0ramp_-1, slab_col_-1

Measuring that ramp with full node transforms rather than untransformed bounds:
**39.2 degrees**, rise 3.40 m over a 4.16 m run. The bake accepts 55, the
walker's own floor_max_angle is 56, and the navmesh had built an eighteen-point
path over it. A ramp that is legal by every number in agent_contract.json, and
a physical capsule that cannot climb it. That is this tool, not the site.

Two causes, both in `_drive`:

*Gravity was applied every frame regardless of `is_on_floor()`.* A waypoint on a
stair flight usually sits at the same height as the body, so the climbing branch
never fires and the flat branch has to walk the slope -- while accumulating a
downward component that pins the capsule into the junction where the ramp meets
the floor. Gravity now applies only while airborne.

*The step-up probe was a single 0.5 m lift.* That assumed the only thing which
can stop a body at a stair mouth is the riser in front of it. If there is no
headroom for the lift there is no step and no second attempt. It now tries 0.5,
0.35 and 0.2 before giving up.

And when it does give up it says which probe failed. "Nothing overhead to lift
into" is a finding about the stairwell, against clearances.min_headroom_m;
"lifted clear but nothing to step onto ahead" is a finding about the obstacle. A
walker that gives up without distinguishing them sends the reader to the wrong
repo -- which is what three sites' worth of "stuck" did for a day.

`floor_snap_length` is set to the step height so a walker stays glued to a
descending slope instead of launching off its crest into frames where the step
probe cannot fire at all.

## [0.39.0] - the director measured the contact and the serializer threw it away

The library sweep came back 17 of 20, and all three failures had the same shape:
every path proof passing, all four walkers stopped at one coordinate. Exactly
what 0.30.0's contact capture was written to explain -- and all three reports
came back with `blocked_by` absent, from a director that had recorded it.

`_conclude` builds each walker's report entry from a hand-written list of five
keys. Everything `_drive` records on a stuck walker -- every slide collision
with its collider name and contact normal, the waypoint it was steering to, how
far short it stopped, `is_on_floor` / `is_on_wall` -- was written to the walker
dict and then dropped on the way out.

A serializer with a fixed key list silently discards whatever is added later.
That is the same defect as an instrument measuring the wrong thing, one layer
further out, and it is worse in one respect: the measurement existed and looked
like it had never been taken. The keys are now named in one place next to a note
saying `_conclude` has to copy them.

`at` follows the same fix. It was set for a walker that ran out the clock and
not for one that gave up, so a stuck walker's position lived only inside the
status prose and nothing could read it as a number.

Three sites to re-run, and the answer to roadmap item 14 is in whichever of them
comes back with an empty contact list.

## [0.38.0] - a stuck walker now says what it is stuck against

Seed 5017 put all four walkers on the same coordinate, (20.5, 0.9, -2.7), on the
same leg, with every path proof passing. The report said where and not what, so
settling it meant reconstructing the site's colliders offline -- and that could
not answer it either: six metres of clear floor in both axes around the point,
and an unobstructed straight line to the target. The obstacle is whatever
`move_and_slide` is touching, and only the engine knows that.

So the walker records it. On giving up, `_drive` captures every slide collision
-- collider name, node path, contact normal, contact point -- plus the waypoint
it was steering to, how far short it stopped, where that waypoint sits in the
path, and `is_on_floor` / `is_on_wall`.

The empty case is the one worth having. A capsule wedged in geometry is a level
defect. A capsule stopped in open space touching NOTHING is this tool's steering
giving up, and the two were indistinguishable in the report. Blaming a level for
the second is how an afternoon goes missing.

## [0.37.0] - the vault is sealed on purpose, and the census said so four different ways

With the anchors on their floors, failures fell from nine legs of thirty-nine to
one or two of thirty-one -- and every remaining one was a vault. The basement
geometry says why. `int_-1_4` is a full-height wall running the whole 32 m at
building-local x 0, and its one opening is filled by
`int_-1_4_open0_BREACHPANEL` (y -3.85 to -1.65) with its lintel above. The gap
under the panel is 0.15 m. Nothing walks through it, which is the point: the
opening is `kind: "breach"`, `breach_class: "reinforceable"`,
`material: "concrete"`, tag `vault_breach`. The vault is entered by blowing it.

So the mission spine was going to fail on the vault forever, on every seed of
every mission, and `WALKTEST_ENFORCED` could never have been flipped.

### why it was one or two vaults per seed and not all four

`LOOT_VAULT_CASH` sits at the centre of `vault_block`, an 8 x 6 m mass that
straddles the dividing wall. The nearest standing room is ~3.5 m away past a
block corner, and the two sides of the wall are within a few centimetres of each
other in distance from the marker. Which side the ring search picked was a
tie-break on identical geometry -- so some vault anchors landed in the sealed
half and stranded, and the rest landed in the stairwell half and passed.

### the nearest standing room is not always one a player can occupy

The census now runs twice. Any anchor that comes out off the main network is
re-searched for the nearest standing room that can walk to a main-network anchor
**and back**, bounded by the same `STAND_SEARCH_M` as the first pass. For a
sealed room that is the floor outside its door, which is where a player stands
to breach -- derived from the navmesh rather than guessed from a wall normal,
which Lot does not have for interior walls.

This is the one place the walktest passes over a substitution, so it is recorded
in three places rather than none: the anchor carries `unreachable_stand_m` (how
far the unreachable one was, so both readings survive), the director prints it,
and Level Factory raises `WALKTEST_ANCHOR_BEHIND_BARRIER`. Every consumer --
path proofs, walker legs, the bot target search -- reads the resolved position
through one cache, so the report cannot grade a route to a position the census
already ruled out.

### clusters union on MUTUAL reachability

Seed 5219 reported `proxy_3 ... reaches 0/16 cluster 16/16` -- the census
contradicting itself in two adjacent columns of the same row. Reachability is
not symmetric, and the asymmetry is the tolerance's rather than the navmesh's:
arrival is judged within `SNAP_MAX` of the destination, so a route from the main
network onto a nearby island "arrives" while the route back off it stops nowhere
near. One directed edge was enough to union. It now takes both.

## [0.36.0] - a marker is where the thing is, not where a body stands

0.35.0 stopped lifting the nav-QA anchors and started snapping them downward,
and the walktest still failed nine legs out of thirty-nine. This is the rest of
it, and the mistake underneath both halves was the same one: treating a marker
position as a standing position.

Deli Counter puts `OBJECTIVE_CAGE` at the cashier counter and
`LOOT_VAULT_CASH` inside the vault block. Their heights -- 0.9 and -2.8 -- are
the heights of the props, and the floor directly beneath them is inside a solid
box. Emitted at marker height, sixteen of twenty-one anchors resolved to the
prop's own tabletop: `cage_counter` at 1.1 m, `count_table` at 4.9 m,
`vault_block` at -2.6 m, each carrying a navmesh surface 0.3 m above it that no
body can climb to and nothing can reach. Every route query in the walktest
started on one of those islands, and the reports read as a severed navmesh for
two days.

### anchors land on their room's floor

`_navqa_anchors` now resolves each marker through `rooms[building/room].center[2]`
-- the storey's floor elevation, read rather than derived, because the storey
height is Deli Counter's to choose and is not in the merged file. A marker whose
room is unknown falls back to the highest floor in its building at or below it;
a marker with no rooms at all keeps its own height and is named on stdout rather
than silently guessed.

### stacked markers become one anchor

Dropping markers to their floor makes some of them coincide: Deli Counter puts
the vault objective and the vault loot at one XY, 0.2 m apart in Z. Two anchors
on one point are not two tests, and this pair is why the reachability census
under-reported for a day -- each stranded anchor still "reached" its twin. Lot
merges them and reports the count.

### the director looks for standing room, not for navmesh

`_snap` (heist_nav_qa) no longer asks "what navmesh is nearest". It searches the
anchor's own storey plane outward in rings for the first place a body fits, so a
loot marker in the middle of an 8 x 6 m vault block resolves to the floor at the
vault's edge -- which is where a player stands to open it. The band is
deliberately asymmetric: a body height DOWN, one max_climb plus a voxel UP. Down
is where the floor is when a marker carries body height; up is how a counter top
came to stand in for a floor.

Three consequences follow, and all three are reported rather than assumed:

- An anchor with no walkable surface anywhere on its storey is no longer "off
  the navmesh by a bit". It is a room that did not bake, it carries
  `no_standing_room`, and Level Factory raises `WALKTEST_ANCHOR_NO_FLOOR`.
- How far a body has to stand from a marker is intel, not a verdict. The old
  `SNAP_MAX` proximity test failed the vault loot at 3 m and blamed the navmesh
  for where a marker was put. Legs now carry `stand_offset_m` and pass.
- Clustering drops the vertical-access concession. A 2.9 m drop onto a tabletop
  satisfied it in both directions, so union-find glued every furniture island to
  the floor and reported "one cluster of 21, 0 stranded" on a run where sixteen
  anchors could not be walked to. A drop is not a two-way edge. Legs keep the
  concession, because a ladder is real access and the proof says which it found.

`_set_leg` and `_nearest_reachable` ask the same question the proofs do, so a
walker is never sent to a counter top and then reported STUCK for failing to
climb it.

Not fixed here, and now measured: props bake as walkable navmesh. `gaming_tables`
is a 12 x 6 m box whose top is 72 m2 of surface a metre off the floor that
nothing can reach, and it is one of sixty-one islands in a navmesh that is 91.7%
one piece. The anchors no longer land on them; the dead polygons are still there.

## [0.35.0] - the anchors were standing on the furniture

The first honest walktest failed all four seeds, and after a day of pointing
instruments at the navmesh the navmesh turned out to be fine. `crew_home` sits
inside building b2, snaps to y 0.2, and reaches 18 of 20 anchors: interior
floors bake, and they are connected to the street. What was broken is where the
anchors were and how they were snapped.

### the height

`_navqa_anchors` reads markers Deli Counter has already placed at body height --
a ground-floor marker carries z 0.9 over a floor at 0.0 -- and `write_navqa_scene`
lifted them another metre. Every building proxy floated about 1.9 m above the
surface it was supposed to be standing on. The lift is dropped for proxies and
bot spawns. `crew_home` keeps it: that one comes from `_walk_positions` at z 0,
so it needs raising off the floor rather than lowering onto it.

### the snap

`map_get_closest_point` is omnidirectional, which is the wrong question for a
standing position. From 1.9 m up, a counter top at 1.4 m is 0.5 m away while the
floor is 1.9 m away -- so the anchor snapped sideways and every route query in
the walktest started on a two-polygon scrap of furniture. `_snap` asks the right
question instead: closest point to a short DOWNWARD segment, because a body
stands on the surface beneath it. Used by both `_prove_path` and the anchor
census.

Neither fix would have been found without the other half of this release.

### clusters, not zeroes

0.26.0 counted how many other anchors each one reaches and flagged zero. It
found nothing, because Lot emits four duplicate marker pairs per site (two
markers 0.2 m apart snapping to one point), so every stranded anchor still
reached its own twin. Sixteen of twenty-one anchors were off the main network
and the count said none.

`_anchor_reachability` now unions the reachability relation into clusters and
flags any anchor NOT on the largest one, reporting `cluster_size`,
`main_cluster_size` and `coincident_with`. That last field names the duplicate
pairs directly, since they are a Lot defect in their own right rather than
noise.

Five tests in `tests/test_navqa_anchors.py`, none of which launch Godot: the
conversion and the height are arithmetic.

## [0.34.0] - an anchor can be on the navmesh and still go nowhere

`_prove_path` has always refused an anchor further than `SNAP_MAX` (2.0 m, from
the agent contract's `qa.snap_max_m`) from the mesh. On the run that started
this, every anchor passed that check and nine legs failed anyway, each reporting

    path stops 32.71 m short (disjoint islands)

which is TRUE, and reads as a claim about the whole site rather than about one
endpoint. Four instruments were pointed at the navmesh for a day: nav_gate
passed the building, three source-geometry modes gave the same nine failures,
six agent-parameter variations moved nothing, and the island census came back
1675 polygons in one connected component out of 1827. The navmesh was never
fragmented. Two-polygon scraps were, and anchors were standing on them.

### the measurement that was missing

Proximity, not connectivity. An anchor 0.7 m from a scrap is on the mesh by
every existing check and can never appear in a route.

`_anchor_reachability` snaps every anchor with `map_get_closest_point` and then
asks, for each, how many OTHER anchors it can reach -- using `_reaches`, which
applies the same rules `_prove_path` does, vertical-access concession included,
so an anchor served only by a ladder is not called isolated. Twenty anchors is
400 queries next to a 230-second walker sim.

The report gains an `anchors` array (`name`, `raw`, `snap`, `snap_m`, `reaches`,
`of`) and a `stranded_anchors` count. A leg that fails from or to a stranded
anchor now carries `isolated_endpoint` and says which anchor before it describes
the path, so the reader is pointed at the placement rather than at the geometry.

Nothing about the verdict changes: a stranded anchor already failed its legs and
still does. What changes is that the report now says what it is.

## [0.33.0] - the report goes where the caller asked

`walktest.py` gains `--report-dir`. The `heist_nav_qa` director names its report
after the scene and writes it beside it, which is right for a hand-run in a site
directory and wrong for a caller that stages a throwaway project somewhere else
and needs the result in its own output directory. Level Factory is that caller:
its walktest stage now runs this runner against a staged project and collects
`site_navqa.walktest.json` from its own work dir.

`copy_report()` copies a report that exists and returns None for one that does
not. That second half is the point -- the director writes nothing when the scene
never ran, and a copy step that invented a destination file would paper over
exactly the failure the caller needs to see.

`--require` is unchanged and now has a help string, because the default is a
trap for an automated caller. Without it a missing Godot 4 binary is a SKIP that
returns 0 and writes no report: a navigation check that never happened, reported
as success. Level Factory passes `--require`.

Seven tests in `tests/test_walktest_runner.py`, none of which launch Godot --
the two things under test are what happens when Godot is absent and where a
written report ends up.

Note on versions: `VERSION` moves 0.24.0 -> 0.25.0 with this change. Lot's four
version sources (`VERSION`, `lot.py`, `version.py`, this file) still disagree
and are left alone deliberately -- build fingerprints read `VERSION`, so
reconciling them is a cache-invalidating change that wants its own pass. See
PIPELINE_ROADMAP.md, "Smaller, carried".

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
